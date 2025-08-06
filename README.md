# Stock Screener

A modern, high-performance stock screening application built with Python/FastAPI backend and React/TypeScript frontend. Uses Polygon.io API for historical stock data and numpy for vectorized filtering operations.

## Features

- **Date Range Selection**: Screen stocks within specific date ranges
- **Multiple Filters**:
  - Volume filters (minimum average volume)
  - Price change filters (percentage change range)
  - Moving average filters (price above/below SMA)
- **High Performance**: Vectorized numpy operations for fast processing
- **Modern UI**: Clean interface built with shadcn/ui components
- **Export Functionality**: Download results as CSV
- **Responsive Design**: Works on desktop and mobile devices

## Architecture

- **Backend**: FastAPI with async support
- **Frontend**: React with TypeScript and Vite
- **Data Source**: Polygon.io API
- **Processing**: NumPy for vectorized calculations
- **UI Components**: shadcn/ui with Tailwind CSS

## Prerequisites

- Python 3.11+
- Node.js 18+
- Polygon.io API key

## Installation

### Backend Setup

1. Navigate to the backend directory:
```bash
cd backend
```

2. Create a `.env` file from the example:
```bash
cp .env.example .env
```

3. Edit `.env` and add your Polygon.io API key:
```
POLYGON_API_KEY=your_polygon_api_key_here
```

4. Install Python dependencies:
```bash
python3 -m pip install --user --break-system-packages -r requirements.txt
```

Or with a virtual environment (recommended):
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Frontend Setup

1. Navigate to the frontend directory:
```bash
cd frontend
```

2. Install dependencies:
```bash
npm install
```

## Running the Application

### Quick Start (Recommended)

Start both backend and frontend with a single command:

```bash
# Using the start script
./start.sh

# Or using Python
python3 start.py

# Or using Make
make start
```

Both services will be accessible from local and public IPs:
- **Frontend**: 
  - Local: http://localhost:5173
  - Public: http://YOUR_PUBLIC_IP:5173
- **Backend API**: 
  - Local: http://localhost:8000
  - Public: http://YOUR_PUBLIC_IP:8000
- **API Docs**: http://YOUR_PUBLIC_IP:8000/docs

### Manual Start

If you prefer to run services separately:

#### Start the Backend

```bash
cd backend
python3 run.py
```

The backend will start on `http://localhost:8000`. You can view the API documentation at `http://localhost:8000/docs`.

#### Start the Frontend

```bash
cd frontend
npm run dev
```

The frontend will start on `http://localhost:5173`.

### Available Commands

```bash
make help     # Show all available commands
make install  # Install all dependencies
make start    # Start both services
make stop     # Stop all services
make backend  # Start only backend
make frontend # Start only frontend
make test     # Run tests
make clean    # Clean cache files
```

## Usage

1. **Select Date Range**: Choose start and end dates for your screening period
2. **Configure Filters**:
   - **Volume Filter**: Set minimum average volume (e.g., 1M shares)
   - **Price Change Filter**: Set min/max percentage change
   - **Moving Average Filter**: Choose period (e.g., 20, 50, 200 days) and condition
3. **Run Screen**: Click "Run Screen" to fetch and filter stocks
4. **View Results**: See qualifying stocks with metrics in the sortable table
5. **Export Data**: Click "Export CSV" to download results

## API Endpoints

- `POST /api/v1/screen` - Main screening endpoint
- `GET /api/v1/symbols` - Get available stock symbols
- `GET /api/v1/filters` - Get filter documentation
- `GET /api/v1/health` - Health check

## Project Structure

```
TheUltimate/
├── backend/
│   ├── app/
│   │   ├── api/          # API endpoints
│   │   ├── core/         # Core filters and logic
│   │   ├── models/       # Data models
│   │   ├── services/     # Business logic
│   │   ├── config.py     # Configuration
│   │   └── main.py       # FastAPI app
│   ├── requirements.txt
│   └── run.py
├── frontend/
│   ├── src/
│   │   ├── components/   # React components
│   │   ├── services/     # API services
│   │   ├── types/        # TypeScript types
│   │   └── App.tsx       # Main app component
│   ├── package.json
│   └── vite.config.ts
└── README.md
```

## Performance

The screener uses vectorized numpy operations for optimal performance:
- Processes thousands of data points in milliseconds
- Efficient memory usage with structured arrays
- Parallel processing for multiple stocks

## Development

### Backend Testing

```bash
cd backend
pytest
```

### Frontend Development

```bash
cd frontend
npm run dev    # Development server
npm run build  # Production build
npm run lint   # Run linter
```

## Configuration

### Backend Configuration

Edit `backend/.env`:
- `POLYGON_API_KEY`: Your Polygon.io API key
- `CORS_ORIGINS`: Allowed frontend origins

### Frontend Configuration

The API URL is configured in `frontend/src/services/api.ts`.

## Troubleshooting

1. **API Key Issues**: Ensure your Polygon.io API key is valid and has the necessary permissions
2. **CORS Errors**: Check that the frontend URL is in `CORS_ORIGINS` in backend configuration
3. **Rate Limiting**: The free Polygon.io tier has rate limits; the app handles this automatically
4. **Missing Dependencies**: Run `pip install -r requirements.txt` or `npm install` as needed

## License

This project is open source and available under the MIT License.