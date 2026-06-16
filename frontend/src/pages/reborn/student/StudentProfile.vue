<template>
  <div class="page-grid">
    <section class="panel lead">
      <p class="kicker">Profile Vault</p>
      <h2>成长档案与能力画像</h2>
      <p>把个人信息、行为轨迹和证据链路结合，形成可追踪的学习档案。</p>
    </section>

    <section class="panel">
      <h3>个人信息</h3>
      <AsyncState
        :loading="profileLoading"
        :error="profileError"
        :empty="!Object.keys(profile).length"
        empty-text="暂无个人信息"
        @retry="loadProfile"
      >
        <dl>
          <div><dt>用户名</dt><dd>{{ profile.username || '-' }}</dd></div>
          <div><dt>角色</dt><dd>{{ profile.role || '-' }}</dd></div>
          <div>
            <dt>邮箱</dt>
            <dd><input v-model.trim="profile.email" type="text" placeholder="请输入邮箱"></dd>
          </div>
          <div>
            <dt>专业</dt>
            <dd><input v-model.trim="profile.major" type="text" placeholder="请输入专业"></dd>
          </div>
        </dl>
        <div class="toolbar">
          <button type="button" class="primary" :disabled="saving" @click="saveProfile">{{ saving ? '保存中...' : '保存资料' }}</button>
        </div>
      </AsyncState>
    </section>

    <section class="panel">
      <h3>个人画像雷达</h3>
      <AsyncState
        :loading="personaLoading"
        :error="personaError"
        :empty="!persona.dimensions?.length"
        empty-text="暂无画像数据"
        @retry="loadPersona"
      >
        <div ref="personaChartRef" class="persona-chart"></div>
        <div class="chip-row">
          <button
            v-for="item in persona.dimensions || []"
            :key="item.key"
            type="button"
            class="ghost"
            :class="{ active: activeDimension === item.key }"
            @click="activeDimension = item.key"
          >
            {{ item.label }} · {{ item.score }}
          </button>
        </div>

        <div class="issues" v-if="activeDimensionSummary">
          <strong>{{ activeDimensionSummary.label }}</strong>
          <p>{{ activeDimensionSummary.summary }}</p>
        </div>

        <div class="issues" v-if="activeEvidence.length">
          <div class="evidence-head">
            <strong>证据链（{{ activeEvidence.length }}）</strong>
            <button
              v-if="activeEvidence.length > evidencePreviewLimit"
              type="button"
              class="ghost mini-btn"
              @click="showAllEvidence = !showAllEvidence"
            >
              {{ showAllEvidence ? '收起' : `展开全部 ${activeEvidence.length} 条` }}
            </button>
          </div>
          <ul class="evidence-list">
            <li v-for="(item, idx) in visibleEvidence" :key="`ev-${idx}`" class="evidence-card">
              <div class="evidence-meta">
                <span>{{ item.title || '-' }}</span>
                <small>{{ formatDateTime(item.created_at) }}</small>
              </div>
              <p>{{ item.snippet || '-' }}</p>
            </li>
          </ul>
        </div>
      </AsyncState>
    </section>

    <section class="panel">
      <h3>近期行为</h3>
      <div class="toolbar">
        <select v-model="type" @change="onFilterChange">
          <option value="">全部类型</option>
          <option value="plan">方案记录</option>
          <option value="review">评审记录</option>
          <option value="submission">提交记录</option>
        </select>
        <input v-model.trim="keyword" type="text" placeholder="按行为关键词筛选" @input="onFilterChange">
      </div>
      <AsyncState
        :loading="historyLoading && !displayHistory.length"
        :error="historyError"
        :empty="!displayHistory.length"
        empty-text="暂无行为记录"
        @retry="loadHistory"
      >
        <ul>
          <li v-for="item in displayHistory" :key="item.id || item.created_at">
            <strong>{{ item.action || item.title || '操作记录' }}</strong>
            <span>{{ formatDateTime(item.created_at) }}</span>
          </li>
        </ul>
        <SimplePager :current-page="currentPage" :total="displayTotal" :page-size="pageSize" @update:currentPage="onPageChange" />
      </AsyncState>
    </section>
  </div>
</template>

<script setup>
import * as echarts from 'echarts';
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { ElMessage } from 'element-plus';
import AsyncState from '../../../components/core/AsyncState.vue';
import SimplePager from '../../../components/core/SimplePager.vue';
import { compactQuery, normalizePagedResult } from '../../../composables/list';
import { profileApi, updateProfileApi } from '../../../api/auth';
import { historyApi, studentPersonaApi } from '../../../api/student';
import { formatDateTime } from '../../../utils/datetime';

const profile = ref({});
const history = ref([]);
const profileLoading = ref(false);
const historyLoading = ref(false);
const personaLoading = ref(false);
const profileError = ref('');
const historyError = ref('');
const personaError = ref('');
const saving = ref(false);

const keyword = ref('');
const type = ref('');
const currentPage = ref(1);
const pageSize = 8;
const serverTotal = ref(0);

const persona = ref({ dimensions: [], evidence_map: {}, radar: [] });
const activeDimension = ref('');
const showAllEvidence = ref(false);
const evidencePreviewLimit = 5;

const personaChartRef = ref(null);
let personaChart = null;
let chartResizeObserver = null;
let chartRenderTimer = null;
let personaRefreshTimer = null;

const displayHistory = computed(() => history.value);
const displayTotal = computed(() => serverTotal.value);
const activeDimensionSummary = computed(
  () => (persona.value.dimensions || []).find((item) => item.key === activeDimension.value) || null
);
const activeEvidence = computed(() => (persona.value.evidence_map || {})[activeDimension.value] || []);
const visibleEvidence = computed(() => {
  if (showAllEvidence.value) return activeEvidence.value;
  return (activeEvidence.value || []).slice(0, evidencePreviewLimit);
});

const buildRadarRows = (payload) => {
  const radarRows = Array.isArray(payload?.radar) ? payload.radar : [];
  if (radarRows.length) {
    return radarRows
      .map((item) => ({ name: String(item?.name || item?.label || ''), value: Number(item?.value || 0) }))
      .filter((item) => item.name);
  }

  const dimensions = Array.isArray(payload?.dimensions) ? payload.dimensions : [];
  return dimensions
    .map((item) => ({ name: String(item?.label || item?.key || ''), value: Number(item?.score || 0) }))
    .filter((item) => item.name);
};

const loadProfile = async () => {
  profileLoading.value = true;
  profileError.value = '';
  try {
    profile.value = (await profileApi()) || {};
  } catch (e) {
    profile.value = {};
    profileError.value = e?.response?.data?.detail || '个人信息加载失败';
  } finally {
    profileLoading.value = false;
  }
};

const loadHistory = async (silent = false) => {
  if (!silent) historyLoading.value = true;
  historyError.value = '';
  try {
    const params = compactQuery({
      mode: 'stream',
      page: currentPage.value,
      page_size: pageSize,
      q: keyword.value,
      status: type.value
    });
    const normalized = normalizePagedResult(await historyApi(params));
    history.value = normalized.items;
    serverTotal.value = normalized.total;
  } catch (e) {
    history.value = [];
    serverTotal.value = 0;
    historyError.value = e?.response?.data?.detail || '行为记录加载失败';
  } finally {
    if (!silent) historyLoading.value = false;
  }
};

const saveProfile = async () => {
  saving.value = true;
  profileError.value = '';
  try {
    profile.value = (await updateProfileApi({
      email: profile.value.email,
      major: profile.value.major
    })) || profile.value;
    ElMessage.success('资料已保存');
  } catch (e) {
    profileError.value = e?.response?.data?.detail || '资料保存失败';
  } finally {
    saving.value = false;
  }
};

const renderPersonaChart = async () => {
  await nextTick();
  const host = personaChartRef.value;
  if (!host) return;

  if (!host.clientWidth || !host.clientHeight) {
    if (chartRenderTimer) clearTimeout(chartRenderTimer);
    chartRenderTimer = setTimeout(() => {
      renderPersonaChart();
    }, 140);
    return;
  }

  const rows = buildRadarRows(persona.value);
  if (!rows.length) {
    personaChart?.clear();
    return;
  }

  if (!personaChart) {
    personaChart = echarts.init(host, null, { renderer: 'svg' });
  }

  const indicators = rows.map((item) => ({ name: item.name, max: 5 }));
  const values = rows.map((item) => Number(item.value || 0));

  personaChart.setOption(
    {
      tooltip: { trigger: 'item' },
      radar: {
        radius: '64%',
        indicator: indicators,
        splitLine: { lineStyle: { color: '#dbe4f1' } },
        splitArea: { areaStyle: { color: ['rgba(20,110,255,0.03)', 'rgba(20,110,255,0.06)'] } }
      },
      series: [
        {
          type: 'radar',
          data: [
            {
              value: values,
              name: '个人画像',
              areaStyle: { color: 'rgba(20,110,255,0.2)' },
              lineStyle: { color: '#146eff', width: 2 }
            }
          ]
        }
      ]
    },
    true
  );
  personaChart.resize();
};

const loadPersona = async (silent = false) => {
  if (!silent) {
    personaLoading.value = true;
    personaError.value = '';
  }
  try {
    const payload = (await studentPersonaApi()) || { dimensions: [], evidence_map: {}, radar: [] };
    persona.value = {
      ...payload,
      dimensions: Array.isArray(payload?.dimensions) ? payload.dimensions : [],
      evidence_map: payload?.evidence_map || {},
      radar: buildRadarRows(payload)
    };
    if (!activeDimension.value) {
      activeDimension.value = persona.value.dimensions?.[0]?.key || '';
    }
    await renderPersonaChart();
  } catch (e) {
    if (!silent) {
      persona.value = { dimensions: [], evidence_map: {}, radar: [] };
      personaError.value = e?.response?.data?.detail || '画像加载失败';
    }
  } finally {
    if (!silent) {
      personaLoading.value = false;
    }
  }
};

const onFilterChange = async () => {
  currentPage.value = 1;
  await loadHistory(true);
};

const onPageChange = async (page) => {
  currentPage.value = page;
  await loadHistory(true);
};

const refreshPersonaSilently = () => {
  loadPersona(true);
};

const onResize = () => {
  personaChart?.resize();
};

onMounted(async () => {
  await loadProfile();
  await loadPersona();
  await loadHistory();

  if (typeof ResizeObserver !== 'undefined') {
    chartResizeObserver = new ResizeObserver(() => {
      personaChart?.resize();
      renderPersonaChart();
    });
    if (personaChartRef.value) {
      chartResizeObserver.observe(personaChartRef.value);
    }
  }

  window.addEventListener('resize', onResize);
  window.addEventListener('focus', refreshPersonaSilently);
  personaRefreshTimer = setInterval(refreshPersonaSilently, 45000);
});

watch(
  () => persona.value.radar,
  () => {
    renderPersonaChart();
  },
  { deep: true }
);

watch(activeDimension, () => {
  showAllEvidence.value = false;
});

onBeforeUnmount(() => {
  if (chartRenderTimer) {
    clearTimeout(chartRenderTimer);
    chartRenderTimer = null;
  }
  if (chartResizeObserver) {
    chartResizeObserver.disconnect();
    chartResizeObserver = null;
  }
  window.removeEventListener('resize', onResize);
  window.removeEventListener('focus', refreshPersonaSilently);
  if (personaRefreshTimer) {
    clearInterval(personaRefreshTimer);
    personaRefreshTimer = null;
  }
  personaChart?.dispose();
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
}

.lead {
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

dl {
  margin-top: 12px;
  display: grid;
  gap: 10px;
}

dt {
  color: var(--ink-muted);
}

dd {
  margin: 4px 0 0;
  color: var(--ink-title);
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

input,
select {
  min-width: 0;
  height: var(--control-height);
  border: 1px solid var(--line-strong);
  background: var(--bg-field);
  color: var(--ink-title);
  padding: 0 10px;
  border-radius: var(--control-radius);
}

ul {
  margin: 12px 0 0;
  padding-left: 18px;
  display: grid;
  gap: 8px;
}

.persona-chart {
  margin-top: 12px;
  width: 100%;
  height: 320px;
  min-height: 260px;
}

.chip-row {
  margin-top: 10px;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

button.ghost {
  min-height: 34px;
  padding: 0 12px;
  border: 1px solid var(--line-strong);
  background: transparent;
  color: var(--ink-title);
  border-radius: 999px;
  cursor: pointer;
}

button.ghost.active {
  border-color: var(--accent);
  background: color-mix(in oklch, var(--accent) 10%, var(--bg-main));
}

.issues {
  margin-top: 10px;
  border: 1px dashed var(--line-soft);
  background: var(--bg-field);
  padding: 10px 12px;
}

.issues p {
  margin: 6px 0 0;
}

.issues li {
  display: grid;
  gap: 4px;
}

.issues small {
  color: var(--ink-muted);
}

.evidence-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.evidence-list {
  margin-top: 8px;
  display: grid;
  gap: 8px;
  list-style: none;
  padding-left: 0;
}

.evidence-card {
  border: 1px solid var(--line-soft);
  border-radius: 8px;
  padding: 8px 10px;
  background: color-mix(in oklch, var(--bg-main) 90%, white);
}

.evidence-meta {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  align-items: baseline;
}

.evidence-card p {
  margin: 6px 0 0;
  font-size: 13px;
  color: var(--ink-body);
}

.mini-btn {
  min-height: 28px;
  padding: 0 10px;
  font-size: 12px;
}

button.primary {
  min-height: 36px;
  padding: 0 14px;
  border: 1px solid var(--ink-title);
  background: var(--ink-title);
  color: var(--bg-main);
  cursor: pointer;
  border-radius: 999px;
}

@media (max-width: 900px) {
  .page-grid {
    grid-template-columns: 1fr;
  }

  .persona-chart {
    height: 280px;
  }
}
</style>

