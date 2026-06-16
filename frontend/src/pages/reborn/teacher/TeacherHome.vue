<template>
  <div class="page-grid">
    <section class="panel lead">
      <p class="kicker">Teacher Dashboard</p>
      <h2>教师驾驶舱</h2>
      <p>班级总览与教学干预统一在同一页面，先看全局，再按案例定位问题。</p>
    </section>

    <section class="panel metric-strip">
      <h3>关键指标</h3>
      <div class="metric-row">
        <article v-for="item in keyMetrics" :key="item.label" class="metric-item">
          <small>{{ item.label }}</small>
          <strong>{{ item.value }}</strong>
        </article>
      </div>
    </section>

    <section class="panel warning-panel">
      <h3>班级预警</h3>
      <ul class="issue-list">
        <li v-for="(item, idx) in warningRows" :key="`warning-${idx}`">
          <strong>{{ levelLabel(item.level) }} · {{ item.title || '-' }}</strong>
          <span>{{ item.detail || '-' }}</span>
          <span>建议动作：{{ item.action || '-' }}</span>
        </li>
      </ul>
    </section>

    <section class="panel process-panel">
      <h3>过程性评价</h3>
      <div class="stats">
        <span>样本项目：{{ processOverview.project_count || 0 }}</span>
        <span>平均过程分：{{ processOverview.avg_process_score || 0 }}</span>
        <span>低过程分项目：{{ processOverview.low_process_count || 0 }}</span>
      </div>
      <div class="table-wrap" v-if="processRows.length">
        <table>
          <thead>
            <tr>
              <th>项目</th>
              <th>学生</th>
              <th>交互活跃度</th>
              <th>迭代次数</th>
              <th>逻辑演进</th>
              <th>过程分</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in processRows" :key="`process-${item.project_id}`">
              <td>{{ item.project_name || '-' }}</td>
              <td>{{ item.student_name || '-' }}</td>
              <td>{{ item.activity_count || 0 }}</td>
              <td>{{ item.iteration_count || 0 }}</td>
              <td>{{ item.score_delta || 0 }}</td>
              <td>{{ item.process_score || 0 }}（{{ levelLabel(item.level) }}）</td>
            </tr>
          </tbody>
        </table>
      </div>
      <p v-else class="chart-note">暂无可展示的过程性评价数据。</p>
    </section>

    <section class="panel plagiarism-panel">
      <h3>剽窃检测</h3>
      <div class="stats">
        <span>检测开关：{{ plagiarismCheck.enabled ? '已启用' : '未启用' }}</span>
        <span>检测项目数：{{ plagiarismCheck.checked_plan_count || 0 }}</span>
        <span>疑似相似组：{{ plagiarismCheck.suspicious_pair_count || 0 }}</span>
      </div>
      <ul class="issue-list" v-if="plagiarismPairs.length">
        <li v-for="(item, idx) in plagiarismPairs" :key="`plagiarism-${idx}`">
          <strong>{{ levelLabel(item.risk_level) }} · 相似度 {{ item.similarity_score || 0 }}%</strong>
          <span>{{ item.student_a_name || '-' }}《{{ item.plan_a_name || '-' }}》 ↔ {{ item.student_b_name || '-' }}《{{ item.plan_b_name || '-' }}》</span>
          <span>{{ item.reason || '-' }}</span>
        </li>
      </ul>
      <p v-else class="chart-note">当前未检测到明显相似文本。</p>
    </section>

    <section class="panel selector-panel">
      <h3>分析案例选择</h3>
      <AsyncState :loading="loading" :error="error" :empty="!displaySelectorRows.length" empty-text="暂无可分析案例" @retry="loadData">
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th class="check-col">勾选</th>
                <th>方案名</th>
                <th class="version-col">版本</th>
                <th class="student-col">学生名字</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in displaySelectorRows" :key="item.projectKey">
                <td>
                  <input type="checkbox" :checked="isChecked(item.projectKey)" @change="toggleChecked(item.projectKey, $event.target.checked)">
                </td>
                <td>{{ item.title || '未命名方案' }}</td>
                <td>V{{ item.version || 1 }}</td>
                <td>{{ item.studentName || '-' }}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <div class="toolbar list-toolbar">
          <button type="button" class="ghost" :disabled="loading" @click="loadData">刷新</button>
          <button type="button" class="primary" :disabled="loading" @click="applySelection">应用到案例分析</button>
        </div>
        <SimplePager :current-page="selectorPage" :total="selectorRows.length" :page-size="selectorPageSize" @update:currentPage="onSelectorPageChange" />
      </AsyncState>
    </section>

    <section class="panel chart-panel">
      <div class="chart-head">
        <h3>Rubric 评分图</h3>
        <span class="chart-note">展示已选择案例在各维度上的平均分</span>
      </div>
      <div ref="rubricChartRef" class="rubric-chart"></div>
    </section>

    <section class="panel chart-panel">
      <div class="chart-head">
        <h3>班级画像雷达</h3>
        <span class="chart-note">基于学生对话、方案与检阅证据聚合</span>
      </div>
      <div ref="personaChartRef" class="rubric-chart"></div>
      <div class="stats">
        <span>样本学生：{{ classPersona.student_count || 0 }}</span>
        <span>画像均分：{{ classPersona.average_score || 0 }}</span>
      </div>
      <ul class="issue-list" v-if="(classPersona.improvements || []).length">
        <li v-for="item in classPersona.improvements" :key="`persona-gap-${item.key}`">
          <strong>{{ item.label }}</strong>
          <span>{{ item.summary }}</span>
        </li>
      </ul>
      <div class="persona-dimension-grid" v-if="personaDimensionRows.length">
        <button
          v-for="item in personaDimensionRows"
          :key="`persona-dimension-${item.key}`"
          type="button"
          class="persona-dimension-btn"
          :class="{ active: selectedPersonaDimension?.key === item.key }"
          @click="selectPersonaDimension(item.key)"
        >
          <span>{{ item.label }}</span>
          <strong>{{ Number(item.score || 0).toFixed(2) }}</strong>
          <small>证据 {{ Number(item.evidence_count || 0) }}</small>
        </button>
      </div>
      <div class="persona-evidence-panel" v-if="selectedPersonaDimension">
        <div class="chart-head">
          <h3>指标证据：{{ selectedPersonaDimension.label }}</h3>
          <span class="chart-note">点击上方指标可切换证据</span>
        </div>
        <ul class="issue-list" v-if="selectedPersonaEvidence.length">
          <li v-for="(item, idx) in selectedPersonaEvidence" :key="`persona-evidence-${selectedPersonaDimension.key}-${idx}`">
            <strong>{{ item.title || '证据片段' }}</strong>
            <span>来源：{{ item.source_type || '-' }} · 学生：{{ item.student_name || '-' }} · 时间：{{ formatDateTime(item.created_at) }}</span>
            <span v-if="(item.keywords || []).length">命中：{{ (item.keywords || []).join(' / ') }}</span>
            <span>{{ item.snippet || '-' }}</span>
          </li>
        </ul>
        <p v-else class="chart-note">该指标暂无可追溯证据。</p>
      </div>
    </section>

    <section class="panel insight-panel">
      <h3>案例分析（已选择完整案例）</h3>
      <div class="stats">
        <span>完整案例数：{{ complete.project_count || 0 }}</span>
        <span>平均 Rubric 评分：{{ complete.avg_rubric_score || 0 }}</span>
      </div>
      <ul class="issue-list">
        <li v-for="(item, idx) in topCompleteIssues" :key="`issue-${idx}`">
          <strong>{{ item.issue || '-' }}</strong>
          <span>{{ item.summary || '该类问题在多个案例中重复出现，需要作为共性教学重点处理。' }}</span>
          <span>涉及案例 {{ item.count || 0 }} 个 · 风险 {{ riskLabel(item.risk) }}</span>
          <span v-if="(item.examples || []).length">典型表现：{{ (item.examples || []).join('；') }}</span>
        </li>
      </ul>
    </section>

    <section class="panel insight-panel">
      <h3>不完整案例分析</h3>
      <div class="stats">
        <span>不完整案例数：{{ incomplete.project_count || 0 }}</span>
        <span>平均进度：{{ incomplete.avg_progress || 0 }}%</span>
      </div>
      <ul class="issue-list">
        <li v-for="(item, idx) in incomplete.missing_top5 || []" :key="`missing-${idx}`">
          <strong>{{ item.part || '-' }}</strong>
          <span>数量 {{ item.count || 0 }} · 紧急度 {{ item.urgency || '-' }}</span>
        </li>
      </ul>
    </section>
  </div>
</template>

<script setup>
import * as echarts from 'echarts';
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue';
import AsyncState from '../../../components/core/AsyncState.vue';
import SimplePager from '../../../components/core/SimplePager.vue';
import { teacherAggregateDashboardApi, teacherClassPersonaApi } from '../../../api/teacher';
import { formatDateTime } from '../../../utils/datetime';

const loading = ref(false);
const error = ref('');
const selectorProjects = ref([]);
const selectedVersionMap = ref({});
const checkedProjectMap = ref({});
const complete = ref({ project_count: 0, avg_rubric_score: 0, top_issues: [] });
const incomplete = ref({ project_count: 0, avg_progress: 0, missing_top5: [] });
const plagiarismCheck = ref({ enabled: true, checked_plan_count: 0, suspicious_pair_count: 0, high_risk_count: 0, suspicious_pairs: [] });
const processEvaluation = ref({ overview: { avg_process_score: 0, project_count: 0, high_process_count: 0, low_process_count: 0 }, project_rows: [] });
const classWarning = ref({ warning_count: 0, items: [] });
const dashboardMetrics = ref({});
const rubricChartRef = ref(null);
const personaChartRef = ref(null);
const classPersona = ref({ dimensions: [], radar: [], improvements: [], student_count: 0, average_score: 0, evidence_map: {} });
const selectedPersonaKey = ref('');
let rubricChart = null;
let personaChart = null;
let personaRefreshTimer = null;

const selectorPage = ref(1);
const selectorPageSize = 8;

const selectorRows = computed(() => {
  return (selectorProjects.value || []).map((proj) => {
    const selectedPlanId = Number(selectedVersionMap.value[proj.project_key] || proj.default_plan_id || 0);
    const selectedVersion = (proj.versions || []).find((v) => Number(v.plan_id) === selectedPlanId) || (proj.versions || [])[0] || {};
    return {
      projectKey: proj.project_key,
      title: proj.title,
      studentName: proj.student_name,
      version: selectedVersion.version || proj.default_version || 1,
      planId: selectedVersion.plan_id || proj.default_plan_id
    };
  });
});

const displaySelectorRows = computed(() => {
  const start = (selectorPage.value - 1) * selectorPageSize;
  return selectorRows.value.slice(start, start + selectorPageSize);
});

const topCompleteIssues = computed(() => (complete.value.top_issues || []).slice(0, 5));
const processOverview = computed(() => processEvaluation.value.overview || {});
const processRows = computed(() => (processEvaluation.value.project_rows || []).slice(0, 10));
const plagiarismPairs = computed(() => (plagiarismCheck.value.suspicious_pairs || []).slice(0, 8));
const warningRows = computed(() => classWarning.value.items || []);

const rubricRadarRows = computed(() => complete.value.class_radar || []);
const personaDimensionRows = computed(() => classPersona.value.dimensions || []);
const selectedPersonaDimension = computed(() => {
  const rows = personaDimensionRows.value;
  if (!rows.length) return null;
  return rows.find((item) => item.key === selectedPersonaKey.value) || rows[0];
});
const selectedPersonaEvidence = computed(() => {
  const active = selectedPersonaDimension.value;
  if (!active?.key) return [];
  const evidenceMap = classPersona.value.evidence_map || {};
  return (evidenceMap[active.key] || []).slice(0, 12);
});

const submittedStudentCount = computed(() => {
  const names = new Set(
    selectorRows.value
      .map((item) => String(item.studentName || '').trim())
      .filter(Boolean)
  );
  return Number(dashboardMetrics.value.submitted_student_count || names.size || 0);
});

const planCount = computed(() => {
  const totalByAnalysis = Number(complete.value.project_count || 0) + Number(incomplete.value.project_count || 0);
  return Number(dashboardMetrics.value.plan_count || selectorRows.value.length || totalByAnalysis || 0);
});

const keyMetrics = computed(() => {
  return [
    { label: '提交案例数量', value: planCount.value },
    { label: '学生数量', value: Number(dashboardMetrics.value.student_count || 0) },
    { label: '已提交学生数', value: submittedStudentCount.value },
    { label: '提交率', value: `${Number(dashboardMetrics.value.submission_rate || 0)}%` },
    { label: 'Rubric 均分', value: Number(dashboardMetrics.value.avg_rubric_score || complete.value.avg_rubric_score || 0) },
    { label: '完整案例数', value: Number(complete.value.project_count || 0) },
    { label: '不完整案例数', value: Number(incomplete.value.project_count || 0) },
    { label: '疑似剽窃组', value: Number(dashboardMetrics.value.plagiarism_suspect_pairs || 0) },
    { label: '班级预警数', value: Number(dashboardMetrics.value.warning_count || 0) },
    { label: '低过程分项目', value: Number(dashboardMetrics.value.low_process_project_count || 0) }
  ];
});

const selectedPlanIds = () => {
  const rows = selectorRows.value.filter((item) => checkedProjectMap.value[item.projectKey] && item.planId);
  return rows.map((item) => Number(item.planId));
};

const isChecked = (projectKey) => Boolean(checkedProjectMap.value[projectKey]);

const toggleChecked = (projectKey, checked) => {
  checkedProjectMap.value = {
    ...checkedProjectMap.value,
    [projectKey]: Boolean(checked)
  };
};

const ensureMaps = () => {
  if (!selectorProjects.value.length) return;
  const nextVersionMap = { ...(selectedVersionMap.value || {}) };
  const nextCheckedMap = { ...(checkedProjectMap.value || {}) };
  let touched = false;
  for (const proj of selectorProjects.value) {
    const key = String(proj.project_key || '').trim();
    if (!key) continue;
    if (!(key in nextVersionMap)) {
      nextVersionMap[key] = proj.default_plan_id;
      touched = true;
    }
    if (!(key in nextCheckedMap)) {
      nextCheckedMap[key] = true;
      touched = true;
    }
  }
  if (touched) {
    selectedVersionMap.value = nextVersionMap;
    checkedProjectMap.value = nextCheckedMap;
  }
};

const ensureSelectedPersonaKey = () => {
  const rows = classPersona.value.dimensions || [];
  if (!rows.length) {
    selectedPersonaKey.value = '';
    return;
  }
  if (!rows.some((item) => item.key === selectedPersonaKey.value)) {
    selectedPersonaKey.value = String(rows[0]?.key || '');
  }
};

const loadData = async (silent = false) => {
  if (!silent) {
    loading.value = true;
    error.value = '';
  }
  try {
    const [aggregate, personaPayload] = await Promise.all([
      teacherAggregateDashboardApi(selectedPlanIds()),
      teacherClassPersonaApi()
    ]);
    selectorProjects.value = aggregate.selector?.projects || [];
    dashboardMetrics.value = aggregate.metrics || {};
    complete.value = aggregate.complete || { project_count: 0, avg_rubric_score: 0, top_issues: [] };
    incomplete.value = aggregate.incomplete || { project_count: 0, avg_progress: 0, missing_top5: [] };
    plagiarismCheck.value = aggregate.plagiarism_check || { enabled: true, checked_plan_count: 0, suspicious_pair_count: 0, high_risk_count: 0, suspicious_pairs: [] };
    processEvaluation.value = aggregate.process_evaluation || { overview: { avg_process_score: 0, project_count: 0, high_process_count: 0, low_process_count: 0 }, project_rows: [] };
    classWarning.value = aggregate.class_warning || { warning_count: 0, items: [] };
    classPersona.value = personaPayload || { dimensions: [], radar: [], improvements: [], student_count: 0, average_score: 0, evidence_map: {} };
    ensureSelectedPersonaKey();
    ensureMaps();
    await renderRubricChart();
    await renderPersonaChart();
  } catch (e) {
    if (!silent) {
      error.value = e?.response?.data?.detail || '教师驾驶舱数据加载失败';
      selectorProjects.value = [];
      plagiarismCheck.value = { enabled: true, checked_plan_count: 0, suspicious_pair_count: 0, high_risk_count: 0, suspicious_pairs: [] };
      processEvaluation.value = { overview: { avg_process_score: 0, project_count: 0, high_process_count: 0, low_process_count: 0 }, project_rows: [] };
      classWarning.value = { warning_count: 0, items: [] };
      classPersona.value = { dimensions: [], radar: [], improvements: [], student_count: 0, average_score: 0, evidence_map: {} };
      selectedPersonaKey.value = '';
    }
  } finally {
    if (!silent) {
      loading.value = false;
    }
  }
};

const applySelection = async () => {
  selectorPage.value = 1;
  await loadData();
};

const onSelectorPageChange = (page) => {
  selectorPage.value = page;
};

const selectPersonaDimension = (key) => {
  selectedPersonaKey.value = String(key || '');
};

const refreshClassPersonaSilently = async () => {
  try {
    const payload = await teacherClassPersonaApi();
    classPersona.value = payload || { dimensions: [], radar: [], improvements: [], student_count: 0, average_score: 0, evidence_map: {} };
    ensureSelectedPersonaKey();
    await renderPersonaChart();
  } catch (_) {
    // keep silent for periodic refresh
  }
};

const riskLabel = (risk) => {
  const value = String(risk || '').toLowerCase();
  if (value === 'high') return '高';
  if (value === 'medium') return '中';
  if (value === 'low') return '低';
  return '-';
};

const levelLabel = (level) => {
  const value = String(level || '').toLowerCase();
  if (value === 'high') return '高';
  if (value === 'medium') return '中';
  if (value === 'low') return '低';
  return '提示';
};

const renderRubricChart = async () => {
  await nextTick();
  if (!rubricChartRef.value) return;

  if (!rubricChart) {
    rubricChart = echarts.init(rubricChartRef.value);
  }

  const rows = rubricRadarRows.value || [];
  const indicators = rows.map((item) => ({ name: item.name || item.label || '维度', max: 5 }));
  const values = rows.map((item) => Number(item.score || item.value || 0));

  rubricChart.setOption({
    tooltip: { trigger: 'item' },
    radar: {
      radius: '62%',
      indicator: indicators,
      splitLine: { lineStyle: { color: '#dbe4f1' } }
    },
    series: [
      {
        type: 'radar',
        data: [
          {
            value: values,
            name: '完整案例均值',
            areaStyle: { color: 'rgba(20,110,255,0.16)' },
            lineStyle: { color: '#146eff' }
          }
        ]
      }
    ]
  }, true);

  rubricChart.resize();
};

const renderPersonaChart = async () => {
  await nextTick();
  if (!personaChartRef.value) return;
  if (!personaChart) {
    personaChart = echarts.init(personaChartRef.value);
  }

  const rows = classPersona.value.radar || [];
  const indicators = rows.map((item) => ({ name: item.name || item.label || '维度', max: 5 }));
  const values = rows.map((item) => Number(item.value || item.score || 0));

  personaChart.setOption({
    tooltip: { trigger: 'item' },
    radar: {
      radius: '62%',
      indicator: indicators,
      splitLine: { lineStyle: { color: '#dbe4f1' } }
    },
    series: [
      {
        type: 'radar',
        data: [
          {
            value: values,
            name: '班级画像',
            areaStyle: { color: 'rgba(32,154,74,0.16)' },
            lineStyle: { color: '#209a4a' }
          }
        ]
      }
    ]
  }, true);

  personaChart.resize();
};

const onResize = () => {
  rubricChart?.resize();
  personaChart?.resize();
};

onMounted(loadData);
onMounted(() => {
  window.addEventListener('resize', onResize);
  window.addEventListener('focus', refreshClassPersonaSilently);
  personaRefreshTimer = setInterval(refreshClassPersonaSilently, 45000);
});

onBeforeUnmount(() => {
  window.removeEventListener('resize', onResize);
  window.removeEventListener('focus', refreshClassPersonaSilently);
  if (personaRefreshTimer) {
    clearInterval(personaRefreshTimer);
    personaRefreshTimer = null;
  }
  rubricChart?.dispose();
  personaChart?.dispose();
  rubricChart = null;
  personaChart = null;
});
</script>

<style scoped>
.page-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}

.panel {
  border: 1px solid var(--line-strong);
  background: var(--bg-panel);
  padding: 18px;
  border-radius: var(--radius-md);
}

.lead,
.metric-strip,
.selector-panel,
.warning-panel,
.process-panel,
.plagiarism-panel {
  grid-column: 1 / -1;
}

.chart-panel {
  grid-column: 1 / -1;
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

.metric-row {
  margin-top: 12px;
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: 10px;
}

.metric-item {
  border: 1px solid var(--line-soft);
  border-radius: var(--radius-sm);
  background: color-mix(in oklch, var(--bg-field) 90%, white);
  padding: 10px;
  display: grid;
  gap: 4px;
}

.metric-item small {
  color: var(--ink-muted);
}

.metric-item strong {
  color: var(--ink-title);
  font-size: 18px;
  font-variant-numeric: tabular-nums;
}

.chart-head {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: baseline;
  flex-wrap: wrap;
}

.chart-note {
  color: var(--ink-muted);
  font-size: 12px;
}

.rubric-chart {
  margin-top: 12px;
  width: 100%;
  height: 360px;
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

.stats {
  margin-top: 12px;
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  font-variant-numeric: tabular-nums;
}

.issue-list {
  margin: 12px 0 0;
  list-style: none;
  padding-left: 0;
  display: grid;
  gap: 10px;
}

.issue-list li {
  border: 1px solid var(--line-soft);
  border-radius: var(--radius-sm);
  background: color-mix(in oklch, var(--bg-field) 90%, white);
  padding: 10px 12px;
  display: grid;
  gap: 4px;
}

.issue-list strong {
  color: var(--ink-title);
}

.issue-list span {
  color: var(--ink-muted);
  font-size: 13px;
}

.persona-dimension-grid {
  margin-top: 12px;
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  gap: 10px;
}

.persona-dimension-btn {
  border: 1px solid var(--line-soft);
  border-radius: var(--radius-sm);
  background: color-mix(in oklch, var(--bg-field) 90%, white);
  color: var(--ink-title);
  padding: 10px 12px;
  display: grid;
  gap: 4px;
  text-align: left;
  cursor: pointer;
}

.persona-dimension-btn strong {
  font-size: 18px;
}

.persona-dimension-btn small {
  color: var(--ink-muted);
}

.persona-dimension-btn.active {
  border-color: color-mix(in oklch, var(--ink-title) 40%, var(--line-strong));
  background: color-mix(in oklch, var(--ink-title) 9%, var(--bg-panel));
}

.persona-evidence-panel {
  margin-top: 14px;
}

@media (max-width: 1180px) {
  .metric-row {
    grid-template-columns: repeat(4, minmax(0, 1fr));
  }
}

@media (max-width: 900px) {
  .page-grid {
    grid-template-columns: 1fr;
  }

  .metric-row {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 520px) {
  .metric-row {
    grid-template-columns: 1fr;
  }

  .rubric-chart {
    height: 300px;
  }
}
</style>

