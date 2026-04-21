import React, { useState, useRef, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  createRequirement,
  uploadVideo,
  submitRequirement,
  getTaskStatus,
  getSpecDownloadUrl,
  listRequirements,
  deleteRequirement,
  getExtraction,
  RequirementForm,
  RequirementItem,
} from '../services/api';

const STATUS_LABELS: Record<string, string> = {
  draft: '草稿',
  submitted: '已提交',
  uploading: '上传中',
  preprocessing: '预处理中',
  transcribing: 'ASR 转录中',
  analyzing: '分析中',
  extracting: '结构化拆解中',
  generating: '文档生成中',
  success: '已完成',
  failed: '失败',
  locked: '已锁定',
};

const PROCESSING_STATUSES = [
  'submitted', 'uploading', 'preprocessing',
  'transcribing', 'analyzing', 'extracting', 'generating'
];

export default function HomePage() {
  const navigate = useNavigate();
  // 表单状态
  const [form, setForm] = useState<RequirementForm>({
    req_type: '网页自动化',
    title: '',
    req_dept: '',
    req_owner: '',
    contact_info: '',
    priority: '中',
    target_url: '',
    login_required: false,
    exec_frequency: '每日',
    input_source: '',
    output_sink: '',
    exception_policy: ['企微群通知'],
    req_background: '',
    current_pain: '',
    current_role: '',
    single_duration: '',
    business_volume: '',
    involved_systems: '',
    execution_time: '',
    rpa_schedule_time: '',
    browser: 'Chrome 120+',
    network_env: '',
    account_type: '',
    current_headcount: '',
    current_hours: '',
    expected_benefit: '',
    expected_saving: '',
  });

  const [videoFile, setVideoFile] = useState<File | null>(null);
  const [currentReqId, setCurrentReqId] = useState<string | null>(null);
  const [taskStatus, setTaskStatus] = useState<string>('');
  const [errorMsg, setErrorMsg] = useState<string>('');
  const [loading, setLoading] = useState(false);
  const [step, setStep] = useState<number>(1); // 1=填表 2=上传 3=处理中 4=完成
  const [showAdvanced, setShowAdvanced] = useState(false);

  // 历史列表
  const [requirements, setRequirements] = useState<RequirementItem[]>([]);
  const [showHistory, setShowHistory] = useState(false);

  const fileInputRef = useRef<HTMLInputElement>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const primaryFieldCount = [
    form.req_type,
    form.title,
    form.req_owner,
    form.req_dept,
    form.exec_frequency,
  ].filter(Boolean).length;
  const draftTitle = form.title?.trim() || '未命名需求';

  // 加载历史
  const loadHistory = useCallback(async () => {
    try {
      const res = await listRequirements();
      setRequirements(res.data);
    } catch (e) {
      console.error('加载历史失败', e);
    }
  }, []);

  useEffect(() => {
    loadHistory();
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [loadHistory]);

  // 轮询状态
  const startPolling = useCallback((reqId: string) => {
    if (pollRef.current) clearInterval(pollRef.current);

    pollRef.current = setInterval(async () => {
      try {
        const res = await getTaskStatus(reqId);
        const status = res.data.status;
        setTaskStatus(status);

        if (status === 'success') {
          setStep(4);
          clearInterval(pollRef.current!);
          pollRef.current = null;
          loadHistory();
        } else if (status === 'failed') {
          setErrorMsg(res.data.message || '处理失败');
          clearInterval(pollRef.current!);
          pollRef.current = null;
          loadHistory();
        }
      } catch (e) {
        console.error('轮询失败', e);
      }
    }, 3000);
  }, [loadHistory]);

  // 提交流程
  const handleSubmit = async () => {
    if (!videoFile) {
      setErrorMsg('请先选择视频文件');
      return;
    }

    setLoading(true);
    setErrorMsg('');

    try {
      // 1. 创建需求
      const createRes = await createRequirement(form);
      const reqId = createRes.data.id;
      setCurrentReqId(reqId);
      setStep(2);

      // 2. 上传视频
      setTaskStatus('uploading');
      await uploadVideo(reqId, videoFile);

      // 3. 提交处理
      setStep(3);
      setTaskStatus('submitted');
      await submitRequirement(reqId);

      // 4. 开始轮询
      startPolling(reqId);
    } catch (e: any) {
      const msg = e.response?.data?.detail || e.message || '提交失败';
      setErrorMsg(msg);
      setStep(1);
    } finally {
      setLoading(false);
    }
  };

  // 重置
  const handleReset = () => {
    setStep(1);
    setVideoFile(null);
    setCurrentReqId(null);
    setTaskStatus('');
    setErrorMsg('');
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  };

  // 删除记录
  const handleDelete = async (id: string) => {
    if (!confirm('确认删除？')) return;
    try {
      await deleteRequirement(id);
      loadHistory();
    } catch (e) {
      console.error('删除失败', e);
    }
  };

  // 查看已完成记录
  const handleView = (item: RequirementItem) => {
    setCurrentReqId(item.id);
    if (item.status === 'success') {
      setStep(4);
      setTaskStatus('success');
    } else if (PROCESSING_STATUSES.includes(item.status)) {
      setStep(3);
      setTaskStatus(item.status);
      startPolling(item.id);
    } else {
      setStep(1);
    }
  };

  return (
    <div className="container">
      {/* 页面标题区 */}
      <div className="page-hero">
        <h2 className="page-hero-title">需求规格说明书生成</h2>
        <p className="page-hero-desc">上传业务操作录屏，AI 自动分析并生成标准化 RPA 需求说明书</p>
      </div>

      {/* 步骤指示器 */}
      <div className="steps">
        <div className={`step-item ${step >= 1 ? (step > 1 ? 'done' : 'active') : ''}`}>
          <span className="step-num">{step > 1 ? '✓' : '1'}</span>
          <span>填写信息</span>
        </div>
        <div className={`step-line ${step > 1 ? 'done' : ''}`}></div>
        <div className={`step-item ${step >= 2 ? (step > 2 ? 'done' : 'active') : ''}`}>
          <span className="step-num">{step > 2 ? '✓' : '2'}</span>
          <span>上传视频</span>
        </div>
        <div className={`step-line ${step > 2 ? 'done' : ''}`}></div>
        <div className={`step-item ${step >= 3 ? (step > 3 ? 'done' : 'active') : ''}`}>
          <span className="step-num">{step > 3 ? '✓' : '3'}</span>
          <span>AI 解析</span>
        </div>
        <div className={`step-line ${step > 3 ? 'done' : ''}`}></div>
        <div className={`step-item ${step >= 4 ? 'active' : ''}`}>
          <span className="step-num">4</span>
          <span>完成</span>
        </div>
      </div>

      {errorMsg && (
        <div className="alert alert-error" style={{maxWidth: 800, margin: '0 auto 16px'}}>{errorMsg}</div>
      )}

      {/* Step 1 & 2: 表单 + 上传 */}
      {step <= 2 && (
        <div className="main-content">
          <div className="form-upload-grid">
            {/* 左：表单 */}
            <div className="card">
              <div className="form-header">
                <div>
                  <div className="card-title">需求基础信息</div>
                  <p className="form-header-desc">首屏只保留最常用字段，其他补充信息可在高级选项中按需完善。</p>
                </div>
                <div className="form-progress-badge">已填写 {primaryFieldCount}/6</div>
              </div>

              <div className="core-form-panel">
                <div className="core-form-grid">
                  <div className="form-group form-group-span-2">
                    <label>需求标题</label>
                    <input
                      className="form-control"
                      placeholder="例：月度经营报表自动下载RPA"
                      value={form.title || ''}
                      onChange={e => setForm({...form, title: e.target.value})}
                    />
                  </div>

                  <div className="form-group">
                    <label>业务类型 <span className="required">*</span></label>
                    <select
                      className="form-control"
                      value={form.req_type}
                      onChange={e => setForm({...form, req_type: e.target.value})}
                    >
                      <option value="报表类">报表类</option>
                      <option value="数据抓取类">数据抓取类</option>
                      <option value="工单办理类">工单办理类</option>
                      <option value="数据录入">数据录入</option>
                      <option value="文件处理">文件处理</option>
                      <option value="网页自动化">网页自动化</option>
                      <option value="系统对接">系统对接</option>
                      <option value="混合型">混合型</option>
                    </select>
                  </div>

                  <div className="form-group">
                    <label>执行频率</label>
                    <select
                      className="form-control"
                      value={form.exec_frequency || ''}
                      onChange={e => setForm({...form, exec_frequency: e.target.value})}
                    >
                      <option value="每日">每日</option>
                      <option value="每周">每周</option>
                      <option value="每月">每月</option>
                      <option value="按需">按需</option>
                    </select>
                  </div>

                  <div className="form-group">
                    <label>需求提出人</label>
                    <input
                      className="form-control"
                      placeholder="姓名"
                      value={form.req_owner || ''}
                      onChange={e => setForm({...form, req_owner: e.target.value})}
                    />
                  </div>

                  <div className="form-group">
                    <label>需求部门</label>
                    <select
                      className="form-control"
                      value={form.req_dept || ''}
                      onChange={e => setForm({...form, req_dept: e.target.value})}
                    >
                      <option value="">请选择</option>
                      <option value="运营部">运营部</option>
                      <option value="客户服务部">客户服务部</option>
                      <option value="市场经营部">市场经营部</option>
                      <option value="计费支撑部">计费支撑部</option>
                      <option value="运维部">运维部</option>
                      <option value="其他">其他</option>
                    </select>
                  </div>

                </div>

                <div className="core-form-meta">
                  <div className="form-group inline-select">
                    <label>优先级</label>
                    <select
                      className="form-control"
                      value={form.priority || '中'}
                      onChange={e => setForm({...form, priority: e.target.value})}
                    >
                      <option value="高">高</option>
                      <option value="中">中</option>
                      <option value="低">低</option>
                    </select>
                  </div>
                </div>
              </div>

              {/* 高级选项折叠 */}
              <div className="advanced-toggle">
                <button
                  type="button"
                  className="btn btn-sm"
                  onClick={() => setShowAdvanced(!showAdvanced)}
                >
                  {showAdvanced ? '收起补充信息 ▲' : '展开补充信息 ▼'}
                </button>
              </div>

              {showAdvanced && (
                <div className="advanced-panel">
                  <div className="advanced-hero">
                    <div>
                      <div className="advanced-hero-title">补充信息</div>
                      <p className="advanced-hero-desc">这些字段会进入最终文档，但不是完成提交的必填项。</p>
                    </div>
                  </div>

                  <div className="advanced-section">
                    <div className="section-subtitle">背景与交付</div>
                    <div className="form-row">
                      <div className="form-group">
                        <label>联系方式</label>
                        <input
                          className="form-control"
                          placeholder="手机号/企微"
                          value={form.contact_info || ''}
                          onChange={e => setForm({...form, contact_info: e.target.value})}
                        />
                      </div>
                      <div className="form-group">
                        <label>需求背景</label>
                        <input
                          className="form-control"
                          placeholder="为什么提出该需求"
                          value={form.req_background || ''}
                          onChange={e => setForm({...form, req_background: e.target.value})}
                        />
                      </div>
                    </div>
                    <div className="form-row">
                      <div className="form-group">
                        <label>当前痛点</label>
                        <input
                          className="form-control"
                          placeholder="当前主要问题"
                          value={form.current_pain || ''}
                          onChange={e => setForm({...form, current_pain: e.target.value})}
                        />
                      </div>
                      <div className="form-group">
                        <label>目标系统 URL</label>
                        <input
                          className="form-control"
                          placeholder="https://..."
                          value={form.target_url || ''}
                          onChange={e => setForm({...form, target_url: e.target.value})}
                        />
                      </div>
                    </div>
                    <div className="form-row">
                      <div className="form-group">
                        <label>输出结果去向</label>
                        <input
                          className="form-control"
                          placeholder="例：导出 Excel / 企微推送"
                          value={form.output_sink || ''}
                          onChange={e => setForm({...form, output_sink: e.target.value})}
                        />
                      </div>
                      <div className="form-group">
                        <label>输入数据来源</label>
                        <input
                          className="form-control"
                          placeholder="例：目标系统筛选条件"
                          value={form.input_source || ''}
                          onChange={e => setForm({...form, input_source: e.target.value})}
                        />
                      </div>
                    </div>
                  </div>

                  <div className="advanced-section">
                    <div className="section-subtitle">流程信息</div>
                    <div className="form-row">
                      <div className="form-group">
                        <label>当前执行角色</label>
                        <input className="form-control" placeholder="目前由谁执行" value={form.current_role || ''} onChange={e => setForm({...form, current_role: e.target.value})} />
                      </div>
                      <div className="form-group">
                        <label>单次耗时</label>
                        <input className="form-control" placeholder="例：3小时" value={form.single_duration || ''} onChange={e => setForm({...form, single_duration: e.target.value})} />
                      </div>
                    </div>
                    <div className="form-row">
                      <div className="form-group">
                        <label>业务量</label>
                        <input className="form-control" placeholder="例：约15张报表，3000行数据" value={form.business_volume || ''} onChange={e => setForm({...form, business_volume: e.target.value})} />
                      </div>
                      <div className="form-group">
                        <label>涉及系统</label>
                        <input className="form-control" placeholder="例：CRM系统、Excel" value={form.involved_systems || ''} onChange={e => setForm({...form, involved_systems: e.target.value})} />
                      </div>
                    </div>
                    <div className="form-row">
                      <div className="form-group">
                        <label>日常执行时段</label>
                        <input className="form-control" placeholder="例：每月5号上午" value={form.execution_time || ''} onChange={e => setForm({...form, execution_time: e.target.value})} />
                      </div>
                      <div className="form-group">
                        <label>建议RPA执行时间</label>
                        <input className="form-control" placeholder="例：每月6号凌晨2点" value={form.rpa_schedule_time || ''} onChange={e => setForm({...form, rpa_schedule_time: e.target.value})} />
                      </div>
                    </div>
                  </div>

                  <div className="advanced-section">
                    <div className="section-subtitle">运行环境与账号</div>
                    <div className="form-row">
                      <div className="form-group">
                        <label>操作浏览器</label>
                        <input className="form-control" placeholder="Chrome 120+" value={form.browser || ''} onChange={e => setForm({...form, browser: e.target.value})} />
                      </div>
                      <div className="form-group">
                        <label>网络环境</label>
                        <input className="form-control" placeholder="内网/外网/VPN" value={form.network_env || ''} onChange={e => setForm({...form, network_env: e.target.value})} />
                      </div>
                    </div>
                    <div className="form-row">
                      <div className="form-group">
                        <label>账号类型</label>
                        <select className="form-control" value={form.account_type || ''} onChange={e => setForm({...form, account_type: e.target.value})}>
                          <option value="">请选择</option>
                          <option value="个人账号">个人账号</option>
                          <option value="共享账号">共享账号</option>
                        </select>
                      </div>
                      <div className="form-group" style={{ display: 'flex', alignItems: 'flex-end', paddingBottom: 4 }}>
                        <label className="checkbox-label">
                          <input type="checkbox" checked={form.multi_user || false} onChange={e => setForm({...form, multi_user: e.target.checked})} />
                          多人共用（可能顶号）
                        </label>
                      </div>
                    </div>
                  </div>

                  <div className="advanced-section">
                    <div className="section-subtitle">收益与价值</div>
                    <div className="form-row">
                      <div className="form-group">
                        <label>当前投入人力</label>
                        <input className="form-control" placeholder="例：2人" value={form.current_headcount || ''} onChange={e => setForm({...form, current_headcount: e.target.value})} />
                      </div>
                      <div className="form-group">
                        <label>当前工时</label>
                        <input className="form-control" placeholder="例：每月6小时" value={form.current_hours || ''} onChange={e => setForm({...form, current_hours: e.target.value})} />
                      </div>
                    </div>
                    <div className="form-row">
                      <div className="form-group">
                        <label>预期收益</label>
                        <input className="form-control" placeholder="例：节省人工、减少差错" value={form.expected_benefit || ''} onChange={e => setForm({...form, expected_benefit: e.target.value})} />
                      </div>
                      <div className="form-group">
                        <label>预期节省工时</label>
                        <input className="form-control" placeholder="例：每月节省4小时" value={form.expected_saving || ''} onChange={e => setForm({...form, expected_saving: e.target.value})} />
                      </div>
                    </div>
                  </div>
                </div>
              )}
            </div>

            {/* 右：上传 + 提交 */}
            <div className="submit-column">
              <div className="card submit-card">
                <div className="card-title">提交面板 <span className="required">*</span></div>

                <div className="submit-summary">
                  <div className="summary-label">当前需求</div>
                  <div className="summary-title">{draftTitle}</div>
                  <div className="summary-tags">
                    <span className="summary-tag">{form.req_type}</span>
                    <span className="summary-tag">{form.exec_frequency || '未设置频率'}</span>
                    <span className="summary-tag muted">{form.req_owner || '未填写提出人'}</span>
                  </div>
                </div>

                <div
                  className={`upload-area ${videoFile ? 'has-file' : ''}`}
                  onClick={() => fileInputRef.current?.click()}
                >
                  <div className="upload-icon">{videoFile ? '✅' : '🎬'}</div>
                  <div className="upload-text">
                    {videoFile ? videoFile.name : '点击或拖拽上传视频文件'}
                  </div>
                  <div className="upload-hint">
                    {videoFile
                      ? `${(videoFile.size / 1024 / 1024).toFixed(1)} MB`
                      : '支持 MP4 / AVI / MOV / MKV'}
                  </div>
                  {!videoFile && (
                    <div className="upload-hint">建议时长 ≤ 15 分钟</div>
                  )}
                </div>

                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".mp4,.avi,.mov,.mkv,.webm,.flv"
                  style={{display: 'none'}}
                  onChange={e => {
                    const f = e.target.files?.[0];
                    if (f) setVideoFile(f);
                  }}
                />

                <div className="submit-tips">
                  <div className="submit-tip-item">
                    <span className="submit-tip-dot"></span>
                    AI 会自动分析录屏并生成结构化需求文档
                  </div>
                  <div className="submit-tip-item">
                    <span className="submit-tip-dot"></span>
                    高级选项可选填，不影响正常提交
                  </div>
                  <div className="submit-tip-item">
                    <span className="submit-tip-dot"></span>
                    当前表单填写越完整，文档越接近最终版本
                  </div>
                </div>

                <button
                  className="btn btn-primary btn-lg"
                  onClick={handleSubmit}
                  disabled={loading || !videoFile}
                  style={{width: '100%', marginTop: 4}}
                >
                  {loading ? '提交中...' : '提交并生成说明书'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Step 3: 处理中 */}
      {step === 3 && (
        <div className="center-card">
          <div className="card">
            <div className="progress-wrapper">
              <div className="progress-spinner"></div>
              <div className="progress-text">
                {STATUS_LABELS[taskStatus] || '处理中...'}
              </div>
              <div className="progress-sub">
                AI 正在解析录屏内容，10 分钟录屏预计需要 3~5 分钟
              </div>
              <div className="progress-bar"></div>
            </div>
          </div>
        </div>
      )}

      {/* Step 4: 完成 */}
      {step === 4 && currentReqId && (
        <div className="center-card">
          <div className="card">
            <div className="result-card">
              <div className="result-icon">🎉</div>
              <div className="result-title">需求规格说明书已生成</div>
              <div className="result-desc">文档已就绪，可下载或在线预览</div>
              <div className="result-actions">
                <a
                  href={getSpecDownloadUrl(currentReqId)}
                  className="btn btn-primary btn-lg"
                  download
                >
                  下载说明书
                </a>
                <button
                  className="btn btn-lg"
                  onClick={() => navigate(`/result/${currentReqId}`)}
                >
                  在线预览
                </button>
                <button className="btn btn-lg" onClick={handleReset}>
                  创建新需求
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* 历史记录 */}
      <div className="card" style={{marginTop: 32}}>
        <div className="card-title history-header">
          <span>历史记录 {requirements.length > 0 && <span className="history-count">{requirements.length}</span>}</span>
          <button className="btn btn-sm" onClick={loadHistory}>刷新</button>
        </div>

        {requirements.length === 0 ? (
          <div className="empty">
            <div className="empty-icon">📋</div>
            <div>暂无记录</div>
          </div>
        ) : (
          <div className="table-wrapper">
            <table>
              <thead>
                <tr>
                  <th>标题</th>
                  <th>类型</th>
                  <th>状态</th>
                  <th>创建时间</th>
                  <th>操作</th>
                </tr>
              </thead>
              <tbody>
                {requirements.map(item => (
                  <tr key={item.id}>
                    <td style={{fontWeight: 500}}>{item.title || '未命名需求'}</td>
                    <td style={{color: '#6b7280'}}>{item.req_type}</td>
                    <td>
                      <span className={`status-badge status-${item.status}`}>
                        {STATUS_LABELS[item.status] || item.status}
                      </span>
                    </td>
                    <td style={{fontSize: 13, color: '#9ca3af'}}>
                      {item.created_at?.slice(0, 19).replace('T', ' ')}
                    </td>
                    <td>
                      <div className="btn-group">
                        {item.status === 'success' && (
                          <>
                            <a
                              href={getSpecDownloadUrl(item.id)}
                              className="btn btn-sm btn-success"
                              download
                            >
                              下载
                            </a>
                            <button
                              className="btn btn-sm"
                              onClick={() => navigate(`/result/${item.id}`)}
                            >
                              预览
                            </button>
                          </>
                        )}
                        {PROCESSING_STATUSES.includes(item.status) && (
                          <button
                            className="btn btn-sm"
                            onClick={() => handleView(item)}
                          >
                            查看
                          </button>
                        )}
                        <button
                          className="btn btn-sm btn-danger"
                          onClick={() => handleDelete(item.id)}
                        >
                          删除
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
