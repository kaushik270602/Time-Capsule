from sqlalchemy import Column, Index, Integer, String, Text, DateTime, Boolean, ForeignKey, CheckConstraint, JSON
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.models.base import Base


class Capsule(Base):
    __tablename__ = "capsules"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    text_content = Column(Text, nullable=True)
    media_urls = Column(JSON, default=list, nullable=False)
    transcriptions = Column(JSON, default=list, nullable=False)
    unlock_date = Column(DateTime(timezone=True), nullable=False, index=True)
    timezone = Column(String(64), nullable=False, default="UTC")
    status = Column(String(20), nullable=False, default="locked", index=True)
    is_public = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Constraints and composite indexes
    __table_args__ = (
        CheckConstraint("status IN ('locked', 'unlocked')", name="check_status"),
        CheckConstraint("unlock_date > created_at", name="check_future_unlock_date"),
        Index("idx_capsules_public_unlocked", "is_public", "status", "unlock_date"),
        Index("idx_capsules_timezone", "timezone"),
    )

    # Relationships
    user = relationship("User", back_populates="capsules")
    unlock_log = relationship("UnlockLog", back_populates="capsule", uselist=False, cascade="all, delete-orphan")
    ai_analysis = relationship("AIAnalysis", back_populates="capsule", uselist=False, cascade="all, delete-orphan")
    notifications = relationship("Notification", back_populates="capsule", cascade="all, delete-orphan")
