import React, { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import {
  getSpecPreview,
  getSpecDownloadUrl,
  updateTimelineStep,
} from '../services/api';

interface TimelineStep {
  step_no: number;
  ts_start: number | null;
  ts_end: number | null;
  action: string | null;
  target_text: string | null;
  context_text: string | null;
  asr_text: string | null;
  screenshot_path: string | null;
}

interface PreviewData {
  title: string;
  form_info: Record<string, any>;
  extraction: {
    business_overview: { auto_goal?: string; scope?: string };
    main_process: Array<{
      name: string;
      steps: Array<{ no: number; action: string; target: string; value?: string; result_file?: string }>;
    }>;
    rules: string[];
    io_spec: { input: string[]; output: string[] };
    system_env: Array<{ name: string; auth?: string; browser?: string }>;
    exceptions: Array<{ code: string; handler: string }>;
  };
  timeline: TimelineStep[];
  status: string;
}

const ACTION_OPTIONS = [
  'unknown', 'open_url', 'click', 'input', 'select', 'login',
  'download', 'export', 'query', 'scroll', 'switch', 'upload', 'http_post'
];

function formatTime(seconds: number | null): string {
  if (seconds === null || seconds === undefined) return '--:--';
  const mm = Math.floor(seconds / 60);
  const ss = Math.floor(seconds % 60);
  return `${mm.toString().padStart(2, '0')}:${ss.toString().padStart(2, '0')}`;
}

export default function ResultPage() {
  const { reqId } = useParams<{ reqId: string }>();
  const [data, setData] = useState<PreviewData | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<'timeline' | 'spec' | 'extraction'>('spec');
  const [editingStep, setEditingStep] = useState<number | null>(null);
  const [editForm, setEditForm] = useState<{ action: string; target_text: string; context_text: string }>({
    action: '', target_text: '', context_text: ''
  });
  const [saveMsg, setSaveMsg] = useState('');

  useEffect(() => {
    if (!reqId) return;
    setLoading(true);
    getSpecPreview(reqId)
      .then(res => setData(res.data))
      .catch(err => console.error('加载预览失败', err))
      .finally(() => setLoading(false));
  }, [reqId]);

  const handleEdit = (step: TimelineStep) => {
    setEditingStep(step.step_no);
    setEditForm({
      action: step.action || 'unknown',
      target_text: step.target_text || '',
      context_text: step.context_text || '',
    });
  };

  const handleSave = async (stepNo: number) => {
    if (!reqId) return;
    try {
      await updateTimelineStep(reqId, stepNo, editForm);
      setSaveMsg(`步骤 ${stepNo} 已保存`);
      setEditingStep(null);
      // Refresh data
      const res = await getSpecPreview(reqId);
      setData(res.data);
      setTimeout(() => setSaveMsg(''), 2000);
    } catch (e: any) {
      setSaveMsg(`保存失败: ${e.message}`);
    }
  };

  if (loading) {
    return (
      <div className="container">
        <div className="center-card">
          <div className="card">
            <div className="progress-wrapper">
              <div className="progress-spinner"></div>
              <div className="progress-text">加载中...</div>
            </div>
          </div>
        </div>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="container">
        <div className="alert alert-error">无法加载数据</div>
        <Link to="/" className="btn">返回首页</Link>
      </div>
    );
  }

  const ext = data.extraction;

  return (
    <div className="container">
      <div className="page-hero">
        <h2 className="page-hero-title">{data.title}</h2>
        <p className="page-hero-desc">
          状态: <span className={`status-badge status-${data.status}`}>{data.status}</span>
          {data.status === 'success' && (
            <a href={getSpecDownloadUrl(reqId!)} className="btn btn-primary btn-sm" download style={{ marginLeft: 16 }}>
              下载 Word 文档
            </a>
          )}
          <Link to="/" className="btn btn-sm" style={{ marginLeft: 8 }}>返回首页</Link>
        </p>
      </div>

      {/* Tab 切换 */}
      <div className="tabs">
        <button className={`tab ${activeTab === 'spec' ? 'active' : ''}`} onClick={() => setActiveTab('spec')}>
          说明书预览
        </button>
        <button className={`tab ${activeTab === 'timeline' ? 'active' : ''}`} onClick={() => setActiveTab('timeline')}>
          操作时间线 ({data.timeline.length})
        </button>
        <button className={`tab ${activeTab === 'extraction' ? 'active' : ''}`} onClick={() => setActiveTab('extraction')}>
          结构化数据
        </button>
      </div>

      {saveMsg && <div className="alert alert-success" style={{ marginBottom: 16 }}>{saveMsg}</div>}

      {/* 说明书预览 */}
      {activeTab === 'spec' && ext && (
        <div className="card spec-preview">
          <h3>1. 需求概述</h3>
          <div className="spec-section">
            <p><strong>自动化目标：</strong>{ext.business_overview?.auto_goal || '—'}</p>
            <p><strong>业务范围：</strong>{ext.business_overview?.scope || '—'}</p>
            <p><strong>需求部门：</strong>{data.form_info?.req_dept || '—'}</p>
            <p><strong>需求提出人：</strong>{data.form_info?.req_owner || '—'}</p>
            <p><strong>业务类型：</strong>{data.form_info?.req_type || '—'}</p>
            <p><strong>优先级：</strong>{data.form_info?.priority || '中'}</p>
            <p><strong>执行频率：</strong>{data.form_info?.exec_frequency || '—'}</p>
          </div>

          <h3>2. 业务背景与痛点</h3>
          <div className="spec-section">
            <p><strong>需求背景：</strong>{data.form_info?.req_background || '通过 RPA 自动化替代人工重复操作，提升效率。'}</p>
            <p><strong>当前痛点：</strong>{data.form_info?.current_pain || '人工操作耗时长、易出错。'}</p>
            {data.form_info?.single_duration && <p><strong>单次耗时：</strong>{data.form_info.single_duration}</p>}
            {data.form_info?.business_volume && <p><strong>业务量：</strong>{data.form_info.business_volume}</p>}
          </div>

          <h3>3. 当前人工流程说明</h3>
          <div className="spec-section">
            <p>{(ext as any).manual_flow_description || '（AI 分析生成中）'}</p>
          </div>

          <h3>4. 涉及系统与对象</h3>
          {ext.system_env && ext.system_env.length > 0 ? (
            <div className="table-wrapper">
              <table>
                <thead>
                  <tr><th>系统名称</th><th>认证方式</th><th>浏览器要求</th></tr>
                </thead>
                <tbody>
                  {ext.system_env.map((s: any, i: number) => (
                    <tr key={i}><td>{s.name}</td><td>{s.auth || '—'}</td><td>{s.browser || '—'}</td></tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : <p className="spec-section">—</p>}
          {data.form_info?.target_url && (
            <div className="spec-section"><p><strong>目标系统 URL：</strong>{data.form_info.target_url}</p></div>
          )}

          <h3>5. 流程步骤说明</h3>
          {ext.main_process?.map((proc: any, pi: number) => (
            <div key={pi} className="spec-section">
              <h4>5.{pi + 1} {proc.name}</h4>
              <div className="table-wrapper">
                <table>
                  <thead>
                    <tr><th>序号</th><th>操作类型</th><th>操作目标</th><th>参数/值</th></tr>
                  </thead>
                  <tbody>
                    {proc.steps?.map((step: any) => (
                      <tr key={step.no}>
                        <td>{step.no}</td>
                        <td><code>{step.action}</code></td>
                        <td>{step.target}</td>
                        <td>{step.value || step.result_file || '—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          ))}

          <h3>6. 业务规则说明</h3>
          <div className="spec-section">
            {ext.rules?.length > 0
              ? ext.rules.map((r: string, i: number) => <p key={i}>{i + 1}. {r}</p>)
              : <p>暂无特殊业务规则</p>
            }
          </div>

          <h3>7. 异常与边界场景</h3>
          {ext.exceptions?.length > 0 ? (
            <div className="table-wrapper">
              <table>
                <thead>
                  <tr><th>异常代码</th><th>处理方式</th></tr>
                </thead>
                <tbody>
                  {ext.exceptions.map((e: any, i: number) => (
                    <tr key={i}><td><code>{e.code}</code></td><td>{e.handler}</td></tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : <p className="spec-section">暂无异常处理策略</p>}

          <h3>8. 输入输出定义</h3>
          <div className="spec-section">
            <p><strong>输入：</strong></p>
            <ul>{ext.io_spec?.input?.map((item: string, i: number) => <li key={i}>{item}</li>)}</ul>
            <p><strong>输出：</strong></p>
            <ul>{ext.io_spec?.output?.map((item: string, i: number) => <li key={i}>{item}</li>)}</ul>
          </div>

          <h3>9. 前置条件与依赖</h3>
          <div className="spec-section">
            {(ext as any).prerequisites?.length > 0
              ? (ext as any).prerequisites.map((p: string, i: number) => <p key={i}>{i + 1}. {p}</p>)
              : <p>暂无特殊前置条件</p>
            }
          </div>

          <h3>10. 权限与安全要求</h3>
          <div className="spec-section">
            {(ext as any).security_requirements?.length > 0
              ? (ext as any).security_requirements.map((s: string, i: number) => <p key={i}>{i + 1}. {s}</p>)
              : <p>需保留执行日志，异常时通知相关人员</p>
            }
          </div>

          <h3>11. 自动化预期收益</h3>
          <div className="spec-section">
            {data.form_info?.current_headcount && <p><strong>当前投入人力：</strong>{data.form_info.current_headcount}</p>}
            {data.form_info?.current_hours && <p><strong>当前工时：</strong>{data.form_info.current_hours}</p>}
            <p><strong>预期收益：</strong>{data.form_info?.expected_benefit || '节省人工、减少差错、提升时效'}</p>
            {data.form_info?.expected_saving && <p><strong>预期节省工时：</strong>{data.form_info.expected_saving}</p>}
          </div>

          <h3>12. 可行性初步判断</h3>
          <div className="spec-section">
            {(ext as any).feasibility_notes?.length > 0
              ? (ext as any).feasibility_notes.map((n: string, i: number) => <p key={i}>{i + 1}. {n}</p>)
              : <p>流程操作规范、步骤固定，适合 RPA 实施</p>
            }
          </div>

          <h3>13. 待确认问题清单</h3>
          {(ext as any).pending_questions?.length > 0 ? (
            <div className="table-wrapper">
              <table>
                <thead>
                  <tr><th>序号</th><th>待确认问题</th><th>状态</th></tr>
                </thead>
                <tbody>
                  {(ext as any).pending_questions.map((q: string, i: number) => (
                    <tr key={i}><td>{i + 1}</td><td>{q}</td><td>待确认</td></tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : <p className="spec-section">暂无待确认问题</p>}
        </div>
      )}

      {/* 操作时间线 */}
      {activeTab === 'timeline' && (
        <div className="card">
          <div className="card-title">操作时间线 - 可点击编辑修正</div>
          {data.timeline.length === 0 ? (
            <div className="empty">
              <div className="empty-icon">📹</div>
              <div>暂无解析数据</div>
            </div>
          ) : (
            <div className="timeline-list">
              {data.timeline.map(step => (
                <div key={step.step_no} className="timeline-item">
                  <div className="timeline-header">
                    <span className="timeline-time">{formatTime(step.ts_start)}</span>
                    <span className="timeline-step-no">步骤 {step.step_no}</span>
                    {editingStep !== step.step_no && (
                      <button className="btn btn-sm" onClick={() => handleEdit(step)}>编辑</button>
                    )}
                  </div>

                  {step.screenshot_path && (
                    <div className="timeline-screenshot">
                      <img
                        src={`/${step.screenshot_path}`}
                        alt={`步骤 ${step.step_no}`}
                        style={{ maxWidth: '100%', maxHeight: 200, borderRadius: 8, border: '1px solid #e5e7eb' }}
                        onError={(e) => { (e.target as HTMLImageElement).style.display = 'none' }}
                      />
                    </div>
                  )}

                  {editingStep === step.step_no ? (
                    <div className="timeline-edit">
                      <div className="form-row">
                        <div className="form-group">
                          <label>动作类型</label>
                          <select
                            className="form-control"
                            value={editForm.action}
                            onChange={e => setEditForm({ ...editForm, action: e.target.value })}
                          >
                            {ACTION_OPTIONS.map(a => <option key={a} value={a}>{a}</option>)}
                          </select>
                        </div>
                        <div className="form-group">
                          <label>操作目标</label>
                          <input
                            className="form-control"
                            value={editForm.target_text}
                            onChange={e => setEditForm({ ...editForm, target_text: e.target.value })}
                          />
                        </div>
                      </div>
                      <div className="form-group">
                        <label>上下文说明</label>
                        <input
                          className="form-control"
                          value={editForm.context_text}
                          onChange={e => setEditForm({ ...editForm, context_text: e.target.value })}
                        />
                      </div>
                      <div className="btn-group">
                        <button className="btn btn-primary btn-sm" onClick={() => handleSave(step.step_no)}>保存</button>
                        <button className="btn btn-sm" onClick={() => setEditingStep(null)}>取消</button>
                      </div>
                    </div>
                  ) : (
                    <div className="timeline-detail">
                      <div className="timeline-badges">
                        <span className={`action-badge action-${step.action || 'unknown'}`}>
                          {step.action || 'unknown'}
                        </span>
                        {step.target_text && <span className="target-badge">{step.target_text}</span>}
                      </div>
                      {step.asr_text && <div className="timeline-asr">🎙 {step.asr_text}</div>}
                      {step.context_text && <div className="timeline-context">📝 {step.context_text}</div>}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* 原始结构化数据 */}
      {activeTab === 'extraction' && (
        <div className="card">
          <div className="card-title">结构化拆解数据（JSON）</div>
          <pre className="json-preview">
            {JSON.stringify(ext, null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
}
