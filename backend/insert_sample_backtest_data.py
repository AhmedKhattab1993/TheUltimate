#!/usr/bin/env python3
"""
Insert sample backtest data into market_structure_results table for testing.
"""

import asyncio
import asyncpg
import json
from datetime import datetime, timedelta
from app.config import settings
import uuid

async def insert_sample_data():
    """Insert sample backtest results."""
    conn = await asyncpg.connect(settings.database_url)
    
    try:
        # Sample backtest results
        samples = [
            {
                "symbol": "AAPL",
                "date_range": {"start": "2025-01-01", "end": "2025-01-31"},
                "parameters": {"stop_loss": 0.02, "take_profit": 0.05},
                "statistics": {
                    "totalReturn": 12.5,
                    "netProfit": 12.5,
                    "netProfitCurrency": 12500,
                    "compoundingAnnualReturn": 10.2,
                    "sharpeRatio": 1.8,
                    "sortinoRatio": 2.1,
                    "maxDrawdown": 5.3,
                    "probabilisticSharpeRatio": 85.5,
                    "totalOrders": 45,
                    "totalTrades": 45,
                    "winRate": 65.0,
                    "lossRate": 35.0,
                    "averageWin": 2.5,
                    "averageLoss": -1.2,
                    "averageWinCurrency": 250,
                    "averageLossCurrency": -120,
                    "profitFactor": 2.1,
                    "profitLossRatio": 2.1,
                    "expectancy": 0.8,
                    "alpha": 0.05,
                    "beta": 0.85,
                    "annualStandardDeviation": 0.18,
                    "annualVariance": 0.032,
                    "informationRatio": 1.2,
                    "trackingError": 0.08,
                    "treynorRatio": 0.15,
                    "startEquity": 100000,
                    "endEquity": 112500,
                    "totalFees": 450,
                    "estimatedStrategyCapacity": 5000000,
                    "lowestCapacityAsset": "AAPL",
                    "portfolioTurnover": 85.5
                }
            },
            {
                "symbol": "MSFT",
                "date_range": {"start": "2025-02-01", "end": "2025-02-28"},
                "parameters": {"stop_loss": 0.015, "take_profit": 0.04},
                "statistics": {
                    "totalReturn": -5.8,
                    "netProfit": -5.8,
                    "netProfitCurrency": -5800,
                    "compoundingAnnualReturn": -8.2,
                    "sharpeRatio": -0.5,
                    "sortinoRatio": -0.3,
                    "maxDrawdown": 12.5,
                    "probabilisticSharpeRatio": 25.5,
                    "totalOrders": 38,
                    "totalTrades": 38,
                    "winRate": 42.0,
                    "lossRate": 58.0,
                    "averageWin": 1.8,
                    "averageLoss": -1.5,
                    "averageWinCurrency": 180,
                    "averageLossCurrency": -150,
                    "profitFactor": 0.85,
                    "profitLossRatio": 1.2,
                    "expectancy": -0.2,
                    "alpha": -0.02,
                    "beta": 0.95,
                    "annualStandardDeviation": 0.22,
                    "annualVariance": 0.048,
                    "informationRatio": -0.4,
                    "trackingError": 0.12,
                    "treynorRatio": -0.08,
                    "startEquity": 100000,
                    "endEquity": 94200,
                    "totalFees": 380,
                    "estimatedStrategyCapacity": 3000000,
                    "lowestCapacityAsset": "MSFT",
                    "portfolioTurnover": 72.5
                }
            },
            {
                "symbol": "GOOGL",
                "date_range": {"start": "2025-03-01", "end": "2025-03-31"},
                "parameters": {"stop_loss": 0.025, "take_profit": 0.06},
                "statistics": {
                    "totalReturn": 18.2,
                    "netProfit": 18.2,
                    "netProfitCurrency": 18200,
                    "compoundingAnnualReturn": 15.8,
                    "sharpeRatio": 2.4,
                    "sortinoRatio": 3.1,
                    "maxDrawdown": 3.8,
                    "probabilisticSharpeRatio": 92.5,
                    "totalOrders": 52,
                    "totalTrades": 52,
                    "winRate": 71.0,
                    "lossRate": 29.0,
                    "averageWin": 3.2,
                    "averageLoss": -0.9,
                    "averageWinCurrency": 320,
                    "averageLossCurrency": -90,
                    "profitFactor": 3.5,
                    "profitLossRatio": 3.5,
                    "expectancy": 1.2,
                    "alpha": 0.08,
                    "beta": 0.75,
                    "annualStandardDeviation": 0.15,
                    "annualVariance": 0.022,
                    "informationRatio": 1.8,
                    "trackingError": 0.06,
                    "treynorRatio": 0.22,
                    "startEquity": 100000,
                    "endEquity": 118200,
                    "totalFees": 520,
                    "estimatedStrategyCapacity": 8000000,
                    "lowestCapacityAsset": "GOOGL",
                    "portfolioTurnover": 95.5
                }
            }
        ]
        
        # Insert each sample
        for i, sample in enumerate(samples):
            result_id = str(uuid.uuid4())
            request_hash = f"sample_hash_{i+1}"
            created_at = datetime.utcnow() - timedelta(days=i*10)
            expires_at = created_at + timedelta(days=30)
            
            query = """
            INSERT INTO market_structure_results 
            (id, hash, symbol, date_range, parameters, statistics, created_at, expires_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            """
            
            await conn.execute(
                query,
                result_id,
                request_hash,
                sample["symbol"],
                json.dumps(sample["date_range"]),
                json.dumps(sample["parameters"]),
                json.dumps(sample["statistics"]),
                created_at,
                expires_at
            )
            
            print(f"Inserted sample backtest result for {sample['symbol']} (ID: {result_id})")
        
        print(f"\nSuccessfully inserted {len(samples)} sample backtest results!")
        
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(insert_sample_data())