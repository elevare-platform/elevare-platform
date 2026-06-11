from pydantic import BaseModel
from datetime import datetime
import uuid


class MatchResult(BaseModel):
    score: int
    matched_keywords: list[str]
    total_job_keywords: int
    computed_at: datetime


class MatchRequest(BaseModel):
    candidate_id: uuid.UUID
    job_id: uuid.UUID
