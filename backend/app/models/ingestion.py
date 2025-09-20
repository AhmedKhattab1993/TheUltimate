"""Models for data ingestion jobs."""

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, FieldValidationInfo, field_validator


class DataIngestionRequest(BaseModel):
    """Request to ingest historical market data."""

    dataset: Literal['minute'] = Field(
        'minute', description='Dataset identifier (currently only minute supported)'
    )
    start_date: date = Field(..., description='Start date for ingestion window')
    end_date: date = Field(..., description='End date for ingestion window')
    resume: bool = Field(False, description='Resume from last checkpoint if available')

    @field_validator('end_date')
    @classmethod
    def validate_range(cls, value: date, info: FieldValidationInfo) -> date:
        start = info.data.get('start_date')
        if start and value < start:
            raise ValueError('end_date must be on or after start_date')
        return value
