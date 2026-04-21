from datetime import datetime
from typing import Optional, List, Dict, Any

from pydantic import BaseModel, Field


# ========== 需求表单 ==========
class RequirementCreate(BaseModel):
    req_type: str = Field(default="网页自动化", description="业务类型")
    title: Optional[str] = Field(default=None, description="需求标题")
    req_dept: Optional[str] = Field(default=None, description="需求部门")
    req_owner: Optional[str] = Field(default=None, description="需求提出人")
    contact_info: Optional[str] = Field(default=None, description="联系方式")
    priority: Optional[str] = Field(default="中", description="优先级(高/中/低)")
    target_url: Optional[str] = Field(default=None, description="目标系统URL")
    login_required: Optional[bool] = Field(default=False, description="是否需要登录")
    exec_frequency: Optional[str] = Field(default=None, description="执行频率")
    input_source: Optional[str] = Field(default=None, description="输入数据来源")
    output_sink: Optional[str] = Field(default=None, description="输出结果去向")
    exception_policy: Optional[List[str]] = Field(default=None, description="异常处理策略")
    glossary: Optional[List[str]] = Field(default=None, description="业务术语词库")
    # 模板 3.1 基础信息
    req_background: Optional[str] = Field(default=None, description="需求背景")
    current_pain: Optional[str] = Field(default=None, description="当前痛点")
    # 模板 3.2 流程信息
    current_role: Optional[str] = Field(default=None, description="当前执行角色")
    single_duration: Optional[str] = Field(default=None, description="单次耗时")
    business_volume: Optional[str] = Field(default=None, description="单次处理的数据量或单据量")
    involved_systems: Optional[str] = Field(default=None, description="涉及系统")
    execution_time: Optional[str] = Field(default=None, description="日常执行时段")
    rpa_schedule_time: Optional[str] = Field(default=None, description="建议RPA执行时间")
    # 模板 3.3 运行环境
    pc_config: Optional[str] = Field(default=None, description="电脑配置/虚拟机规格")
    browser: Optional[str] = Field(default=None, description="操作浏览器")
    network_env: Optional[str] = Field(default=None, description="网络环境")
    # 模板 3.4 账号信息
    account_type: Optional[str] = Field(default=None, description="账号类型(个人/共享)")
    multi_user: Optional[bool] = Field(default=False, description="是否多人共用")
    permission_limit: Optional[str] = Field(default=None, description="操作权限限制")
    # 模板 3.5 前置条件
    data_prerequisite: Optional[str] = Field(default=None, description="数据源前提")
    system_prerequisite: Optional[str] = Field(default=None, description="目标系统前提")
    other_dependency: Optional[str] = Field(default=None, description="其他依赖")
    sensitive_data: Optional[bool] = Field(default=False, description="是否涉及敏感数据")
    compliance_req: Optional[str] = Field(default=None, description="合规要求")
    # 模板 3.7 收益与价值
    current_headcount: Optional[str] = Field(default=None, description="当前投入人力")
    current_hours: Optional[str] = Field(default=None, description="当前工时")
    expected_benefit: Optional[str] = Field(default=None, description="预期收益")
    expected_saving: Optional[str] = Field(default=None, description="预期节省工时")
    quality_improvement: Optional[str] = Field(default=None, description="质量改进")


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
    ts_start_seconds: Optional[float] = None
    ts_end_seconds: Optional[float] = None


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
    # 模板扩展字段（LLM 提取）
    manual_flow_description: str = ""
    prerequisites: List[str] = []
    security_requirements: List[str] = []
    feasibility_notes: List[str] = []
    pending_questions: List[str] = []


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
