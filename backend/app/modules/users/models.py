from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import UUID, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import BaseModel

from .enums import AccountStatus, UserRole

if TYPE_CHECKING:
    from app.modules.auth.models import RefreshToken


class User(BaseModel):
    __tablename__ = "users"

    first_name: Mapped[str] = mapped_column(
        String(30),
        nullable=False
    )
    last_name: Mapped[str] = mapped_column(
        String(30),
        nullable=False
    )
    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True
    )
    phone_number: Mapped[str] = mapped_column(
        String(15),
        unique=True,
        nullable=True,
        index=True
    )
    password_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )
    account_status: Mapped[AccountStatus] = mapped_column(
        String(20),
        nullable=False,
        default=AccountStatus.ACTIVE.value,
        server_default=AccountStatus.ACTIVE.value
    )
    role: Mapped[UserRole] = mapped_column(
        String(20),
        nullable=False,
        default=UserRole.GUEST.value,
        server_default=UserRole.GUEST.value
    )
    last_login_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )


    # Relationships
    profile: Mapped[UserProfile] = relationship(
        "UserProfile",
        back_populates="user",
        uselist=False
    )
    refresh_tokens: Mapped[list[RefreshToken]] = relationship(
        "RefreshToken",
        back_populates="user",
    )


class UserProfile(BaseModel):
    __tablename__ = "user_profiles"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True
    )
    avatar_url: Mapped[str] = mapped_column(
        String(255),
        nullable=True,
    )
    city: Mapped[str] = mapped_column(String(255), nullable=True)
    state: Mapped[str] = mapped_column(String(255), nullable=True)

    # relationships
    user: Mapped[User] = relationship(
        "User",
        back_populates="profile"
    )

