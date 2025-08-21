"""
API endpoints for combined screener and backtest results.
"""

from fastapi import APIRouter, HTTPException, Query, Depends
from typing import List, Optional, Dict, Any
from datetime import date, datetime
import logging
from uuid import UUID
import asyncpg

from ..services.database import db_pool
from ..models.combined_results import CombinedScreenerBacktestResponse, CombinedScreenerBacktestRow

router = APIRouter(prefix="/api/v2/combined-results", tags=["combined-results"])
logger = logging.getLogger(__name__)


@router.get("/", response_model=CombinedScreenerBacktestResponse)
async def get_combined_results(
    session_id: Optional[UUID] = Query(None, description="Filter by specific screener session ID"),
    start_date: Optional[date] = Query(None, description="Filter by screening date start"),
    end_date: Optional[date] = Query(None, description="Filter by screening date end"),
    source: Optional[str] = Query(None, description="Filter by source (ui/pipeline)"),
    symbol: Optional[str] = Query(None, description="Filter by specific symbol"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of results"),
    offset: int = Query(0, ge=0, description="Number of results to skip")
) -> CombinedScreenerBacktestResponse:
    """
    Get combined screener and backtest results.
    
    Returns a flat table with all columns from both screener and backtest results.
    Each row represents one symbol's screening and corresponding backtest results.
    """
    try:
        # Build the query with filters
        query = """
        SELECT 
            screener_session_id,
            screening_date,
            source,
            symbol,
            company_name,
            screened_at,
            filter_min_price,
            filter_max_price,
            filter_price_vs_ma_enabled,
            filter_price_vs_ma_period,
            filter_price_vs_ma_condition,
            filter_rsi_enabled,
            filter_rsi_period,
            filter_rsi_threshold,
            filter_rsi_condition,
            filter_gap_enabled,
            filter_gap_threshold,
            filter_gap_direction,
            filter_prev_day_dollar_volume_enabled,
            filter_prev_day_dollar_volume,
            filter_relative_volume_enabled,
            filter_relative_volume_recent_days,
            filter_relative_volume_lookback_days,
            filter_relative_volume_min_ratio,
            backtest_id,
            cache_hit,
            backtest_start_date,
            backtest_end_date,
            total_return,
            net_profit,
            net_profit_currency,
            compounding_annual_return,
            final_value,
            start_equity,
            end_equity,
            sharpe_ratio,
            sortino_ratio,
            max_drawdown,
            probabilistic_sharpe_ratio,
            annual_standard_deviation,
            annual_variance,
            beta,
            alpha,
            total_trades,
            winning_trades,
            losing_trades,
            win_rate,
            loss_rate,
            average_win,
            average_loss,
            profit_factor,
            profit_loss_ratio,
            expectancy,
            total_orders,
            information_ratio,
            tracking_error,
            treynor_ratio,
            total_fees,
            estimated_strategy_capacity,
            lowest_capacity_asset,
            portfolio_turnover,
            pivot_highs_detected,
            pivot_lows_detected,
            bos_signals_generated,
            position_flips,
            liquidation_events,
            initial_cash,
            pivot_bars,
            lower_timeframe,
            strategy_name,
            backtest_created_at
        FROM combined_screener_backtest_results
        WHERE 1=1
        """
        
        params = []
        param_count = 0
        
        # Add filters
        if session_id:
            param_count += 1
            query += f" AND screener_session_id = ${param_count}"
            params.append(session_id)
            
        if start_date:
            param_count += 1
            query += f" AND screening_date >= ${param_count}"
            params.append(start_date)
            
        if end_date:
            param_count += 1
            query += f" AND screening_date <= ${param_count}"
            params.append(end_date)
            
        if source:
            param_count += 1
            query += f" AND source = ${param_count}"
            params.append(source)
            
        if symbol:
            param_count += 1
            query += f" AND symbol = ${param_count}"
            params.append(symbol.upper())
        
        # Add ordering
        query += " ORDER BY screening_date DESC, screened_at DESC, total_return DESC NULLS LAST"
        
        # Get total count for pagination
        count_query = f"SELECT COUNT(*) FROM ({query}) as t"
        total_count = await db_pool.fetchval(count_query, *params)
        
        # Add pagination
        param_count += 1
        query += f" LIMIT ${param_count}"
        params.append(limit)
        
        param_count += 1
        query += f" OFFSET ${param_count}"
        params.append(offset)
        
        # Execute query
        rows = await db_pool.fetch(query, *params)
        
        # Convert rows to response model
        results = []
        for row in rows:
            result = CombinedScreenerBacktestRow(
                # Screener columns
                screener_session_id=row['screener_session_id'],
                screening_date=row['screening_date'].isoformat() if row['screening_date'] else None,
                source=row['source'],
                symbol=row['symbol'],
                company_name=row['company_name'],
                screened_at=row['screened_at'].isoformat() if row['screened_at'] else None,
                
                # Filter parameters
                filter_min_price=float(row['filter_min_price']) if row['filter_min_price'] else None,
                filter_max_price=float(row['filter_max_price']) if row['filter_max_price'] else None,
                filter_price_vs_ma_enabled=row['filter_price_vs_ma_enabled'],
                filter_price_vs_ma_period=row['filter_price_vs_ma_period'],
                filter_price_vs_ma_condition=row['filter_price_vs_ma_condition'],
                filter_rsi_enabled=row['filter_rsi_enabled'],
                filter_rsi_period=row['filter_rsi_period'],
                filter_rsi_threshold=float(row['filter_rsi_threshold']) if row['filter_rsi_threshold'] else None,
                filter_rsi_condition=row['filter_rsi_condition'],
                filter_gap_enabled=row['filter_gap_enabled'],
                filter_gap_threshold=float(row['filter_gap_threshold']) if row['filter_gap_threshold'] else None,
                filter_gap_direction=row['filter_gap_direction'],
                filter_prev_day_dollar_volume_enabled=row['filter_prev_day_dollar_volume_enabled'],
                filter_prev_day_dollar_volume=float(row['filter_prev_day_dollar_volume']) if row['filter_prev_day_dollar_volume'] else None,
                filter_relative_volume_enabled=row['filter_relative_volume_enabled'],
                filter_relative_volume_recent_days=row['filter_relative_volume_recent_days'],
                filter_relative_volume_lookback_days=row['filter_relative_volume_lookback_days'],
                filter_relative_volume_min_ratio=float(row['filter_relative_volume_min_ratio']) if row['filter_relative_volume_min_ratio'] else None,
                
                # Backtest columns
                backtest_id=row['backtest_id'],
                cache_hit=row['cache_hit'],
                backtest_start_date=row['backtest_start_date'].isoformat() if row['backtest_start_date'] else None,
                backtest_end_date=row['backtest_end_date'].isoformat() if row['backtest_end_date'] else None,
                backtest_created_at=row['backtest_created_at'].isoformat() if row['backtest_created_at'] else None,
                strategy_name=row['strategy_name'],
                
                # Performance metrics
                total_return=float(row['total_return']) if row['total_return'] else None,
                net_profit=float(row['net_profit']) if row['net_profit'] else None,
                net_profit_currency=float(row['net_profit_currency']) if row['net_profit_currency'] else None,
                compounding_annual_return=float(row['compounding_annual_return']) if row['compounding_annual_return'] else None,
                final_value=float(row['final_value']) if row['final_value'] else None,
                start_equity=float(row['start_equity']) if row['start_equity'] else None,
                end_equity=float(row['end_equity']) if row['end_equity'] else None,
                
                # Risk metrics
                sharpe_ratio=float(row['sharpe_ratio']) if row['sharpe_ratio'] else None,
                sortino_ratio=float(row['sortino_ratio']) if row['sortino_ratio'] else None,
                max_drawdown=float(row['max_drawdown']) if row['max_drawdown'] else None,
                probabilistic_sharpe_ratio=float(row['probabilistic_sharpe_ratio']) if row['probabilistic_sharpe_ratio'] else None,
                annual_standard_deviation=float(row['annual_standard_deviation']) if row['annual_standard_deviation'] else None,
                annual_variance=float(row['annual_variance']) if row['annual_variance'] else None,
                beta=float(row['beta']) if row['beta'] else None,
                alpha=float(row['alpha']) if row['alpha'] else None,
                
                # Trading statistics
                total_trades=row['total_trades'],
                winning_trades=row['winning_trades'],
                losing_trades=row['losing_trades'],
                win_rate=float(row['win_rate']) if row['win_rate'] else None,
                loss_rate=float(row['loss_rate']) if row['loss_rate'] else None,
                average_win=float(row['average_win']) if row['average_win'] else None,
                average_loss=float(row['average_loss']) if row['average_loss'] else None,
                profit_factor=float(row['profit_factor']) if row['profit_factor'] else None,
                profit_loss_ratio=float(row['profit_loss_ratio']) if row['profit_loss_ratio'] else None,
                expectancy=float(row['expectancy']) if row['expectancy'] else None,
                total_orders=row['total_orders'],
                
                # Advanced metrics
                information_ratio=float(row['information_ratio']) if row['information_ratio'] else None,
                tracking_error=float(row['tracking_error']) if row['tracking_error'] else None,
                treynor_ratio=float(row['treynor_ratio']) if row['treynor_ratio'] else None,
                total_fees=float(row['total_fees']) if row['total_fees'] else None,
                estimated_strategy_capacity=float(row['estimated_strategy_capacity']) if row['estimated_strategy_capacity'] else None,
                lowest_capacity_asset=row['lowest_capacity_asset'],
                portfolio_turnover=float(row['portfolio_turnover']) if row['portfolio_turnover'] else None,
                
                # Strategy-specific metrics
                pivot_highs_detected=row['pivot_highs_detected'],
                pivot_lows_detected=row['pivot_lows_detected'],
                bos_signals_generated=row['bos_signals_generated'],
                position_flips=row['position_flips'],
                liquidation_events=row['liquidation_events'],
                
                # Algorithm parameters
                initial_cash=float(row['initial_cash']) if row['initial_cash'] else None,
                pivot_bars=row['pivot_bars'],
                lower_timeframe=row['lower_timeframe']
            )
            results.append(result)
        
        return CombinedScreenerBacktestResponse(
            results=results,
            total_count=total_count,
            limit=limit,
            offset=offset
        )
        
    except Exception as e:
        logger.error(f"Error fetching combined results: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sessions", response_model=List[Dict[str, Any]])
async def get_screener_sessions(
    source: Optional[str] = Query(None, description="Filter by source (ui/pipeline)"),
    limit: int = Query(20, ge=1, le=100, description="Maximum number of sessions")
) -> List[Dict[str, Any]]:
    """
    Get list of screener sessions with summary statistics.
    
    Returns sessions ordered by most recent first.
    """
    try:
        query = """
        SELECT DISTINCT
            sr.session_id,
            sr.source,
            MIN(sr.data_date) as start_date,
            MAX(sr.data_date) as end_date,
            COUNT(DISTINCT sr.symbol) as total_symbols,
            COUNT(DISTINCT sr.data_date) as total_days,
            MIN(sr.created_at) as created_at,
            COUNT(DISTINCT sbl.backtest_id) as total_backtests
        FROM screener_results sr
        LEFT JOIN screener_backtest_links sbl ON sr.session_id = sbl.screener_session_id
        WHERE sr.session_id IS NOT NULL
        """
        
        params = []
        if source:
            query += " AND sr.source = $1"
            params.append(source)
            
        query += """
        GROUP BY sr.session_id, sr.source
        ORDER BY created_at DESC
        LIMIT $""" + str(len(params) + 1)
        params.append(limit)
        
        rows = await db_pool.fetch(query, *params)
        
        sessions = []
        for row in rows:
            sessions.append({
                "session_id": str(row['session_id']),
                "source": row['source'],
                "start_date": row['start_date'].isoformat() if row['start_date'] else None,
                "end_date": row['end_date'].isoformat() if row['end_date'] else None,
                "total_symbols": row['total_symbols'],
                "total_days": row['total_days'],
                "created_at": row['created_at'].isoformat() if row['created_at'] else None,
                "total_backtests": row['total_backtests']
            })
            
        return sessions
        
    except Exception as e:
        logger.error(f"Error fetching screener sessions: {e}")
        raise HTTPException(status_code=500, detail=str(e))