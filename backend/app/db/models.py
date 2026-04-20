import enum
from datetime import datetime

from sqlalchemy import Column, String, Text, Float, Integer, DateTime, Enum as SAEnum
from app.db.engine import Base


class RequirementStatus(str, enum.Enum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    UPLOADING = "uploading"
    PREPROCESSING = "preprocessing"
    TRANSCRIBING = "transcribing"
    ANALYZING = "analyzing"
    EXTRACTING = "extracting"
    GENERATING = "generating"
    SUCCESS = "success"
    FAILED = "failed"
    LOCKED = "locked"


class Requirement(Base):
    __tablename__ = "requirement"

    id = Column(String, primary_key=True)
    req_type = Column(String, nullable=False, default="网页自动化")
    title = Column(String, nullable=True)
    payload_json = Column(Text, nullable=True)
    creator = Column(String, nullable=True)
    status = Column(String, default=RequirementStatus.DRAFT.value)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Asset(Base):
    __tablename__ = "asset"

    id = Column(String, primary_key=True)
    requirement_id = Column(String, nullable=False)
    kind = Column(String, nullable=False)  # video/image/doc/glossary
    path = Column(String, nullable=False)
    original_name = Column(String, nullable=True)
    duration = Column(Float, nullable=True)
    fps = Column(Integer, nullable=True)
    width = Column(Integer, nullable=True)
    height = Column(Integer, nullable=True)


class TimelineStep(Base):
    __tablename__ = "timeline_step"

    id = Column(Integer, primary_key=True, autoincrement=True)
    requirement_id = Column(String, nullable=False)
    step_no = Column(Integer, nullable=False)
    ts_start = Column(Float, nullable=True)
    ts_end = Column(Float, nullable=True)
    action = Column(String, nullable=True)
    target_text = Column(Text, nullable=True)
    target_bbox = Column(Text, nullable=True)
    context_text = Column(Text, nullable=True)
    asr_text = Column(Text, nullable=True)
    screenshot_path = Column(String, nullable=True)
    edited_by_user = Column(Integer, default=0)


class Extraction(Base):
    __tablename__ = "extraction"

    requirement_id = Column(String, primary_key=True)
    business_overview = Column(Text, nullable=True)
    main_process = Column(Text, nullable=True)
    rules = Column(Text, nullable=True)
    io_spec = Column(Text, nullable=True)
    system_env = Column(Text, nullable=True)
    exceptions = Column(Text, nullable=True)
    model_name = Column(String, nullable=True)
    cost_tokens = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class SpecDoc(Base):
    __tablename__ = "spec_doc"

    id = Column(String, primary_key=True)
    requirement_id = Column(String, nullable=False)
    version = Column(Integer, default=1)
    path = Column(String, nullable=False)
    locked = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)


class LLMProvider(Base):
    __tablename__ = "llm_provider"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    api_key = Column(String, nullable=False)
    base_url = Column(String, nullable=False)
    model_name = Column(String, nullable=False)
    enabled = Column(Integer, default=1)
    created_at = Column(DateTime, default=datetime.utcnow)
