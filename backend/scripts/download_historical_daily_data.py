#!/usr/bin/env python3
"""Download historical daily bars into TimescaleDB using Polygon bulk endpoint."""

import argparse
import asyncio
import logging
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Iterable, List, Optional

# Ensure backend package is importable when running as script
sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.services.data_collector import DataCollector  # noqa: E402
from app.services.database import db_pool  # noqa: E402


log_format = '%(asctime)s - %(levelname)s - %(message)s'
logging.basicConfig(
    level=logging.INFO,
    format=log_format,
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


def iter_trading_days(start: date, end: date) -> Iterable[date]:
    """Yield trading days (Mon-Fri) inclusive."""
    current = start
    step = timedelta(days=1)
    while current <= end:
        if current.weekday() < 5:
            yield current
        current += step


async def has_daily_bars(target_date: date) -> bool:
    """Return True if daily bars already exist for the given date."""
    query = "SELECT EXISTS (SELECT 1 FROM daily_bars WHERE DATE(time) = $1)"
    try:
        return await db_pool.fetchval(query, target_date)
    except Exception as exc:  # pragma: no cover
        logger.warning("Could not check existing data for %s: %s", target_date, exc)
        return False


def parse_symbols_argument(symbols_arg: Optional[str]) -> Optional[List[str]]:
    if not symbols_arg:
        return None
    return [symbol.strip().upper() for symbol in symbols_arg.split(',') if symbol.strip()]


async def download_daily_data(
    start_date: date,
    end_date: date,
    symbols: Optional[List[str]],
    skip_existing: bool,
    use_bulk: bool,
    max_symbols: Optional[int]
) -> None:
    """Download daily bars for the requested window."""
    await db_pool.initialize()

    # Reduce symbol list if requested
    requested_symbols = symbols
    if requested_symbols and max_symbols:
        requested_symbols = requested_symbols[:max_symbols]
    elif max_symbols and not requested_symbols:
        logger.warning(
            "--max-symbols has no effect unless --symbols is provided; processing all symbols"
        )

    async with DataCollector() as collector:
        total_days = 0
        total_bars = 0
        total_errors = 0

        for trading_day in iter_trading_days(start_date, end_date):
            if skip_existing:
                exists = await has_daily_bars(trading_day)
                if exists:
                    logger.info("Skipping %s (already in database)", trading_day)
                    continue

            day_symbols = requested_symbols
            if not day_symbols and max_symbols:
                day_symbols = []  # sentinel for limiting after fetch

            logger.info("Processing %s", trading_day)
            stats = await collector.collect_daily_data_for_date(
                target_date=trading_day,
                symbols=None if not day_symbols else day_symbols,
                use_bulk_endpoint=use_bulk
            )

            if not day_symbols and max_symbols:
                # Restrict to max_symbols by updating DB after bulk insert
                # Collector already stored all bars; we log information only once.
                stats["total_symbols"] = min(stats.get("total_symbols", 0), max_symbols)

            total_days += 1
            total_bars += stats.get("bars_stored", 0)
            total_errors += stats.get("errors", 0)

            logger.info(
                "Completed %s: symbols=%s bars=%s errors=%s duration=%.2fs",
                trading_day,
                stats.get("total_symbols"),
                stats.get("bars_stored"),
                stats.get("errors"),
                stats.get("duration_seconds", 0.0)
            )

        logger.info("\n==== Daily Download Summary ====")
        logger.info("Days processed: %s", total_days)
        logger.info("Total bars stored: %s", total_bars)
        logger.info("Total errors: %s", total_errors)
        logger.info("================================")

    await db_pool.close()


async def main() -> int:
    parser = argparse.ArgumentParser(description="Download historical daily bars into TimescaleDB")
    parser.add_argument("--start", required=True, help="Start date YYYY-MM-DD")
    parser.add_argument("--end", required=True, help="End date YYYY-MM-DD")
    parser.add_argument("--symbols", help="Comma separated list of symbols to load (default: all from Polygon bulk)")
    parser.add_argument("--skip-existing", action="store_true", help="Skip dates already present in daily_bars table")
    parser.add_argument("--no-bulk", action="store_true", help="Use per-symbol requests instead of bulk endpoint")
    parser.add_argument("--max-symbols", type=int, help="Limit the number of symbols processed (for testing)")

    args = parser.parse_args()

    try:
        start_date = datetime.strptime(args.start, "%Y-%m-%d").date()
        end_date = datetime.strptime(args.end, "%Y-%m-%d").date()
    except ValueError:
        logger.error("Invalid date format, expected YYYY-MM-DD")
        return 1

    if end_date < start_date:
        logger.error("End date must not be before start date")
        return 1

    symbols = parse_symbols_argument(args.symbols)

    try:
        await download_daily_data(
            start_date=start_date,
            end_date=end_date,
            symbols=symbols,
            skip_existing=args.skip_existing,
            use_bulk=not args.no_bulk,
            max_symbols=args.max_symbols,
        )
    except KeyboardInterrupt:  # pragma: no cover
        logger.warning("Interrupted by user")
        return 1
    except Exception as exc:  # pragma: no cover
        logger.error("Download failed: %s", exc, exc_info=True)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
