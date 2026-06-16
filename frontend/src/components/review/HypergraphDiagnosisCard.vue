<template>
  <div class="hypergraph-card">
    <p v-if="!hasDiagnosis" class="empty-text">{{ emptyText }}</p>
    <template v-else>
      <section class="group overview-shell">
        <button
          type="button"
          class="group-head group-toggle"
          :aria-expanded="isCardOpen('overview', true)"
          @click="toggleCard('overview', true)"
        >
          <h4>超图诊断</h4>
          <span class="group-toggle-side">
            <span class="status-pill" :class="statusClass">{{ diagnosisStatus }}</span>
            <span class="toggle-state">{{ cardToggleText('overview', true) }}</span>
          </span>
        </button>
        <div v-show="isCardOpen('overview', true)" class="group-body">
          <div class="overview-grid">
            <article class="metric metric-wide">
              <span class="label">匹配项目</span>
              <strong>{{ matchedProjectText }}</strong>
            </article>
            <article class="metric">
              <span class="label">总体判断</span>
              <strong>{{ diagnosisConclusion }}</strong>
            </article>
            <article class="metric">
              <span class="label">关键缺口</span>
              <strong>{{ gapSummary }}</strong>
            </article>
          </div>
          <div class="mini-metrics">
            <article v-for="item in overviewMetrics" :key="item.label" class="mini-metric">
              <span>{{ item.label }}</span>
              <strong>{{ item.value }}</strong>
            </article>
          </div>
          <div v-if="summaryEvidence.length" class="summary-evidence">
            <span class="summary-evidence-title">诊断依据</span>
            <ul class="list compact summary-list">
              <li v-for="(item, idx) in summaryEvidence" :key="`summary-${idx}`">{{ item }}</li>
            </ul>
          </div>
        </div>
      </section>

      <section v-if="explanationCards.length" class="group">
        <button
          type="button"
          class="group-head group-toggle"
          :aria-expanded="isCardOpen('explanation', true)"
          @click="toggleCard('explanation', true)"
        >
          <span class="group-toggle-main">
            <h4>系统是这样得出结论的</h4>
            <span class="section-count">{{ explanationCards.length }}</span>
          </span>
          <span class="toggle-state">{{ cardToggleText('explanation', true) }}</span>
        </button>
        <div v-show="isCardOpen('explanation', true)" class="group-body">
          <p class="section-tip">系统先匹配最接近的项目，再看命中的关键节点和超边关系，最后结合缺口、风险和相似案例给出结论。</p>
          <div class="evidence-list">
            <article v-for="(item, idx) in explanationCards" :key="`explain-${idx}`" class="evidence-card explanation-card">
              <div class="evidence-head">
                <strong>{{ item.title }}</strong>
                <span v-if="item.badge" class="meta-pill">{{ item.badge }}</span>
              </div>
              <p class="evidence-text">{{ item.detail }}</p>
              <ul v-if="item.points.length" class="list compact">
                <li v-for="(point, pointIdx) in item.points" :key="`point-${idx}-${pointIdx}`">{{ point }}</li>
              </ul>
            </article>
          </div>
        </div>
      </section>

      <section v-if="findingRows.length" class="group">
        <button
          type="button"
          class="group-head group-toggle"
          :aria-expanded="isCardOpen('findings', true)"
          @click="toggleCard('findings', true)"
        >
          <span class="group-toggle-main">
            <h4>诊断总结</h4>
            <span class="section-count">{{ findingRows.length }}</span>
          </span>
          <span class="toggle-state">{{ cardToggleText('findings', true) }}</span>
        </button>
        <div v-show="isCardOpen('findings', true)" class="group-body">
          <p class="section-tip">这里直接给出诊断结论、依据和建议动作，便于教师或学生快速判断下一步怎么改。</p>
          <div class="finding-list">
            <article v-for="item in findingRows" :key="item.key" class="finding-card" :class="`finding-${item.level}`">
              <div class="finding-head">
                <strong>{{ item.title }}</strong>
                <span class="finding-level" :class="`finding-level-${item.level}`">{{ levelText(item.level) }}</span>
              </div>
              <p class="finding-detail">{{ item.detail }}</p>
              <ul v-if="showFindingEvidenceList(item) && item.evidence.length" class="list compact">
                <li v-for="(evidence, idx) in item.evidence" :key="`${item.key}-${idx}`">{{ evidence }}</li>
              </ul>
              <p v-if="item.action" class="finding-action">建议动作：{{ item.action }}</p>
            </article>
          </div>
        </div>
      </section>

      <section v-if="riskPatterns.length" class="group">
        <button
          type="button"
          class="group-head group-toggle"
          :aria-expanded="isCardOpen('risk', false)"
          @click="toggleCard('risk', false)"
        >
          <span class="group-toggle-main">
            <h4>风险模式</h4>
            <span class="section-count">{{ riskPatterns.length }}</span>
          </span>
          <span class="toggle-state">{{ cardToggleText('risk', false) }}</span>
        </button>
        <div v-show="isCardOpen('risk', false)" class="group-body">
          <div class="finding-list">
            <article v-for="(item, idx) in sectionRows(riskPatterns, 'risk', 6)" :key="`risk-${idx}`" class="finding-card finding-warning">
              <div class="finding-head">
                <strong>{{ item.type }}</strong>
                <span class="risk-pill" :class="riskLevelClass(item.severity)">{{ item.severity }}</span>
              </div>
              <p v-if="item.example" class="finding-detail">{{ item.example }}</p>
            </article>
          </div>
          <button v-if="showToggle(riskPatterns, 6)" type="button" class="toggle-btn" @click="toggleSection('risk')">
            {{ isExpanded('risk') ? '收起' : `展开其余 ${sectionHiddenCount(riskPatterns, 'risk', 6)} 条` }}
          </button>
        </div>
      </section>

      <section v-if="suggestedEvidenceRows.length" class="group">
        <button
          type="button"
          class="group-head group-toggle"
          :aria-expanded="isCardOpen('evidence', false)"
          @click="toggleCard('evidence', false)"
        >
          <span class="group-toggle-main">
            <h4>建议补充证据</h4>
            <span class="section-count">{{ suggestedEvidenceRows.length }}</span>
          </span>
          <span class="toggle-state">{{ cardToggleText('evidence', false) }}</span>
        </button>
        <div v-show="isCardOpen('evidence', false)" class="group-body">
          <p class="section-tip">这里告诉你还缺哪些材料来证明方案成立，每条都说明支撑的是哪类结论，以及来源从哪里补。</p>
          <div class="evidence-list">
            <article v-for="(item, idx) in sectionRows(suggestedEvidenceRows, 'evidence', 6)" :key="`evidence-${idx}`" class="evidence-card suggestion-card">
              <div class="evidence-head">
                <strong>{{ item.supportTitle }}</strong>
                <span v-if="item.evidenceTypeLabel" class="meta-pill">{{ item.evidenceTypeLabel }}</span>
              </div>
              <span class="field-label">建议补什么</span>
              <p class="evidence-text">{{ item.text }}</p>
              <p v-if="item.explanation" class="evidence-explainer">{{ item.explanation }}</p>
              <div class="meta-row">
                <span v-if="item.referenceLabel" class="meta-pill">{{ item.referenceLabel }}</span>
                <span v-if="item.competition" class="meta-pill">案例 {{ item.competition }}</span>
                <span v-if="item.fileName" class="meta-pill">{{ item.fileName }}</span>
              </div>
            </article>
          </div>
          <button v-if="showToggle(suggestedEvidenceRows, 6)" type="button" class="toggle-btn" @click="toggleSection('evidence')">
            {{ isExpanded('evidence') ? '收起' : `展开其余 ${sectionHiddenCount(suggestedEvidenceRows, 'evidence', 6)} 条` }}
          </button>
        </div>
      </section>

      <section v-if="similarProjects.length" class="group">
        <button
          type="button"
          class="group-head group-toggle"
          :aria-expanded="isCardOpen('similar', false)"
          @click="toggleCard('similar', false)"
        >
          <span class="group-toggle-main">
            <h4>相似项目参考</h4>
            <span class="section-count">{{ similarProjects.length }}</span>
          </span>
          <span class="toggle-state">{{ cardToggleText('similar', false) }}</span>
        </button>
        <div v-show="isCardOpen('similar', false)" class="group-body">
          <div class="evidence-list">
            <article v-for="(item, idx) in sectionRows(similarProjects, 'similar', 5)" :key="`similar-${idx}`" class="evidence-card">
              <p class="evidence-text">{{ item.name }}</p>
              <div class="meta-row">
                <span class="meta-pill">ID {{ item.id }}</span>
                <span class="meta-pill">相似度 {{ item.score }}</span>
              </div>
            </article>
          </div>
          <button v-if="showToggle(similarProjects, 5)" type="button" class="toggle-btn" @click="toggleSection('similar')">
            {{ isExpanded('similar') ? '收起' : `展开其余 ${sectionHiddenCount(similarProjects, 'similar', 5)} 条` }}
          </button>
        </div>
      </section>

      <section v-if="showProvenance && provenanceRows.length" class="group">
        <button
          type="button"
          class="group-head group-toggle"
          :aria-expanded="isCardOpen('provenance', false)"
          @click="toggleCard('provenance', false)"
        >
          <span class="group-toggle-main">
            <h4>溯源证据</h4>
            <span class="section-count">{{ provenanceRows.length }}</span>
          </span>
          <span class="toggle-state">{{ cardToggleText('provenance', false) }}</span>
        </button>
        <div v-show="isCardOpen('provenance', false)" class="group-body">
          <p class="section-tip">这里说明每条结论对应的是哪个来源。点击卡片后，学生端或教师端会尽量跳到对应批注、问题或对话位置。</p>
          <div class="evidence-list">
            <button
              v-for="(item, idx) in sectionRows(provenanceRows, 'source_all', 8)"
              :key="`source-${idx}`"
              type="button"
              class="evidence-card trace-btn"
              @click="emit('trace-click', item.raw)"
            >
              <div class="evidence-head">
                <strong>{{ item.supportTitle }}</strong>
                <span v-if="item.kindLabel" class="meta-pill">{{ item.kindLabel }}</span>
              </div>
              <span class="field-label">对应来源</span>
              <p class="evidence-title">{{ item.title }}</p>
              <p v-if="item.text" class="evidence-text">{{ item.text }}</p>
              <p v-if="item.explanation" class="evidence-explainer">{{ item.explanation }}</p>
              <div class="meta-row">
                <span v-if="item.referenceLabel" class="meta-pill">{{ item.referenceLabel }}</span>
                <span v-if="item.fileName" class="meta-pill">{{ item.fileName }}</span>
                <span v-if="item.competition" class="meta-pill">{{ item.competition }}</span>
              </div>
            </button>
          </div>
          <button v-if="showToggle(provenanceRows, 8)" type="button" class="toggle-btn" @click="toggleSection('source_all')">
            {{ isExpanded('source_all') ? '收起' : `展开其余 ${sectionHiddenCount(provenanceRows, 'source_all', 8)} 条` }}
          </button>
        </div>
      </section>
    </template>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue';

const props = defineProps({
  meta: {
    type: Object,
    default: () => ({})
  },
  emptyText: {
    type: String,
    default: '暂无超图诊断结果'
  },
  showProvenance: {
    type: Boolean,
    default: true
  }
});

const emit = defineEmits(['trace-click']);

const meta = computed(() => props.meta || {});
const hasDiagnosis = computed(() => Object.keys(meta.value || {}).length > 0);
const expandedSections = ref({});
const openCards = ref({
  overview: true,
  explanation: true,
  findings: true,
  risk: false,
  evidence: false,
  similar: false,
  provenance: false
});

const cleanText = (value) => String(value ?? '').replace(/\s+/g, ' ').trim();
const asArray = (value) => (Array.isArray(value) ? value : []);

const dedupeBy = (rows, getKey) => {
  const seen = new Set();
  return rows.filter((item) => {
    const key = cleanText(getKey(item)).toLowerCase();
    if (!key || seen.has(key)) return false;
    seen.add(key);
    return true;
  });
};

const basename = (value) => {
  const raw = cleanText(value);
  if (!raw) return '';
  const parts = raw.split(/[\\/]+/).filter(Boolean);
  return parts[parts.length - 1] || raw;
};

const formatPercent = (value) => {
  const num = Number(value);
  if (!Number.isFinite(num)) return '-';
  if (num >= 0 && num <= 1) return `${Math.round(num * 100)}%`;
  return `${Math.round(num)}%`;
};

const formatScore = (value) => {
  const num = Number(value);
  if (!Number.isFinite(num)) return '-';
  if (num >= 0 && num <= 1) return `${(num * 100).toFixed(0)}%`;
  return `${num.toFixed(2)}`;
};

const formatListText = (value) => {
  if (value == null) return '';
  if (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') {
    return cleanText(value);
  }
  if (Array.isArray(value)) {
    return value.map((item) => formatListText(item)).filter(Boolean).join('；');
  }
  if (typeof value === 'object') {
    const preferred = ['summary', 'conclusion', 'text', 'detail', 'reason', 'message', 'label', 'name', 'type', 'value'];
    const picked = preferred.map((key) => cleanText(value[key])).filter(Boolean);
    if (picked.length) return picked.slice(0, 3).join('；');
    return Object.entries(value)
      .map(([key, item]) => {
        const text = cleanText(item);
        return text ? `${key}: ${text}` : '';
      })
      .filter(Boolean)
      .slice(0, 3)
      .join('；');
  }
  return '';
};

const textArray = (value) => asArray(value).map((item) => formatListText(item)).filter(Boolean);

const evidenceTypeText = (value) => {
  const normalized = cleanText(value).toLowerCase();
  if (!normalized) return '';
  if (normalized === 'document_snippet') return '文档证据';
  if (normalized === 'enrichment') return '补强论证';
  if (normalized === 'metric') return '量化指标';
  if (normalized === 'expert_opinion') return '专家意见';
  return cleanText(value).replace(/_/g, ' ');
};

const inputTypeText = (value) => {
  const normalized = cleanText(value).toLowerCase();
  if (normalized === 'project_id') return '按项目节点匹配';
  if (normalized === 'text') return '按文本内容匹配';
  if (normalized === 'none') return '未启用';
  return cleanText(value) || '未知';
};

const hyperedgeTypeText = (value) => {
  const normalized = cleanText(value);
  if (normalized === 'RiskPattern') return '风险模式关系';
  if (normalized === 'ValueLoop') return '价值闭环关系';
  if (normalized === 'ResourceLeverage') return '资源杠杆关系';
  if (normalized === 'EvidenceChain') return '证据链关系';
  return normalized || '关系';
};

const supportTitleFromNodeLabel = (label) => {
  const normalized = cleanText(label);
  if (normalized === 'Market') return '支撑市场需求与用户场景判断';
  if (normalized === 'Technology') return '支撑技术可行性判断';
  if (normalized === 'Method') return '支撑实施路径判断';
  if (normalized === 'Metric') return '支撑量化指标与验证结果判断';
  if (normalized === 'Project') return '支撑项目匹配判断';
  if (normalized === 'Mistake') return '支撑风险判断';
  return '支撑结论判断';
};

const supportTitleFromHyperedgeType = (label) => {
  const normalized = cleanText(label);
  if (normalized === 'RiskPattern') return '支撑风险判断';
  if (normalized === 'ValueLoop') return '支撑商业闭环判断';
  if (normalized === 'ResourceLeverage') return '支撑资源利用与成本判断';
  if (normalized === 'EvidenceChain') return '支撑证据链完整度判断';
  return '支撑关系判断';
};

const buildReferenceLabel = (fileName, kindLabel) => {
  if (fileName) return '来源文件';
  if (kindLabel === '超边溯源') return '来源关系';
  return '';
};

const explainSuggestion = (title) => {
  if (!title) return '';
  return `这条材料主要用来${title.replace('支撑', '证明')}。`;
};

const explainProvenance = (kindLabel, supportTitle) => {
  const sourceType = kindLabel === '超边溯源' ? '超图关系' : '原始节点材料';
  return `这条来源主要用于${supportTitle.replace('支撑', '说明')}，来源类型是${sourceType}。`;
};

const normalizeEvidenceRecord = (item) => {
  if (item && typeof item === 'object' && !Array.isArray(item)) {
    const text = cleanText(item.text || item.summary || item.detail || item.reason || item.message || formatListText(item));
    const fileName = basename(item.file || item.source_file || item.path);
    const competition = cleanText(item.competition);
    const evidenceTypeLabel = evidenceTypeText(item.evidence_type || item.type);
    const supportTitle = item.support_title || '支撑结论判断';
    return {
      text,
      fileName,
      competition,
      evidenceTypeLabel,
      supportTitle,
      explanation: explainSuggestion(supportTitle),
      referenceLabel: buildReferenceLabel(fileName, '')
    };
  }
  const text = cleanText(item);
  return {
    text,
    fileName: '',
    competition: '',
    evidenceTypeLabel: '',
    supportTitle: '支撑结论判断',
    explanation: explainSuggestion('支撑结论判断'),
    referenceLabel: ''
  };
};

const metrics = computed(() => meta.value.metrics || {});
const consistencyAlerts = computed(() => textArray(meta.value.consistency_alerts || meta.value.warnings));
const missingNodeLabels = computed(() => textArray(meta.value.missing_node_labels || meta.value.missing_key_nodes));
const matchedLabelRows = computed(() => textArray(meta.value?.entity_match_stats?.matched_labels));

const matchedProject = computed(() => {
  const record = meta.value.matched_project || {};
  return {
    id: cleanText(record.id || meta.value.matched_project_node_id || meta.value.resolved_project_node_id),
    name: cleanText(record.name || meta.value.matched_project_name)
  };
});

const matchedProjectText = computed(() => {
  if (!matchedProject.value.id && !matchedProject.value.name) return '未匹配';
  if (!matchedProject.value.id) return matchedProject.value.name;
  if (!matchedProject.value.name) return `ID ${matchedProject.value.id}`;
  return `${matchedProject.value.name}（ID ${matchedProject.value.id}）`;
});

const diagnosisStatus = computed(() => {
  if (meta.value.enabled === true) return '已启用';
  if (meta.value.enabled === false) return '未启用';
  return '未知';
});

const statusClass = computed(() => {
  if (diagnosisStatus.value === '已启用') return 'status-on';
  if (diagnosisStatus.value === '未启用') return 'status-off';
  return 'status-unknown';
});

const similarProjects = computed(() => asArray(meta.value.similar_projects)
  .map((item) => ({
    id: cleanText(item?.id || item?.project_id),
    name: cleanText(item?.name || item?.project_name || item?.node_name || item?.id),
    score: formatScore(item?.similarity_score ?? item?.score)
  }))
  .filter((item) => item.name));

const riskPatterns = computed(() => asArray(meta.value.risk_patterns)
  .map((item) => ({
    type: cleanText(item?.type),
    severity: cleanText(item?.severity || '中') || '中',
    example: cleanText(item?.example)
  }))
  .filter((item) => item.type));

const suggestedEvidenceRows = computed(() => dedupeBy(
  asArray(meta.value.suggested_evidence)
    .map((item) => normalizeEvidenceRecord(item))
    .filter((item) => item.text),
  (item) => `${item.text}|${item.fileName}|${item.competition}|${item.evidenceTypeLabel}`
));

const nodeSources = computed(() => asArray(meta.value?.provenance?.node_sources));
const edgeEvidence = computed(() => asArray(meta.value?.provenance?.hyperedge_evidence));

const provenanceRows = computed(() => {
  const rows = [];
  for (const item of nodeSources.value) {
    const supportTitle = supportTitleFromNodeLabel(item?.node_label);
    rows.push({
      title: `[${cleanText(item?.node_label || '-')}] ${cleanText(item?.node_name || item?.node_id || '-')}`,
      text: cleanText(item?.text),
      fileName: basename(item?.file),
      competition: cleanText(item?.competition),
      kindLabel: '节点溯源',
      supportTitle,
      explanation: explainProvenance('节点溯源', supportTitle),
      referenceLabel: buildReferenceLabel(basename(item?.file), '节点溯源'),
      raw: item
    });
  }
  for (const item of edgeEvidence.value) {
    const supportTitle = supportTitleFromHyperedgeType(item?.hyperedge_type);
    rows.push({
      title: `[${cleanText(item?.hyperedge_type || '-')}] ${cleanText(item?.hyperedge_id || '-')}`,
      text: cleanText(item?.text),
      fileName: '',
      competition: '',
      kindLabel: '超边溯源',
      supportTitle,
      explanation: explainProvenance('超边溯源', supportTitle),
      referenceLabel: buildReferenceLabel('', '超边溯源'),
      raw: item
    });
  }
  return dedupeBy(rows.filter((item) => item.title || item.text), (item) => `${item.title}|${item.text}|${item.fileName}|${item.kindLabel}`);
});

const provenanceTotal = computed(() => provenanceRows.value.length);

const diagnosisConclusion = computed(() => {
  const summary = meta.value.diagnosis_summary || {};
  const conclusion = cleanText(summary.conclusion);
  if (conclusion) return conclusion;
  if (riskPatterns.value.length || consistencyAlerts.value.length || missingNodeLabels.value.length) {
    return '当前方案存在结构缺口，暂不适合直接放大执行。';
  }
  const labelCoverage = Number(metrics.value.label_coverage_rate || 0);
  const explainability = Number(metrics.value.explainability_item_rate || 0);
  if (labelCoverage >= 80 && explainability >= 60) {
    return '当前结构较完整，可以进入下一轮优化和论证强化。';
  }
  return '当前结构基本可用，但证据链仍需加强。';
});

const summaryEvidence = computed(() => {
  const summary = meta.value.diagnosis_summary || {};
  const evidence = textArray(summary.evidence);
  if (evidence.length) return evidence;
  return [
    `标签覆盖率 ${formatPercent(metrics.value.label_coverage_rate)}，可解释项覆盖 ${formatPercent(metrics.value.explainability_item_rate)}。`,
    `一致性告警 ${consistencyAlerts.value.length} 条，缺失节点 ${missingNodeLabels.value.length} 项，风险模式 ${riskPatterns.value.length} 条。`,
    `溯源证据 ${provenanceTotal.value} 条，相似项目 ${similarProjects.value.length} 个。`
  ];
});

const gapSummary = computed(() => {
  const parts = [];
  if (consistencyAlerts.value.length) parts.push(`告警 ${consistencyAlerts.value.length}`);
  if (missingNodeLabels.value.length) parts.push(`缺节点 ${missingNodeLabels.value.length}`);
  if (riskPatterns.value.length) parts.push(`风险 ${riskPatterns.value.length}`);
  return parts.length ? parts.join(' / ') : '暂无明显结构缺口';
});

const overviewMetrics = computed(() => [
  { label: '标签覆盖率', value: formatPercent(metrics.value.label_coverage_rate) },
  { label: '可解释覆盖', value: formatPercent(metrics.value.explainability_item_rate) },
  { label: '溯源证据', value: provenanceTotal.value },
  { label: '相似项目', value: similarProjects.value.length }
]);

const matchedNodePreview = computed(() => dedupeBy(
  nodeSources.value
    .map((item) => ({
      label: cleanText(item?.node_label),
      name: cleanText(item?.node_name || item?.node_id),
      text: cleanText(item?.text)
    }))
    .filter((item) => item.label || item.name),
  (item) => `${item.label}|${item.name}`
).slice(0, 6));

const hyperedgePreview = computed(() => dedupeBy(
  edgeEvidence.value
    .map((item) => ({
      typeLabel: hyperedgeTypeText(item?.hyperedge_type),
      text: cleanText(item?.text),
      id: cleanText(item?.hyperedge_id)
    }))
    .filter((item) => item.typeLabel || item.text || item.id),
  (item) => `${item.typeLabel}|${item.text}|${item.id}`
).slice(0, 5));

const explanationCards = computed(() => {
  const cards = [];
  const confidence = formatPercent(metrics.value.project_confidence_rate);
  const matchMode = inputTypeText(meta.value.input_type);

  if (matchedProject.value.id || matchedProject.value.name) {
    cards.push({
      title: '先匹配到哪个项目',
      badge: matchMode,
      detail: matchedProject.value.name
        ? `系统先把当前方案与超图中的项目进行比对，当前最接近的是“${matchedProject.value.name}”。`
        : '系统已经完成项目匹配，但当前没有可展示的项目名称。',
      points: [
        confidence !== '-' ? `项目匹配置信度：${confidence}` : '',
        matchedLabelRows.value.length ? `命中的节点类型：${matchedLabelRows.value.join('、')}` : '',
        matchedNodePreview.value.length ? `当前命中了 ${matchedNodePreview.value.length} 个关键节点。` : ''
      ].filter(Boolean)
    });
  }

  if (matchedNodePreview.value.length) {
    cards.push({
      title: '命中了哪些关键节点',
      badge: `${matchedNodePreview.value.length} 个节点`,
      detail: '这些节点表示方案最接近的主题、能力和证据方向，系统据此判断你更像哪个项目、强项在哪里、缺口在哪里。',
      points: matchedNodePreview.value.map((item) => `${item.label || '节点'}：${item.name}${item.text ? `，依据“${item.text.slice(0, 36)}”` : ''}`)
    });
  }

  if (hyperedgePreview.value.length) {
    cards.push({
      title: '命中了哪些超边关系',
      badge: `${hyperedgePreview.value.length} 条关系`,
      detail: '超边不是单个点，而是多个节点之间形成的关系。系统命中这些关系后，才会判断闭环、风险和证据链是否成立。',
      points: hyperedgePreview.value.map((item) => `${item.typeLabel}：${item.text || item.id || '已命中关系'}`)
    });
  }

  if (similarProjects.value.length) {
    cards.push({
      title: '参考了哪些相似项目',
      badge: `${similarProjects.value.length} 个项目`,
      detail: '系统还会参考相似项目的结构，判断当前方案更接近哪类成熟案例。',
      points: similarProjects.value.slice(0, 3).map((item) => `${item.name}，相似度 ${item.score}`)
    });
  }

  if (missingNodeLabels.value.length || consistencyAlerts.value.length || riskPatterns.value.length) {
    cards.push({
      title: '为什么会得到当前诊断结果',
      badge: '结论原因',
      detail: '最终结论不是只看单个节点，而是综合命中的节点、命中的关系、缺失项和一致性告警一起判断出来的。',
      points: [
        missingNodeLabels.value.length ? `缺失关键节点：${missingNodeLabels.value.join('、')}` : '',
        consistencyAlerts.value.length ? `一致性告警：${consistencyAlerts.value.slice(0, 3).join('；')}` : '',
        riskPatterns.value.length ? `命中风险关系：${riskPatterns.value.slice(0, 3).map((item) => item.type).join('、')}` : ''
      ].filter(Boolean)
    });
  }

  return cards;
});

const normalizeFinding = (item, index) => ({
  key: cleanText(item?.key) || `finding-${index}`,
  title: cleanText(item?.title) || `结论 ${index + 1}`,
  level: cleanText(item?.level || 'neutral').toLowerCase() || 'neutral',
  detail: cleanText(item?.detail || item?.summary || item?.conclusion),
  evidence: textArray(item?.evidence),
  action: cleanText(item?.action || item?.suggestion)
});

const derivedFindingRows = computed(() => {
  const rows = [
    {
      key: 'overall',
      title: '总体判断',
      level: riskPatterns.value.length || consistencyAlerts.value.length || missingNodeLabels.value.length ? 'warning' : 'positive',
      detail: diagnosisConclusion.value,
      evidence: [
        `标签覆盖率 ${formatPercent(metrics.value.label_coverage_rate)}`,
        `可解释覆盖 ${formatPercent(metrics.value.explainability_item_rate)}`,
        `项目匹配置信度 ${formatPercent(metrics.value.project_confidence_rate)}`
      ],
      action: riskPatterns.value.length || consistencyAlerts.value.length || missingNodeLabels.value.length
        ? '先补齐结构缺口，再继续扩展市场、技术或商业闭环。'
        : '继续补充高质量业务证据，把结构优势转成说服力。'
    },
    {
      key: 'consistency',
      title: '结构一致性',
      level: consistencyAlerts.value.length ? 'warning' : 'positive',
      detail: consistencyAlerts.value.length ? `发现 ${consistencyAlerts.value.length} 条一致性问题。` : '暂未发现明显结构冲突。',
      evidence: consistencyAlerts.value,
      action: consistencyAlerts.value.length ? '逐条修正告警对应的逻辑链和事实链。' : ''
    },
    {
      key: 'missing',
      title: '关键节点覆盖',
      level: missingNodeLabels.value.length ? 'warning' : 'positive',
      detail: missingNodeLabels.value.length ? `存在 ${missingNodeLabels.value.length} 项关键节点缺失。` : '关键节点覆盖较完整。',
      evidence: missingNodeLabels.value,
      action: missingNodeLabels.value.length ? `优先补齐：${missingNodeLabels.value.slice(0, 4).join('、')}` : ''
    },
    {
      key: 'risk',
      title: '风险模式识别',
      level: riskPatterns.value.length ? 'warning' : 'neutral',
      detail: riskPatterns.value.length ? `识别到 ${riskPatterns.value.length} 条风险模式。` : '暂未识别到明显高风险模式。',
      evidence: riskPatterns.value.map((item) => `${item.type}（${item.severity}）`),
      action: riskPatterns.value.length ? '针对高频风险模式补边界条件、量化指标和验证证据。' : ''
    },
    {
      key: 'evidence',
      title: '证据充分性',
      level: suggestedEvidenceRows.value.length ? 'warning' : 'positive',
      detail: suggestedEvidenceRows.value.length ? `当前仍需补充 ${suggestedEvidenceRows.value.length} 条关键证据。` : '当前关键证据较完整。',
      evidence: suggestedEvidenceRows.value.map((item) => item.text),
      action: suggestedEvidenceRows.value.length ? '优先补能直接支撑市场、指标和风险控制的证据。' : ''
    }
  ];
  if (similarProjects.value.length) {
    rows.push({
      key: 'similar',
      title: '相似项目参照',
      level: 'neutral',
      detail: `匹配到 ${similarProjects.value.length} 个相似项目，可用于校准结构和论证方式。`,
      evidence: similarProjects.value.map((item) => `${item.name}（相似度 ${item.score}）`),
      action: '对比相似项目的市场定义、指标设计和证据链组织方式。'
    });
  }
  return rows.filter((item) => item.detail || item.evidence.length);
});

const findingRows = computed(() => {
  const findings = asArray(meta.value?.diagnosis_summary?.findings);
  if (findings.length) {
    return dedupeBy(findings.map(normalizeFinding).filter((item) => item.detail || item.evidence.length), (item) => `${item.key}|${item.title}|${item.detail}`);
  }
  return dedupeBy(derivedFindingRows.value, (item) => `${item.key}|${item.title}|${item.detail}`);
});

const showFindingEvidenceList = (item) => !['evidence', 'provenance', 'risk'].includes(cleanText(item?.key).toLowerCase());

const levelText = (level) => {
  if (level === 'positive') return '良好';
  if (level === 'warning') return '待处理';
  if (level === 'negative') return '高风险';
  return '观察';
};

const riskLevelClass = (severity) => {
  const normalized = cleanText(severity).toLowerCase();
  if (normalized.includes('高') || normalized.includes('high') || normalized.includes('critical')) return 'risk-high';
  if (normalized.includes('低') || normalized.includes('low')) return 'risk-low';
  return 'risk-mid';
};

const isCardOpen = (key, fallback = false) => {
  if (Object.prototype.hasOwnProperty.call(openCards.value, key)) {
    return Boolean(openCards.value[key]);
  }
  return fallback;
};

const toggleCard = (key, fallback = false) => {
  openCards.value[key] = !isCardOpen(key, fallback);
};

const cardToggleText = (key, fallback = false) => (isCardOpen(key, fallback) ? '收起' : '展开');

const isExpanded = (key) => Boolean(expandedSections.value[key]);
const toggleSection = (key) => {
  expandedSections.value[key] = !isExpanded(key);
};
const sectionRows = (rows, key, limit = 5) => (isExpanded(key) ? rows : rows.slice(0, limit));
const showToggle = (rows, limit = 5) => rows.length > limit;
const sectionHiddenCount = (rows, key, limit = 5) => (isExpanded(key) ? 0 : Math.max(0, rows.length - limit));
</script>

<style scoped>
.hypergraph-card {
  margin-top: 12px;
  padding: 14px;
  border: 1px solid var(--line-soft);
  border-radius: 12px;
  background: linear-gradient(180deg, color-mix(in oklch, var(--bg-main) 94%, white), var(--bg-field));
  display: grid;
  gap: 12px;
}

.empty-text {
  margin: 0;
  color: var(--ink-muted);
}

.group {
  display: grid;
  gap: 10px;
  border: 1px solid var(--line-soft);
  border-radius: 10px;
  padding: 10px;
  background: color-mix(in oklch, var(--bg-main) 90%, white);
}

.overview-shell {
  background: linear-gradient(155deg, color-mix(in oklch, var(--bg-main) 86%, white), color-mix(in oklch, var(--bg-main) 92%, white));
}

.group-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.group-toggle {
  width: 100%;
  padding: 0;
  border: 0;
  background: transparent;
  text-align: left;
  cursor: pointer;
}

.group-toggle-main,
.group-toggle-side {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.group-toggle-side {
  margin-left: auto;
}

.group-toggle:hover h4,
.group-toggle:hover .toggle-state {
  color: var(--accent);
}

.group-body {
  display: grid;
  gap: 10px;
}

h4 {
  margin: 0;
  font-size: 14px;
  color: var(--ink-title);
}

.status-pill,
.section-count {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 28px;
  padding: 2px 10px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 600;
  color: var(--ink-muted);
  background: color-mix(in oklch, var(--bg-main) 84%, white);
  border: 1px solid var(--line-soft);
}

.status-on {
  color: #0f766e;
  background: rgba(15, 118, 110, 0.12);
  border-color: rgba(15, 118, 110, 0.28);
}

.status-off {
  color: #b45309;
  background: rgba(180, 83, 9, 0.12);
  border-color: rgba(180, 83, 9, 0.28);
}

.status-unknown {
  color: var(--ink-muted);
}

.toggle-state {
  display: inline-flex;
  align-items: center;
  min-height: 28px;
  padding: 0 10px;
  border-radius: 999px;
  border: 1px solid var(--line-soft);
  background: color-mix(in oklch, var(--bg-main) 90%, white);
  color: var(--ink-muted);
  font-size: 12px;
  font-weight: 600;
}

.overview-grid {
  display: grid;
  gap: 8px;
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.metric {
  border: 1px solid var(--line-soft);
  background: color-mix(in oklch, var(--bg-main) 90%, white);
  border-radius: 8px;
  padding: 8px 10px;
  display: grid;
  gap: 4px;
}

.metric-wide {
  grid-column: 1 / -1;
}

.label {
  font-size: 12px;
  color: var(--ink-muted);
}

.mini-metrics {
  display: grid;
  gap: 8px;
  grid-template-columns: repeat(4, minmax(0, 1fr));
}

.mini-metric {
  border: 1px solid var(--line-soft);
  border-radius: 8px;
  padding: 6px 8px;
  display: grid;
  gap: 2px;
  background: color-mix(in oklch, var(--bg-main) 88%, white);
}

.mini-metric span {
  font-size: 12px;
  color: var(--ink-muted);
}

.summary-evidence {
  display: grid;
  gap: 6px;
  padding: 8px 10px;
  border: 1px solid var(--line-soft);
  border-radius: 8px;
  background: color-mix(in oklch, var(--bg-main) 90%, white);
}

.summary-evidence-title {
  font-size: 12px;
  color: var(--ink-muted);
  font-weight: 600;
}

.section-tip {
  margin: 0;
  font-size: 12px;
  line-height: 1.6;
  color: var(--ink-muted);
}

.finding-list,
.evidence-list {
  display: grid;
  gap: 10px;
}

.finding-card,
.evidence-card {
  border: 1px solid var(--line-soft);
  border-radius: 10px;
  padding: 10px 12px;
  background: color-mix(in oklch, var(--bg-main) 93%, white);
}

.finding-positive {
  background: color-mix(in oklch, #0f766e 5%, var(--bg-main));
  border-color: color-mix(in oklch, #0f766e 18%, var(--line-soft));
}

.finding-warning {
  background: color-mix(in oklch, #d97706 5%, var(--bg-main));
  border-color: color-mix(in oklch, #d97706 18%, var(--line-soft));
}

.finding-neutral,
.explanation-card {
  background: color-mix(in oklch, #1d4ed8 4%, var(--bg-main));
  border-color: color-mix(in oklch, #1d4ed8 14%, var(--line-soft));
}

.finding-head,
.evidence-head {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  align-items: center;
}

.finding-level,
.meta-pill {
  display: inline-flex;
  align-items: center;
  min-height: 24px;
  padding: 0 10px;
  border-radius: 999px;
  border: 1px solid var(--line-soft);
  font-size: 12px;
  color: var(--ink-muted);
  background: color-mix(in oklch, var(--bg-main) 88%, white);
}

.finding-level-positive {
  color: #0f766e;
}

.finding-level-warning {
  color: #b45309;
}

.finding-level-negative {
  color: #b91c1c;
}

.finding-detail,
.finding-action,
.evidence-text,
.evidence-title {
  margin: 8px 0 0;
  line-height: 1.65;
}

.finding-action {
  color: var(--ink-title);
  font-weight: 600;
}

.field-label {
  margin-top: 8px;
  font-size: 12px;
  color: var(--ink-muted);
  font-weight: 600;
}

.evidence-explainer {
  margin: 6px 0 0;
  line-height: 1.6;
  color: var(--ink-muted);
}

.list {
  margin: 8px 0 0;
  padding-left: 18px;
  display: grid;
  gap: 6px;
}

.list.compact {
  gap: 4px;
}

.meta-row {
  margin-top: 8px;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.trace-btn {
  width: 100%;
  text-align: left;
  cursor: pointer;
}

.trace-btn:hover {
  border-color: var(--accent);
}

.risk-pill {
  display: inline-block;
  padding: 1px 8px;
  border-radius: 999px;
  font-size: 12px;
  line-height: 18px;
}

.risk-high {
  background: rgba(220, 38, 38, 0.12);
  color: #b91c1c;
}

.risk-mid {
  background: rgba(217, 119, 6, 0.12);
  color: #92400e;
}

.risk-low {
  background: rgba(22, 163, 74, 0.12);
  color: #166534;
}

.toggle-btn {
  justify-self: start;
  min-height: 28px;
  padding: 0 10px;
  border: 1px solid var(--line-soft);
  border-radius: 999px;
  background: color-mix(in oklch, var(--bg-main) 92%, white);
  color: var(--ink-muted);
  font-size: 12px;
  cursor: pointer;
}

.toggle-btn:hover {
  border-color: var(--accent);
}

@media (max-width: 860px) {
  .overview-grid,
  .mini-metrics {
    grid-template-columns: 1fr 1fr;
  }
}

@media (max-width: 640px) {
  .overview-grid,
  .mini-metrics {
    grid-template-columns: 1fr;
  }

  .group-head,
  .finding-head,
  .evidence-head {
    align-items: flex-start;
  }

  .group-toggle-main,
  .group-toggle-side {
    flex-wrap: wrap;
  }
}
</style>
