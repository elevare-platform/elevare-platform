"""Request and response shapes for the rescore endpoints."""

import uuid

from pydantic import BaseModel, model_validator


class RescoreStatus(BaseModel):
    """How many of a job's candidates have no usable score and could be rescored."""

    applications: int
    pipeline: int
    total: int


class RescoreRequest(BaseModel):
    """Rescore one candidate, or (with neither id) everyone on the job that needs it."""

    application_id: uuid.UUID | None = None
    talent_pool_profile_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def _one_at_most(self):
        if self.application_id and self.talent_pool_profile_id:
            raise ValueError("Send an application_id or a talent_pool_profile_id, not both")
        return self


class RescoreResult(BaseModel):
    """What one press of Rescore did.

    ``reparsing``: the CV could not be read, so it is being read again from the stored
    file and scored when that finishes. ``scoring``: the CV was readable, so it was only
    scored again. ``in_progress``: the CV is still being read, nothing to do yet.
    ``no_stored_file``: the CV could not be read and there is no stored file to read
    again, so it needs a new upload. ``remaining``: still waiting after this press
    (at most one batch is started at a time).
    """

    scoring: int
    reparsing: int
    in_progress: int
    no_stored_file: int
    remaining: int
