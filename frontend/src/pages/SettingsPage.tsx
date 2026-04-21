import React, { useState, useEffect } from 'react';
import {
  listProviders,
  addProvider,
  deleteProvider,
  testProvider,
  ProviderItem,
} from '../services/api';

export default function SettingsPage() {
  const [providers, setProviders] = useState<ProviderItem[]>([]);
  const [showAdd, setShowAdd] = useState(false);
  const [newProvider, setNewProvider] = useState({
    name: '',
    api_key: '',
    base_url: '',
    model_name: '',
  });
  const [testResult, setTestResult] = useState<string>('');

  const loadProviders = async () => {
    try {
      const res = await listProviders();
      setProviders(res.data);
    } catch (e) {
      console.error('加载 Provider 失败', e);
    }
  };

  useEffect(() => {
    loadProviders();
  }, []);

  const handleAdd = async () => {
    if (!newProvider.name || !newProvider.api_key || !newProvider.base_url || !newProvider.model_name) {
      alert('请填写所有字段');
      return;
    }
    try {
      await addProvider(newProvider);
      setShowAdd(false);
      setNewProvider({ name: '', api_key: '', base_url: '', model_name: '' });
      loadProviders();
    } catch (e: any) {
      alert('添加失败: ' + (e.response?.data?.detail || e.message));
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm('确认删除？')) return;
    try {
      await deleteProvider(id);
      loadProviders();
    } catch (e) {
      console.error('删除失败', e);
    }
  };

  const handleTest = async (id: string) => {
    setTestResult('测试中...');
    try {
      const res = await testProvider(id);
      setTestResult(res.data.success ? '✅ 连接成功' : `❌ ${res.data.message}`);
    } catch (e: any) {
      setTestResult(`❌ 测试失败: ${e.message}`);
    }
  };

  return (
    <div className="container">
      <h2 className="page-title">系统设置</h2>

      <div className="card">
        <div className="card-title" style={{ justifyContent: 'space-between' }}>
          <span>LLM Provider 管理</span>
          <button className="btn btn-primary btn-sm" onClick={() => setShowAdd(!showAdd)}>
            {showAdd ? '取消' : '+ 添加'}
          </button>
        </div>

        {testResult && (
          <div className={`alert ${testResult.startsWith('✅') ? 'alert-success' : 'alert-error'}`}>
            {testResult}
          </div>
        )}

        {showAdd && (
          <div className="provider-add-form">
            <div className="form-row">
              <div className="form-group">
                <label>名称</label>
                <input
                  className="form-control"
                  placeholder="例：DeepSeek"
                  value={newProvider.name}
                  onChange={e => setNewProvider({ ...newProvider, name: e.target.value })}
                />
              </div>
              <div className="form-group">
                <label>模型名称</label>
                <input
                  className="form-control"
                  placeholder="例：deepseek-chat"
                  value={newProvider.model_name}
                  onChange={e => setNewProvider({ ...newProvider, model_name: e.target.value })}
                />
              </div>
            </div>
            <div className="form-group">
              <label>API Base URL</label>
              <input
                className="form-control"
                placeholder="例：https://api.deepseek.com/v1"
                value={newProvider.base_url}
                onChange={e => setNewProvider({ ...newProvider, base_url: e.target.value })}
              />
            </div>
            <div className="form-group">
              <label>API Key</label>
              <input
                className="form-control"
                type="password"
                placeholder="sk-..."
                value={newProvider.api_key}
                onChange={e => setNewProvider({ ...newProvider, api_key: e.target.value })}
              />
            </div>
            <button className="btn btn-primary" onClick={handleAdd}>确认添加</button>
          </div>
        )}

        {providers.length === 0 ? (
          <div className="empty">
            <div className="empty-icon">⚙️</div>
            <div>尚未配置 LLM Provider</div>
            <div style={{ fontSize: 13, color: '#9ca3af', marginTop: 8 }}>
              请添加一个 OpenAI 兼容的 LLM Provider（如 DeepSeek、Qwen、OpenAI）
            </div>
          </div>
        ) : (
          <div className="table-wrapper">
            <table>
              <thead>
                <tr>
                  <th>名称</th>
                  <th>模型</th>
                  <th>Base URL</th>
                  <th>API Key</th>
                  <th>操作</th>
                </tr>
              </thead>
              <tbody>
                {providers.map(p => (
                  <tr key={p.id}>
                    <td style={{fontWeight: 500}}>{p.name}</td>
                    <td>{p.model_name}</td>
                    <td style={{ fontSize: 12, color: '#6b7280' }}>{p.base_url}</td>
                    <td style={{ fontSize: 12, color: '#9ca3af' }}>{p.api_key_masked}</td>
                    <td>
                      <div className="btn-group">
                        <button className="btn btn-sm" onClick={() => handleTest(p.id)}>
                          测试
                        </button>
                        <button className="btn btn-sm btn-danger" onClick={() => handleDelete(p.id)}>
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

      <div className="card">
        <div className="card-title">ASR 配置</div>
        <div className="alert alert-info">
          当前引擎：Faster-Whisper（通过环境变量配置）
        </div>
        <div className="settings-info">
          <p>• 模型大小：<code>WHISPER_MODEL_SIZE</code>（默认 large-v3-turbo）</p>
          <p>• 运行设备：<code>WHISPER_DEVICE</code>（cpu / cuda）</p>
          <p>• 首次运行会自动下载模型文件，请确保网络通畅</p>
        </div>
      </div>

      <div className="card">
        <div className="card-title">企业微信推送（预留）</div>
        <div className="alert alert-info">
          企微推送功能已预留接口，后续可通过配置 <code>WECOM_WEBHOOK</code> 环境变量启用
        </div>
      </div>
    </div>
  );
}
