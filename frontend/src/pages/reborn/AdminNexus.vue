<template>
  <div class="admin-grid">
    <section class="belt overview-belt">
      <div class="head-row">
        <div>
          <h2>平台运营与监管总览</h2>
          <p>统一展示管理端能力：账号治理、超图/知识图谱、调用观测与反馈可解释性。</p>
        </div>
        <button type="button" class="primary" :disabled="loading" @click="load">刷新全部</button>
      </div>
      <div class="metric-grid">
        <article>
          <small>用户总数</small>
          <strong>{{ overview.users?.total || 0 }}</strong>
        </article>
        <article>
          <small>方案总数</small>
          <strong>{{ overview.projects?.total || 0 }}</strong>
        </article>
        <article>
          <small>评阅总数</small>
          <strong>{{ overview.reviews?.total || 0 }}</strong>
        </article>
        <article>
          <small>待处理师徒申请</small>
          <strong>{{ overview.runtime?.pending_mentorship || 0 }}</strong>
        </article>
        <article>
          <small>账号激活率</small>
          <strong>{{ activeRate }}%</strong>
        </article>
        <article>
          <small>管理员占比</small>
          <strong>{{ adminRate }}%</strong>
        </article>
        <article>
          <small>7天内活跃用户</small>
          <strong>{{ recentActiveCount }}</strong>
        </article>
      </div>
      <div class="runtime-line">
        检索模式 {{ overview.runtime?.retrieval_mode || '-' }} ｜ 编排模式 {{ overview.runtime?.workflow_mode || '-' }} ｜ 更新时间 {{ formatDateTime(overview.runtime?.time) }}
      </div>
    </section>

    <section class="belt activity-belt">
      <h3>最近活动</h3>
      <AsyncState :loading="loadingOverview" :error="overviewError" :empty="!pagedActivities.length" empty-text="暂无活动" @retry="loadOverview">
        <div class="activity-list">
          <div v-for="(row, idx) in pagedActivities" :key="`act-${idx}`" class="activity-row">
            <span class="activity-event">{{ formatActivityEvent(row) }}</span>
            <span class="activity-actor">{{ formatActivityActor(row) }}</span>
            <small class="activity-time">{{ formatDateTime(row.time) }}</small>
          </div>
        </div>
        <SimplePager :current-page="activityPage" :total="activities.length" :page-size="activityPageSize" @update:currentPage="onActivityPageChange" />
      </AsyncState>
    </section>

    <section class="belt activity-belt">
      <h3>图谱调用与反馈可解释性</h3>
      <AsyncState :loading="loadingObs" :error="obsError" :empty="!pagedGraphLogs.length" empty-text="暂无监管日志" @retry="loadGraphObservability">
        <div class="metric-grid compact">
          <article>
            <small>图谱总调用</small>
            <strong>{{ graphObs.call_stats?.total_calls || 0 }}</strong>
          </article>
          <article>
            <small>调用成功率</small>
            <strong>{{ graphObs.call_stats?.success_rate || 0 }}%</strong>
          </article>
          <article>
            <small>溯源命中率</small>
            <strong>{{ graphObs.feedback_stats?.provenance_rate || 0 }}%</strong>
          </article>
          <article>
            <small>可解释项覆盖</small>
            <strong>{{ graphObs.feedback_stats?.explainable_item_rate || 0 }}%</strong>
          </article>
        </div>
        <table>
          <thead>
            <tr>
              <th>时间</th>
              <th>图谱</th>
              <th>操作</th>
              <th>来源</th>
              <th>结果</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in pagedGraphLogs" :key="item.id || `${item.time}-${item.operation}`">
              <td>{{ formatDateTime(item.time) }}</td>
              <td>{{ item.graph_type || '-' }}</td>
              <td>{{ item.operation || '-' }}</td>
              <td>{{ item.source || '-' }}</td>
              <td>{{ item.success ? '成功' : '失败' }}</td>
            </tr>
          </tbody>
        </table>
        <SimplePager :current-page="graphLogPage" :total="graphObs.recent_logs?.length || 0" :page-size="graphLogPageSize" @update:currentPage="onGraphLogPageChange" />
      </AsyncState>
    </section>

    <section class="belt graph-belt">
      <div class="head-row slim">
        <h3>超图可视化</h3>
        <span class="note">
          超边 {{ hyperStats.rendered_hyperedge_count || 0 }}/{{ hyperStats.total_hyperedge_count || 0 }} ｜
          节点 {{ hyperStats.rendered_node_count || 0 }} ｜ 连线 {{ hyperStats.rendered_edge_count || 0 }}
        </span>
      </div>
      <div class="graph-meta">
        <span class="tag">dataset: {{ hyperStats.dataset || '-' }}</span>
        <span class="tag" :title="hyperStats.source_root || ''">source: {{ shortenPath(hyperStats.source_root) }}</span>
        <span v-for="item in topHyperedgeTypes" :key="`hyper-type-${item.type}`" class="tag">
          {{ item.type }} {{ item.count }}
        </span>
      </div>
      <AsyncState :loading="loadingGraphs" :error="hyperError" :empty="!hyperHasData" empty-text="暂无超图数据" @retry="loadGraphs">
        <div ref="hypergraphRef" class="graph-canvas"></div>
      </AsyncState>
      <div class="taxonomy-grid" v-if="hyperTypeRows.length || hyperMemberRows.length">
        <article class="taxonomy-card" v-if="hyperTypeRows.length">
          <h4>超边分类分布</h4>
          <div ref="hyperTypeChartRef" class="taxonomy-chart"></div>
          <table class="taxonomy-table">
            <thead>
              <tr>
                <th>超边类型</th>
                <th>数量</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in hyperTypeRows" :key="`h-type-${item.type}`">
                <td>{{ item.type }}</td>
                <td>{{ item.count }}</td>
              </tr>
            </tbody>
          </table>
        </article>
        <article class="taxonomy-card" v-if="hyperMemberRows.length">
          <h4>超边成员标签分布</h4>
          <div ref="hyperMemberChartRef" class="taxonomy-chart"></div>
          <table class="taxonomy-table">
            <thead>
              <tr>
                <th>成员标签</th>
                <th>数量</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in hyperMemberRows" :key="`h-member-${item.label}`">
                <td>{{ item.label }}</td>
                <td>{{ item.count }}</td>
              </tr>
            </tbody>
          </table>
        </article>
      </div>
    </section>

    <section class="belt graph-belt">
      <div class="head-row slim">
        <h3>知识图谱可视化</h3>
        <span class="note">
          节点 {{ kgStats.rendered_node_count || 0 }}/{{ kgStats.total_node_count || 0 }} ｜
          边 {{ kgStats.rendered_edge_count || 0 }}/{{ kgStats.total_edge_count || 0 }}
        </span>
      </div>
      <div class="graph-meta">
        <span class="tag">dataset: {{ kgStats.dataset || '-' }}</span>
        <span class="tag" :title="kgStats.source_root || ''">source: {{ shortenPath(kgStats.source_root) }}</span>
        <span v-for="item in topKgLabels" :key="`kg-label-${item.label}`" class="tag">
          {{ item.label }} {{ item.count }}
        </span>
        <span v-for="item in topKgRelations" :key="`kg-rel-${item.type}`" class="tag">
          {{ item.type }} {{ item.count }}
        </span>
      </div>
      <AsyncState :loading="loadingGraphs" :error="kgError" :empty="!kgHasData" empty-text="暂无知识图谱数据" @retry="loadGraphs">
        <div ref="knowledgeRef" class="graph-canvas"></div>
      </AsyncState>
      <div class="taxonomy-grid" v-if="kgLabelRows.length || kgRelationRows.length">
        <article class="taxonomy-card" v-if="kgLabelRows.length">
          <h4>节点分类分布</h4>
          <div ref="kgLabelChartRef" class="taxonomy-chart"></div>
          <table class="taxonomy-table">
            <thead>
              <tr>
                <th>节点类型</th>
                <th>数量</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in kgLabelRows" :key="`kg-node-${item.label}`">
                <td>{{ item.label }}</td>
                <td>{{ item.count }}</td>
              </tr>
            </tbody>
          </table>
        </article>
        <article class="taxonomy-card" v-if="kgRelationRows.length">
          <h4>边分类分布</h4>
          <div ref="kgRelationChartRef" class="taxonomy-chart"></div>
          <table class="taxonomy-table">
            <thead>
              <tr>
                <th>关系类型</th>
                <th>数量</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in kgRelationRows" :key="`kg-rel-${item.type}`">
                <td>{{ item.type }}</td>
                <td>{{ item.count }}</td>
              </tr>
            </tbody>
          </table>
        </article>
      </div>
    </section>

    <section class="belt user-belt">
      <h3>用户治理</h3>
      <div class="toolbar">
        <input v-model.trim="filters.q" type="text" placeholder="用户名/邮箱" @input="onFilterChange">
        <select v-model="filters.role" @change="onFilterChange">
          <option value="all">全部角色</option>
          <option value="student">student</option>
          <option value="teacher">teacher</option>
          <option value="administer">admin</option>
        </select>
        <select v-model="filters.is_active" @change="onFilterChange">
          <option value="all">全部状态</option>
          <option value="true">active</option>
          <option value="false">inactive</option>
        </select>
      </div>
      <div class="batch-wrap">
        <p class="note">批量导入格式：每行 `角色,姓名,学号/工号,默认密码,邮箱`，角色仅支持 `student/teacher`</p>
        <textarea v-model="batchRaw" rows="5" placeholder="student,张三,20260011,Student@123,zhangsan@example.com"></textarea>
        <div class="toolbar">
          <select v-model="batchDefaultRole">
            <option value="student">默认 role=student</option>
            <option value="teacher">默认 role=teacher</option>
          </select>
          <label class="switch-wrap">
            <input v-model="batchOverwrite" type="checkbox">
            <span>覆盖已有用户密码</span>
          </label>
          <button type="button" class="primary" :disabled="batchLoading" @click="batchCreate">
            {{ batchLoading ? '导入中...' : '批量导入用户' }}
          </button>
        </div>
        <p v-if="batchResult" class="note">{{ batchResult }}</p>
      </div>
      <AsyncState :loading="loadingUsers" :error="usersError" :empty="!pagedUsers.length" empty-text="暂无用户数据" @retry="loadUsers">
        <table>
          <thead>
            <tr>
              <th>用户名</th>
              <th>邮箱</th>
              <th>角色</th>
              <th>最近登录</th>
              <th>启用</th>
              <th>角色调整</th>
              <th>管理员权限</th>
              <th>平台超管</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in pagedUsers" :key="item.id || item.username">
              <td>{{ item.username || '-' }}</td>
              <td>{{ item.email || '-' }}</td>
              <td>{{ item.role || '-' }}</td>
              <td>{{ formatDateTime(item.last_login) }}</td>
              <td>
                <label class="switch-wrap">
                  <input
                    type="checkbox"
                    :checked="Boolean(item.is_active)"
                    :disabled="isSelf(item) || updatingUserId === item.id"
                    @change="updateStatus(item, { is_active: $event.target.checked })"
                  >
                  <span>{{ item.is_active ? 'active' : 'inactive' }}</span>
                </label>
              </td>
              <td>
                <select
                  :value="item.role"
                  :disabled="isSelf(item) || updatingUserId === item.id"
                  @change="updateStatus(item, { role: $event.target.value })"
                >
                  <option value="student">student</option>
                  <option value="teacher">teacher</option>
                  <option value="administer">admin</option>
                </select>
              </td>
              <td>
                <label class="switch-wrap">
                  <input
                    type="checkbox"
                    :checked="Boolean(item.is_staff)"
                    :disabled="isSelf(item) || updatingUserId === item.id"
                    @change="updateStatus(item, { is_staff: $event.target.checked })"
                  >
                  <span>{{ item.is_staff ? 'yes' : 'no' }}</span>
                </label>
              </td>
              <td>
                <label class="switch-wrap">
                  <input
                    type="checkbox"
                    :checked="Boolean(item.is_superuser)"
                    :disabled="isSelf(item) || updatingUserId === item.id"
                    @change="updateStatus(item, { is_superuser: $event.target.checked })"
                  >
                  <span>{{ item.is_superuser ? 'yes' : 'no' }}</span>
                </label>
              </td>
            </tr>
          </tbody>
        </table>
        <SimplePager :current-page="currentPage" :total="usersTotal" :page-size="pageSize" @update:currentPage="onPageChange" />
      </AsyncState>
    </section>
  </div>
</template>

<script setup>
import * as echarts from 'echarts';
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue';
import AsyncState from '../../components/core/AsyncState.vue';
import SimplePager from '../../components/core/SimplePager.vue';
import { asArray } from '../../composables/list';
import {
  adminBatchUsersApi,
  adminGraphObservabilityApi,
  adminHypergraphApi,
  adminKnowledgeGraphApi,
  adminOverviewApi,
  adminUpdateUserStatusApi,
  adminUsersApi
} from '../../api/admin';
import { formatDateTime } from '../../utils/datetime';
import { readStoredJson } from '../../utils/storage';

const loading = ref(false);
const loadingOverview = ref(false);
const loadingUsers = ref(false);
const loadingGraphs = ref(false);
const loadingObs = ref(false);
const overviewError = ref('');
const usersError = ref('');
const hyperError = ref('');
const kgError = ref('');
const obsError = ref('');
const updatingUserId = ref(0);

const overview = ref({ users: {}, projects: {}, reviews: {}, runtime: {}, recent_activities: [] });
const activities = computed(() => overview.value.recent_activities || []);
const activityPage = ref(1);
const activityPageSize = 5;
const pagedActivities = computed(() => {
  const start = (activityPage.value - 1) * activityPageSize;
  return activities.value.slice(start, start + activityPageSize);
});

const users = ref([]);
const filters = ref({ q: '', role: 'all', is_active: 'all' });
const currentPage = ref(1);
const pageSize = 10;
const usersTotal = ref(0);
const currentUserId = ref(Number(readStoredJson('user', {})?.id || 0));
const pagedUsers = computed(() => {
  const start = (currentPage.value - 1) * pageSize;
  return users.value.slice(start, start + pageSize);
});
const activeRate = computed(() => {
  if (!usersTotal.value) return 0;
  const active = users.value.filter((item) => Boolean(item?.is_active)).length;
  return Math.round((active / usersTotal.value) * 10000) / 100;
});
const adminRate = computed(() => {
  if (!usersTotal.value) return 0;
  const admins = users.value.filter((item) => Boolean(item?.is_admin || item?.is_staff || item?.is_superuser || item?.role === 'administer')).length;
  return Math.round((admins / usersTotal.value) * 10000) / 100;
});
const recentActiveCount = computed(() => {
  const now = Date.now();
  const limit = 7 * 24 * 3600 * 1000;
  return users.value.filter((item) => {
    if (!item?.last_login) return false;
    const ts = new Date(item.last_login).getTime();
    return Number.isFinite(ts) && now - ts <= limit;
  }).length;
});

const graphObs = ref({ recent_logs: [], call_stats: {}, feedback_stats: {} });
const graphLogPage = ref(1);
const graphLogPageSize = 8;
const pagedGraphLogs = computed(() => {
  const start = (graphLogPage.value - 1) * graphLogPageSize;
  return (graphObs.value.recent_logs || []).slice(start, start + graphLogPageSize);
});
const hypergraphRef = ref(null);
const knowledgeRef = ref(null);
const hyperTypeChartRef = ref(null);
const hyperMemberChartRef = ref(null);
const kgLabelChartRef = ref(null);
const kgRelationChartRef = ref(null);
const hyperStats = ref({});
const kgStats = ref({});
const hyperHasData = ref(false);
const kgHasData = ref(false);
const topHyperedgeTypes = computed(() => asArray(hyperStats.value?.hyperedge_type_top).slice(0, 6));
const topKgLabels = computed(() => asArray(kgStats.value?.node_label_top).slice(0, 4));
const topKgRelations = computed(() => asArray(kgStats.value?.relation_type_top).slice(0, 4));
const hyperTypeRows = computed(() => asArray(hyperStats.value?.hyperedge_type_top));
const hyperMemberRows = computed(() => asArray(hyperStats.value?.member_label_top));
const kgLabelRows = computed(() => asArray(kgStats.value?.node_label_top));
const kgRelationRows = computed(() => asArray(kgStats.value?.relation_type_top));
let hyperChart = null;
let kgChart = null;
let hyperTypeChart = null;
let hyperMemberChart = null;
let kgLabelChart = null;
let kgRelationChart = null;
const batchRaw = ref('');
const batchDefaultRole = ref('student');
const batchOverwrite = ref(false);
const batchLoading = ref(false);
const batchResult = ref('');

const formatActivityEvent = (row) => row?.title || row?.event || row?.operation || row?.action || '-';

const formatActivityActor = (row) => row?.student_name || row?.teacher_name || row?.actor || row?.user || row?.student || row?.teacher || row?.meta || '-';

const shortenPath = (value) => {
  const raw = String(value || '').trim();
  if (!raw) return '-';
  const parts = raw.split(/[\\/]+/).filter(Boolean);
  if (parts.length <= 2) return raw;
  return `.../${parts.slice(-2).join('/')}`;
};

const isTimeoutError = (error) => {
  const code = String(error?.code || '').toUpperCase();
  const message = String(error?.message || '').toLowerCase();
  return code === 'ECONNABORTED' || message.includes('timeout');
};

const fetchHypergraphWithFallback = async () => {
  try {
    return await adminHypergraphApi({ limit_hyperedges: 100, max_members: 5 }, { timeout: 20000 });
  } catch (error) {
    if (!isTimeoutError(error)) throw error;
    return await adminHypergraphApi({ limit_hyperedges: 48, max_members: 4 }, { timeout: 12000 });
  }
};

const fetchKnowledgeGraphWithFallback = async () => {
  try {
    return await adminKnowledgeGraphApi({ limit_nodes: 160, limit_edges: 300 }, { timeout: 20000 });
  } catch (error) {
    if (!isTimeoutError(error)) throw error;
    return await adminKnowledgeGraphApi({ limit_nodes: 100, limit_edges: 180 }, { timeout: 12000 });
  }
};

const normalizeGraphPayload = (payload) => {
  if (!payload || typeof payload !== 'object') {
    return { nodes: [], links: [], categories: [], stats: {} };
  }
  if (Array.isArray(payload.nodes) || Array.isArray(payload.links)) {
    return payload;
  }
  if (payload.graph && typeof payload.graph === 'object') {
    return payload.graph;
  }
  if (payload.data && typeof payload.data === 'object') {
    return payload.data;
  }
  return { nodes: [], links: [], categories: [], stats: {} };
};

const GRAPH_ICON_COLORS = ['#0B6E4F', '#1B4D89', '#8E3B46', '#7A5C1E', '#5D3FD3', '#A34700', '#006D77', '#6B2D5C'];

const categoryNameByIndex = (categories = []) => {
  const map = {};
  (categories || []).forEach((item, idx) => {
    map[idx] = String(item?.name || '').trim() || `C${idx}`;
  });
  return map;
};

const categoryIconUri = (categoryName, idx) => {
  const label = String(categoryName || '').trim() || `C${idx}`;
  const shortLabel = label.slice(0, 2).toUpperCase();
  const color = GRAPH_ICON_COLORS[idx % GRAPH_ICON_COLORS.length];
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="96" height="96" viewBox="0 0 96 96"><defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop offset="0%" stop-color="${color}"/><stop offset="100%" stop-color="#0f172a"/></linearGradient></defs><circle cx="48" cy="48" r="44" fill="url(#g)"/><circle cx="48" cy="48" r="43" fill="none" stroke="rgba(255,255,255,0.28)" stroke-width="2"/><text x="48" y="56" text-anchor="middle" fill="#ffffff" font-family="Arial, sans-serif" font-size="24" font-weight="700">${shortLabel}</text></svg>`;
  return `image://data:image/svg+xml;utf8,${encodeURIComponent(svg)}`;
};

const withImageSymbols = (payload) => {
  const categories = payload?.categories || [];
  const categoryMap = categoryNameByIndex(categories);
  return (payload?.nodes || []).map((node) => {
    const categoryIndex = Number(node?.category ?? -1);
    const categoryName = categoryMap[categoryIndex] || 'Entity';
    const symbolSize = Number(node?.symbolSize || 18);
    return {
      ...node,
      symbol: categoryIconUri(categoryName, Math.max(0, categoryIndex)),
      symbolSize,
      symbolKeepAspect: true
    };
  });
};

const drawGraph = (chart, payload) => {
  const nodesWithSymbols = withImageSymbols(payload || {});
  chart.setOption({
    tooltip: {
      formatter: (params) => {
        if (params?.dataType === 'node') {
          const node = params.data || {};
          const title = String(node.name || node.id || '-');
          const kind = String(node.value || '');
          return kind ? `${title}<br/>${kind}` : title;
        }
        if (params?.dataType === 'edge') {
          const edge = params.data || {};
          return String(edge.value || edge.name || '关联');
        }
        return '';
      }
    },
    legend: [{ data: (payload.categories || []).map((x) => x.name) }],
    series: [
      {
        type: 'graph',
        layout: 'force',
        roam: true,
        data: nodesWithSymbols,
        links: payload.links || [],
        categories: payload.categories || [],
        force: { repulsion: 130, edgeLength: [32, 120] },
        label: { show: true, fontSize: 11 },
        lineStyle: { opacity: 0.38 }
      }
    ]
  }, true);
};

const drawStatChart = (chart, rows, options = {}) => {
  const dataRows = asArray(rows).slice(0, 12);
  const labelKey = options.labelKey || 'name';
  const title = options.title || '';
  const color = options.color || '#1B4D89';
  const labels = dataRows.map((item) => String(item?.[labelKey] || '-'));
  const values = dataRows.map((item) => Number(item?.count || 0));
  chart.setOption({
    title: title ? { text: title, left: 0, textStyle: { fontSize: 12, color: '#475569' } } : undefined,
    grid: { left: 60, right: 18, top: title ? 26 : 10, bottom: 10, containLabel: true },
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    xAxis: {
      type: 'value',
      axisLine: { show: false },
      axisTick: { show: false },
      splitLine: { lineStyle: { color: 'rgba(100,116,139,0.14)' } }
    },
    yAxis: {
      type: 'category',
      data: labels,
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: { color: '#475569', width: 120, overflow: 'truncate' }
    },
    series: [{
      type: 'bar',
      data: values,
      barWidth: 14,
      itemStyle: {
        color,
        borderRadius: [6, 6, 6, 6]
      }
    }]
  }, true);
};

const syncTaxonomyCharts = async () => {
  await nextTick();

  const syncSingleChart = (refEl, chartInstance, rows, options) => {
    const hasRows = asArray(rows).length > 0;
    if (refEl && hasRows) {
      const chart = chartInstance || echarts.init(refEl);
      drawStatChart(chart, rows, options);
      chart.resize();
      return chart;
    }
    if (chartInstance) {
      chartInstance.dispose();
    }
    return null;
  };

  hyperTypeChart = syncSingleChart(hyperTypeChartRef.value, hyperTypeChart, hyperTypeRows.value, { labelKey: 'type', title: '超边类型', color: '#0B6E4F' });
  hyperMemberChart = syncSingleChart(hyperMemberChartRef.value, hyperMemberChart, hyperMemberRows.value, { labelKey: 'label', title: '成员标签', color: '#A34700' });
  kgLabelChart = syncSingleChart(kgLabelChartRef.value, kgLabelChart, kgLabelRows.value, { labelKey: 'label', title: '节点类型', color: '#1B4D89' });
  kgRelationChart = syncSingleChart(kgRelationChartRef.value, kgRelationChart, kgRelationRows.value, { labelKey: 'type', title: '关系类型', color: '#8E3B46' });
};

const syncGraphCharts = async (hyperData, kgData) => {
  await nextTick();

  if (hypergraphRef.value && hyperHasData.value) {
    hyperChart = hyperChart || echarts.init(hypergraphRef.value);
    drawGraph(hyperChart, hyperData || { nodes: [], links: [], categories: [] });
    hyperChart.resize();
  } else if (hyperChart) {
    hyperChart.dispose();
    hyperChart = null;
  }

  if (knowledgeRef.value && kgHasData.value) {
    kgChart = kgChart || echarts.init(knowledgeRef.value);
    drawGraph(kgChart, kgData || { nodes: [], links: [], categories: [] });
    kgChart.resize();
  } else if (kgChart) {
    kgChart.dispose();
    kgChart = null;
  }
};

const loadOverview = async () => {
  loadingOverview.value = true;
  overviewError.value = '';
  try {
    overview.value = (await adminOverviewApi()) || {};
    activityPage.value = 1;
  } catch (e) {
    overview.value = { users: {}, projects: {}, reviews: {}, runtime: {}, recent_activities: [] };
    overviewError.value = e?.response?.data?.detail || '总览指标加载失败';
  } finally {
    loadingOverview.value = false;
  }
};

const loadUsers = async () => {
  loadingUsers.value = true;
  usersError.value = '';
  try {
    const res = await adminUsersApi(filters.value);
    users.value = asArray(res);
    usersTotal.value = users.value.length;
  } catch (e) {
    users.value = [];
    usersTotal.value = 0;
    usersError.value = e?.response?.data?.detail || '用户数据加载失败';
  } finally {
    loadingUsers.value = false;
  }
};

const loadGraphs = async () => {
  loadingGraphs.value = true;
  hyperError.value = '';
  kgError.value = '';
  try {
    const [hyperResult, kgResult] = await Promise.allSettled([
      fetchHypergraphWithFallback(),
      fetchKnowledgeGraphWithFallback()
    ]);
    const hyperData = hyperResult.status === 'fulfilled' ? normalizeGraphPayload(hyperResult.value) : null;
    const kgData = kgResult.status === 'fulfilled' ? normalizeGraphPayload(kgResult.value) : null;

    hyperStats.value = hyperData?.stats || {};
    kgStats.value = kgData?.stats || {};
    hyperHasData.value = Array.isArray(hyperData?.nodes) && hyperData.nodes.length > 0;
    kgHasData.value = Array.isArray(kgData?.nodes) && kgData.nodes.length > 0;
    hyperError.value = hyperResult.status === 'rejected' ? hyperResult.reason?.response?.data?.detail || '超图渲染失败' : '';
    kgError.value = kgResult.status === 'rejected' ? kgResult.reason?.response?.data?.detail || '知识图谱渲染失败' : '';
    if (!hyperError.value && !hyperHasData.value && hyperStats.value?.load_error) {
      hyperError.value = hyperStats.value.load_error;
    }
    if (!kgError.value && !kgHasData.value && kgStats.value?.load_error) {
      kgError.value = kgStats.value.load_error;
    }

    // AsyncState uses `loadingGraphs` to gate slot rendering.
    // Turn loading off before syncing charts so refs exist in DOM.
    loadingGraphs.value = false;
    if (hyperHasData.value || kgHasData.value) {
      await syncGraphCharts(hyperData, kgData);
    } else {
      await syncGraphCharts(null, null);
    }
    await syncTaxonomyCharts();
  } catch (e) {
    hyperHasData.value = false;
    kgHasData.value = false;
    hyperError.value = e?.response?.data?.detail || '超图渲染失败';
    kgError.value = e?.response?.data?.detail || '知识图谱渲染失败';
    await syncTaxonomyCharts();
  } finally {
    loadingGraphs.value = false;
  }
};

const loadGraphObservability = async () => {
  loadingObs.value = true;
  obsError.value = '';
  try {
    graphObs.value = (await adminGraphObservabilityApi({ limit: 80 })) || { recent_logs: [], call_stats: {}, feedback_stats: {} };
    graphLogPage.value = 1;
  } catch (e) {
    graphObs.value = { recent_logs: [], call_stats: {}, feedback_stats: {} };
    obsError.value = e?.response?.data?.detail || '监管数据加载失败';
  } finally {
    loadingObs.value = false;
  }
};

const updateStatus = async (row, payload) => {
  if (!row?.id) return;
  updatingUserId.value = row.id;
  try {
    await adminUpdateUserStatusApi(row.id, payload);
    await loadUsers();
  } finally {
    updatingUserId.value = 0;
  }
};

const batchCreate = async () => {
  if (!batchRaw.value.trim()) {
    batchResult.value = '请先输入批量用户数据';
    return;
  }
  batchLoading.value = true;
  try {
    const result = await adminBatchUsersApi({
      raw: batchRaw.value,
      default_role: batchDefaultRole.value,
      overwrite_password: batchOverwrite.value
    });
    const summary = result?.summary || {};
    batchResult.value = `导入完成：创建${summary.created_count || 0}，更新${summary.updated_count || 0}，跳过${summary.skipped_count || 0}，失败${summary.error_count || 0}`;
    await loadUsers();
  } catch (e) {
    batchResult.value = e?.response?.data?.detail || '批量导入失败';
  } finally {
    batchLoading.value = false;
  }
};

const isSelf = (row) => Number(row?.id || 0) === Number(currentUserId.value || 0);

const onFilterChange = async () => {
  currentPage.value = 1;
  await loadUsers();
};

const onPageChange = async (page) => {
  currentPage.value = page;
};

const onActivityPageChange = (page) => {
  activityPage.value = page;
};

const onGraphLogPageChange = (page) => {
  graphLogPage.value = page;
};

const load = async () => {
  loading.value = true;
  try {
    await Promise.all([loadOverview(), loadUsers(), loadGraphs(), loadGraphObservability()]);
  } finally {
    loading.value = false;
  }
};

onMounted(load);

const handleResize = () => {
  hyperChart?.resize();
  kgChart?.resize();
  hyperTypeChart?.resize();
  hyperMemberChart?.resize();
  kgLabelChart?.resize();
  kgRelationChart?.resize();
};

window.addEventListener('resize', handleResize);

onBeforeUnmount(() => {
  window.removeEventListener('resize', handleResize);
  hyperChart?.dispose();
  kgChart?.dispose();
  hyperTypeChart?.dispose();
  hyperMemberChart?.dispose();
  kgLabelChart?.dispose();
  kgRelationChart?.dispose();
  hyperChart = null;
  kgChart = null;
  hyperTypeChart = null;
  hyperMemberChart = null;
  kgLabelChart = null;
  kgRelationChart = null;
});
</script>

<style scoped>
.admin-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}

.belt {
  border: 1px solid var(--line-strong);
  background: var(--bg-panel);
  padding: 18px;
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-soft);
}

.overview-belt,
.activity-belt,
.graph-belt,
.user-belt {
  grid-column: 1 / -1;
}

.head-row {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 14px;
}

.head-row.slim {
  align-items: center;
}

.note {
  color: var(--ink-muted);
  font-size: 12px;
  line-height: 1.5;
}

.graph-meta {
  margin-top: 10px;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.tag {
  display: inline-flex;
  align-items: center;
  min-height: 24px;
  padding: 0 10px;
  border-radius: 999px;
  border: 1px solid var(--line-soft);
  background: color-mix(in oklch, var(--bg-field) 88%, white);
  color: var(--ink-body);
  font-size: 12px;
  line-height: 1;
}

h2,
h3 {
  margin: 0;
  font-family: var(--font-display);
  color: var(--ink-title);
  letter-spacing: 0.012em;
}

p {
  margin: 10px 0 0;
}

.metric-grid {
  margin-top: 12px;
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
}

.metric-grid.compact {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.metric-grid article {
  border: 1px solid color-mix(in oklch, var(--line-soft) 90%, white);
  border-radius: 12px;
  padding: 10px 11px;
  display: grid;
  gap: 4px;
  background: color-mix(in oklch, var(--bg-field) 88%, white);
}

.metric-grid small {
  color: var(--ink-muted);
  font-size: 12px;
  letter-spacing: 0.02em;
}

.metric-grid strong {
  color: var(--ink-title);
  font-size: 20px;
  line-height: 1.15;
  font-variant-numeric: tabular-nums;
}

.runtime-line {
  margin-top: 12px;
  color: var(--ink-muted);
  border-top: 1px dashed color-mix(in oklch, var(--line-soft) 88%, white);
  padding-top: 10px;
  font-size: 13px;
}

.activity-list {
  margin-top: 12px;
  display: grid;
  gap: 10px;
}

.activity-row {
  display: grid;
  grid-template-columns: minmax(0, 2fr) minmax(180px, 1fr) 150px;
  gap: 12px;
  align-items: center;
  padding: 12px 14px;
  border: 1px solid color-mix(in oklch, var(--line-soft) 90%, white);
  border-radius: 12px;
  background: color-mix(in oklch, var(--bg-field) 90%, white);
}

.activity-event,
.activity-actor {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.activity-event {
  color: var(--ink-title);
  font-weight: 650;
}

.activity-actor,
.activity-time {
  color: var(--ink-muted);
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

.batch-wrap {
  margin-top: 12px;
  border: 1px dashed var(--line-soft);
  background: var(--bg-field);
  padding: 12px;
}

.batch-wrap textarea {
  width: 100%;
  margin-top: 8px;
  border: 1px solid var(--line-strong);
  background: color-mix(in oklch, var(--bg-main) 94%, white);
  color: var(--ink-title);
  border-radius: var(--control-radius);
  padding: 10px;
  min-height: 96px;
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
  border-collapse: separate;
  border-spacing: 0;
  margin-top: 12px;
  table-layout: fixed;
}

th,
td {
  text-align: left;
  padding: 12px 10px;
  border-bottom: 1px solid var(--table-border);
  color: var(--ink-body);
  vertical-align: top;
  word-break: break-word;
  overflow-wrap: anywhere;
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

ul {
  margin: 12px 0 0;
  padding-left: 18px;
  display: grid;
  gap: 8px;
}

li {
  display: grid;
  gap: 2px;
}

small {
  color: var(--ink-muted);
}

.switch-wrap {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  white-space: nowrap;
}

button.primary {
  min-height: 36px;
  border: 1px solid var(--ink-title);
  background: var(--ink-title);
  color: var(--bg-main);
  border-radius: 999px;
  padding: 0 14px;
  cursor: pointer;
}

.graph-canvas {
  margin-top: 12px;
  width: 100%;
  height: 420px;
  border: 1px solid color-mix(in oklch, var(--line-soft) 90%, white);
  border-radius: 12px;
  background: color-mix(in oklch, var(--bg-field) 91%, white);
}

.taxonomy-grid {
  margin-top: 12px;
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.taxonomy-card {
  border: 1px solid color-mix(in oklch, var(--line-soft) 90%, white);
  border-radius: 12px;
  background: color-mix(in oklch, var(--bg-field) 91%, white);
  padding: 10px;
}

.taxonomy-card h4 {
  margin: 0;
  color: var(--ink-title);
  font-size: 14px;
}

.taxonomy-chart {
  margin-top: 8px;
  height: 220px;
  width: 100%;
}

.taxonomy-table {
  margin-top: 8px;
  width: 100%;
  border-collapse: collapse;
}

.taxonomy-table th,
.taxonomy-table td {
  padding: 7px 6px;
  border-bottom: 1px solid color-mix(in oklch, var(--line-soft) 90%, white);
  font-size: 12px;
}

.taxonomy-table th {
  color: var(--ink-muted);
  font-weight: 600;
}

.activity-belt table th:nth-child(1),
.activity-belt table td:nth-child(1) {
  width: 140px;
}

.activity-belt table th:nth-child(2),
.activity-belt table td:nth-child(2) {
  width: 120px;
}

.activity-belt table th:nth-child(3),
.activity-belt table td:nth-child(3) {
  width: 42%;
}

.activity-belt table th:nth-child(4),
.activity-belt table td:nth-child(4) {
  width: 22%;
}

.activity-belt table th:nth-child(5),
.activity-belt table td:nth-child(5) {
  width: 90px;
}

.activity-belt td:nth-child(3),
.activity-belt td:nth-child(4) {
  line-height: 1.45;
}

@media (max-width: 1100px) {
  .admin-grid {
    grid-template-columns: 1fr;
  }

  .metric-grid,
  .metric-grid.compact {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .activity-row {
    grid-template-columns: 1fr;
    gap: 8px;
  }

  .taxonomy-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 480px) {
  .metric-grid,
  .metric-grid.compact {
    grid-template-columns: 1fr;
  }

  .graph-canvas {
    height: 320px;
  }

  .head-row {
    flex-wrap: wrap;
  }
}
</style>






