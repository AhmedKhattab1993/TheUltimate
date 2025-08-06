# Stock Screener Application Architecture

## Executive Summary

This document outlines the architecture for a high-performance stock screener application that fetches historical data from Polygon API, processes it using vectorized operations, and presents results through a modern React frontend. The architecture emphasizes separation of concerns, scalability, and performance optimization through numpy-based computations.

## System Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        React Frontend                           │
│                      (shadcn/ui + Vite)                        │
└───────────────────────┬─────────────────────────┬──────────────┘
                        │ REST API               │ WebSocket
                        ▼                        ▼
┌─────────────────────────────────────────────────────────────────┐
│                     FastAPI Backend                             │
│  ┌─────────────┐  ┌──────────────┐  ┌───────────────────┐    │
│  │   API       │  │   Screener   │  │    WebSocket      │    │
│  │  Handlers   │  │   Engine     │  │    Manager        │    │
│  └──────┬──────┘  └──────┬───────┘  └───────────────────┘    │
│         │                 │                                     │
│  ┌──────▼──────┐  ┌──────▼───────┐  ┌───────────────────┐    │
│  │   Service   │  │   Filter     │  │   Background      │    │
│  │   Layer     │  │   Engine     │  │   Workers         │    │
│  └──────┬──────┘  └──────────────┘  └───────────────────┘    │
│         │                                                       │
│  ┌──────▼──────────────────────────────────────────────┐      │
│  │              Data Access Layer                       │      │
│  │  ┌────────┐  ┌────────────┐  ┌─────────────────┐  │      │
│  │  │ Polygon│  │   Cache    │  │    Database     │  │      │
│  │  │  Client│  │  Manager   │  │   Repository    │  │      │
│  │  └────────┘  └────────────┘  └─────────────────┘  │      │
│  └──────────────────────────────────────────────────────┘      │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
                    ┌───────────────────────┐
                    │    PostgreSQL DB      │
                    │  ┌─────────────────┐ │
                    │  │ Timeseries Data │ │
                    │  └─────────────────┘ │
                    └───────────────────────┘
```

## Technology Stack

### Backend
- **Language**: Python 3.11+
- **Framework**: FastAPI (async support, high performance)
- **Data Processing**: NumPy, Pandas (for initial data preparation)
- **Database**: PostgreSQL with TimescaleDB extension
- **Cache**: Redis (for API response caching)
- **Task Queue**: Celery with Redis broker
- **API Client**: httpx (async HTTP client)
- **Data Validation**: Pydantic
- **Testing**: pytest, pytest-asyncio

### Frontend
- **Framework**: React 18 with TypeScript
- **Build Tool**: Vite
- **UI Library**: shadcn/ui (Radix UI + Tailwind CSS)
- **State Management**: Zustand
- **Data Fetching**: TanStack Query (React Query)
- **Charts**: Recharts or Lightweight Charts
- **Forms**: React Hook Form + Zod
- **Date Handling**: date-fns

### Infrastructure
- **Container**: Docker & Docker Compose
- **Reverse Proxy**: Nginx
- **Monitoring**: Prometheus + Grafana
- **Logging**: Structured logging with JSON format

## Project Structure

```
stock-screener/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                 # FastAPI app initialization
│   │   ├── config.py               # Configuration management
│   │   ├── dependencies.py         # Dependency injection
│   │   │
│   │   ├── api/                    # API layer
│   │   │   ├── __init__.py
│   │   │   ├── v1/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── endpoints/
│   │   │   │   │   ├── screener.py
│   │   │   │   │   ├── stocks.py
│   │   │   │   │   ├── filters.py
│   │   │   │   │   └── websocket.py
│   │   │   │   └── dependencies.py
│   │   │   └── middleware/
│   │   │       ├── auth.py
│   │   │       └── rate_limit.py
│   │   │
│   │   ├── core/                   # Core business logic
│   │   │   ├── __init__.py
│   │   │   ├── screener/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── engine.py      # Main screener engine
│   │   │   │   ├── filters/       # Filter implementations
│   │   │   │   │   ├── base.py
│   │   │   │   │   ├── price.py
│   │   │   │   │   ├── volume.py
│   │   │   │   │   ├── technical.py
│   │   │   │   │   └── composite.py
│   │   │   │   └── matrix_ops.py  # Vectorized operations
│   │   │   └── models/
│   │   │       ├── __init__.py
│   │   │       ├── stock.py
│   │   │       ├── screening.py
│   │   │       └── filter.py
│   │   │
│   │   ├── services/               # Service layer
│   │   │   ├── __init__.py
│   │   │   ├── stock_service.py
│   │   │   ├── screening_service.py
│   │   │   └── cache_service.py
│   │   │
│   │   ├── data/                   # Data access layer
│   │   │   ├── __init__.py
│   │   │   ├── polygon/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── client.py      # Polygon API client
│   │   │   │   ├── models.py      # API response models
│   │   │   │   └── mapper.py      # Data transformation
│   │   │   ├── database/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── connection.py
│   │   │   │   ├── repositories/
│   │   │   │   │   ├── base.py
│   │   │   │   │   ├── stock.py
│   │   │   │   │   └── screening.py
│   │   │   │   └── models.py      # SQLAlchemy models
│   │   │   └── cache/
│   │   │       ├── __init__.py
│   │   │       ├── redis_client.py
│   │   │       └── strategies.py
│   │   │
│   │   ├── workers/                # Background tasks
│   │   │   ├── __init__.py
│   │   │   ├── celery_app.py
│   │   │   ├── tasks/
│   │   │   │   ├── data_sync.py
│   │   │   │   └── cache_warm.py
│   │   │   └── schedulers.py
│   │   │
│   │   └── utils/
│   │       ├── __init__.py
│   │       ├── logging.py
│   │       ├── exceptions.py
│   │       └── validators.py
│   │
│   ├── tests/
│   ├── alembic/                    # Database migrations
│   ├── requirements.txt
│   └── Dockerfile
│
├── frontend/
│   ├── src/
│   │   ├── main.tsx
│   │   ├── App.tsx
│   │   ├── components/
│   │   │   ├── ui/                # shadcn/ui components
│   │   │   ├── screener/
│   │   │   │   ├── ScreenerForm.tsx
│   │   │   │   ├── FilterBuilder.tsx
│   │   │   │   ├── ResultsTable.tsx
│   │   │   │   └── StockChart.tsx
│   │   │   └── layout/
│   │   │       ├── Header.tsx
│   │   │       └── Layout.tsx
│   │   ├── hooks/
│   │   │   ├── useScreener.ts
│   │   │   ├── useStockData.ts
│   │   │   └── useWebSocket.ts
│   │   ├── services/
│   │   │   ├── api.ts
│   │   │   └── websocket.ts
│   │   ├── store/
│   │   │   ├── screenerStore.ts
│   │   │   └── uiStore.ts
│   │   ├── types/
│   │   │   └── index.ts
│   │   └── utils/
│   │       ├── formatters.ts
│   │       └── validators.ts
│   ├── public/
│   ├── package.json
│   ├── tsconfig.json
│   ├── vite.config.ts
│   └── Dockerfile
│
├── docker-compose.yml
├── nginx.conf
└── README.md
```

## Backend Architecture Details

### 1. Data Access Layer

#### Polygon Client
```python
# Async client with rate limiting and retry logic
class PolygonClient:
    - fetch_historical_data(symbols, start_date, end_date)
    - fetch_aggregates(symbol, timespan, from_date, to_date)
    - batch_fetch_stocks(symbols, date_range)
```

#### Cache Strategy
- **L1 Cache**: In-memory LRU cache for hot data
- **L2 Cache**: Redis for distributed caching
- Cache key pattern: `stock:{symbol}:{date}:{timespan}`
- TTL: 24 hours for historical data, 5 minutes for recent data

#### Database Schema
```sql
-- TimescaleDB hypertable for efficient time-series queries
CREATE TABLE stock_data (
    time        TIMESTAMPTZ NOT NULL,
    symbol      VARCHAR(10) NOT NULL,
    open        DECIMAL(10,2),
    high        DECIMAL(10,2),
    low         DECIMAL(10,2),
    close       DECIMAL(10,2),
    volume      BIGINT,
    vwap        DECIMAL(10,4),
    PRIMARY KEY (time, symbol)
);

-- Convert to hypertable
SELECT create_hypertable('stock_data', 'time');

-- Indexes for common queries
CREATE INDEX idx_symbol_time ON stock_data (symbol, time DESC);
CREATE INDEX idx_volume ON stock_data (volume);
```

### 2. Screener Engine

#### Matrix Operations Module
```python
class MatrixOperations:
    def __init__(self, data: np.ndarray):
        self.data = data  # Shape: (n_stocks, n_days, n_features)
    
    def calculate_moving_average(self, window: int) -> np.ndarray:
        # Vectorized MA calculation
        
    def calculate_price_change(self) -> np.ndarray:
        # Vectorized percentage change
        
    def apply_filters(self, filters: List[Filter]) -> np.ndarray:
        # Return boolean mask for qualifying stocks
```

#### Filter Architecture
```python
# Base filter interface
class BaseFilter(ABC):
    @abstractmethod
    def apply(self, data: np.ndarray) -> np.ndarray:
        pass

# Composite pattern for complex filters
class CompositeFilter(BaseFilter):
    def __init__(self, operator: str = 'AND'):
        self.filters: List[BaseFilter] = []
        self.operator = operator
```

### 3. Service Layer

#### Screening Service
```python
class ScreeningService:
    async def run_screening(
        self,
        symbols: List[str],
        date_range: DateRange,
        filters: List[FilterConfig]
    ) -> ScreeningResult:
        # 1. Fetch data (check cache first)
        # 2. Convert to numpy arrays
        # 3. Apply filters using vectorized operations
        # 4. Return results with metadata
```

## API Design

### REST Endpoints

```yaml
# Screening endpoints
POST   /api/v1/screener/run
GET    /api/v1/screener/results/{screening_id}
GET    /api/v1/screener/filters
POST   /api/v1/screener/filters/validate

# Stock data endpoints
GET    /api/v1/stocks
GET    /api/v1/stocks/{symbol}
GET    /api/v1/stocks/{symbol}/history

# WebSocket endpoint
WS     /ws/screener/live
```

### Request/Response Models

```python
# Screening request
class ScreeningRequest(BaseModel):
    symbols: List[str] | None  # None = all stocks
    date_range: DateRange
    filters: List[FilterConfig]
    output_format: Literal["daily", "aggregated"]

# Filter configuration
class FilterConfig(BaseModel):
    type: FilterType
    field: str
    operator: ComparisonOperator
    value: float | List[float]
    params: dict | None

# Screening result
class ScreeningResult(BaseModel):
    screening_id: str
    request: ScreeningRequest
    results: List[DailyResult]
    metadata: ScreeningMetadata
```

## Frontend Architecture

### Component Hierarchy

```
App
├── Layout
│   ├── Header
│   └── MainContent
│       ├── ScreenerDashboard
│       │   ├── FilterPanel
│       │   │   ├── DateRangePicker
│       │   │   ├── SymbolSelector
│       │   │   └── FilterBuilder
│       │   │       └── FilterRow
│       │   ├── ResultsPanel
│       │   │   ├── ResultsTable
│       │   │   ├── ResultsChart
│       │   │   └── ExportOptions
│       │   └── ScreenerControls
│       └── StockDetail (modal/drawer)
```

### State Management

```typescript
// Zustand store structure
interface ScreenerStore {
  // State
  filters: Filter[]
  dateRange: DateRange
  symbols: string[]
  results: ScreeningResult | null
  loading: boolean
  
  // Actions
  addFilter: (filter: Filter) => void
  removeFilter: (id: string) => void
  runScreening: () => Promise<void>
  exportResults: (format: ExportFormat) => void
}
```

## Data Flow

### Screening Process Flow

1. **User Input**: User configures filters and date range in UI
2. **API Request**: Frontend sends screening request to backend
3. **Data Fetching**: 
   - Check cache for requested data
   - Fetch missing data from Polygon API
   - Store in cache and database
4. **Processing**:
   - Load data into numpy arrays
   - Apply filters using vectorized operations
   - Generate results matrix
5. **Response**: Return filtered results to frontend
6. **Display**: Render results in table/chart format

### Real-time Updates (Future)

1. WebSocket connection established on page load
2. Subscribe to relevant stock symbols
3. Receive real-time price updates
4. Update screening results dynamically

## Performance Optimizations

### Backend Optimizations

1. **Vectorized Operations**: All filtering done using numpy broadcasting
2. **Parallel Processing**: Use asyncio for concurrent API calls
3. **Batch Processing**: Process multiple symbols in single operation
4. **Memory Management**: Use memory-mapped files for large datasets
5. **Query Optimization**: Proper indexing and partitioning in TimescaleDB

### Frontend Optimizations

1. **Virtual Scrolling**: For large result sets
2. **Memoization**: Cache expensive calculations
3. **Lazy Loading**: Load data as needed
4. **Web Workers**: Offload heavy computations
5. **React.memo**: Prevent unnecessary re-renders

## Scalability Considerations

### Horizontal Scaling

1. **Stateless API servers**: Easy to add more instances
2. **Read replicas**: For database queries
3. **Distributed cache**: Redis cluster
4. **Load balancing**: Nginx upstream configuration
5. **Message queue**: For background tasks

### Data Partitioning

1. **Time-based partitioning**: Monthly partitions in TimescaleDB
2. **Symbol-based sharding**: For extreme scale
3. **Cache partitioning**: Separate cache instances by data type

## Security Considerations

1. **API Authentication**: JWT tokens
2. **Rate Limiting**: Per-user and per-IP limits
3. **Input Validation**: Strict validation of all inputs
4. **SQL Injection Prevention**: Use parameterized queries
5. **CORS Configuration**: Whitelist allowed origins

## Monitoring and Observability

1. **Metrics**: Prometheus metrics for API latency, cache hit rates
2. **Logging**: Structured JSON logs with correlation IDs
3. **Tracing**: OpenTelemetry for distributed tracing
4. **Health Checks**: Readiness and liveness probes
5. **Alerting**: Alert on high latency, error rates

## Development Workflow

1. **Local Development**: Docker Compose for all services
2. **Testing**: Unit tests, integration tests, E2E tests
3. **CI/CD**: GitHub Actions for automated testing and deployment
4. **Documentation**: OpenAPI spec for API, Storybook for UI components
5. **Code Quality**: Pre-commit hooks, linting, type checking

## Future Enhancements

1. **Real-time Data**: WebSocket integration for live updates
2. **Advanced Filters**: Custom formula support, ML-based filters
3. **Backtesting**: Test screening strategies on historical data
4. **Alert System**: Notify users when stocks meet criteria
5. **Portfolio Integration**: Track screening results over time
6. **AI Insights**: Natural language filter creation

## Key Architectural Decisions

### Decision 1: NumPy for Data Processing
**Rationale**: NumPy provides the fastest vectorized operations for numerical data in Python. The broadcasting capabilities allow us to apply filters across thousands of stocks simultaneously.
**Alternative Considered**: Pandas - rejected due to higher memory overhead and slower performance for pure numerical operations.

### Decision 2: FastAPI over Django/Flask
**Rationale**: FastAPI provides native async support, automatic API documentation, and better performance. The built-in validation with Pydantic reduces boilerplate code.
**Alternative Considered**: Django REST Framework - rejected due to unnecessary ORM overhead and synchronous nature.

### Decision 3: PostgreSQL with TimescaleDB
**Rationale**: TimescaleDB provides excellent time-series query performance while maintaining PostgreSQL compatibility. Automatic partitioning and compression reduce storage costs.
**Alternative Considered**: InfluxDB - rejected due to limited query capabilities and ecosystem.

### Decision 4: React with shadcn/ui
**Rationale**: shadcn/ui provides modern, accessible components without vendor lock-in. The copy-paste approach allows full customization while maintaining consistency.
**Alternative Considered**: Material-UI - rejected due to bundle size and opinionated styling.

### Decision 5: Microservices vs Modular Monolith
**Decision**: Modular monolith initially, with clear service boundaries for future extraction.
**Rationale**: Reduces operational complexity while maintaining clean architecture. Easy to extract services later if needed.

## Implementation Roadmap

### Phase 1: Core Infrastructure (Week 1-2)
- Set up project structure
- Configure Docker environment
- Implement basic FastAPI app
- Set up PostgreSQL with TimescaleDB
- Create React app with shadcn/ui

### Phase 2: Data Layer (Week 3-4)
- Implement Polygon API client
- Design and implement database schema
- Build caching layer
- Create data access repositories

### Phase 3: Screening Engine (Week 5-6)
- Implement numpy-based matrix operations
- Build filter system
- Create screening service
- Add unit tests for core logic

### Phase 4: API Layer (Week 7)
- Implement REST endpoints
- Add request validation
- Create API documentation
- Implement error handling

### Phase 5: Frontend Basic (Week 8-9)
- Build component structure
- Implement filter builder UI
- Create results table
- Add basic charting

### Phase 6: Integration (Week 10)
- End-to-end testing
- Performance optimization
- Docker deployment setup
- Documentation

### Phase 7: Advanced Features (Week 11-12)
- Add more filter types
- Implement result export
- Add user preferences
- Performance monitoring

## Conclusion

This architecture provides a solid foundation for a high-performance stock screener that can handle large-scale data processing while maintaining clean separation of concerns. The modular design allows for easy extension and scaling as requirements grow.