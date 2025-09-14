#!/usr/bin/env python3
"""Apply grid trades table migration."""

import asyncio
import asyncpg
import logging
from pathlib import Path
import sys

# Add backend to path
sys.path.append(str(Path(__file__).parent.parent))

from app.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def apply_migration():
    """Apply the grid_market_structure_trades table migration."""
    
    try:
        # Connect to database
        conn = await asyncpg.connect(settings.database_url)
        logger.info("Connected to database")
        
        # Check if table already exists
        exists = await conn.fetchval('''
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'grid_market_structure_trades'
            )
        ''')
        
        if exists:
            logger.info("Table grid_market_structure_trades already exists, skipping migration")
            await conn.close()
            return
        
        logger.info("Creating grid_market_structure_trades table...")
        
        # Create the table
        await conn.execute('''
            CREATE TABLE grid_market_structure_trades (
                id BIGSERIAL PRIMARY KEY,
                symbol VARCHAR(10) NOT NULL,
                backtest_date DATE NOT NULL,
                pivot_bars INTEGER NOT NULL,
                
                -- Trade details
                trade_time TIMESTAMP WITH TIME ZONE NOT NULL,
                direction VARCHAR(10) NOT NULL,
                quantity INTEGER NOT NULL,
                fill_price NUMERIC(10, 2) NOT NULL,
                fill_quantity INTEGER NOT NULL,
                order_fee NUMERIC(10, 2) DEFAULT 0,
                
                -- Additional trade metrics
                profit_loss NUMERIC(10, 2),
                profit_loss_percent NUMERIC(8, 4),
                position_size INTEGER,
                position_value NUMERIC(12, 2),
                
                -- Trade metadata
                order_id VARCHAR(50),
                order_type VARCHAR(20),
                trade_type VARCHAR(20),
                signal_reason TEXT,
                
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                
                FOREIGN KEY (symbol, backtest_date, pivot_bars)
                    REFERENCES grid_market_structure(symbol, backtest_date, pivot_bars)
                    ON DELETE CASCADE
            )
        ''')
        
        logger.info("Created grid_market_structure_trades table")
        
        # Create indexes
        await conn.execute('''
            CREATE INDEX idx_grid_trades_lookup
            ON grid_market_structure_trades(symbol, backtest_date, pivot_bars)
        ''')
        
        await conn.execute('''
            CREATE INDEX idx_grid_trades_time
            ON grid_market_structure_trades(trade_time)
        ''')
        
        await conn.execute('''
            CREATE INDEX idx_grid_trades_direction
            ON grid_market_structure_trades(direction)
        ''')
        
        logger.info("Created indexes on grid_market_structure_trades")
        
        # Verify the table was created
        columns = await conn.fetch('''
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'grid_market_structure_trades'
            ORDER BY ordinal_position
        ''')
        
        logger.info(f"\nTable created with {len(columns)} columns:")
        for col in columns:
            logger.info(f"  - {col['column_name']}: {col['data_type']}")
        
        await conn.close()
        logger.info("\nMigration completed successfully!")
        
    except Exception as e:
        logger.error(f"Error applying migration: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(apply_migration())