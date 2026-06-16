<template>
  <div class="page-grid">
    <section class="panel lead">
      <p class="kicker">Prep Assistant</p>
      <h2>备课辅助</h2>
      <p>先筛选学生提交项目，再生成共性问题与知识点推荐，最后进入备课智能体对话。</p>
    </section>

    <section class="panel">
      <h3>选择项目</h3>
      <div class="toolbar list-toolbar">
        <button type="button" class="ghost" @click="loadPlans">刷新项目</button>
        <button type="button" class="primary" :disabled="summarizing" @click="summarizeIssues">
          {{ summarizing ? '生成中...' : '共性总结' }}
        </button>
      </div>
      <AsyncState :loading="loadingPlans" :error="error" :empty="!displayPlanRows.length" empty-text="暂无可选项目" @retry="loadPlans">
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th class="check-col">勾选</th>
                <th>项目名</th>
                <th class="version-col">版本</th>
                <th class="student-col">提交学生</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in displayPlanRows" :key="item.id">
                <td>
                  <input type="checkbox" :value="item.id" v-model="selectedPlanIds">
                </td>
                <td>{{ item.title || item.name || '未命名项目' }}</td>
                <td>V{{ item.version || 1 }}</td>
                <td>{{ item.student_name || item.student || '-' }}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <SimplePager :current-page="planPage" :total="plans.length" :page-size="planPageSize" @update:currentPage="onPlanPageChange" />
      </AsyncState>
    </section>

    <section class="panel list-panel" v-if="hasSummarized">
      <h3>共性问题与知识点推荐</h3>
      <div class="toolbar list-toolbar">
        <input v-model.trim="issueKeyword" type="text" placeholder="按共性问题关键词筛选" @input="onIssueFilterChange">
      </div>
      <AsyncState :loading="loading" :error="error" :empty="!displayIssues.length && !knowledge.length" empty-text="暂无分析结果" @retry="loadSummaryData">
        <div class="summary-block" v-if="displayIssues.length">
          <h4>共性问题</h4>
          <ul>
            <li v-for="item in displayIssues" :key="item.id || item.rule_id">
              <strong>{{ item.issue || item.problem_type || item.title || '问题项' }}</strong>
              <span>{{ item.summary || item.sample_case || '常见表现待补充' }}</span>
              <span>涉及案例 {{ item.count || item.frequency || 0 }} 个 · 风险 {{ riskLabel(item.risk) }}</span>
            </li>
          </ul>
          <SimplePager :current-page="issuePage" :total="issueTotal" :page-size="issuePageSize" @update:currentPage="onIssuePageChange" />
        </div>
        <div class="summary-block" v-if="knowledge.length">
          <h4>知识点推荐</h4>
          <ul>
            <li v-for="(item, idx) in knowledge" :key="`k-${idx}`">
              <strong>{{ item.knowledge_point || item.title || item.issue || item.problem_type || '推荐知识点' }}</strong>
              <span v-if="item.issue">对应问题：{{ item.issue }}</span>
              <span v-if="item.teaching_goal">讲解目标：{{ item.teaching_goal }}</span>
              <span v-if="(item.core_concepts || []).length">核心概念：{{ (item.core_concepts || []).join(' / ') }}</span>
              <span v-if="(item.teaching_path || []).length">讲解路径：{{ (item.teaching_path || []).join(' → ') }}</span>
              <span v-if="item.class_activity">课堂活动：{{ item.class_activity }}</span>
              <span v-if="item.after_class_task">课后任务：{{ item.after_class_task }}</span>
              <span v-if="item.assessment_rubric">评估标准：{{ item.assessment_rubric }}</span>
              <span v-if="item.teacher_prompt">课堂追问：{{ item.teacher_prompt }}</span>
              <span v-if="item.priority || item.recommended_minutes">优先级：{{ item.priority || '-' }} · 建议时长：{{ item.recommended_minutes || '-' }} 分钟</span>
            </li>
          </ul>
        </div>
      </AsyncState>
    </section>

    <section class="panel">
      <h3>备课智能体对话</h3>
      <AgentChatWindow
        title="教师备课助手"
        :messages="aiChat"
        :sessions="history"
        :model-value="question"
        :loading="chatLoading"
        placeholder="可提问：如何讲解盈利模式模糊这个共性问题？"
        @update:model-value="question = $event"
        @send="askAi"
        @new-chat="newChat"
        @select-session="loadHistory"
        @delete-session="deleteSession"
      />
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue';
import AsyncState from '../../../components/core/AsyncState.vue';
import SimplePager from '../../../components/core/SimplePager.vue';
import AgentChatWindow from '../../../components/AgentChatWindow.vue';
import { commonIssuesApi, knowledgeApi, listPlansApi, teacherAggregateDashboardApi, teacherAiChatApi } from '../../../api/teacher';
import { normalizePagedResult } from '../../../composables/list';

const issues = ref([]);
const loading = ref(false);
const loadingPlans = ref(false);
const error = ref('');
const issueKeyword = ref('');
const issuePage = ref(1);
const issuePageSize = 8;

const plans = ref([]);
const selectedPlanIds = ref([]);
const planPage = ref(1);
const planPageSize = 8;

const knowledge = ref([]);
const summarizing = ref(false);
const hasSummarized = ref(false);

const question = ref('');
const chatLoading = ref(false);
const aiChat = ref([{ role: 'ai', text: '你好，我可以基于共性问题帮助你准备课堂讲解思路。' }]);
const history = ref([]);

const filteredIssues = computed(() => {
  const keyword = issueKeyword.value.trim().toLowerCase();
  if (!keyword) return issues.value;
  return (issues.value || []).filter((item) => {
    const issue = String(item.issue || item.problem_type || item.title || '').toLowerCase();
    const summary = String(item.summary || item.sample_case || '').toLowerCase();
    return issue.includes(keyword) || summary.includes(keyword);
  });
});

const displayIssues = computed(() => {
  const start = (issuePage.value - 1) * issuePageSize;
  return filteredIssues.value.slice(start, start + issuePageSize);
});

const issueTotal = computed(() => filteredIssues.value.length);

const displayPlanRows = computed(() => {
  const start = (planPage.value - 1) * planPageSize;
  return plans.value.slice(start, start + planPageSize);
});

const loadSummaryData = async () => {
  loading.value = true;
  error.value = '';
  try {
    const selectedIds = (selectedPlanIds.value || []).map((id) => Number(id)).filter((id) => Number.isFinite(id));
    // Keep common issue records synchronized for downstream knowledge recommendation endpoint.
    const issueSyncPromise = commonIssuesApi({ plan_ids: selectedIds.join(',') });
    const [aggregateRes, _, knowledgeRes] = await Promise.all([
      teacherAggregateDashboardApi(selectedIds),
      issueSyncPromise,
      knowledgeApi()
    ]);
    const topIssues = (aggregateRes?.complete?.top_issues || []).slice(0, 3);
    issues.value = topIssues.map((item, idx) => ({ ...item, id: item.issue || `top-${idx}` }));
    knowledge.value = Array.isArray(knowledgeRes) ? knowledgeRes : (knowledgeRes?.items || []);
  } catch (e) {
    issues.value = [];
    knowledge.value = [];
    error.value = e?.response?.data?.detail || '备课分析数据加载失败';
  } finally {
    loading.value = false;
  }
};

const loadPlans = async () => {
  loadingPlans.value = true;
  error.value = '';
  try {
    const res = await listPlansApi({ page: 1, page_size: 500 });
    const normalized = normalizePagedResult(res);
    plans.value = normalized.items;
    const maxPage = Math.max(1, Math.ceil(plans.value.length / planPageSize));
    if (planPage.value > maxPage) {
      planPage.value = maxPage;
    }
  } catch (e) {
    plans.value = [];
    error.value = e?.response?.data?.detail || '项目列表加载失败';
  } finally {
    loadingPlans.value = false;
  }
};

const summarizeIssues = async () => {
  if (!selectedPlanIds.value.length) {
    error.value = '请先勾选要分析的项目';
    return;
  }
  summarizing.value = true;
  hasSummarized.value = true;
  issuePage.value = 1;
  try {
    await loadSummaryData();
  } finally {
    summarizing.value = false;
  }
};

const persistHistory = () => {
  localStorage.setItem('teacherPrepChatHistory', JSON.stringify(history.value.slice(0, 20)));
};

const archiveCurrent = () => {
  if (aiChat.value.length < 2) {
    return;
  }
  history.value.unshift({
    id: Date.now(),
    preview: aiChat.value.slice(-1)[0]?.text?.slice(0, 60) || '历史对话',
    messages: [...aiChat.value]
  });
  persistHistory();
};

const newChat = () => {
  archiveCurrent();
  aiChat.value = [{ role: 'ai', text: '新对话已创建。你可以从本周共性问题开始提问。' }];
};

const loadHistory = (index) => {
  aiChat.value = [...(history.value[index]?.messages || [])];
};

const deleteSession = (index) => {
  history.value.splice(index, 1);
  persistHistory();
};

const askAi = async () => {
  if (!question.value.trim()) return;
  aiChat.value.push({ role: 'teacher', text: question.value.trim() });
  chatLoading.value = true;
  try {
    const res = await teacherAiChatApi({
      question: question.value.trim(),
      context: {
        type: 'prep',
        commonIssues: issues.value.slice(0, 5),
        knowledgeRecommendations: knowledge.value.slice(0, 6),
        selectedPlanIds: selectedPlanIds.value
      }
    });
    aiChat.value.push({ role: 'ai', text: res.answer });
    question.value = '';
  } finally {
    chatLoading.value = false;
  }
};

const onIssueFilterChange = () => {
  issuePage.value = 1;
};

const onIssuePageChange = (page) => {
  issuePage.value = page;
};

const onPlanPageChange = (page) => {
  planPage.value = page;
};

onMounted(async () => {
  await loadPlans();
  history.value = JSON.parse(localStorage.getItem('teacherPrepChatHistory') || '[]');
});

const riskLabel = (risk) => {
  const value = String(risk || '').toLowerCase();
  if (value === 'high') return '高';
  if (value === 'medium') return '中';
  if (value === 'low') return '低';
  return '-';
};
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

.table-wrap {
  margin-top: 12px;
  overflow-x: auto;
}

table {
  width: 100%;
  border-collapse: separate;
  border-spacing: 0;
}

th,
td {
  text-align: left;
  padding: 12px 10px;
  border-bottom: 1px solid var(--table-border);
}

th {
  color: var(--ink-muted);
  font-size: 12px;
  font-weight: 600;
  background: color-mix(in oklch, var(--bg-field) 84%, white);
}

.check-col {
  width: 80px;
}

.version-col,
.student-col {
  width: 140px;
}

.toolbar {
  margin-top: 12px;
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
}

input {
  flex: 1 1 240px;
  min-width: 0;
  height: var(--control-height);
  border: 1px solid var(--line-strong);
  background: var(--bg-field);
  color: var(--ink-title);
  padding: 0 10px;
  border-radius: var(--control-radius);
}

button.primary,
button.ghost {
  min-height: 36px;
  padding: 0 14px;
  border: 1px solid var(--ink-title);
  cursor: pointer;
  border-radius: 999px;
}

button.primary {
  background: var(--ink-title);
  color: var(--bg-main);
}

button.ghost {
  background: transparent;
  color: var(--ink-title);
}

.summary-block {
  margin-top: 12px;
}

.summary-block h4 {
  margin: 0;
  color: var(--ink-title);
  font-size: 15px;
}

.summary-block ul {
  margin: 10px 0 0;
  padding-left: 18px;
  display: grid;
  gap: 8px;
}

.summary-block li {
  display: grid;
  gap: 4px;
}

.summary-block li strong {
  color: var(--ink-title);
}

.summary-block li span {
  color: var(--ink-muted);
  font-size: 13px;
}

.list-panel {
  min-height: 420px;
  display: flex;
  flex-direction: column;
}

.list-panel :deep(.state-shell) {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

@media (max-width: 900px) {
  .toolbar > * {
    flex: 1 1 100%;
  }
}
</style>

