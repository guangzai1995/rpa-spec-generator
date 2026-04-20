from datetime import datetime
from typing import Optional, List, Dict, Any

from pydantic import BaseModel, Field


# ========== 需求表单 ==========
class RequirementCreate(BaseModel):
    req_type: str = Field(default="网页自动化", description="业务类型")
    title: Optional[str] = Field(default=None, description="需求标题")
    req_dept: Optional[str] = Field(default=None, description="需求部门")
    req_owner: Optional[str] = Field(default=None, description="需求提出人")
    target_url: Optional[str] = Field(default=None, description="目标系统URL")
    login_required: Optional[bool] = Field(default=False, description="是否需要登录")
    exec_frequency: Optional[str] = Field(default=None, description="执行频率")
    input_source: Optional[str] = Field(default=None, description="输入数据来源")
    output_sink: Optional[str] = Field(default=None, description="输出结果去向")
    exception_policy: Optional[List[str]] = Field(default=None, description="异常处理策略")
    glossary: Optional[List[str]] = Field(default=None, description="业务术语词库")


class RequirementUpdate(BaseModel):
    title: Optional[str] = None
    req_type: Optional[str] = None
    payload_json: Optional[str] = None


class RequirementResponse(BaseModel):
    id: str
    req_type: str
    title: Optional[str]
    status: str
    error_message: Optional[str]
    created_at: Optional[str]
    updated_at: Optional[str]

    class Config:
        from_attributes = True


# ========== 解析步骤 ==========
class TimelineStepSchema(BaseModel):
    step_no: int
    ts_start: Optional[float] = None
    ts_end: Optional[float] = None
    action: Optional[str] = None
    target_text: Optional[str] = None
    context_text: Optional[str] = None
    asr_text: Optional[str] = None
    screenshot_path: Optional[str] = None


class TimelineStepUpdate(BaseModel):
    action: Optional[str] = None
    target_text: Optional[str] = None
    context_text: Optional[str] = None


# ========== 结构化拆解 ==========
class BusinessOverview(BaseModel):
    auto_goal: str = ""
    scope: str = ""


class ProcessStep(BaseModel):
    no: int
    action: str
    target: str
    value: Optional[str] = None
    result_file: Optional[str] = None


class MainProcess(BaseModel):
    name: str
    steps: List[ProcessStep]


class IOSpec(BaseModel):
    input: List[str] = []
    output: List[str] = []


class SystemEnv(BaseModel):
    name: str
    auth: Optional[str] = None
    browser: Optional[str] = None


class ExceptionItem(BaseModel):
    code: str
    handler: str


class ExtractionResult(BaseModel):
    business_overview: BusinessOverview = BusinessOverview()
    main_process: List[MainProcess] = []
    rules: List[str] = []
    io_spec: IOSpec = IOSpec()
    system_env: List[SystemEnv] = []
    exceptions: List[ExceptionItem] = []


# ========== 任务状态 ==========
class TaskStatusResponse(BaseModel):
    requirement_id: str
    status: str
    message: Optional[str] = None
    progress: Optional[int] = None


# ========== LLM Provider ==========
class LLMProviderCreate(BaseModel):
    name: str
    api_key: str
    base_url: str
    model_name: str


class LLMProviderResponse(BaseModel):
    id: str
    name: str
    base_url: str
    model_name: str
    enabled: int

    class Config:
        from_attributes = True
