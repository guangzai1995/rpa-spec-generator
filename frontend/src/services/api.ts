import axios from 'axios';

const api = axios.create({
  baseURL: '/api/v1',
  timeout: 60000,
});

export interface RequirementForm {
  req_type: string;
  title?: string;
  req_dept?: string;
  req_owner?: string;
  target_url?: string;
  login_required?: boolean;
  exec_frequency?: string;
  input_source?: string;
  output_sink?: string;
  exception_policy?: string[];
  glossary?: string[];
}

export interface RequirementItem {
  id: string;
  req_type: string;
  title: string | null;
  status: string;
  error_message: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface TaskStatus {
  requirement_id: string;
  status: string;
  message: string | null;
}

export interface ProviderItem {
  id: string;
  name: string;
  base_url: string;
  model_name: string;
  api_key_masked: string;
  enabled: number;
}

// 需求管理
export const createRequirement = (data: RequirementForm) =>
  api.post<RequirementItem>('/requirements', data);

export const listRequirements = () =>
  api.get<RequirementItem[]>('/requirements');

export const getRequirement = (id: string) =>
  api.get(`/requirements/${id}`);

export const deleteRequirement = (id: string) =>
  api.delete(`/requirements/${id}`);

// 视频上传
export const uploadVideo = (reqId: string, file: File) => {
  const formData = new FormData();
  formData.append('file', file);
  return api.post(`/requirements/${reqId}/upload`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 300000, // 5分钟超时
  });
};

// 提交任务
export const submitRequirement = (reqId: string) =>
  api.post(`/requirements/${reqId}/submit`);

// 状态查询
export const getTaskStatus = (reqId: string) =>
  api.get<TaskStatus>(`/requirements/${reqId}/status`);

// 下载文档
export const getSpecDownloadUrl = (reqId: string) =>
  `/api/v1/requirements/${reqId}/spec.docx`;

// 获取时间线
export const getTimeline = (reqId: string) =>
  api.get(`/requirements/${reqId}/timeline`);

// 获取结构化结果
export const getExtraction = (reqId: string) =>
  api.get(`/requirements/${reqId}/extraction`);

// Provider 管理
export const listProviders = () =>
  api.get<ProviderItem[]>('/providers');

export const addProvider = (data: {
  name: string;
  api_key: string;
  base_url: string;
  model_name: string;
}) => api.post('/providers', data);

export const deleteProvider = (id: string) =>
  api.delete(`/providers/${id}`);

export const testProvider = (id: string) =>
  api.post(`/providers/${id}/test`);

// 健康检查
export const healthCheck = () =>
  axios.get('/api/health');

export default api;
