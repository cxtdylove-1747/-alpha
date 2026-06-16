import request from '../utils/request';

export const listApplicationsApi = (params = {}) => request.get('/mentorship/applications', { params });
export const auditApplicationApi = (id, payload) => request.post(`/mentorship/${id}/audit`, payload);
export const dashboardApi = () => request.get('/teacher/dashboard');
export const teacherAggregateDashboardApi = (selectedPlanIds = []) => {
  const params = {};
  if (Array.isArray(selectedPlanIds) && selectedPlanIds.length) {
    params.selected_plan_ids = selectedPlanIds.join(',');
  }
  return request.get('/teacher/aggregate-dashboard', { params });
};
export const listMetricsStreamApi = (params = {}) => request.get('/teacher/metrics-stream', { params });
export const teacherRuleDrilldownApi = (ruleId) => request.get('/teacher/rule-drilldown', { params: { rule_id: ruleId } });
export const teacherProjectEvidenceDetailApi = (planId) => request.get(`/teacher/project/${planId}/evidence-detail`);
export const classRadarApi = () => request.get('/teacher/class-radar');
export const teacherClassPersonaApi = () => request.get('/teacher/class-persona');
export const classLearningReportApi = () => request.get('/teacher/class-learning-report');
export const commonMistakesApi = () => request.get('/teacher/common-mistakes');
export const highRiskProjectsApi = (params = {}) => request.get('/teacher/high-risk-projects', { params });
export const listTeacherStudentsApi = (params = {}) => request.get('/teacher/students', { params });
export const unbindTeacherStudentApi = (studentId) => request.post(`/teacher/students/${studentId}/unbind`);
export const teacherInterventionApi = (payload) => request.post('/teacher/intervention', payload);
export const caseLibrarySummaryApi = () => request.get('/teacher/case-library-summary');
export const promptScenesApi = (params = {}) => request.get('/teacher/prompt-scenes', { params });
export const commonIssuesApi = (planIdsOrParams = []) => {
  const params = {};
  if (Array.isArray(planIdsOrParams) && planIdsOrParams.length) {
    params.plan_ids = planIdsOrParams.join(',');
  }
  if (planIdsOrParams && typeof planIdsOrParams === 'object' && !Array.isArray(planIdsOrParams)) {
    Object.assign(params, planIdsOrParams);
  }
  return request.get('/teacher/common-issues', { params });
};
export const knowledgeApi = () => request.get('/teacher/knowledge-recommendations');
export const scoringRubricsApi = () => request.get('/teacher/rubrics');
export const listPlansApi = (params = {}) => request.get('/plans', { params });
export const deletePlanApi = (planId, params = {}) => request.delete(`/plans/${planId}`, { params });
export const genTeacherReviewApi = (payload) => request.post('/reviews/generate', payload);
export const genTeacherReviewAsyncApi = (payload) => request.post('/reviews/generate-async', payload);
export const reviewTaskStatusApi = (taskId) => request.get(`/reviews/tasks/${taskId}`);
export const listPlanReviewsApi = (planId, params = {}) => request.get(`/plans/${planId}/reviews`, { params });
export const updateReviewApi = (reviewId, payload) => request.put(`/reviews/${reviewId}`, payload);
export const teacherAiChatApi = (payload) => request.post('/teacher/ai-chat', payload);
export const importHypergraphCaseApi = (payload) => request.post('/hypergraph/import-case', payload);

