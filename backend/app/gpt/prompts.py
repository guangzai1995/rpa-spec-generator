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
  "manual_flow_description": "描述当前人工执行该流程的完整步骤说明，包括操作人员的习惯做法、耗时环节、重复性操作等",
  "main_process": [
    {{
      "name": "主流程名称",
      "ts_start_seconds": 0,
      "ts_end_seconds": 120,
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
  ],
  "prerequisites": ["前置条件1：如数据源需每日固定时间更新", "前置条件2"],
  "security_requirements": ["权限与安全要求1：如需保留执行日志", "要求2"],
  "feasibility_notes": ["可行性判断1：如流程固定、适合RPA实施", "判断2"],
  "pending_questions": ["待确认问题1：如筛选条件是否固定", "问题2"]
}}
```

重要原则：
- **严格基于视频内容**：所有输出必须来自视频画面、ASR 语音、或用户填写的表单信息
- **未提及则留空**：如果视频中没有展示或提及某项内容，对应字段输出空字符串""或空数组[]，绝不可臆造
- 例如：视频未展示登录过程，则 system_env 中不要编造认证方式；视频未提到业务规则，则 rules 留空数组

要求：
1. 将碎片化的视频操作步骤归并为有意义的主流程和子步骤
2. action 使用标准类型：open_url/click/input/select/download/upload/export/query/login/http_post
3. main_process 中每个流程必须包含 ts_start_seconds 和 ts_end_seconds，表示该流程在视频中对应的起止时间（秒），根据时间线标记 [MM:SS] 推算
3. 仅当视频中出现条件分支、格式校验时才提取业务规则，否则 rules 留空
4. exceptions 仅包含视频中出现或可合理推断的异常场景，不要凭空补全
5. manual_flow_description 仅描述视频中实际展示的人工操作流程，未展示则留空
6. prerequisites 仅列出从视频/表单中可推断的前置条件，不确定的不要写
7. security_requirements 仅列出视频中可见的权限、安全相关信息，未涉及则留空
8. feasibility_notes 基于视频中实际看到的系统和操作来评估，不要泛泛而谈
9. pending_questions 列出视频中信息不足、需要确认的问题
10. 仅输出 JSON，不要包含 markdown 代码块标记"""
