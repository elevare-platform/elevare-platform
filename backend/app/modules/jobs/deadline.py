"""Whether a job can still be applied to, as far as its application deadline goes.

``ApplicationService.apply_to_job`` turns an application away once the deadline has passed, but
the job itself stays ACTIVE (nothing closes it). A list that offers jobs to candidates leaves
those out with this condition, so a candidate is not shown a job they cannot apply to.
"""

from sqlalchemy import ColumnElement, func, or_

from app.modules.jobs.models import Job


def deadline_not_passed() -> ColumnElement[bool]:
    """Jobs with no deadline, or whose deadline is not yet in the past."""
    return or_(Job.application_deadline.is_(None), Job.application_deadline >= func.now())
