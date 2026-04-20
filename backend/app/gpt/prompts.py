# RPA 需求结构化拆解 Prompt

SYSTEM_PROMPT = """你是一个专业的 RPA（机器人流程自动化）需求分析师。
你的任务是分析业务操作视频的 ASR 转录文本和关键帧信息，生成结构化的 RPA 需求说明书内容。
所有输出必须使用中文，技术术语可保留英文。
严格按照指定的 JSON Schema 输出，不要添加额外字段。"""

# S1: 概述抽取
PROMPT_S1_OVERVIEW = """请基于以下业务操作视频的语音转录内容和基础信息，生成业务概述。

需求基础信息：
{form_info}

ASR 转录总览：
{asr_text}

请输出 JSON 格式：
{{
  "auto_goal": "一句话描述自动化目标",
  "scope": "业务范围描述（如：单系统网页自动化、跨系统数据录入等）"
}}

仅输出 JSON，不要包含其他内容。"""

# S2: 流程归并
PROMPT_S2_PROCESS = """请将以下操作步骤归并为主流程-子步骤二级结构。

操作步骤时间线：
{timeline_steps}

ASR 转录文本：
{asr_text}

请输出 JSON 格式：
{{
  "main_process": [
    {{
      "name": "流程名称（如：登录系统）",
      "steps": [
        {{
          "no": 1,
          "action": "动作类型（open_url/click/input/select/download/upload/http_post等）",
          "target": "操作目标描述",
          "value": "输入值或参数（可选）",
          "result_file": "输出文件路径（可选）"
        }}
      ]
    }}
  ]
}}

要求：
1. 将碎片化步骤合并为有意义的主流程
2. 每个主流程包含具体的子步骤
3. action 使用标准化的动作类型
4. 仅输出 JSON"""

# S3: 规则/判断
PROMPT_S3_RULES = """请从以下内容中识别业务规则、条件分支、格式校验和异常跳转。

ASR 转录文本：
{asr_text}

操作流程：
{process_json}

请输出 JSON 格式：
{{
  "rules": [
    "规则描述1",
    "规则描述2"
  ]
}}

仅输出 JSON。"""

# S4: 输入输出规范
PROMPT_S4_IO = """请列出 RPA 流程的输入数据源和输出结果。

需求基础信息：
{form_info}

操作流程：
{process_json}

请输出 JSON 格式：
{{
  "io_spec": {{
    "input": ["输入项1", "输入项2"],
    "output": ["输出项1", "输出项2"]
  }}
}}

仅输出 JSON。"""

# S5: 系统与权限
PROMPT_S5_SYSTEM = """请汇总 RPA 流程涉及的业务系统、登录方式和权限要求。

需求基础信息：
{form_info}

操作流程：
{process_json}

请输出 JSON 格式：
{{
  "system_env": [
    {{
      "name": "系统名称",
      "auth": "认证方式（如：工号+密码）",
      "browser": "浏览器要求（如：Chrome ≥ 120）"
    }}
  ]
}}

仅输出 JSON。"""

# S6: 异常处理
PROMPT_S6_EXCEPTIONS = """请基于 RPA 流程类型，补全通用异常和处理逻辑。

需求基础信息：
{form_info}

操作流程：
{process_json}

已知异常处理策略：
{exception_policy}

请输出 JSON 格式：
{{
  "exceptions": [
    {{
      "code": "异常代码（如：LOGIN_FAIL）",
      "handler": "处理方式描述"
    }}
  ]
}}

常见 RPA 异常类型参考：LOGIN_FAIL, PAGE_TIMEOUT, ELEMENT_NOT_FOUND, DOWNLOAD_FAIL, NETWORK_ERROR, DATA_FORMAT_ERROR, PERMISSION_DENIED

仅输出 JSON。"""

# 合并 Prompt（当 token 充足时可一次完成）
PROMPT_FULL_EXTRACTION = """你是一个专业的 RPA 需求分析师。请分析以下业务操作视频的信息，生成完整的结构化 RPA 需求说明。

## 需求基础信息
{form_info}

## ASR 语音转录内容
{asr_text}

## 视频关键帧操作步骤
{timeline_steps}

请严格按以下 JSON 格式输出完整的结构化结果：

```json
{{
  "business_overview": {{
    "auto_goal": "一句话描述自动化目标",
    "scope": "业务范围"
  }},
  "main_process": [
    {{
      "name": "主流程名称",
      "steps": [
        {{"no": 1, "action": "动作类型", "target": "操作目标", "value": "参数值(可选)", "result_file": "输出文件(可选)"}}
      ]
    }}
  ],
  "rules": ["业务规则1", "业务规则2"],
  "io_spec": {{
    "input": ["输入项"],
    "output": ["输出项"]
  }},
  "system_env": [
    {{"name": "系统名称", "auth": "认证方式", "browser": "浏览器要求"}}
  ],
  "exceptions": [
    {{"code": "异常代码", "handler": "处理方式"}}
  ]
}}
```

要求：
1. 将碎片化的视频操作步骤归并为有意义的主流程和子步骤
2. action 使用标准类型：open_url/click/input/select/download/upload/export/query/login/http_post
3. 识别条件分支、格式校验等业务规则
4. 补全常见异常处理（LOGIN_FAIL, PAGE_TIMEOUT, ELEMENT_NOT_FOUND, DOWNLOAD_FAIL 等）
5. 仅输出 JSON，不要包含 markdown 代码块标记"""
