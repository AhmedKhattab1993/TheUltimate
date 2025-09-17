"""
API endpoints for filter optimization.
"""

from fastapi import APIRouter, HTTPException, Depends
from typing import Optional
import logging

from ..models.filter_optimization import OptimizationRequest, OptimizationResponse
from ..services.filter_optimizer import FilterOptimizer

router = APIRouter(prefix="/api/v2/filter-optimizer", tags=["filter-optimizer"])
logger = logging.getLogger(__name__)


@router.post("/optimize", response_model=OptimizationResponse)
async def optimize_filters(request: OptimizationRequest):
    """
    Optimize screener filter parameters to maximize the target metric.
    
    This endpoint tests various combinations of filter parameters against historical data
    and returns the best-performing combinations based on the specified target metric.
    """
    try:
        optimizer = FilterOptimizer()
        result = await optimizer.optimize_filters(request)
        return result
    except Exception as e:
        logger.error(f"Error optimizing filters: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/suggested-ranges")
async def get_suggested_ranges(start_date: str, end_date: str):
    """
    Get suggested parameter ranges based on the data distribution in the specified date range.
    
    This helps users set reasonable search ranges for the optimizer.
    """
    try:
        from ..services.database import db_pool
        from datetime import datetime
        
        # Convert string dates to date objects
        start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
        end_date_obj = datetime.strptime(end_date, '%Y-%m-%d').date()
        
        # Query to get min/max values from the data
        query = """
        SELECT 
            MIN(price) as min_price,
            MAX(price) as max_price,
            PERCENTILE_CONT(0.05) WITHIN GROUP (ORDER BY price) as price_5th,
            PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY price) as price_95th,
            
            MIN(rsi_14) as min_rsi,
            MAX(rsi_14) as max_rsi,
            
            MIN(gap_percent) as min_gap,
            MAX(gap_percent) as max_gap,
            PERCENTILE_CONT(0.05) WITHIN GROUP (ORDER BY gap_percent) as gap_5th,
            PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY gap_percent) as gap_95th,
            
            MIN(prev_day_dollar_volume) as min_volume,
            MAX(prev_day_dollar_volume) as max_volume,
            PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY prev_day_dollar_volume) as volume_25th,
            PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY prev_day_dollar_volume) as volume_75th,
            
            MIN(relative_volume) as min_rel_volume,
            MAX(relative_volume) as max_rel_volume
        FROM grid_screening
        WHERE date BETWEEN $1::date AND $2::date
            AND price IS NOT NULL
            AND rsi_14 IS NOT NULL
        """
        
        result = await db_pool.fetchrow(query, start_date_obj, end_date_obj)
        
        if not result:
            raise HTTPException(status_code=404, detail="No data found for the specified date range")
        
        # Suggest reasonable ranges based on percentiles
        suggestions = {
            "price_range": {
                "min": {
                    "suggested_min": max(1, float(result['price_5th'] or 1)),
                    "suggested_max": float(result['price_95th'] or 100),
                    "suggested_step": 5.0
                },
                "max": {
                    "suggested_min": max(10, float(result['price_5th'] or 10)),
                    "suggested_max": min(500, float(result['price_95th'] or 500)),
                    "suggested_step": 10.0
                }
            },
            "rsi_range": {
                "min": {
                    "suggested_min": 20.0,
                    "suggested_max": 40.0,
                    "suggested_step": 5.0
                },
                "max": {
                    "suggested_min": 60.0,
                    "suggested_max": 80.0,
                    "suggested_step": 5.0
                }
            },
            "gap_range": {
                "min": {
                    "suggested_min": max(-20, float(result['gap_5th'] or -10)),
                    "suggested_max": 0.0,
                    "suggested_step": 1.0
                },
                "max": {
                    "suggested_min": 0.0,
                    "suggested_max": min(20, float(result['gap_95th'] or 10)),
                    "suggested_step": 1.0
                }
            },
            "volume": {
                "min": {
                    "suggested_min": float(result['volume_25th'] or 1000000),
                    "suggested_max": float(result['volume_75th'] or 10000000),
                    "suggested_step": 1000000.0
                }
            },
            "relative_volume": {
                "min": {
                    "suggested_min": 1.0,
                    "suggested_max": 3.0,
                    "suggested_step": 0.5
                }
            }
        }
        
        return {
            "date_range": {"start": start_date, "end": end_date},
            "data_summary": {
                "price_range": [float(result['min_price'] or 0), float(result['max_price'] or 0)],
                "rsi_range": [float(result['min_rsi'] or 0), float(result['max_rsi'] or 0)],
                "gap_range": [float(result['min_gap'] or 0), float(result['max_gap'] or 0)],
                "volume_range": [float(result['min_volume'] or 0), float(result['max_volume'] or 0)],
                "rel_volume_range": [float(result['min_rel_volume'] or 0), float(result['max_rel_volume'] or 0)]
            },
            "suggested_ranges": suggestions
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting suggested ranges: {e}")
        raise HTTPException(status_code=500, detail=str(e))