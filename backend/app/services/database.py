"""
Database connection management for TimescaleDB
"""
import asyncpg
import asyncio
import logging
from typing import Optional, Dict, Any, List
from contextlib import asynccontextmanager
import pytz
from datetime import datetime

from app.config import settings

logger = logging.getLogger(__name__)

# Eastern timezone for market data
ET = pytz.timezone('US/Eastern')


class DatabasePool:
    """Manages database connection pool for TimescaleDB"""
    
    def __init__(self):
        self._pool: Optional[asyncpg.Pool] = None
        self._initialized = False
        
    async def initialize(self):
        """Initialize the connection pool"""
        if self._initialized:
            return
            
        try:
            self._pool = await asyncpg.create_pool(
                settings.database_url,
                min_size=settings.database_pool_min_size,
                max_size=settings.database_pool_max_size,
                command_timeout=settings.database_command_timeout,
                # Set timezone to Eastern for all connections
                server_settings={
                    'timezone': 'US/Eastern'
                }
            )
            self._initialized = True
            logger.info(f"Database pool initialized with {settings.database_pool_min_size}-{settings.database_pool_max_size} connections")
            
        except Exception as e:
            logger.error(f"Failed to initialize database pool: {e}")
            raise
            
    async def close(self):
        """Close the connection pool"""
        if self._pool:
            await self._pool.close()
            self._initialized = False
            logger.info("Database pool closed")
            
    @asynccontextmanager
    async def acquire(self):
        """Acquire a connection from the pool"""
        if not self._initialized:
            await self.initialize()
            
        async with self._pool.acquire() as connection:
            yield connection
            
    async def execute(self, query: str, *args):
        """Execute a query"""
        async with self.acquire() as conn:
            return await conn.execute(query, *args)
            
    async def fetch(self, query: str, *args) -> List[asyncpg.Record]:
        """Fetch multiple rows"""
        async with self.acquire() as conn:
            return await conn.fetch(query, *args)
            
    async def fetchrow(self, query: str, *args) -> Optional[asyncpg.Record]:
        """Fetch a single row"""
        async with self.acquire() as conn:
            return await conn.fetchrow(query, *args)
            
    async def fetchval(self, query: str, *args):
        """Fetch a single value"""
        async with self.acquire() as conn:
            return await conn.fetchval(query, *args)
            
    async def executemany(self, query: str, args_list: List[tuple]):
        """Execute many queries"""
        async with self.acquire() as conn:
            return await conn.executemany(query, args_list)
            
    async def copy_records_to_table(
        self,
        table_name: str,
        records: List[tuple],
        columns: List[str]
    ):
        """
        Bulk insert records using COPY command for maximum performance
        
        Args:
            table_name: Name of the table
            records: List of tuples containing record data
            columns: List of column names
        """
        async with self.acquire() as conn:
            # Use COPY for bulk inserts
            result = await conn.copy_records_to_table(
                table_name,
                records=records,
                columns=columns
            )
            return result


# Global database pool instance
db_pool = DatabasePool()


def convert_to_et(dt: datetime) -> datetime:
    """Convert datetime to Eastern Time"""
    if dt.tzinfo is None:
        # Assume UTC if no timezone
        dt = pytz.utc.localize(dt)
    return dt.astimezone(ET)


def get_et_now() -> datetime:
    """Get current time in Eastern Time"""
    return datetime.now(ET)


async def check_database_connection() -> bool:
    """Check if database connection is working"""
    try:
        await db_pool.execute('SELECT 1')
        return True
    except Exception as e:
        logger.error(f"Database connection check failed: {e}")
        return False


async def get_table_count(table_name: str) -> int:
    """Get row count for a table"""
    try:
        count = await db_pool.fetchval(f'SELECT COUNT(*) FROM {table_name}')
        return count
    except Exception as e:
        logger.error(f"Failed to get count for table {table_name}: {e}")
        return 0


class DatabaseTransaction:
    """Context manager for database transactions"""
    
    def __init__(self, pool: DatabasePool = None):
        self.pool = pool or db_pool
        self.conn = None
        self.transaction = None
        
    async def __aenter__(self):
        self.conn = await self.pool._pool.acquire()
        self.transaction = self.conn.transaction()
        await self.transaction.start()
        return self.conn
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        try:
            if exc_type is None:
                await self.transaction.commit()
            else:
                await self.transaction.rollback()
        finally:
            await self.pool._pool.release(self.conn)