<template>
  <div class="page-grid">
    <section class="panel lead">
      <p class="kicker">Plan Manager</p>
      <h2>方案上传、检阅与迭代</h2>
      <p>上传新版本、查看批注并与智能体追问，保持方案迭代闭环。</p>
    </section>

    <section class="panel">
      <h3>上传方案</h3>
      <div class="toolbar">
        <input type="file" accept=".pdf,.doc,.docx" @change="onFileChange">
        <button type="button" class="primary" :disabled="uploading" @click="openUploadDialog">
          {{ uploading ? '上传中...' : '上传方案' }}
        </button>
      </div>
      <p v-if="selectedFileName" class="hint">已选择文件：{{ selectedFileName }}</p>
      <p v-if="uploadSuccess" class="success">上传成功，已加入方案列表。</p>
    </section>

    <section class="panel">
      <h3>方案列表</h3>
      <div class="toolbar list-toolbar">
        <input v-model.trim="keyword" type="text" placeholder="按方案名称搜索" @input="onFilterChange">
        <select v-model="status" @change="onFilterChange">
          <option value="">全部状态</option>
          <option value="draft">draft</option>
          <option value="submitted">submitted</option>
        </select>
      </div>
      <AsyncState :loading="loading" :error="error" :empty="!displayPlans.length" empty-text="暂无匹配结果，请调整筛选后重试。" @retry="loadPlans">
        <div class="list-meta">共 {{ displayTotal }} 条方案</div>
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th class="name-col">名称</th>
                <th class="version-col">版本</th>
                <th class="status-col">状态</th>
                <th>上传时间</th>
                <th class="action-col">操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in displayPlans" :key="item.projectKey">
                <td class="title-cell" :title="item.title || '未命名项目'">{{ shortTitle(item.title || '未命名项目') }}</td>
                <td>
                  <select class="version-select" :value="item.selectedVersionId" @change="onVersionChange(item, $event.target.value)">
                    <option v-for="ver in item.versions" :key="ver.id" :value="ver.id">V{{ ver.version || 1 }}</option>
                  </select>
                </td>
                <td><span class="status-chip">{{ item.status || 'draft' }}</span></td>
                <td>{{ formatDateTime(item.created_at) }}</td>
                <td class="actions">
                  <button type="button" class="ghost" @click="openPdf(item.selectedVersion)">查看</button>
                  <button type="button" class="ghost" :disabled="reviewing" @click="review(item.selectedVersion)">AI检阅</button>
                  <button
                    type="button"
                    class="primary"
                    :disabled="isSubmittedPlan(item.selectedVersion) || submittingPlanId === Number(item.selectedVersion.id)"
                    @click="openSubmit(item.selectedVersion)"
                  >
                    {{ submittingPlanId === Number(item.selectedVersion.id) ? '提交中...' : '提交教师' }}
                  </button>
                  <button
                    type="button"
                    class="ghost danger"
                    :disabled="deleteLoading && deletingProjectKey === item.projectKey"
                    @click="removeProject(item)"
                  >
                    {{ deleteLoading && deletingProjectKey === item.projectKey ? '删除中...' : '删除项目' }}
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <SimplePager :current-page="currentPage" :total="displayTotal" :page-size="pageSize" @update:currentPage="onPageChange" />
      </AsyncState>
    </section>

    <section v-if="diagnosis.summary || hasHypergraphDiagnosis" class="panel">
      <h3>超图诊断结果</h3>
      <HypergraphDiagnosisCard :meta="hypergraphMeta" :show-provenance="true" @trace-click="onTraceClick" />
    </section>

    <section v-if="activePlan" class="panel">
      <h3>方案预览与批注</h3>
      <PdfPreviewAnnotator
        ref="annotatorRef"
        :pdf-url="currentPdfUrl"
        :document-text="currentDocumentText"
        :annotations="annotations"
        :focus-keyword="focusKeyword"
      />
    </section>

    <section v-if="diagnosis.summary" class="panel">
      <h3>检阅摘要</h3>
      <ReviewSummaryPanel
        :summary="diagnosis.summary"
        :issues="diagnosis.issues || []"
        :guidance-questions="diagnosis.guidance_questions || []"
        :review-meta="diagnosis.review_meta || {}"
      />
    </section>

    <section v-if="showRubric" class="panel">
      <div class="rubric-head">
        <div>
          <h3>Rubric评分</h3>
          <p class="hint rubric-hint">本次检阅按维度展示评分与判断依据，便于你回看每一项为什么被扣分。</p>
        </div>
        <div v-if="rubricScoreText" class="rubric-total">
          <span class="rubric-total-label">平均分</span>
          <strong>{{ rubricScoreText }}</strong>
        </div>
      </div>
      <div class="table-wrap">
        <table class="rubric-table">
          <thead>
            <tr>
              <th>维度</th>
              <th class="rubric-score-col">分数</th>
              <th>说明</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(row, idx) in rubricRows" :key="`rubric-${idx}`">
              <td class="rubric-label">{{ row.label }}</td>
              <td class="rubric-score">{{ formatRubricScore(row.score) }}</td>
              <td>{{ row.reason || '已完成评分。' }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <section v-if="activePlan" class="panel">
      <h3>基于方案的追问对话</h3>
      <AgentChatWindow
        ref="chatWindowRef"
        title="文档追问"
        :messages="pdfChatRecords"
        :sessions="[]"
        :model-value="pdfChatQuestion"
        :loading="pdfChatLoading"
        :task-status="pdfTaskStatus"
        :task-error="pdfTaskError"
        :focus-keyword="chatFocusKeyword"
        placeholder="可追问：这条批注为什么这么判断？"
        @update:model-value="pdfChatQuestion = $event"
        @send="askPdfAi"
        @new-chat="resetPdfChat"
        @select-session="() => {}"
      />
    </section>

    <div v-if="submitDialog" class="modal-mask" @click.self="closeSubmitDialog">
      <section class="modal-card">
        <h3>提交给教师</h3>
        <div class="toolbar modal-toolbar">
          <select v-model="submitForm.teacherId">
            <option value="">选择教师</option>
            <option v-for="item in approvedTeachers" :key="item.teacher || item.teacher_id || item.id" :value="item.teacher || item.teacher_id || item.id">
              {{ item.teacher_name }}
            </option>
          </select>
          <input v-model.trim="submitForm.note" type="text" placeholder="备注：例如重点修改了用户画像">
        </div>
        <div class="toolbar modal-actions">
          <button type="button" class="primary" :disabled="submittingPlanId === Number(activePlan?.id || 0)" @click="submitToTeacher">
            {{ submittingPlanId === Number(activePlan?.id || 0) ? '提交中...' : '确认提交' }}
          </button>
          <button type="button" class="ghost" :disabled="submittingPlanId === Number(activePlan?.id || 0)" @click="closeSubmitDialog">取消</button>
        </div>
      </section>
    </div>

    <div v-if="deleteDialog" class="modal-mask" @click.self="closeDeleteDialog">
      <section class="modal-card">
        <h3>删除项目</h3>
        <p class="hint">
          删除某版本（V{{ deleteTarget?.selectedVersion?.version || 1 }}）的项目《{{ deleteTarget?.title || '未命名项目' }}》还是删除所有项目？
        </p>
        <div class="toolbar modal-actions">
          <button type="button" class="ghost danger-outline" :disabled="deleteLoading" @click="executeDelete('single')">
            {{ deleteLoadingAction === 'single' ? '删除中...' : '仅删除该版本' }}
          </button>
          <button type="button" class="danger-solid" :disabled="deleteLoading" @click="executeDelete('project')">
            {{ deleteLoadingAction === 'project' ? '删除中...' : '删除所有' }}
          </button>
          <button type="button" class="ghost" :disabled="deleteLoading" @click="closeDeleteDialog">取消</button>
        </div>
      </section>
    </div>

    <div v-if="uploadDialog" class="modal-mask" @click.self="closeUploadDialog">
      <section class="modal-card">
        <h3>确认上传方式</h3>
        <div class="toolbar modal-toolbar">
          <select v-model="uploadMode" @change="onUploadModeChange">
            <option value="new">新建项目</option>
            <option value="update">更新已有项目</option>
          </select>
          <input v-if="uploadMode === 'new'" v-model.trim="uploadForm.title" type="text" placeholder="新建项目名称">
          <select v-else v-model="selectedBasePlanId">
            <option value="">选择要更新的项目</option>
            <option v-for="item in basePlanOptions" :key="item.id" :value="item.id">
              {{ item.title || item.name || item.id }}
            </option>
          </select>
        </div>
        <div class="toolbar modal-actions">
          <button type="button" class="primary" :disabled="uploading" @click="uploadConfirm">确认上传</button>
          <button type="button" class="ghost" :disabled="uploading" @click="closeUploadDialog">取消</button>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue';
import { ElMessage } from 'element-plus';
import AsyncState from '../../../components/core/AsyncState.vue';
import SimplePager from '../../../components/core/SimplePager.vue';
import AgentChatWindow from '../../../components/AgentChatWindow.vue';
import PdfPreviewAnnotator from '../../../components/PdfPreviewAnnotator.vue';
import HypergraphDiagnosisCard from '../../../components/review/HypergraphDiagnosisCard.vue';
import ReviewSummaryPanel from '../../../components/review/ReviewSummaryPanel.vue';
import {
  createAgentTaskApi,
  deletePlanApi,
  genReviewAsyncApi,
  listMentorApplicationsApi,
  listPlanReviewsApi,
  listPlansApi,
  pdfChatHistoryApi,
  reviewTaskStatusApi,
  submitPlanApi,
  uploadPlanApi,
  waitAgentTaskApi
} from '../../../api/student';
import { compactQuery, normalizePagedResult } from '../../../composables/list';
import { formatDateTime } from '../../../utils/datetime';

const plans = ref([]);
const allPlans = ref([]);
const loading = ref(false);
const reviewing = ref(false);
const error = ref('');
const keyword = ref('');
const status = ref('');
const currentPage = ref(1);
const pageSize = 5;
const uploadForm = reactive({ title: '' });
const uploadMode = ref('new');
const selectedBasePlanId = ref('');
const file = ref(null);
const selectedFileName = ref('');
const uploadDialog = ref(false);
const uploading = ref(false);
const uploadSuccess = ref(false);
const activePlan = ref(null);
const currentPdfUrl = ref('');
const currentDocumentText = ref('');
const annotations = ref([]);
const diagnosis = ref({});
const rubricRows = ref([]);
const focusKeyword = ref('');
const chatFocusKeyword = ref('');
const pdfChatRecords = ref([{ role: 'ai', content: '我已读取并完成检阅。你可以继续追问批注细节。' }]);
const pdfChatQuestion = ref('');
const pdfChatLoading = ref(false);
const pdfTaskStatus = ref('');
const pdfTaskError = ref('');
const submitDialog = ref(false);
const submitForm = reactive({ teacherId: '', note: '' });
const approvedTeachers = ref([]);
const submittingPlanId = ref(0);
const submittedPlanMap = ref({});
const deletingProjectKey = ref('');
const deleteDialog = ref(false);
const deleteTarget = ref(null);
const deleteLoading = ref(false);
const deleteLoadingAction = ref('');
const annotatorRef = ref(null);
const chatWindowRef = ref(null);
const ACTIVE_PLAN_KEY = 'studentActivePlanId';
const PDF_CHAT_PENDING_KEY = 'studentPdfChatPendingTask';

const groupedPlans = computed(() => {
  const map = new Map();
  for (const row of allPlans.value || []) {
    const key = String(row.project_id || row.project_key || row.root_plan_id || row.base_plan_id || row.title || row.name || row.id);
    if (!map.has(key)) {
      map.set(key, []);
    }
    map.get(key).push(row);
  }

  return Array.from(map.entries()).map(([projectKey, rows]) => {
    const versions = [...rows].sort((a, b) => Number(b.version || 1) - Number(a.version || 1));
    const latest = versions[0] || {};
    const opened = versions.find((item) => Number(item.id) === Number(activePlan.value?.id));
    const selected = opened || latest;
    return {
      projectKey,
      title: selected.title || selected.name || '未命名项目',
      status: selected.status,
      created_at: selected.created_at,
      versions,
      selectedVersionId: selected.id,
      selectedVersion: selected
    };
  });
});

const displayPlans = computed(() => {
  const start = (currentPage.value - 1) * pageSize;
  return groupedPlans.value.slice(start, start + pageSize);
});
const displayTotal = computed(() => groupedPlans.value.length);
const isIncomplete = computed(() => diagnosis.value?.review_meta?.is_complete === false);
const showRubric = computed(() => !isIncomplete.value && rubricRows.value.length > 0);
const rubricScoreValue = computed(() => {
  const score = Number(diagnosis.value?.total_score ?? diagnosis.value?.review_meta?.total_score);
  return Number.isFinite(score) ? score : null;
});
const rubricScoreMax = computed(() => {
  const scoreMax = Number(diagnosis.value?.score_max ?? diagnosis.value?.review_meta?.score_max ?? 5);
  return Number.isFinite(scoreMax) && scoreMax > 0 ? scoreMax : 5;
});
const rubricScoreText = computed(() => {
  if (rubricScoreValue.value == null) return '';
  return `${formatRubricScore(rubricScoreValue.value)} / ${formatRubricScore(rubricScoreMax.value)}`;
});
const hypergraphMeta = computed(() => diagnosis.value?.review_meta?.hypergraph || {});
const hasHypergraphDiagnosis = computed(() => Object.keys(hypergraphMeta.value || {}).length > 0);
const basePlanOptions = computed(() => groupedPlans.value.map((row) => row.selectedVersion));
const isSubmittedPlan = (plan) => {
  const id = Number(plan?.id || 0);
  if (!id) return String(plan?.status || '').toLowerCase() === 'submitted';
  return String(plan?.status || '').toLowerCase() === 'submitted' || Boolean(submittedPlanMap.value[id]);
};
const markPlanSubmitted = (planId) => {
  const id = Number(planId || 0);
  if (!id) return;
  submittedPlanMap.value = {
    ...submittedPlanMap.value,
    [id]: true
  };
};
const applySubmittedToLocal = (planId) => {
  const id = Number(planId || 0);
  if (!id) return;
  markPlanSubmitted(id);
  allPlans.value = (allPlans.value || []).map((item) => (Number(item?.id) === id ? { ...item, status: 'submitted' } : item));
  plans.value = (plans.value || []).map((item) => (Number(item?.id) === id ? { ...item, status: 'submitted' } : item));
  if (Number(activePlan.value?.id) === id) {
    activePlan.value = { ...(activePlan.value || {}), status: 'submitted' };
  }
};

const loadPlans = async () => {
  loading.value = true;
  error.value = '';
  try {
    const params = compactQuery({
      page: 1,
      page_size: 200,
      q: keyword.value,
      status: status.value
    });
    const res = await listPlansApi(params);
    const normalized = normalizePagedResult(res);
    allPlans.value = normalized.items;
    plans.value = normalized.items;
    const nextSubmittedMap = {};
    for (const item of normalized.items || []) {
      if (String(item?.status || '').toLowerCase() === 'submitted' && Number(item?.id || 0)) {
        nextSubmittedMap[Number(item.id)] = true;
      }
    }
    submittedPlanMap.value = nextSubmittedMap;
    const maxPage = Math.max(1, Math.ceil(groupedPlans.value.length / pageSize));
    if (currentPage.value > maxPage) {
      currentPage.value = maxPage;
    }
  } catch (e) {
    error.value = e?.response?.data?.detail || '方案列表加载失败';
    allPlans.value = [];
    plans.value = [];
  } finally {
    loading.value = false;
  }
};

const fetchApprovedTeachers = async () => {
  const list = await listMentorApplicationsApi({ status: 'approved', page: 1, page_size: 200 });
  approvedTeachers.value = normalizePagedResult(list).items || [];
};

const onFilterChange = async () => {
  currentPage.value = 1;
  await loadPlans();
};

const onPageChange = async (page) => {
  currentPage.value = page;
};

const onUploadModeChange = () => {
  selectedBasePlanId.value = '';
};

const onFileChange = (event) => {
  file.value = event.target.files?.[0] || null;
  selectedFileName.value = file.value?.name || '';
  if (uploadMode.value === 'new' && file.value && !uploadForm.title) {
    uploadForm.title = file.value.name.replace(/\.(pdf|doc|docx)$/i, '');
  }
};

const shortTitle = (text) => {
  const raw = String(text || '');
  if (raw.length <= 16) return raw;
  return `${raw.slice(0, 16)}...`;
};

const formatRubricScore = (value) => {
  const num = Number(value);
  if (!Number.isFinite(num)) return '--';
  if (Number.isInteger(num)) return String(num);
  return num.toFixed(num >= 10 ? 0 : 1).replace(/\.0$/, '');
};

const onVersionChange = async (row, versionId) => {
  const selected = (row.versions || []).find((item) => String(item.id) === String(versionId));
  if (!selected) return;
  await openPdf(selected);
};

const openUploadDialog = () => {
  if (!file.value) {
    error.value = '请先选择PDF或Word文件';
    return;
  }
  uploadDialog.value = true;
};

const closeUploadDialog = () => {
  if (uploading.value) return;
  uploadDialog.value = false;
};

const uploadConfirm = async () => {
  if (!file.value) {
    error.value = '请先选择PDF或Word文件';
    return;
  }
  if (uploadMode.value === 'new' && !uploadForm.title.trim()) {
    error.value = '新建项目请填写项目名称';
    return;
  }
  if (uploadMode.value === 'update' && !selectedBasePlanId.value) {
    error.value = '请选择要更新的项目';
    return;
  }

  const fd = new FormData();
  if (uploadMode.value === 'new') {
    fd.append('title', uploadForm.title.trim());
  } else {
    fd.append('base_plan_id', String(selectedBasePlanId.value));
  }
  fd.append('pdf_file', file.value);
  uploading.value = true;
  uploadSuccess.value = false;
  try {
    await uploadPlanApi(fd);
    uploadForm.title = '';
    file.value = null;
    selectedFileName.value = '';
    uploadDialog.value = false;
    uploadSuccess.value = true;
    await loadPlans();
  } finally {
    uploading.value = false;
  }
};

const applyReviewResult = (reviewData) => {
  if (!reviewData) return;
  diagnosis.value = { ...reviewData };
  rubricRows.value = (reviewData.dimension_scores || reviewData.review_meta?.dimension_scores || []).map((row, idx) => ({
    label: row.label || row.dimension || row.name || `R${idx + 1}`,
    score: row.score,
    reason: row.reason || row.comment || row.suggestion || ''
  }));
  annotations.value = reviewData.annotations || [];
  focusKeyword.value = '';
  chatFocusKeyword.value = '';
};

const onTraceClick = async (item) => {
  const keyword = String(item?.text || item?.node_name || item?.node_id || '').trim();
  if (!keyword) return;
  focusKeyword.value = keyword;
  chatFocusKeyword.value = keyword;
  if (annotatorRef.value?.focusByText) {
    await annotatorRef.value.focusByText(keyword);
  }
};

const loadLatestReview = async (planId) => {
  const reviews = await listPlanReviewsApi(planId, { status: 'student' });
  const latest = (reviews?.items || reviews || []).find((item) => item.audience_role === 'student') || (reviews?.items || reviews || [])[0];
  if (latest) {
    applyReviewResult(latest);
  } else {
    diagnosis.value = {};
    annotations.value = [];
    rubricRows.value = [];
  }
};

const loadPdfChatHistory = async (planId) => {
  try {
    const res = await pdfChatHistoryApi(planId);
    const historyMessages = res.messages || [];
    if (historyMessages.length) {
      pdfChatRecords.value = historyMessages;
      return;
    }
  } catch (_) {
    // ignore
  }
  pdfChatRecords.value = [{ role: 'ai', content: '我已读取并完成检阅。你可以继续追问批注细节。' }];
};

const openPdf = async (row) => {
  currentPdfUrl.value = row.pdf_file;
  currentDocumentText.value = row.extracted_text || '';
  activePlan.value = row;
  localStorage.setItem(ACTIVE_PLAN_KEY, String(row.id));
  await loadLatestReview(row.id);
  await loadPdfChatHistory(row.id);
};

const review = async (row) => {
  reviewing.value = true;
  try {
    await openPdf(row);
    const task = await genReviewAsyncApi({ plan_id: row.id, audience_role: 'student' });
    const taskId = Number(task?.task_id || 0);
    if (!taskId) {
      throw new Error('检阅任务创建失败');
    }

    const startedAt = Date.now();
    let reviewData = null;
    while (Date.now() - startedAt < 10 * 60 * 1000) {
      const statusRes = await reviewTaskStatusApi(taskId);
      const statusText = String(statusRes?.status || '').toLowerCase();
      if (statusText === 'done') {
        reviewData = statusRes?.review || null;
        break;
      }
      if (statusText === 'error') {
        throw new Error(statusRes?.error || '检阅任务执行失败');
      }
      await new Promise((resolve) => setTimeout(resolve, 2000));
    }

    if (reviewData) {
      applyReviewResult(reviewData);
    } else {
      await loadLatestReview(row.id);
    }
    await loadPdfChatHistory(row.id);
  } catch (e) {
    error.value = e?.response?.data?.message || e?.message || '检阅失败';
  } finally {
    reviewing.value = false;
  }
};

const removeProject = async (projectRow) => {
  if (!projectRow?.selectedVersion?.id) {
    error.value = '未找到可删除的项目版本';
    return;
  }
  deleteTarget.value = projectRow;
  deleteDialog.value = true;
};

const closeDeleteDialog = () => {
  if (deleteLoading.value) return;
  deleteDialog.value = false;
  deleteTarget.value = null;
};

const resetActivePlan = () => {
  activePlan.value = null;
  currentPdfUrl.value = '';
  currentDocumentText.value = '';
  diagnosis.value = {};
  annotations.value = [];
  rubricRows.value = [];
  localStorage.removeItem(ACTIVE_PLAN_KEY);
};

const executeDelete = async (scope) => {
  const target = deleteTarget.value;
  const selectedVersion = target?.selectedVersion
    || (target?.versions || []).find((item) => String(item?.id) === String(target?.selectedVersionId))
    || (target?.versions || [])[0]
    || null;
  const selectedVersionId = Number(selectedVersion?.id || 0);
  if (!selectedVersionId) {
    ElMessage.error('未找到可删除的版本');
    return;
  }
  if (deleteLoading.value) return;

  deleteLoading.value = true;
  deleteLoadingAction.value = scope;
  deletingProjectKey.value = String(target?.projectKey || 'deleting');
  try {
    if (scope === 'project') {
      const targetTitle = String(target?.title || '');
      await deletePlanApi(selectedVersionId, { scope: 'project' });
      if (String(activePlan.value?.title || '') === targetTitle) {
        resetActivePlan();
      }
      ElMessage.success('已删除所有版本');
    } else {
      await deletePlanApi(selectedVersionId);
      if (Number(activePlan.value?.id || 0) === selectedVersionId) {
        resetActivePlan();
      }
      ElMessage.success('已删除该版本');
    }
    deleteDialog.value = false;
    deleteTarget.value = null;
    await loadPlans();
  } catch (e) {
    error.value = e?.response?.data?.message || e?.response?.data?.detail || '删除失败';
    ElMessage.error(error.value);
  } finally {
    deleteLoading.value = false;
    deleteLoadingAction.value = '';
    deletingProjectKey.value = '';
  }
};

const openSubmit = async (row) => {
  if (isSubmittedPlan(row) || submittingPlanId.value === Number(row?.id || 0)) return;
  if (!approvedTeachers.value.length) {
    await fetchApprovedTeachers();
  }
  if (!approvedTeachers.value.length) {
    error.value = '暂无已通过的导师，请先在“教师连接”申请并通过审核';
    return;
  }
  activePlan.value = row;
  submitForm.teacherId = '';
  submitForm.note = '';
  submitDialog.value = true;
};

const closeSubmitDialog = () => {
  if (submittingPlanId.value === Number(activePlan.value?.id || 0)) return;
  submitDialog.value = false;
};

const submitToTeacher = async () => {
  if (!activePlan.value?.id) {
    error.value = '未找到可提交的方案';
    return;
  }
  if (isSubmittedPlan(activePlan.value)) {
    submitDialog.value = false;
    ElMessage.info('该方案已是 submitted 状态');
    return;
  }
  if (submittingPlanId.value === Number(activePlan.value.id)) return;
  if (!submitForm.teacherId) {
    error.value = '请选择教师';
    return;
  }

  try {
    submittingPlanId.value = Number(activePlan.value.id);
    const res = await submitPlanApi(activePlan.value.id, {
      teacher_id: submitForm.teacherId,
      note: submitForm.note
    });
    const submittedPlan = res?.plan || null;
    const submittedId = Number(submittedPlan?.id || activePlan.value.id || 0);
    applySubmittedToLocal(submittedId);
    submitDialog.value = false;
    submitForm.note = '';
    submitForm.teacherId = '';
    ElMessage.success('方案已提交给教师');
    await loadPlans();
  } catch (e) {
    error.value = e?.response?.data?.message || e?.response?.data?.detail || '提交教师失败';
  } finally {
    submittingPlanId.value = 0;
  }
};

const onPdfTaskStatusChange = ({ status, error: taskError }) => {
  pdfTaskStatus.value = status || '';
  pdfTaskError.value = taskError || '';
};

const settlePdfTaskStatus = () => {
  if (pdfTaskStatus.value !== 'done') return;
  setTimeout(() => {
    if (pdfTaskStatus.value === 'done') pdfTaskStatus.value = '';
  }, 1200);
};

const askPdfAi = async () => {
  if (!activePlan.value || !pdfChatQuestion.value.trim()) return;
  const question = pdfChatQuestion.value.trim();
  pdfChatRecords.value.push({ role: 'student', content: question });
  pdfChatLoading.value = true;
  pdfTaskError.value = '';
  try {
    const task = await createAgentTaskApi({
      agent: 'pdf_chat',
      payload: { plan_id: activePlan.value.id, question, review_id: diagnosis.value.id }
    });
    localStorage.setItem(PDF_CHAT_PENDING_KEY, JSON.stringify({ taskId: task.task_id }));
    const res = await waitAgentTaskApi(task.task_id, { onStatusChange: onPdfTaskStatusChange });
    localStorage.removeItem(PDF_CHAT_PENDING_KEY);
    if (!res?.answer) {
      throw new Error('任务结果为空');
    }
    pdfChatRecords.value.push({ role: 'ai', content: res.answer });
    pdfChatQuestion.value = '';
  } finally {
    pdfChatLoading.value = false;
    settlePdfTaskStatus();
  }
};

const resumePendingPdfChatTask = async () => {
  const raw = localStorage.getItem(PDF_CHAT_PENDING_KEY);
  if (!raw) return;
  try {
    const pending = JSON.parse(raw);
    if (!pending?.taskId) {
      localStorage.removeItem(PDF_CHAT_PENDING_KEY);
      return;
    }
    pdfChatLoading.value = true;
    const res = await waitAgentTaskApi(Number(pending.taskId), { onStatusChange: onPdfTaskStatusChange });
    localStorage.removeItem(PDF_CHAT_PENDING_KEY);
    if (!res?.answer) throw new Error('任务结果为空');
    pdfChatRecords.value.push({ role: 'ai', content: res.answer });
  } finally {
    pdfChatLoading.value = false;
    settlePdfTaskStatus();
  }
};

const resetPdfChat = () => {
  pdfChatRecords.value = [{ role: 'ai', content: '新对话已创建，请继续提问。' }];
};

onMounted(async () => {
  await loadPlans();
  await fetchApprovedTeachers();
  const activePlanId = Number(localStorage.getItem(ACTIVE_PLAN_KEY) || 0);
  if (activePlanId) {
    const selected = (allPlans.value || []).find((item) => Number(item.id) === activePlanId);
    if (selected) {
      await openPdf(selected);
    }
  }
  await resumePendingPdfChatTask();
});
</script>

<style scoped>
.page-grid {
  display: grid;
  gap: 16px;
}

.panel {
  border: 1px solid var(--line-strong);
  background: var(--bg-panel);
  padding: 18px;
}

.kicker {
  margin: 0;
  font-size: 12px;
  color: var(--ink-muted);
  letter-spacing: 0.15em;
  text-transform: uppercase;
}

h2,
h3 {
  margin: 10px 0 0;
  color: var(--ink-title);
  font-family: var(--font-display);
}

.toolbar {
  margin-top: 12px;
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
}

.toolbar > input,
.toolbar > select {
  flex: 1 1 220px;
  min-width: 0;
}

.toolbar > button {
  flex: 0 0 auto;
}

input,
select {
  height: var(--control-height);
  border: 1px solid var(--line-strong);
  background: var(--bg-field);
  color: var(--ink-title);
  padding: 0 10px;
  border-radius: var(--control-radius);
}

table {
  width: 100%;
  margin-top: 12px;
  border-collapse: separate;
  border-spacing: 0;
  table-layout: fixed;
}

th,
td {
  text-align: left;
  padding: 12px 10px;
  border-bottom: 1px solid var(--table-border);
  vertical-align: top;
}

th {
  color: var(--ink-muted);
  font-size: 12px;
  font-weight: 600;
  background: color-mix(in oklch, var(--bg-field) 84%, white);
}

tbody tr:hover td {
  background: var(--table-hover-bg);
}

.actions {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}

.actions button {
  min-height: 30px;
  padding: 0 10px;
  font-size: 12px;
  white-space: nowrap;
}

.name-col {
  width: 260px;
}

.version-col {
  width: 94px;
}

.status-col {
  width: 108px;
}

.action-col {
  width: 300px;
}

.version-select {
  min-width: 88px;
  height: 34px;
}

.list-meta {
  margin-top: 12px;
  color: var(--ink-muted);
  font-size: 13px;
}

.table-wrap {
  overflow-x: auto;
}

.title-cell {
  font-weight: 600;
  color: var(--ink-title);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.status-chip {
  display: inline-flex;
  align-items: center;
  height: 28px;
  padding: 0 10px;
  border-radius: 999px;
  border: 1px solid var(--line-soft);
  background: color-mix(in oklch, var(--bg-field) 88%, white);
  font-variant-numeric: tabular-nums;
}

button.primary,
button.ghost {
  min-height: 36px;
  padding: 0 14px;
  border: 1px solid var(--accent);
  cursor: pointer;
  border-radius: 999px;
}

button.primary {
  background: var(--accent);
  color: #fff;
}

button.ghost {
  background: color-mix(in oklch, var(--bg-field) 90%, white);
  color: var(--ink-body);
}

button.ghost.danger {
  border-color: var(--danger);
  color: var(--danger);
}

.modal-actions .danger-outline {
  border-color: #c0392b;
  color: #c0392b;
}

.modal-actions .danger-solid {
  min-height: 36px;
  padding: 0 14px;
  border: 1px solid #c0392b;
  border-radius: 999px;
  background: #c0392b;
  color: #fff;
  cursor: pointer;
}

.modal-actions .danger-solid:disabled,
.modal-actions .danger-outline:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.success {
  margin-top: 8px;
  color: oklch(0.46 0.12 160);
}

.rubric-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 12px;
}

.rubric-hint {
  margin-top: 6px;
}

.rubric-total {
  min-width: 132px;
  padding: 12px 14px;
  border: 1px solid var(--line-strong);
  border-radius: 14px;
  background: color-mix(in oklch, var(--bg-field) 86%, white);
  text-align: right;
}

.rubric-total-label {
  display: block;
  color: var(--ink-muted);
  font-size: 12px;
}

.rubric-total strong {
  display: block;
  margin-top: 4px;
  font-size: 22px;
  color: var(--ink-title);
}

.rubric-table .rubric-score-col {
  width: 96px;
}

.rubric-label {
  font-weight: 600;
  color: var(--ink-title);
}

.rubric-score {
  font-weight: 700;
  color: var(--accent);
}

.hint {
  margin-top: 8px;
  color: var(--ink-muted);
  font-size: 13px;
}

.modal-mask {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.45);
  z-index: 1200;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 16px;
}

.modal-card {
  width: min(640px, 100%);
  border: 1px solid var(--line-strong);
  background: color-mix(in oklch, var(--bg-panel) 96%, white);
  padding: 18px;
  border-radius: 16px;
  box-shadow: var(--shadow-mid);
}

.modal-toolbar > input,
.modal-toolbar > select {
  flex: 1 1 100%;
}

.modal-actions {
  justify-content: flex-end;
}

@media (max-width: 768px) {
  .rubric-head {
    flex-direction: column;
  }

  .rubric-total {
    width: 100%;
    text-align: left;
  }
}

</style>

