from __future__ import annotations

from typing import TYPE_CHECKING
import uuid

from sqlalchemy import UUID, String, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import BaseModel

if TYPE_CHECKING:
    from app.modules.users.models import EmployerProfile


class KYCDocument(BaseModel):
    __tablename__ = "employer_kyc_documents"

    employer_profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("employer_profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    key: Mapped[str] = mapped_column(Text)
    filename: Mapped[str] = mapped_column(String(255))
    document_type: Mapped[str] = mapped_column(String(50), nullable=False)

    # Relationships
    employer_profile: Mapped["EmployerProfile"] = relationship(
        "EmployerProfile",
        back_populates="kyc_documents",
    )
