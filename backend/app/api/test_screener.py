"""
Test cases for the screener API endpoints.

Run with: pytest backend/app/api/test_screener.py
"""

import pytest
from fastapi.testclient import TestClient
from datetime import date, timedelta
from unittest.mock import Mock, AsyncMock, patch

from app.main import app
from app.models.stock import StockData, StockBar
from app.services.polygon_client import PolygonAPIError


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def mock_polygon_client():
    """Create mock Polygon client."""
    mock = Mock()
    mock.check_market_status = AsyncMock(return_value={"market": "open"})
    mock.fetch_batch_historical_data = AsyncMock()
    return mock


def test_health_check(client, mock_polygon_client):
    """Test health check endpoint."""
    with patch('app.api.screener.get_polygon_client', return_value=mock_polygon_client):
        response = client.get("/api/v1/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "timestamp" in data
        assert "checks" in data
        assert "polygon_api" in data["checks"]


def test_health_check_polygon_error(client, mock_polygon_client):
    """Test health check when Polygon API is down."""
    mock_polygon_client.check_market_status = AsyncMock(
        side_effect=PolygonAPIError("API unavailable", status_code=503)
    )
    
    with patch('app.api.screener.get_polygon_client', return_value=mock_polygon_client):
        response = client.get("/api/v1/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "degraded"
        assert data["checks"]["polygon_api"]["status"] == "unhealthy"


def test_get_symbols(client):
    """Test get available symbols endpoint."""
    response = client.get("/api/v1/symbols")
    
    assert response.status_code == 200
    symbols = response.json()
    assert isinstance(symbols, list)
    assert len(symbols) > 0
    assert "AAPL" in symbols
    assert all(isinstance(s, str) for s in symbols)


def test_get_filters(client):
    """Test get available filters endpoint."""
    response = client.get("/api/v1/filters")
    
    assert response.status_code == 200
    filters = response.json()
    
    # Check filter structure
    assert "volume" in filters
    assert "price_change" in filters
    assert "moving_average" in filters
    
    # Check volume filter details
    volume_filter = filters["volume"]
    assert "description" in volume_filter
    assert "parameters" in volume_filter
    assert "min_average" in volume_filter["parameters"]
    assert "lookback_days" in volume_filter["parameters"]


def test_screen_missing_filters(client):
    """Test screening endpoint with missing filters."""
    request_data = {
        "start_date": str(date.today() - timedelta(days=30)),
        "end_date": str(date.today()),
        "symbols": ["AAPL"],
        "filters": {}  # No filters specified
    }
    
    response = client.post("/api/v1/screen", json=request_data)
    
    assert response.status_code == 400
    assert "At least one filter must be specified" in response.json()["detail"]


def test_screen_invalid_date_range(client):
    """Test screening with invalid date range."""
    request_data = {
        "start_date": str(date.today()),
        "end_date": str(date.today() - timedelta(days=30)),  # End before start
        "symbols": ["AAPL"],
        "filters": {
            "volume": {"min_average": 1000000}
        }
    }
    
    response = client.post("/api/v1/screen", json=request_data)
    
    assert response.status_code == 422  # Validation error


def test_screen_volume_filter(client, mock_polygon_client):
    """Test screening with volume filter."""
    # Create mock stock data
    mock_stock_data = {
        "AAPL": StockData(
            symbol="AAPL",
            bars=[
                StockBar(
                    symbol="AAPL",
                    date=date.today() - timedelta(days=i),
                    open=150.0,
                    high=155.0,
                    low=149.0,
                    close=152.0,
                    volume=50000000,
                    vwap=151.5
                )
                for i in range(30)
            ]
        )
    }
    
    mock_polygon_client.fetch_batch_historical_data.return_value = mock_stock_data
    
    with patch('app.api.screener.get_polygon_client', return_value=mock_polygon_client):
        request_data = {
            "start_date": str(date.today() - timedelta(days=30)),
            "end_date": str(date.today()),
            "symbols": ["AAPL"],
            "filters": {
                "volume": {
                    "min_average": 10000000,
                    "lookback_days": 20
                }
            }
        }
        
        response = client.post("/api/v1/screen", json=request_data)
        
        assert response.status_code == 200
        data = response.json()
        assert data["total_symbols_screened"] == 1
        assert data["total_qualifying_stocks"] == 1
        assert len(data["results"]) == 1
        assert data["results"][0]["symbol"] == "AAPL"


def test_screen_combined_filters(client, mock_polygon_client):
    """Test screening with multiple filters."""
    # Create mock stock data with varying prices
    bars = []
    for i in range(60):
        base_price = 150.0 + (i * 0.5)  # Upward trend
        bars.append(
            StockBar(
                symbol="AAPL",
                date=date.today() - timedelta(days=59-i),
                open=base_price,
                high=base_price + 2,
                low=base_price - 1,
                close=base_price + 1,
                volume=50000000,
                vwap=base_price + 0.5
            )
        )
    
    mock_stock_data = {"AAPL": StockData(symbol="AAPL", bars=bars)}
    mock_polygon_client.fetch_batch_historical_data.return_value = mock_stock_data
    
    with patch('app.api.screener.get_polygon_client', return_value=mock_polygon_client):
        request_data = {
            "start_date": str(date.today() - timedelta(days=60)),
            "end_date": str(date.today()),
            "symbols": ["AAPL"],
            "filters": {
                "volume": {
                    "min_average": 10000000,
                    "lookback_days": 20
                },
                "price_change": {
                    "min_change": 0.0,
                    "max_change": 5.0,
                    "period_days": 1
                },
                "moving_average": {
                    "period": 20,
                    "condition": "above"
                }
            }
        }
        
        response = client.post("/api/v1/screen", json=request_data)
        
        assert response.status_code == 200
        data = response.json()
        assert "execution_time_ms" in data
        assert data["total_symbols_screened"] == 1


def test_screen_polygon_api_error(client, mock_polygon_client):
    """Test screening when Polygon API fails."""
    mock_polygon_client.fetch_batch_historical_data = AsyncMock(
        side_effect=PolygonAPIError("API rate limit exceeded", status_code=429)
    )
    
    with patch('app.api.screener.get_polygon_client', return_value=mock_polygon_client):
        request_data = {
            "start_date": str(date.today() - timedelta(days=30)),
            "end_date": str(date.today()),
            "symbols": ["AAPL"],
            "filters": {
                "volume": {"min_average": 1000000}
            }
        }
        
        response = client.post("/api/v1/screen", json=request_data)
        
        assert response.status_code == 503
        assert "External API error" in response.json()["error"]


def test_root_endpoint(client):
    """Test root endpoint."""
    response = client.get("/")
    
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Stock Screener"
    assert "endpoints" in data
    assert all(endpoint in data["endpoints"] for endpoint in ["health", "screen", "symbols", "filters"])