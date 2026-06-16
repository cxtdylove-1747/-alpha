import request from '../utils/request';

export const guideChatApi = (payload) => request.post('/ai/chat', payload);
export const createAgentTaskApi = (payload) => request.post('/agent/chat-async', payload);
export const agentTaskStatusApi = (taskId) => request.get(`/agent/chat-tasks/${taskId}`);
export const waitAgentTaskApi = async (taskId, options = {}) => {
  const intervalMs = typeof options === 'number' ? options : (options.intervalMs || 2000);
  const onStatusChange = typeof options === 'object' ? options.onStatusChange : null;
  let lastStatus = '';

  const notify = (status, error = '') => {
    if (typeof onStatusChange !== 'function') {
      return;
    }
    if (status === lastStatus && !error) {
      return;
    }
    lastStatus = status;
    onStatusChange({ status, error });
  };

  notify('queued');
  while (true) {
    const status = await agentTaskStatusApi(taskId);
    const normalizedStatus = status.status === 'pending' ? 'queued' : (status.status || 'running');

    if (normalizedStatus === 'done') {
      if (!status.result || typeof status.result !== 'object') {
        notify('error', '出了些小问题');
        throw new Error('出了些小问题');
      }
      notify('done');
      return status.result;
    }
    if (normalizedStatus === 'error') {
      const error = status.error || '出了些小问题';
      notify('error', error);
      throw new Error(error);
    }

    notify(normalizedStatus);
    await new Promise((resolve) => setTimeout(resolve, intervalMs));
  }
};
export const pdfChatApi = (payload) => request.post('/ai/pdf-chat', payload);
export const roadmapSimulateApi = (payload) => request.post('/agent/roadmap-simulate', payload);
export const pitchOptimizeApi = (payload) => request.post('/agent/pitch-optimize', payload);
export const pitchSimulateApi = (payload) => request.post('/agent/pitch-simulate', payload);
export const competitionAdviseApi = (payload) => request.post('/agent/competition-advise', payload);
export const competitionCoachChatApi = (payload) => request.post('/agent/competition-coach-chat', payload);
export const competitionCoachExportWordApi = (payload) => request.post('/agent/competition-coach-export-word', payload, {
  responseType: 'blob'
});
export const tutorApi = (payload) => request.post('/agent/tutor', payload);
export const financialDesignApi = (payload) => request.post('/agent/financial-design', payload);
export const caseRecallApi = (payload) => request.post('/agent/case-recall', payload);
export const workflowOrchestrateApi = (payload) => request.post('/agent/workflow-orchestrate', payload);

export const pdfChatHistoryApi = (planId) => request.get('/ai/pdf-chat', { params: { plan_id: planId } });
export const validateLogicApi = (payload) => request.post('/ai/validate', payload);

export const uploadPlanApi = (formData) => request.post('/plans/upload', formData, {
  headers: { 'Content-Type': 'multipart/form-data' }
});
export const listPlansApi = (params = {}) => request.get('/plans', { params });
export const deletePlanApi = (planId, params = {}) => request.delete(`/plans/${planId}`, { params });
export const submitPlanApi = (planId, payload) => request.post(`/plans/${planId}/submit`, payload);
export const genReviewApi = (payload) => request.post('/reviews/generate', payload);
export const genReviewAsyncApi = (payload) => request.post('/reviews/generate-async', payload);
export const reviewTaskStatusApi = (taskId) => request.get(`/reviews/tasks/${taskId}`);
export const listPlanReviewsApi = (planId, params = {}) => request.get(`/plans/${planId}/reviews`, { params });
export const planBottleneckApi = (planId) => request.get(`/project/${planId}/bottleneck`);
export const projectRubricScoreApi = (planId) => request.get(`/project/${planId}/rubric-score`);
export const projectEvidenceChainApi = (planId) => request.get(`/project/${planId}/evidence-chain`);
export const projectPotentialReportApi = (planId) => request.get(`/project/${planId}/potential-report`);
export const projectHypergraphReasoningApi = (planId) => request.get(`/project/${planId}/hypergraph-reasoning`);

export const applyMentorApi = (payload) => request.post('/mentorship/apply', payload);
export const listMentorApplicationsApi = (params = {}) => request.get('/mentorship/applications', { params });

export const listMessagesApi = (params = {}) => request.get('/messages', { params });
export const markMessagesReadApi = (messageIds) => request.post('/messages/read', { message_ids: messageIds });
export const historyApi = (params = {}) => request.get('/history', { params });
export const studentPersonaApi = () => request.get('/student/persona');
export const studentClassPersonaApi = () => request.get('/student/class-persona');
