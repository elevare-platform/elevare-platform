"""Add interview_strict_runs and interview_turns: the state of a strict, text-question interview

Revision ID: p22_0030
Revises: p22_0029

``interview_strict_runs`` has one row per interview that uses the strict style (the style is
decided when the invite is created; an interview with no row here is the existing live
interview). It holds the rules the candidate accepted (version and time) and a copy of the
job's questions taken when the interview starts, so editing the job's list later never
changes an interview that has begun. ``interview_turns`` has one row per question or
follow-up the candidate was shown, with the time it was shown and the text of the answer.

Safe on the live database: two brand-new tables and no change to ``interviews``. That is
deliberate: a new column on ``interviews`` would break every interview query between the
new containers starting and this migration finishing. The old code never looks at either
table. (docs/08_DECISIONS.md, "The new strict, text-only AI interview", item 24.)
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "p22_0030"
down_revision: str | None = "p22_0029"
branch_labels = None
depends_on = None


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    ]


def upgrade() -> None:
    op.create_table(
        "interview_strict_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        *_timestamps(),
        sa.Column(
            "interview_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("interviews.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("rules_version", sa.String(20), nullable=True),
        sa.Column("rules_accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("questions", postgresql.JSONB(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        # How many earlier recordings (kept by the browser across a reload) were uploaded as
        # separate parts. The server joins them with the final recording into one video
        # before scoring, then sets this back to 0.
        sa.Column("recording_parts", sa.Integer(), nullable=False, server_default="0"),
        # Which try this is. An employer reinstating an interview that ended starts the next
        # one; the leave count and the time away are counted per attempt.
        sa.Column("attempt", sa.Integer(), nullable=False, server_default="1"),
        # The last time the candidate's screen was heard from (a heartbeat every 15 seconds),
        # so a reload is timed from when the page was last seen.
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        # Set while the candidate is away from the interview screen: when it began and why.
        sa.Column("away_since", sa.DateTime(timezone=True), nullable=True),
        sa.Column("away_kind", sa.String(20), nullable=True),
        # When the interview was ended or stopped, and why. Cleared when it is reinstated.
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("end_reason", sa.String(20), nullable=True),
        # Set when an employer reinstates an interview: the moment its clock stopped. The clock
        # starts again when the candidate next opens the link, which moves the interview's
        # start and the open question forward by the time in between. Cleared then.
        sa.Column("paused_at", sa.DateTime(timezone=True), nullable=True),
        # The final recordings of earlier attempts (storage keys, oldest first), joined in front
        # of the latest one when the interview finishes.
        sa.Column("previous_recordings", postgresql.JSONB(), nullable=True),
        sa.UniqueConstraint("interview_id", name="uq_interview_strict_runs_interview"),
    )

    op.create_table(
        "interview_turns",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        *_timestamps(),
        sa.Column(
            "interview_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("interviews.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(10), nullable=False),
        sa.Column("question_number", sa.Integer(), nullable=False),
        sa.Column("question_text", sa.Text(), nullable=False),
        sa.Column("time_limit_seconds", sa.Integer(), nullable=False),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("answered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("answer_text", sa.Text(), nullable=True),
        sa.Column("answer_seconds", sa.Float(), nullable=True),
        sa.UniqueConstraint("interview_id", "position", name="uq_interview_turns_position"),
    )
    op.create_index("ix_interview_turns_interview_id", "interview_turns", ["interview_id"])

    # The timeline of a strict interview: every leave, reload, key press, stop, ending and
    # reinstatement, with the time the SERVER saw it, so the employer can check each against
    # the recording. Kept after the interview, with the recording.
    op.create_table(
        "interview_conduct_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        *_timestamps(),
        sa.Column(
            "interview_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("interviews.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("attempt", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("detail", sa.String(40), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("duration_seconds", sa.Float(), nullable=True),
        # Whether it counts towards ending the interview (a key press never does).
        sa.Column("counted", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_index(
        "ix_interview_conduct_events_interview_id", "interview_conduct_events", ["interview_id"]
    )


def downgrade() -> None:
    op.drop_index(
        "ix_interview_conduct_events_interview_id", table_name="interview_conduct_events"
    )
    op.drop_table("interview_conduct_events")
    op.drop_index("ix_interview_turns_interview_id", table_name="interview_turns")
    op.drop_table("interview_turns")
    op.drop_table("interview_strict_runs")
