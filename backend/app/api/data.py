"""API endpoints for data ingestion jobs."""

from fastapi import APIRouter, HTTPException

from ..models.backtest import BacktestRunInfo
from ..models.ingestion import DataIngestionRequest
from ..services.lean_job_service import lean_job_service

router = APIRouter(prefix="/api/v2/data", tags=["data"])


@router.post("/ingest", response_model=BacktestRunInfo)
async def start_data_ingestion(request: DataIngestionRequest) -> BacktestRunInfo:
    try:
        return await lean_job_service.submit_data_job(request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail="Failed to queue ingestion job") from exc
