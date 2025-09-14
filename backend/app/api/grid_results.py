"""
API endpoints for grid analysis results.
Provides combined access to grid screening and market structure backtest results.
"""

from fastapi import APIRouter, HTTPException, Query, Depends
from typing import List, Optional, Dict, Any
from datetime import datetime, date
import logging
import asyncpg
import json

from ..services.database import db_pool
from ..models.grid_results import (
    GridResultSummary,
    GridResultDetail,
    GridScreeningResult,
    GridMarketStructureResult,
    GridResultsListResponse
)

router = APIRouter(prefix="/api/v2/grid/results", tags=["grid-results"])
logger = logging.getLogger(__name__)


@router.get("", response_model=GridResultsListResponse)
async def list_grid_results(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Results per page"),
    start_date: Optional[date] = Query(None, description="Filter results after this date"),
    end_date: Optional[date] = Query(None, description="Filter results before this date"),
    symbol: Optional[str] = Query(None, description="Filter by symbol")
):
    """
    List grid analysis results with pagination and filtering.
    
    Returns combined screening and backtest results grouped by date.
    """
    try:
        # Build the query to get unique dates
        date_query = """
        SELECT DISTINCT data_date
        FROM (
            SELECT DISTINCT date as data_date FROM grid_screening
            UNION
            SELECT DISTINCT backtest_date as data_date FROM grid_market_structure
        ) dates
        WHERE 1=1
        """
        
        params = []
        param_count = 0
        
        # Add date filters
        if start_date:
            param_count += 1
            date_query += f" AND data_date >= ${param_count}"
            params.append(start_date)
            
        if end_date:
            param_count += 1
            date_query += f" AND data_date <= ${param_count}"
            params.append(end_date)
        
        # Add ordering and pagination
        date_query += f"""
        ORDER BY data_date DESC
        LIMIT ${param_count + 1}
        OFFSET ${param_count + 2}
        """
        
        params.extend([page_size, (page - 1) * page_size])
        
        # Get paginated dates
        date_rows = await db_pool.fetch(date_query, *params)
        
        if not date_rows:
            return GridResultsListResponse(
                results=[],
                total_count=0,
                page=page,
                page_size=page_size
            )
        
        # Get total count
        count_query = """
        SELECT COUNT(DISTINCT data_date)
        FROM (
            SELECT DISTINCT date as data_date FROM grid_screening
            UNION
            SELECT DISTINCT backtest_date as data_date FROM grid_market_structure
        ) dates
        WHERE 1=1
        """
        if start_date:
            count_query += " AND data_date >= $1"
        if end_date:
            count_query += f" AND data_date <= ${2 if start_date else 1}"
        
        total_count = await db_pool.fetchval(count_query, *params[:param_count])
        
        # For each date, get summary data
        summaries = []
        for row in date_rows:
            process_date = row['data_date']
            
            # Get screening summary for this date
            screening_query = """
            SELECT 
                COUNT(DISTINCT symbol) as symbol_count,
                MIN(created_at) as first_created,
                MAX(created_at) as last_created
            FROM grid_screening
            WHERE date = $1
            """
            
            # Add symbol filter if provided
            if symbol:
                screening_query += " AND symbol = $2"
                screening_result = await db_pool.fetchrow(screening_query, process_date, symbol)
            else:
                screening_result = await db_pool.fetchrow(screening_query, process_date)
            
            # Get backtest summary for this date
            backtest_query = """
            SELECT 
                COUNT(*) as backtest_count,
                COUNT(DISTINCT symbol) as symbol_count,
                COUNT(DISTINCT pivot_bars) as pivot_bars_count,
                COUNT(*) as completed_count,
                0 as failed_count,
                MIN(created_at) as first_created,
                MAX(created_at) as last_created
            FROM grid_market_structure
            WHERE backtest_date = $1
            """
            
            if symbol:
                backtest_query += " AND symbol = $2"
                backtest_result = await db_pool.fetchrow(backtest_query, process_date, symbol)
            else:
                backtest_result = await db_pool.fetchrow(backtest_query, process_date)
            
            # Calculate timing info
            screening_time = None
            if screening_result and screening_result['first_created'] and screening_result['last_created']:
                duration = (screening_result['last_created'] - screening_result['first_created']).total_seconds()
                screening_time = duration * 1000  # Convert to ms
            
            backtest_time = None
            if backtest_result and backtest_result['first_created'] and backtest_result['last_created']:
                duration = (backtest_result['last_created'] - backtest_result['first_created']).total_seconds()
                backtest_time = duration * 1000  # Convert to ms
            
            # Create summary
            summary = GridResultSummary(
                date=process_date,
                screening_symbols=screening_result['symbol_count'] if screening_result else 0,
                backtest_count=backtest_result['backtest_count'] if backtest_result else 0,
                backtest_completed=backtest_result['completed_count'] if backtest_result else 0,
                backtest_failed=backtest_result['failed_count'] if backtest_result else 0,
                screening_time_ms=screening_time,
                backtest_time_ms=backtest_time
            )
            summaries.append(summary)
        
        return GridResultsListResponse(
            results=summaries,
            total_count=total_count,
            page=page,
            page_size=page_size
        )
        
    except Exception as e:
        logger.error(f"Error listing grid results: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{date}/detail", response_model=GridResultDetail)
async def get_grid_result_detail(
    date: date,
    symbol: Optional[str] = Query(None, description="Filter by specific symbol")
):
    """
    Get detailed grid results for a specific date.
    
    Returns all screening results and backtest results for the date.
    """
    try:
        # Get screening results
        screening_query = """
        SELECT 
            symbol,
            price,
            ma_20,
            ma_50,
            ma_200,
            rsi_14,
            gap_percent,
            prev_day_dollar_volume,
            relative_volume,
            date,
            created_at
        FROM grid_screening
        WHERE date = $1
        """
        
        if symbol:
            screening_query += " AND symbol = $2"
            screening_rows = await db_pool.fetch(screening_query, date, symbol)
        else:
            screening_query += " ORDER BY symbol"
            screening_rows = await db_pool.fetch(screening_query, date)
        
        # Get backtest results
        backtest_query = """
        SELECT 
            symbol,
            pivot_bars,
            statistics,
            backtest_date,
            created_at
        FROM grid_market_structure
        WHERE backtest_date = $1
        """
        
        if symbol:
            backtest_query += " AND symbol = $2"
            backtest_rows = await db_pool.fetch(backtest_query, date, symbol)
        else:
            backtest_query += " ORDER BY symbol, pivot_bars"
            backtest_rows = await db_pool.fetch(backtest_query, date)
        
        # Convert to response models
        screening_results = []
        for row in screening_rows:
            screening_results.append(GridScreeningResult(
                symbol=row['symbol'],
                price=float(row['price']) if row['price'] else 0,
                ma_20=float(row['ma_20']) if row['ma_20'] else 0,
                ma_50=float(row['ma_50']) if row['ma_50'] else 0,
                ma_200=float(row['ma_200']) if row['ma_200'] else 0,
                rsi_14=float(row['rsi_14']) if row['rsi_14'] else 0,
                gap_percent=float(row['gap_percent']) if row['gap_percent'] else 0,
                prev_day_dollar_volume=float(row['prev_day_dollar_volume']) if row['prev_day_dollar_volume'] else 0,
                relative_volume=float(row['relative_volume']) if row['relative_volume'] else 0
            ))
        
        backtest_results = []
        for row in backtest_rows:
            # Extract key statistics
            stats = json.loads(row['statistics']) if row['statistics'] else {}
            
            backtest_results.append(GridMarketStructureResult(
                symbol=row['symbol'],
                pivot_bars=row['pivot_bars'],
                status='completed',
                total_return=stats.get('total_return', 0),
                sharpe_ratio=stats.get('sharpe_ratio', 0),
                max_drawdown=stats.get('max_drawdown', 0),
                win_rate=stats.get('win_rate', 0),
                total_trades=stats.get('total_trades', 0),
                backtest_id=None
            ))
        
        return GridResultDetail(
            date=date,
            screening_results=screening_results,
            backtest_results=backtest_results,
            total_screening_symbols=len(screening_results),
            total_backtests=len(backtest_results)
        )
        
    except Exception as e:
        logger.error(f"Error getting grid result detail: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{date}/symbols/{symbol}")
async def get_symbol_grid_results(
    date: date,
    symbol: str
):
    """
    Get grid results for a specific symbol on a specific date.
    
    Returns both screening and all backtest results for the symbol.
    """
    try:
        # Get screening result
        screening_query = """
        SELECT 
            symbol,
            price,
            ma_20,
            ma_50,
            ma_200,
            rsi_14,
            gap_percent,
            prev_day_dollar_volume,
            relative_volume,
            date,
            created_at
        FROM grid_screening
        WHERE date = $1 AND symbol = $2
        """
        
        screening_row = await db_pool.fetchrow(screening_query, date, symbol)
        
        if not screening_row:
            raise HTTPException(
                status_code=404, 
                detail=f"No screening results found for {symbol} on {date}"
            )
        
        # Get all backtest results for this symbol
        backtest_query = """
        SELECT 
            symbol,
            pivot_bars,
            statistics,
            backtest_date,
            created_at
        FROM grid_market_structure
        WHERE backtest_date = $1 AND symbol = $2
        ORDER BY pivot_bars
        """
        
        backtest_rows = await db_pool.fetch(backtest_query, date, symbol)
        
        # Build response
        screening = GridScreeningResult(
            symbol=screening_row['symbol'],
            price=float(screening_row['price']) if screening_row['price'] else 0,
            ma_20=float(screening_row['ma_20']) if screening_row['ma_20'] else 0,
            ma_50=float(screening_row['ma_50']) if screening_row['ma_50'] else 0,
            ma_200=float(screening_row['ma_200']) if screening_row['ma_200'] else 0,
            rsi_14=float(screening_row['rsi_14']) if screening_row['rsi_14'] else 0,
            gap_percent=float(screening_row['gap_percent']) if screening_row['gap_percent'] else 0,
            prev_day_dollar_volume=float(screening_row['prev_day_dollar_volume']) if screening_row['prev_day_dollar_volume'] else 0,
            relative_volume=float(screening_row['relative_volume']) if screening_row['relative_volume'] else 0
        )
        
        backtests = []
        for row in backtest_rows:
            import json
            stats = json.loads(row['statistics']) if row['statistics'] else {}
            
            backtests.append({
                "pivot_bars": row['pivot_bars'],
                "status": 'completed',
                "total_return": stats.get('TotalNetProfit', 0),
                "sharpe_ratio": stats.get('SharpeRatio', 0),
                "max_drawdown": stats.get('Drawdown', 0),
                "win_rate": stats.get('WinRate', 0),
                "total_trades": stats.get('TotalNumberOfTrades', 0),
                "backtest_id": None,
                "parameters": {}
            })
        
        return {
            "symbol": symbol,
            "date": date,
            "screening": screening,
            "backtests": backtests
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting symbol grid results: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{date}/trades")
async def get_grid_trades(
    date: date,
    symbol: Optional[str] = None,
    pivot_bars: Optional[int] = None,
    limit: int = Query(50, description="Maximum number of trades to return", ge=1, le=500)
):
    """
    Get trades for grid analysis results.
    
    Can filter by symbol and/or pivot_bars value.
    Returns the last N trades (default 50) ordered by trade time descending.
    """
    try:
        # Build query
        query = """
            SELECT 
                t.symbol,
                t.pivot_bars,
                t.trade_time AT TIME ZONE 'America/New_York' as trade_time_et,
                t.direction,
                t.quantity,
                t.fill_price,
                t.fill_quantity,
                t.order_fee,
                t.position_value,
                t.trade_type,
                t.signal_reason,
                EXTRACT(EPOCH FROM t.trade_time)::BIGINT as trade_time_unix
            FROM grid_market_structure_trades t
            WHERE t.backtest_date = $1
        """
        
        params = [date]
        param_count = 1
        
        if symbol:
            param_count += 1
            query += f" AND t.symbol = ${param_count}"
            params.append(symbol)
        
        if pivot_bars is not None:
            param_count += 1
            query += f" AND t.pivot_bars = ${param_count}"
            params.append(pivot_bars)
        
        query += " ORDER BY t.trade_time DESC"
        param_count += 1
        query += f" LIMIT ${param_count}"
        params.append(limit)
        
        rows = await db_pool.fetch(query, *params)
        
        # Convert to list of dicts with formatted data
        trades = []
        for row in rows:
            trades.append({
                "symbol": row['symbol'],
                "pivotBars": row['pivot_bars'],
                "tradeTime": row['trade_time_et'].isoformat(),
                "tradeTimeUnix": row['trade_time_unix'],
                "direction": row['direction'],
                "quantity": abs(float(row['quantity'])),
                "fillPrice": float(row['fill_price']) if row['fill_price'] else 0,
                "fillQuantity": float(row['fill_quantity']) if row['fill_quantity'] else abs(float(row['quantity'])),
                "orderFee": float(row['order_fee']) if row['order_fee'] else 0,
                "positionValue": float(row['position_value']) if row['position_value'] else 0,
                "tradeType": row['trade_type'],
                "signalReason": row['signal_reason']
            })
        
        return trades
        
    except Exception as e:
        logger.error(f"Error getting grid trades: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{date}/symbols/{symbol}/pivot/{pivot_bars}/trades")
async def get_symbol_pivot_trades(
    date: date,
    symbol: str,
    pivot_bars: int,
    limit: int = Query(50, description="Maximum number of trades to return", ge=1, le=500)
):
    """
    Get trades for a specific symbol and pivot_bars combination.
    
    Returns the last N trades (default 50) ordered by trade time descending.
    """
    try:
        # Verify the grid result exists
        result_exists = await db_pool.fetchval("""
            SELECT EXISTS(
                SELECT 1 FROM grid_market_structure 
                WHERE symbol = $1 AND backtest_date = $2 AND pivot_bars = $3
            )
        """, symbol, date, pivot_bars)
        
        if not result_exists:
            raise HTTPException(
                status_code=404, 
                detail=f"Grid result not found for {symbol} on {date} with pivot_bars={pivot_bars}"
            )
        
        # Fetch trades
        query = """
            SELECT 
                t.trade_time AT TIME ZONE 'America/New_York' as trade_time_et,
                t.direction,
                t.quantity,
                t.fill_price,
                t.fill_quantity,
                t.order_fee,
                t.position_value,
                t.trade_type,
                t.signal_reason,
                EXTRACT(EPOCH FROM t.trade_time)::BIGINT as trade_time_unix
            FROM grid_market_structure_trades t
            WHERE t.symbol = $1 AND t.backtest_date = $2 AND t.pivot_bars = $3
            ORDER BY t.trade_time DESC
            LIMIT $4
        """
        
        rows = await db_pool.fetch(query, symbol, date, pivot_bars, limit)
        
        # Convert to list of dicts with formatted data
        trades = []
        for row in rows:
            trades.append({
                "symbol": symbol,
                "tradeTime": row['trade_time_et'].isoformat(),
                "tradeTimeUnix": row['trade_time_unix'],
                "direction": row['direction'],
                "quantity": abs(float(row['quantity'])),
                "fillPrice": float(row['fill_price']) if row['fill_price'] else 0,
                "fillQuantity": float(row['fill_quantity']) if row['fill_quantity'] else abs(float(row['quantity'])),
                "orderFee": float(row['order_fee']) if row['order_fee'] else 0,
                "positionValue": float(row['position_value']) if row['position_value'] else 0,
                "tradeType": row['trade_type'],
                "signalReason": row['signal_reason']
            })
        
        return trades
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting symbol pivot trades: {e}")
        raise HTTPException(status_code=500, detail=str(e))