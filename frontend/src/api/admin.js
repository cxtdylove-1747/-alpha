import request from '../utils/request';

export const adminOverviewApi = () => request.get('/admin/overview');
export const adminUsersApi = (params = {}) => request.get('/admin/users', { params });
export const adminBatchUsersApi = (payload) => request.post('/admin/users', payload);
export const adminUpdateUserStatusApi = (userId, payload) => request.post(`/admin/users/${userId}/status`, payload);
export const adminHypergraphApi = (params = {}, options = {}) => request.get('/admin/graphs/hypergraph', {
  params,
  timeout: Number(options.timeout || 20000)
});
export const adminKnowledgeGraphApi = (params = {}, options = {}) => request.get('/admin/graphs/knowledge', {
  params,
  timeout: Number(options.timeout || 20000)
});
export const adminGraphObservabilityApi = (params = {}) => request.get('/admin/graphs/observability', { params });

