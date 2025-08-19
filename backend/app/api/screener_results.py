"""
API endpoints for screener results management - Updated for New Schema.
This version works with the migrated column-based database schema using individual typed columns
instead of JSON storage. Compatible with the new filter structure including price_vs_ma, RSI,
gap direction, and relative volume filters.
"""

from fastapi import APIRouter, HTTPException, Query, Depends
from typing import List, Optional, Dict, Any
from datetime import datetime, date
import logging
import json
from pathlib import Path
import uuid

from ..models.screener_results import (
    ScreenerResultSummary,
    ScreenerResultDetail,
    ScreenerResultsListResponse,
    SymbolMetrics
)
from ..services.screener_results import screener_results_manager
from ..services.database import db_pool

router = APIRouter(prefix="/api/v2/screener/results", tags=["screener-results"])
logger = logging.getLogger(__name__)


def create_filter_description(filters: dict) -> str:
    """Create a user-friendly description of the filters applied."""
    descriptions = []
    
    # Price range
    if 'min_price' in filters or 'max_price' in filters:
        if 'min_price' in filters and 'max_price' in filters:
            descriptions.append(f"Price: ${filters['min_price']:.2f} - ${filters['max_price']:.2f}")
        elif 'min_price' in filters:
            descriptions.append(f"Price: ≥ ${filters['min_price']:.2f}")
        elif 'max_price' in filters:
            descriptions.append(f"Price: ≤ ${filters['max_price']:.2f}")
    
    # Price vs MA
    if 'price_vs_ma' in filters and filters['price_vs_ma']['enabled']:
        pvm = filters['price_vs_ma']
        period = pvm.get('ma_period', 20)
        condition = pvm.get('condition', 'above')
        descriptions.append(f"Price {condition} SMA{period}")
    
    # Price vs VWAP
    if 'price_vs_vwap' in filters and filters['price_vs_vwap']['enabled']:
        condition = filters['price_vs_vwap'].get('condition', 'above')
        descriptions.append(f"Price {condition} VWAP")
    
    # Note: Market Cap, Change, and ATR filters are not supported in the new schema
    
    # RSI
    if 'rsi' in filters and filters['rsi']['enabled']:
        rsi = filters['rsi']
        period = rsi.get('rsi_period', 14)
        threshold = rsi.get('threshold', 0)
        condition = rsi.get('condition', 'above')
        descriptions.append(f"RSI{period} {condition} {threshold}")
    
    # Gap
    if 'gap' in filters and filters['gap']['enabled']:
        gap = filters['gap']
        threshold = gap.get('gap_threshold', 0)
        direction = gap.get('direction', 'any')
        if direction == 'any':
            descriptions.append(f"Gap ≥ {threshold}%")
        else:
            descriptions.append(f"Gap {direction} ≥ {threshold}%")
    
    # Previous Day Dollar Volume
    if 'prev_day_dollar_volume' in filters and filters['prev_day_dollar_volume']['enabled']:
        pdv = filters['prev_day_dollar_volume']
        min_vol = pdv.get('min_dollar_volume', 0)
        if min_vol >= 1_000_000:
            descriptions.append(f"Volume ≥ ${min_vol / 1_000_000:.1f}M")
        elif min_vol >= 1_000:
            descriptions.append(f"Volume ≥ ${min_vol / 1_000:.0f}K")
        else:
            descriptions.append(f"Volume ≥ ${min_vol:,.0f}")
    
    # Relative Volume
    if 'relative_volume' in filters and filters['relative_volume']['enabled']:
        rv = filters['relative_volume']
        ratio = rv.get('min_ratio', 1.0)
        recent = rv.get('recent_days', 1)
        lookback = rv.get('lookback_days', 20)
        descriptions.append(f"Relative Volume ({recent}d vs {lookback}d) ≥ {ratio}x")
    
    return "; ".join(descriptions) if descriptions else "No filters applied"


@router.get("", response_model=ScreenerResultsListResponse)
async def list_screener_results(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Results per page"),
    start_date: Optional[date] = Query(None, description="Filter results after this date"),
    end_date: Optional[date] = Query(None, description="Filter results before this date")
):
    """
    List screener results with pagination and date filtering.
    
    Args:
        page: Page number (1-based)
        page_size: Number of results per page
        start_date: Optional filter for results after this date
        end_date: Optional filter for results before this date
        
    Returns:
        Paginated list of screener results
    """
    try:
        # First, get unique sessions with pagination
        session_query = """
        SELECT DISTINCT ON (session_id) 
            session_id,
            MIN(created_at) OVER (PARTITION BY session_id) as session_created_at
        FROM screener_results
        WHERE 1=1
        """
        
        params = []
        param_count = 0
        
        # Add date filters if provided
        if start_date:
            param_count += 1
            session_query += f" AND created_at::date >= ${param_count}"
            params.append(start_date)
            
        if end_date:
            param_count += 1
            session_query += f" AND created_at::date <= ${param_count}"
            params.append(end_date)
        
        # Wrap in subquery for ordering and pagination
        paginated_session_query = f"""
        WITH unique_sessions AS (
            {session_query}
        )
        SELECT session_id
        FROM unique_sessions
        ORDER BY session_created_at DESC
        LIMIT ${param_count + 1}
        OFFSET ${param_count + 2}
        """
        
        params.append(page_size)
        params.append((page - 1) * page_size)
        
        # Get paginated session IDs
        session_rows = await db_pool.fetch(paginated_session_query, *params)
        session_ids = [row['session_id'] for row in session_rows]
        
        if not session_ids:
            return ScreenerResultsListResponse(
                results=[],
                total_count=0,
                page=page,
                page_size=page_size
            )
        
        # Get total count of unique sessions
        count_query = """
        SELECT COUNT(DISTINCT session_id) 
        FROM screener_results 
        WHERE 1=1
        """
        if start_date:
            count_query += f" AND created_at::date >= $1"
        if end_date:
            count_query += f" AND created_at::date <= ${2 if start_date else 1}"
        
        total_session_count = await db_pool.fetchval(count_query, *params[:param_count])
        
        # Now get all rows for these sessions
        query = """
        SELECT 
            id,
            symbol,
            company_name,
            screened_at,
            data_date,
            filter_min_price,
            filter_max_price,
            filter_prev_day_dollar_volume_enabled,
            filter_prev_day_dollar_volume,
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
            filter_relative_volume_enabled,
            filter_relative_volume_recent_days,
            filter_relative_volume_lookback_days,
            filter_relative_volume_min_ratio,
            session_id,
            created_at
        FROM screener_results
        WHERE session_id = ANY($1::uuid[])
        ORDER BY created_at DESC, symbol
        """
        
        # Execute query
        rows = await db_pool.fetch(query, session_ids)
        
        # Group results by session_id to create summaries
        session_groups = {}
        for row in rows:
            session_id = str(row['session_id']) if row['session_id'] else str(row['id'])
            if session_id not in session_groups:
                session_groups[session_id] = []
            session_groups[session_id].append(row)
        
        # Convert to response models
        summaries = []
        for session_id, session_rows in session_groups.items():
            # Reconstruct filters from the first row of the session (new schema)
            first_row = session_rows[0]
            filters = {}
            
            # Price Range Filter
            if first_row['filter_min_price'] is not None:
                filters['min_price'] = float(first_row['filter_min_price'])
            if first_row['filter_max_price'] is not None:
                filters['max_price'] = float(first_row['filter_max_price'])
            
            # Previous Day Dollar Volume Filter
            if first_row['filter_prev_day_dollar_volume_enabled']:
                filters['prev_day_dollar_volume'] = {
                    'enabled': True,
                    'min_dollar_volume': float(first_row['filter_prev_day_dollar_volume']) if first_row['filter_prev_day_dollar_volume'] is not None else 0
                }
            
            # Price vs MA Filter
            if first_row['filter_price_vs_ma_enabled']:
                filters['price_vs_ma'] = {
                    'enabled': True,
                    'ma_period': first_row['filter_price_vs_ma_period'] or 20,
                    'condition': first_row['filter_price_vs_ma_condition'] or 'above'
                }
            
            # RSI Filter
            if first_row['filter_rsi_enabled']:
                filters['rsi'] = {
                    'enabled': True,
                    'rsi_period': first_row['filter_rsi_period'] or 14,
                    'threshold': float(first_row['filter_rsi_threshold']) if first_row['filter_rsi_threshold'] is not None else 0,
                    'condition': first_row['filter_rsi_condition'] or 'above'
                }
            
            # Gap Filter
            if first_row['filter_gap_enabled']:
                filters['gap'] = {
                    'enabled': True,
                    'gap_threshold': float(first_row['filter_gap_threshold']) if first_row['filter_gap_threshold'] is not None else 0,
                    'direction': first_row['filter_gap_direction'] or 'any'
                }
            
            # Relative Volume Filter
            if first_row['filter_relative_volume_enabled']:
                filters['relative_volume'] = {
                    'enabled': True,
                    'recent_days': first_row['filter_relative_volume_recent_days'] or 1,
                    'lookback_days': first_row['filter_relative_volume_lookback_days'] or 20,
                    'min_ratio': float(first_row['filter_relative_volume_min_ratio']) if first_row['filter_relative_volume_min_ratio'] is not None else 1.0
                }
            
            # Add date range
            filters['start_date'] = first_row['data_date'].isoformat()
            filters['end_date'] = first_row['data_date'].isoformat()
            
            # Add user-friendly filter description
            filters['description'] = create_filter_description(filters)
            
            # Calculate execution time (default to 100ms if not available)
            execution_time_ms = 100.0
            total_symbols_screened = len(session_rows)
            
            summary = ScreenerResultSummary(
                id=session_id,
                timestamp=first_row['created_at'].isoformat() if first_row['created_at'] else first_row['screened_at'].isoformat(),
                symbol_count=len(session_rows),
                filters=filters,
                execution_time_ms=execution_time_ms,
                total_symbols_screened=total_symbols_screened
            )
            summaries.append(summary)
        
        # Sort by timestamp descending
        summaries.sort(key=lambda x: x.timestamp, reverse=True)
        
        # Return all summaries (already paginated at session level)
        return ScreenerResultsListResponse(
            results=summaries,
            total_count=total_session_count,  # Total unique sessions from the count query
            page=page,
            page_size=page_size
        )
        
    except Exception as e:
        logger.error(f"Error listing screener results: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{result_id}", response_model=ScreenerResultDetail)
async def get_screener_result(result_id: str):
    """
    Get detailed screener result by ID.
    
    Args:
        result_id: The result ID (UUID)
        
    Returns:
        Detailed screener result including all symbols and metrics
    """
    try:
        # Query the screener_results table - get all rows for this session (new schema)
        query = """
        SELECT 
            id,
            symbol,
            company_name,
            screened_at,
            data_date,
            filter_min_price,
            filter_max_price,
            filter_prev_day_dollar_volume_enabled,
            filter_prev_day_dollar_volume,
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
            filter_relative_volume_enabled,
            filter_relative_volume_recent_days,
            filter_relative_volume_lookback_days,
            filter_relative_volume_min_ratio,
            session_id,
            created_at
        FROM screener_results
        WHERE session_id = $1::uuid OR id = $1::uuid
        ORDER BY symbol
        """
        
        rows = await db_pool.fetch(query, result_id)
        
        if not rows:
            raise HTTPException(status_code=404, detail=f"Screener result '{result_id}' not found")
        
        # Reconstruct filters from the first row (new schema)
        first_row = rows[0]
        filters = {}
        
        # Price Range Filter
        if first_row['filter_min_price'] is not None:
            filters['min_price'] = float(first_row['filter_min_price'])
        if first_row['filter_max_price'] is not None:
            filters['max_price'] = float(first_row['filter_max_price'])
        
        # Previous Day Dollar Volume Filter
        if first_row['filter_prev_day_dollar_volume_enabled']:
            filters['prev_day_dollar_volume'] = {
                'enabled': True,
                'min_dollar_volume': float(first_row['filter_prev_day_dollar_volume']) if first_row['filter_prev_day_dollar_volume'] is not None else 0
            }
        
        # Price vs MA Filter
        if first_row['filter_price_vs_ma_enabled']:
            filters['price_vs_ma'] = {
                'enabled': True,
                'ma_period': first_row['filter_price_vs_ma_period'] or 20,
                'condition': first_row['filter_price_vs_ma_condition'] or 'above'
            }
        
        # RSI Filter
        if first_row['filter_rsi_enabled']:
            filters['rsi'] = {
                'enabled': True,
                'rsi_period': first_row['filter_rsi_period'] or 14,
                'threshold': float(first_row['filter_rsi_threshold']) if first_row['filter_rsi_threshold'] is not None else 0,
                'condition': first_row['filter_rsi_condition'] or 'above'
            }
        
        # Gap Filter
        if first_row['filter_gap_enabled']:
            filters['gap'] = {
                'enabled': True,
                'gap_threshold': float(first_row['filter_gap_threshold']) if first_row['filter_gap_threshold'] is not None else 0,
                'direction': first_row['filter_gap_direction'] or 'any'
            }
        
        # Relative Volume Filter
        if first_row['filter_relative_volume_enabled']:
            filters['relative_volume'] = {
                'enabled': True,
                'recent_days': first_row['filter_relative_volume_recent_days'] or 1,
                'lookback_days': first_row['filter_relative_volume_lookback_days'] or 20,
                'min_ratio': float(first_row['filter_relative_volume_min_ratio']) if first_row['filter_relative_volume_min_ratio'] is not None else 1.0
            }
        
        # Add date range
        filters['start_date'] = first_row['data_date'].isoformat()
        filters['end_date'] = first_row['data_date'].isoformat()
        
        # Add user-friendly filter description
        filters['description'] = create_filter_description(filters)
        
        # Build symbols with metrics from all rows (price and volume not stored in new schema)
        symbols_with_metrics = []
        for row in rows:
            symbol_data = SymbolMetrics(
                symbol=row['symbol'],
                latest_price=None,  # Price data not stored in new schema
                latest_volume=None  # Volume data not stored in new schema
            )
            symbols_with_metrics.append(symbol_data)
        
        # Build metadata
        session_id = str(first_row['session_id']) if first_row['session_id'] else str(first_row['id'])
        metadata = {
            "execution_time_ms": 100.0,  # Default value
            "total_symbols_screened": len(rows),
            "date_range": {
                "start": first_row['data_date'].isoformat(),
                "end": first_row['data_date'].isoformat()
            },
            "request_hash": session_id,  # Use session_id as a proxy for request_hash
            "expires_at": None
        }
        
        # Create detailed response
        detail = ScreenerResultDetail(
            id=session_id,
            timestamp=first_row['created_at'].isoformat() if first_row['created_at'] else first_row['screened_at'].isoformat(),
            symbol_count=len(rows),
            filters=filters,
            metadata=metadata,
            symbols=symbols_with_metrics
        )
        
        return detail
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting screener result: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{result_id}")
async def delete_screener_result(result_id: str):
    """
    Delete a screener result.
    
    Args:
        result_id: The result ID to delete
        
    Returns:
        Success message if deleted
    """
    try:
        # Delete from database
        query = "DELETE FROM screener_results WHERE id = $1 RETURNING id"
        
        deleted_id = await db_pool.fetchval(query, result_id)
        
        if not deleted_id:
            raise HTTPException(status_code=404, detail=f"Screener result '{result_id}' not found")
        
        return {"message": f"Screener result '{result_id}' deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting screener result: {e}")
        raise HTTPException(status_code=500, detail=str(e))