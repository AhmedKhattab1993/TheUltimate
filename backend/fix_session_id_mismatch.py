#!/usr/bin/env python3
"""
Fix session ID mismatches in existing data.
This script updates screener_results to match the session IDs used in screener_backtest_links.
"""

import asyncio
import asyncpg
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


async def fix_session_mismatches():
    """Fix session ID mismatches between screener_results and screener_backtest_links."""
    # Database connection
    conn = await asyncpg.connect(
        host='localhost',
        port=5432,
        user='postgres',
        password='postgres',
        database='stock_screener'
    )
    
    try:
        # Find all unique date/session combinations in backtest links that don't match screener results
        mismatches = await conn.fetch("""
            WITH link_sessions AS (
                SELECT DISTINCT 
                    screener_session_id,
                    data_date,
                    COUNT(*) as link_count
                FROM screener_backtest_links
                GROUP BY screener_session_id, data_date
            ),
            screener_sessions AS (
                SELECT DISTINCT 
                    session_id,
                    data_date,
                    COUNT(*) as screener_count
                FROM screener_results
                WHERE source = 'pipeline'
                GROUP BY session_id, data_date
            )
            SELECT 
                ls.screener_session_id as link_session_id,
                ls.data_date,
                ls.link_count,
                ss.session_id as screener_session_id,
                ss.screener_count
            FROM link_sessions ls
            LEFT JOIN screener_sessions ss ON ls.data_date = ss.data_date
            WHERE ls.screener_session_id != ss.session_id OR ss.session_id IS NULL
            ORDER BY ls.data_date DESC
        """)
        
        logger.info(f"Found {len(mismatches)} session mismatches to fix")
        
        for mismatch in mismatches:
            link_session = mismatch['link_session_id']
            screener_session = mismatch['screener_session_id']
            data_date = mismatch['data_date']
            link_count = mismatch['link_count']
            
            logger.info(f"\nDate: {data_date}")
            logger.info(f"  Links use session: {link_session} ({link_count} links)")
            logger.info(f"  Screener uses session: {screener_session}")
            
            if screener_session is not None:
                # Update screener results to use the link session ID
                result = await conn.execute("""
                    UPDATE screener_results
                    SET session_id = $1
                    WHERE session_id = $2 AND data_date = $3 AND source = 'pipeline'
                """, link_session, screener_session, data_date)
                
                count = int(result.split()[-1])
                logger.info(f"  Updated {count} screener records to use session {link_session}")
        
        # Verify the fix
        logger.info("\nVerifying the fix...")
        join_stats = await conn.fetchrow("""
            WITH join_check AS (
                SELECT 
                    sbl.backtest_id,
                    CASE 
                        WHEN sr.session_id IS NOT NULL THEN 'matched'
                        ELSE 'unmatched'
                    END as match_status
                FROM screener_backtest_links sbl
                LEFT JOIN screener_results sr ON 
                    sr.session_id = sbl.screener_session_id 
                    AND sr.symbol = sbl.symbol 
                    AND sr.data_date = sbl.data_date
            )
            SELECT 
                COUNT(*) as total_links,
                COUNT(CASE WHEN match_status = 'matched' THEN 1 END) as matched_links,
                COUNT(CASE WHEN match_status = 'unmatched' THEN 1 END) as unmatched_links,
                ROUND(COUNT(CASE WHEN match_status = 'matched' THEN 1 END) * 100.0 / COUNT(*), 2) as match_rate
            FROM join_check
        """)
        
        logger.info(f"\nJoin statistics after fix:")
        logger.info(f"  Total links: {join_stats['total_links']}")
        logger.info(f"  Matched links: {join_stats['matched_links']}")
        logger.info(f"  Unmatched links: {join_stats['unmatched_links']}")
        logger.info(f"  Match rate: {join_stats['match_rate']}%")
        
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(fix_session_mismatches())