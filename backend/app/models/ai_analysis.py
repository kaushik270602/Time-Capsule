from sqlalchemy import Column, Integer, String, Float, Text, DateTime, ForeignKey, JSON, CheckConstraint
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.models.base import Base


class AIAnalysis(Base):
    __tablename__ = "ai_analysis"

    id = Column(Integer, primary_key=True, index=True)
    capsule_id = Column(Integer, ForeignKey("capsules.id", ondelete="CASCADE"), nullable=False, index=True)
    summary = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # New fields
    sentiment_label = Column(String(20), nullable=True)
    sentiment_confidence = Column(Float, nullable=True)
    tone_description = Column(Text, nullable=True)
    image_analyses = Column(JSON, nullable=True)
    video_summaries = Column(JSON, nullable=True)
    recap_text = Column(Text, nullable=True)
    processing_status = Column(String(20), nullable=False, default="pending")
    error_message = Column(Text, nullable=True)

    __table_args__ = (
        CheckConstraint(
            "processing_status IN ('pending', 'processing', 'completed', 'failed')",
            name="check_processing_status",
        ),
    )

    # Relationships
    capsule = relationship("Capsule", back_populates="ai_analysis")
