<template>
  <div class="page-grid">
    <section class="panel lead">
      <p class="kicker">Review Center</p>
      <h2>先选学生，再选项目评审</h2>
      <p>按学生聚焦查看项目，生成并编辑教师评审建议。</p>
    </section>

    <section class="panel">
      <h3>选择项目</h3>
      <div class="toolbar">
        <select v-model="selectedStudentKey" @change="onStudentChange">
          <option value="">请选择学生</option>
          <option v-for="item in studentOptions" :key="item.key" :value="item.key">{{ item.label }}</option>
        </select>
        <select v-model="selectedPlanId" :disabled="!selectedStudentKey" @change="onPlanChange">
          <option value="">请选择项目</option>
          <option v-for="item in filteredPlans" :key="item.id" :value="item.id">{{ item.name || item.title || item.id }}</option>
        </select>
        <button type="button" class="ghost" :disabled="!selectedPlanId" @click="previewPdf(activePlan)">预览方案</button>
        <button type="button" class="primary" :disabled="!selectedPlanId || generatingPlanId" @click="genReview(activePlan)">
          {{ generatingPlanId ? '生成中...' : '生成教师建议' }}
        </button>
        <button type="button" class="ghost danger" :disabled="!selectedPlanId" @click="removePlan(activePlan)">删除方案</button>
      </div>
    </section>

    <section class="panel" v-if="activePlan">
      <h3>方案预览</h3>
      <PdfPreviewAnnotator
        :pdf-url="currentPdfUrl"
        :document-text="currentDocumentText"
        :annotations="review.annotations || []"
        :focus-keyword="focusKeyword"
      />
    </section>

    <section class="panel" v-if="review.summary">
      <h3>教师建议</h3>
      <div ref="summaryRef" class="summary markdown-summary" v-html="renderMarkdown(review.summary)"></div>
      <div class="issues" v-if="(review.issues || []).length">
        <strong>问题清单</strong>
        <ul>
          <li v-for="(item, idx) in review.issues" :key="`issue-${idx}`" :class="{ focused: focusedIssueIndex === idx }">{{ item.description || item }}</li>
        </ul>
      </div>
      <div class="issues" v-if="(review.guidance_questions || []).length">
        <strong>引导问题</strong>
        <ul>
          <li v-for="(item, idx) in review.guidance_questions" :key="`q-${idx}`">{{ item }}</li>
        </ul>
      </div>
      <div class="issues" v-if="rubricRows.length">
        <strong>Rubric 评分</strong>
        <ul>
          <li v-for="(item, idx) in rubricRows" :key="`r-${idx}`">
            <span>{{ item.label }}：{{ item.score }}</span>
            <small>{{ item.reason || '无评语' }}</small>
          </li>
        </ul>
      </div>
      <div class="toolbar">
        <textarea v-model="suggestionText" rows="4" placeholder="可补充个性化教师建议"></textarea>
        <button type="button" class="primary" :disabled="!review.id" @click="saveReview">保存批阅编辑</button>
      </div>
    </section>

    <div v-if="mermaidPreviewVisible" class="mermaid-preview-mask" @click.self="closeMermaidPreview">
      <div class="mermaid-preview-panel" role="dialog" aria-modal="true" aria-label="Mermaid 图预览">
        <div class="mermaid-preview-toolbar">
          <strong>图谱预览</strong>
          <button type="button" class="preview-btn close-btn" @click="closeMermaidPreview">关闭</button>
        </div>
        <div class="mermaid-preview-body">
          <div class="mermaid-preview-canvas" v-html="mermaidPreviewSvg"></div>
        </div>
      </div>
    </div>

    <section class="panel" v-if="review.summary || hasHypergraphDiagnosis">
      <h3>超图诊断结果</h3>
      <HypergraphDiagnosisCard :meta="hypergraphMeta" :show-provenance="true" @trace-click="jumpFromTrace" />
    </section>

    <section class="panel" v-if="activePlan">
      <h3>教师 AI 对话</h3>
      <AgentChatWindow
        title="教师AI对话（当前方案上下文）"
        :messages="aiChat"
        :sessions="history"
        :model-value="chatQuestion"
        :loading="chatLoading"
        :focus-keyword="chatFocusKeyword"
        placeholder="可提问：这个项目盈利模式如何优化？"
        @update:model-value="chatQuestion = $event"
        @send="askAi"
        @new-chat="newChat"
        @select-session="loadHistory"
        @delete-session="deleteSession"
      />
    </section>
  </div>
</template>

<script setup>
import mermaid from 'mermaid';
import MarkdownIt from 'markdown-it';
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import AgentChatWindow from '../../../components/AgentChatWindow.vue';
import PdfPreviewAnnotator from '../../../components/PdfPreviewAnnotator.vue';
import HypergraphDiagnosisCard from '../../../components/review/HypergraphDiagnosisCard.vue';
import {
  deletePlanApi,
  genTeacherReviewAsyncApi,
  listPlanReviewsApi,
  listPlansApi,
  reviewTaskStatusApi,
  teacherAiChatApi,
  updateReviewApi
} from '../../../api/teacher';
import { asArray } from '../../../composables/list';

const plans = ref([]);
const selectedStudentKey = ref('');
const selectedPlanId = ref('');
const activePlan = ref(null);
const review = ref({});
const suggestionText = ref('');
const currentPdfUrl = ref('');
const currentDocumentText = ref('');
const generatingPlanId = ref(null);
const pollingTimer = ref(null);
const summaryRef = ref(null);
const chatQuestion = ref('');
const chatLoading = ref(false);
const aiChat = ref([{ role: 'ai', text: '你好，我可以结合当前方案与诊断结果提供讲解与优化思路。' }]);
const history = ref([]);
const focusKeyword = ref('');
const chatFocusKeyword = ref('');
const focusedIssueIndex = ref(-1);
const mermaidPreviewVisible = ref(false);
const mermaidPreviewSvg = ref('');
const ACTIVE_PLAN_KEY = 'teacherReviewActivePlanId';
const PENDING_TASK_KEY = 'teacherReviewPendingTask';
const PLAN_REFRESH_MS = 15000;
const markdown = new MarkdownIt({ html: false, linkify: true, breaks: true });
let planRefreshTimer = null;

mermaid.initialize({ startOnLoad: false, securityLevel: 'loose' });

const renderMarkdown = (content) => markdown.render(String(content || ''));
const closeMermaidPreview = () => {
  mermaidPreviewVisible.value = false;
  mermaidPreviewSvg.value = '';
};
const openMermaidPreview = (svgMarkup) => {
  if (!svgMarkup) return;
  mermaidPreviewSvg.value = svgMarkup;
  mermaidPreviewVisible.value = true;
};

const getPlanStudentKey = (plan) => {
  return String(
    plan?.student_id ||
    plan?.student ||
    plan?.student_name ||
    plan?.owner ||
    plan?.owner_name ||
    ''
  ).trim();
};

const getPlanStudentLabel = (plan) => {
  return String(plan?.student_name || plan?.student || plan?.owner_name || plan?.owner || '未知学生').trim();
};

const studentOptions = computed(() => {
  const map = new Map();
  for (const plan of plans.value || []) {
    const key = getPlanStudentKey(plan);
    if (!key) continue;
    if (!map.has(key)) {
      map.set(key, getPlanStudentLabel(plan));
    }
  }
  return Array.from(map.entries()).map(([key, label]) => ({ key, label }));
});

const filteredPlans = computed(() => {
  if (!selectedStudentKey.value) return [];
  return (plans.value || []).filter((plan) => getPlanStudentKey(plan) === selectedStudentKey.value);
});

const rubricRows = computed(() => {
  const rows = review.value.dimension_scores || review.value.review_meta?.dimension_scores || [];
  return rows.map((item, idx) => ({
    label: item.label || item.dimension || item.name || `R${idx + 1}`,
    score: item.score,
    reason: item.reason || item.comment || item.suggestion || ''
  }));
});

const hypergraphMeta = computed(() => review.value.review_meta?.hypergraph || {});
const hasHypergraphDiagnosis = computed(() => Object.keys(hypergraphMeta.value || {}).length > 0);

const stopTaskPolling = () => {
  if (pollingTimer.value) {
    clearInterval(pollingTimer.value);
    pollingTimer.value = null;
  }
};

const applyReview = (payload) => {
  if (!payload) return;
  review.value = payload;
  suggestionText.value = (payload.suggestions || []).join('\n');
  focusedIssueIndex.value = -1;
  focusKeyword.value = '';
  chatFocusKeyword.value = '';
};

const textHit = (a, b) => {
  const left = String(a || '').trim().toLowerCase();
  const right = String(b || '').trim().toLowerCase();
  if (!left || !right || right.length < 3) return false;
  return left.includes(right) || right.includes(left);
};

const jumpFromTrace = (item) => {
  const keywordText = String(item?.text || item?.node_name || '').trim();
  if (!keywordText) return;
  const issueIdx = (review.value.issues || []).findIndex((row) => textHit(row?.description, keywordText) || textHit(row?.snippet, keywordText));
  if (issueIdx >= 0) {
    focusedIssueIndex.value = issueIdx;
    return;
  }
  if ((review.value.annotations || []).some((row) => textHit(row?.description, keywordText) || textHit(row?.question, keywordText))) {
    focusKeyword.value = keywordText;
    return;
  }
  if ((aiChat.value || []).some((msg) => msg?.role === 'ai' && textHit(msg?.content || msg?.text, keywordText))) {
    chatFocusKeyword.value = keywordText;
  }
};

const renderMermaidInSummary = async () => {
  await nextTick();
  if (!summaryRef.value) return;
  const root = summaryRef.value;
  const codeBlocks = root.querySelectorAll('pre code.language-mermaid, pre code.lang-mermaid');
  codeBlocks.forEach((code) => {
    const pre = code.closest('pre');
    if (!pre) return;
    const node = document.createElement('div');
    node.className = 'mermaid';
    node.textContent = code.textContent || '';
    pre.replaceWith(node);
  });
  const mermaidNodes = root.querySelectorAll('.mermaid');
  if (mermaidNodes.length) {
    await mermaid.run({ nodes: Array.from(mermaidNodes) });
    mermaidNodes.forEach((node) => {
      const svg = node.querySelector('svg');
      if (!svg) return;
      svg.removeAttribute('width');
      svg.removeAttribute('height');
      if (!svg.getAttribute('viewBox')) {
        try {
          const box = svg.getBBox();
          if (box.width > 0 && box.height > 0) {
            svg.setAttribute('viewBox', `0 0 ${box.width} ${box.height}`);
          }
        } catch (_) {
          // keep original geometry when bbox is unavailable
        }
      }
      svg.style.display = 'block';
      svg.style.height = 'auto';
      svg.style.width = 'auto';
      svg.style.maxWidth = '100%';
      svg.style.maxHeight = '100%';
      node.classList.add('mermaid-fit');
      node.style.cursor = 'zoom-in';

      if (!node.dataset.previewBound) {
        node.dataset.previewBound = '1';
        node.addEventListener('click', () => {
          const currentSvg = node.querySelector('svg');
          if (currentSvg) {
            openMermaidPreview(currentSvg.outerHTML);
          }
        });
      }
    });
  }
};

const loadLatestTeacherReview = async (planId) => {
  const list = await listPlanReviewsApi(planId, { status: 'teacher' });
  const latestTeacher = (list?.items || list || []).find((item) => item.audience_role === 'teacher') || null;
  if (latestTeacher) {
    applyReview(latestTeacher);
  } else {
    review.value = {};
  }
};

const previewPdf = async (row) => {
  if (!row) return;
  activePlan.value = row;
  selectedPlanId.value = String(row.id);
  currentPdfUrl.value = row.pdf_file;
  currentDocumentText.value = row.extracted_text || '';
  localStorage.setItem(ACTIVE_PLAN_KEY, String(row.id));
  await loadLatestTeacherReview(row.id);
};

const onStudentChange = () => {
  selectedPlanId.value = '';
  activePlan.value = null;
  currentPdfUrl.value = '';
  currentDocumentText.value = '';
  review.value = {};
};

const onPlanChange = async () => {
  const selected = filteredPlans.value.find((item) => String(item.id) === String(selectedPlanId.value));
  if (selected) {
    await previewPdf(selected);
  }
};

const genReview = async (row) => {
  if (!row) return;
  activePlan.value = row;
  currentPdfUrl.value = row.pdf_file;
  currentDocumentText.value = row.extracted_text || '';
  localStorage.setItem(ACTIVE_PLAN_KEY, String(row.id));
  generatingPlanId.value = row.id;
  try {
    const task = await genTeacherReviewAsyncApi({ plan_id: row.id, audience_role: 'teacher' });
    localStorage.setItem(PENDING_TASK_KEY, JSON.stringify({ taskId: task.task_id, planId: row.id }));
    stopTaskPolling();
    const poll = async () => {
      const result = await reviewTaskStatusApi(task.task_id);
      if (result.status === 'done') {
        if (result.review) {
          applyReview(result.review);
        } else {
          await loadLatestTeacherReview(row.id);
        }
        localStorage.removeItem(PENDING_TASK_KEY);
        generatingPlanId.value = null;
        stopTaskPolling();
      } else if (result.status === 'error') {
        localStorage.removeItem(PENDING_TASK_KEY);
        generatingPlanId.value = null;
        stopTaskPolling();
      }
    };
    await poll();
    pollingTimer.value = setInterval(poll, 3000);
  } catch (_) {
    generatingPlanId.value = null;
  }
};

const removePlan = async (row) => {
  if (!row?.id) return;
  await deletePlanApi(row.id);
  plans.value = plans.value.filter((item) => item.id !== row.id);
  if (activePlan.value?.id === row.id) {
    activePlan.value = null;
    currentPdfUrl.value = '';
    currentDocumentText.value = '';
    review.value = {};
    selectedPlanId.value = '';
    localStorage.removeItem(ACTIVE_PLAN_KEY);
  }
};

const saveReview = async () => {
  const suggestions = suggestionText.value
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean);
  review.value = await updateReviewApi(review.value.id, { suggestions });
};

const persistHistory = () => {
  localStorage.setItem('teacherReviewChatHistory', JSON.stringify(history.value.slice(0, 20)));
};

const newChat = () => {
  if (aiChat.value.length > 1) {
    history.value.unshift({
      id: Date.now(),
      preview: aiChat.value.slice(-1)[0]?.text?.slice(0, 60) || '历史对话',
      messages: [...aiChat.value]
    });
    persistHistory();
  }
  aiChat.value = [{ role: 'ai', text: '新对话已创建。可继续基于当前方案提问。' }];
};

const loadHistory = (index) => {
  aiChat.value = [...(history.value[index]?.messages || [])];
};

const deleteSession = (index) => {
  history.value.splice(index, 1);
  persistHistory();
};

const askAi = async () => {
  if (!chatQuestion.value.trim()) return;
  aiChat.value.push({ role: 'teacher', text: chatQuestion.value.trim() });
  chatLoading.value = true;
  try {
    const res = await teacherAiChatApi({
      question: chatQuestion.value.trim(),
      context: {
        type: 'review',
        plan: activePlan.value || {},
        review: review.value || {},
        hypergraph: hypergraphMeta.value || {}
      }
    });
    aiChat.value.push({ role: 'ai', text: res.answer });
    chatQuestion.value = '';
  } finally {
    chatLoading.value = false;
  }
};

const loadTeacherPlans = async () => {
  const res = await listPlansApi({ page: 1, page_size: 500, status: 'submitted' });
  plans.value = asArray(res?.items || res);

  if (!plans.value.length) {
    selectedStudentKey.value = '';
    selectedPlanId.value = '';
    activePlan.value = null;
    currentPdfUrl.value = '';
    currentDocumentText.value = '';
    return;
  }

  const activeId = Number(activePlan.value?.id || selectedPlanId.value || 0);
  if (!activeId) return;

  const refreshed = plans.value.find((item) => Number(item.id) === activeId);
  if (refreshed) {
    activePlan.value = refreshed;
    selectedStudentKey.value = getPlanStudentKey(refreshed);
    selectedPlanId.value = String(refreshed.id);
    currentPdfUrl.value = refreshed.pdf_file;
    currentDocumentText.value = refreshed.extracted_text || '';
  }
};

watch(() => review.value.summary, () => {
  renderMermaidInSummary();
});

onMounted(async () => {
  try {
    await loadTeacherPlans();
  } catch (_) {
    plans.value = [];
  }

  history.value = JSON.parse(localStorage.getItem('teacherReviewChatHistory') || '[]');

  const activePlanId = Number(localStorage.getItem(ACTIVE_PLAN_KEY) || 0);
  if (activePlanId) {
    const selected = plans.value.find((item) => item.id === activePlanId);
    if (selected) {
      selectedStudentKey.value = getPlanStudentKey(selected);
      await previewPdf(selected);
    }
  }

  const pendingRaw = localStorage.getItem(PENDING_TASK_KEY);
  if (pendingRaw) {
    try {
      const pending = JSON.parse(pendingRaw);
      if (pending?.planId) {
        const selected = plans.value.find((item) => item.id === Number(pending.planId));
        if (selected) {
          activePlan.value = selected;
          selectedStudentKey.value = getPlanStudentKey(selected);
          selectedPlanId.value = String(selected.id);
          currentPdfUrl.value = selected.pdf_file;
          currentDocumentText.value = selected.extracted_text || '';
          generatingPlanId.value = selected.id;
        }
      }
      stopTaskPolling();
      const poll = async () => {
        const result = await reviewTaskStatusApi(pending.taskId);
        if (result.status === 'done') {
          if (result.review) {
            applyReview(result.review);
          } else if (pending?.planId) {
            await loadLatestTeacherReview(pending.planId);
          }
          localStorage.removeItem(PENDING_TASK_KEY);
          generatingPlanId.value = null;
          stopTaskPolling();
        } else if (result.status === 'error') {
          localStorage.removeItem(PENDING_TASK_KEY);
          generatingPlanId.value = null;
          stopTaskPolling();
        }
      };
      await poll();
      pollingTimer.value = setInterval(poll, 3000);
    } catch (_) {
      localStorage.removeItem(PENDING_TASK_KEY);
      generatingPlanId.value = null;
    }
  }

  planRefreshTimer = setInterval(async () => {
    try {
      await loadTeacherPlans();
    } catch (_) {
      // keep silent for polling
    }
  }, PLAN_REFRESH_MS);
});

onBeforeUnmount(() => {
  stopTaskPolling();
  if (planRefreshTimer) {
    clearInterval(planRefreshTimer);
    planRefreshTimer = null;
  }
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
.toolbar > select,
.toolbar > textarea {
  flex: 1 1 240px;
  min-width: 0;
}

.toolbar > button {
  flex: 0 0 auto;
}

input,
select {
  margin-top: 0;
  min-width: 0;
  height: var(--control-height);
  border: 1px solid var(--line-strong);
  background: var(--bg-field);
  color: var(--ink-title);
  padding: 0 10px;
  border-radius: var(--control-radius);
}

textarea {
  width: 100%;
  min-height: 120px;
  border: 1px solid var(--line-strong);
  background: var(--bg-field);
  color: var(--ink-title);
  padding: 10px;
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

.summary {
  white-space: pre-wrap;
  line-height: 1.6;
}

.issues {
  margin-top: 12px;
  padding: 12px;
  border: 1px dashed var(--line-soft);
  background: var(--bg-field);
  border-radius: 12px;
}

ul {
  margin: 12px 0 0;
  padding-left: 20px;
  display: grid;
  gap: 10px;
}

li {
  display: grid;
  gap: 3px;
}

li.focused {
  background: color-mix(in oklch, var(--accent) 12%, white);
  border-radius: 8px;
  padding: 8px 10px;
}

small {
  color: var(--ink-muted);
}

.line-list {
  display: grid;
  gap: 4px;
}

.markdown-summary :deep(p) {
  margin: 0 0 6px;
}

.markdown-summary :deep(p:last-child) {
  margin-bottom: 0;
}

.markdown-summary :deep(.mermaid) {
  margin: 14px 0;
  padding: 18px;
  border: 1px solid color-mix(in oklch, var(--line-soft) 78%, white);
  border-radius: 14px;
  background: color-mix(in oklch, var(--bg-main) 92%, white);
  position: relative;
  height: clamp(360px, 64vh, 980px);
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: center;
}

.markdown-summary :deep(.mermaid.mermaid-fit svg) {
  width: auto;
  max-width: 100%;
  height: auto;
  max-height: 100%;
}

.mermaid-preview-mask {
  position: fixed;
  inset: 0;
  background: rgba(10, 18, 32, 0.45);
  display: grid;
  place-items: center;
  z-index: 80;
  padding: 18px;
}

.mermaid-preview-panel {
  width: min(97vw, 1760px);
  height: min(94vh, 1120px);
  border-radius: 14px;
  border: 1px solid color-mix(in oklch, var(--line-soft) 78%, white);
  background: var(--bg-panel);
  display: grid;
  grid-template-rows: auto 1fr;
  overflow: hidden;
  box-shadow: 0 16px 56px rgba(8, 15, 35, 0.24);
}

.mermaid-preview-toolbar {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
  padding: 12px 14px;
  border-bottom: 1px solid color-mix(in oklch, var(--line-soft) 78%, white);
  background: color-mix(in oklch, var(--bg-main) 94%, white);
}

.preview-btn {
  min-height: 30px;
  padding: 0 10px;
  border: 1px solid var(--line-soft);
  background: var(--bg-panel);
  color: var(--ink-body);
  border-radius: 999px;
  cursor: pointer;
}

.preview-btn.close-btn {
  border-color: color-mix(in oklch, var(--danger) 45%, white);
  color: var(--danger);
}

.mermaid-preview-body {
  overflow: auto;
  padding: 18px;
  background: color-mix(in oklch, var(--bg-main) 96%, white);
}

.mermaid-preview-canvas {
  min-width: 100%;
}

.mermaid-preview-canvas :deep(svg) {
  width: auto;
  max-width: none;
  height: auto;
  display: block;
}

@media (max-width: 480px) {
  .toolbar > input,
  .toolbar > select,
  .toolbar > textarea,
  .toolbar > button {
    flex: 1 1 100%;
  }

  textarea {
    min-height: 104px;
  }

  ul {
    padding-left: 16px;
  }

  .mermaid-preview-mask {
    padding: 10px;
  }

  .mermaid-preview-panel {
    width: 100%;
    height: 92vh;
  }

  .markdown-summary :deep(.mermaid) {
    height: clamp(260px, 56vh, 620px);
    padding: 12px;
  }
}
</style>

