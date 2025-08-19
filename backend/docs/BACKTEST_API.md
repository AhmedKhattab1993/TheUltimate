# Backtesting API Documentation

The backtesting API provides endpoints to run LEAN algorithm backtests, monitor their progress in real-time, and retrieve historical results.

## API Endpoints

### 1. List Available Strategies

```
GET /api/v2/backtest/strategies
```

Returns a list of all available LEAN strategies in the project.

**Response:**
```json
[
  {
    "name": "main",
    "file_path": "/path/to/main.py",
    "description": "Default LEAN strategy",
    "last_modified": "2025-08-10T10:00:00"
  }
]
```

### 2. Get Strategy Details

```
GET /api/v2/backtest/strategies/{name}
```

Get detailed information about a specific strategy including available parameters.

**Response:**
```json
{
  "name": "main",
  "file_path": "/path/to/main.py",
  "description": "Default LEAN strategy",
  "parameters": {
    "risk_level": {
      "type": "string",
      "required": false
    }
  },
  "last_modified": "2025-08-10T10:00:00"
}
```

### 3. Start a Backtest

```
POST /api/v2/backtest/run
```

Start a new backtest with the specified configuration.

**Request Body:**
```json
{
  "strategy_name": "main",
  "start_date": "2013-10-07",
  "end_date": "2013-10-11",
  "initial_cash": 100000,
  "symbols": ["SPY"],
  "resolution": "Minute",
  "parameters": {
    "risk_level": "moderate"
  }
}
```

**Response:**
```json
{
  "backtest_id": "uuid-here",
  "status": "running",
  "request": { ... },
  "created_at": "2025-08-10T10:00:00",
  "started_at": "2025-08-10T10:00:01",
  "container_id": "docker-container-id"
}
```

### 4. Get Backtest Status

```
GET /api/v2/backtest/status/{backtest_id}
```

Get the current status of a running or completed backtest.

**Response:**
```json
{
  "backtest_id": "uuid-here",
  "status": "running",
  "request": { ... },
  "created_at": "2025-08-10T10:00:00",
  "started_at": "2025-08-10T10:00:01",
  "container_id": "docker-container-id"
}
```

### 5. Get Backtest Progress

```
GET /api/v2/backtest/progress/{backtest_id}
```

Get detailed progress information for a running backtest.

**Response:**
```json
{
  "backtest_id": "uuid-here",
  "status": "running",
  "progress_percentage": 45.5,
  "current_date": "2013-10-09",
  "log_entries": [
    "Processing data for 2013-10-09...",
    "Total Trades: 15"
  ],
  "statistics": {
    "total_trades": 15,
    "sharpe_ratio": 1.25
  }
}
```

### 6. Cancel a Backtest

```
DELETE /api/v2/backtest/cancel/{backtest_id}
```

Cancel a running backtest.

**Response:**
```json
{
  "message": "Backtest 'uuid-here' cancelled successfully"
}
```

### 7. List Historical Results

```
GET /api/v2/backtest/results?page=1&page_size=20&strategy_name=main
```

List historical backtest results with pagination.

**Query Parameters:**
- `page`: Page number (default: 1)
- `page_size`: Results per page (default: 20, max: 100)
- `strategy_name`: Filter by strategy name (optional)

**Response:**
```json
{
  "results": [
    {
      "backtest_id": "uuid-here",
      "strategy_name": "main",
      "start_date": "2013-10-07",
      "end_date": "2013-10-11",
      "initial_cash": 100000,
      "final_value": 115500,
      "statistics": {
        "total_return": 15.5,
        "sharpe_ratio": 1.25,
        "max_drawdown": -8.3,
        "win_rate": 55.0,
        "total_trades": 150,
        "average_win": 125.50,
        "average_loss": -85.25,
        "profit_factor": 1.35,
        "net_profit": 15500.0
      },
      "created_at": "2025-08-10T10:00:00",
      "result_path": "/path/to/results"
    }
  ],
  "total_count": 50,
  "page": 1,
  "page_size": 20
}
```

### 8. Get Specific Result

```
GET /api/v2/backtest/results/{timestamp}
```

Get detailed results for a specific backtest.

**Parameters:**
- `timestamp`: The timestamp folder name (e.g., "2025-08-10_05-09-01")

**Response:** Complete backtest result including trades and equity curve.

### 9. Delete Result

```
DELETE /api/v2/backtest/results/{timestamp}
```

Delete a backtest result.

### 10. WebSocket Monitoring

```
WebSocket /api/v2/backtest/monitor/{backtest_id}
```

Connect via WebSocket for real-time backtest monitoring.

**Message Types:**

1. **Connected Event**
```json
{
  "event": "connected",
  "backtest_id": "uuid-here",
  "status": "running"
}
```

2. **Progress Update**
```json
{
  "event": "progress_update",
  "backtest_id": "uuid-here",
  "progress": {
    "progress_percentage": 45.5,
    "current_date": "2013-10-09",
    "statistics": { ... }
  }
}
```

3. **Completion Event**
```json
{
  "event": "backtest_completed",
  "backtest_id": "uuid-here",
  "result": { ... }
}
```

4. **Failure Event**
```json
{
  "event": "backtest_failed",
  "backtest_id": "uuid-here",
  "error": "Error message"
}
```

## Example Usage

### Starting a Backtest

```python
import httpx

async def start_backtest():
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8000/api/v2/backtest/run",
            json={
                "strategy_name": "main",
                "start_date": "2013-10-07",
                "end_date": "2013-10-11",
                "initial_cash": 100000,
                "symbols": ["SPY"],
                "resolution": "Minute"
            }
        )
        result = response.json()
        return result["backtest_id"]
```

### Monitoring Progress via WebSocket

```python
import websockets
import json

async def monitor_backtest(backtest_id):
    uri = f"ws://localhost:8000/api/v2/backtest/monitor/{backtest_id}"
    
    async with websockets.connect(uri) as websocket:
        while True:
            message = await websocket.recv()
            data = json.loads(message)
            
            if data["event"] == "progress_update":
                progress = data["progress"]
                print(f"Progress: {progress['progress_percentage']:.1f}%")
            elif data["event"] == "backtest_completed":
                print("Backtest completed!")
                break
```

## Data Resolutions

The following data resolutions are supported:
- `Tick`: Tick-level data
- `Second`: Second bars
- `Minute`: Minute bars (default)
- `Hour`: Hourly bars
- `Daily`: Daily bars

## Notes

1. Backtests run in Docker containers using the LEAN engine
2. Results are stored in timestamped folders under `test-project/backtests/`
3. The WebSocket connection provides real-time updates during backtest execution
4. Historical data must be available in the LEAN data directory for the requested symbols and date range
5. Multiple backtests can run simultaneously, each in its own container