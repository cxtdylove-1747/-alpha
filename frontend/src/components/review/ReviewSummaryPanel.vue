<template>
  <div class="review-summary-panel">
    <p class="summary-lead">{{ leadText }}</p>

    <section v-if="analysisContent" class="analysis-section">
      <h4 class="analysis-title">补充分析评审要点</h4>
      <MarkdownBlock class="analysis-markdown" :content="analysisContent" />
    </section>

    <section v-if="normalizedIssues.length" class="detail-section">
      <h4>问题清单</h4>
      <ul>
        <li v-for="(item, idx) in normalizedIssues" :key="`issue-${idx}`">{{ item }}</li>
      </ul>
    </section>

    <section v-if="normalizedQuestions.length" class="detail-section">
      <h4>引导提问</h4>
      <ul>
        <li v-for="(item, idx) in normalizedQuestions" :key="`question-${idx}`">{{ item }}</li>
      </ul>
    </section>

    <footer v-if="completionText" class="completion-strip">{{ completionText }}</footer>
  </div>
</template>

<script setup>
import { computed } from 'vue';
import MarkdownBlock from '../MarkdownBlock.vue';

const props = defineProps({
  summary: {
    type: String,
    default: ''
  },
  issues: {
    type: Array,
    default: () => []
  },
  guidanceQuestions: {
    type: Array,
    default: () => []
  },
  reviewMeta: {
    type: Object,
    default: () => ({})
  }
});

const normalizeText = (value) => String(value ?? '').replace(/\s+/g, ' ').trim();
const simplifyText = (value) => normalizeText(value)
  .replace(/^[\-\*•]\s*/, '')
  .replace(/^\d+[.)、]\s*/, '');
const makeCompareKey = (value) => simplifyText(value).replace(/[：:，,。.;；！？!?、\s]/g, '');
const dedupeTextList = (items, limit = 8) => {
  const used = new Set();
  const rows = [];
  for (const item of items) {
    const text = simplifyText(item);
    if (!text) continue;
    const key = makeCompareKey(text);
    if (!key || used.has(key)) continue;
    used.add(key);
    rows.push(text);
    if (rows.length >= limit) break;
  }
  return rows;
};

const analysisContent = computed(() => String(props.summary || '')
  .replace(/^\s{0,3}#{1,6}\s+补充分析评审要点[:：]?\s*/i, '')
  .trim());

const normalizedIssues = computed(() => dedupeTextList((props.issues || [])
  .map((item) => {
    if (item && typeof item === 'object') {
      return item.description || item.title || item.text || item.conclusion;
    }
    return item;
  })
  .filter(Boolean), 6));

const normalizedQuestions = computed(() => dedupeTextList((props.guidanceQuestions || [])
  .map((item) => item)
  .filter(Boolean), 6));

const leadText = computed(() => {
  const meta = props.reviewMeta || {};
  if (meta.unrelated_content || meta.project_material_state === 'unrelated') {
    return '当前材料还不能按完整项目计划书检阅，我先把关键缺失点和补写方向列清楚，方便你补成可评审版本。';
  }
  if (meta.is_partial_project || meta.project_material_state === 'partial_project') {
    return '本次检阅优先判断项目完成度与关键缺失模块，采用引导式问题帮助你补齐计划书主线。';
  }

  const dimensionMap = {
    innovation: '创新性与竞争力',
    '创新点': '创新性与竞争力',
    logic: '逻辑一致性',
    '逻辑框架': '逻辑一致性',
    feasibility: '可行性',
    '可行性': '可行性',
    completeness: '完整度',
    '完整性': '完整度',
    competition: '大赛适配度',
    '大赛适配': '大赛适配度',
    '表达与结构': '表达质量',
    '基础检阅': '表达质量'
  };

  const themes = [];
  for (const item of props.issues || []) {
    const raw = item && typeof item === 'object'
      ? (item.dimension || item.code || item.category || '')
      : '';
    const key = normalizeText(raw);
    const lowerKey = typeof key === 'string' ? key.toLowerCase() : '';
    const label = dimensionMap[key] || dimensionMap[lowerKey] || '';
    if (label && !themes.includes(label)) {
      themes.push(label);
    }
    if (themes.length >= 2) break;
  }

  if (themes.length >= 2) {
    return `本次检阅聚焦${themes[0]}与${themes[1]}，采用引导式问题帮助你迭代。`;
  }
  if (themes.length === 1) {
    return `本次检阅重点围绕${themes[0]}展开，并结合批注帮助你继续完善方案。`;
  }
  return '本次检阅聚焦逻辑一致性与可行性，采用引导式问题帮助你迭代。';
});

const completionText = computed(() => {
  const meta = props.reviewMeta || {};
  if (meta.is_complete !== false && !meta.is_partial_project) return '';
  const progress = Number(meta.progress || 0);
  const missing = Array.isArray(meta.missing_parts)
    ? meta.missing_parts.map((item) => normalizeText(item?.part)).filter(Boolean)
    : [];
  if (!missing.length) {
    return progress ? `当前进度 ${progress}%` : '';
  }
  return `当前进度 ${progress}% · 仍需补齐：${missing.join('、')}`;
});
</script>

<style scoped>
.review-summary-panel {
  display: grid;
  gap: 18px;
}

.summary-lead {
  margin: 0;
  color: var(--ink-body);
  font-size: 15px;
  line-height: 1.85;
}

.analysis-section {
  display: grid;
  gap: 12px;
}

.analysis-title {
  margin: 0;
  color: var(--ink-title);
  font-size: 18px;
  font-weight: 700;
}

.analysis-markdown {
  color: var(--ink-body);
  font-size: 15px;
  line-height: 1.95;
}

.analysis-markdown :deep(ul) {
  margin: 0;
  padding-left: 1.25em;
}

.analysis-markdown :deep(li) {
  margin: 0 0 12px;
}

.analysis-markdown :deep(li:last-child) {
  margin-bottom: 0;
}

.analysis-markdown :deep(strong) {
  color: var(--ink-title);
  font-weight: 800;
}

.detail-section {
  border: 1px dashed color-mix(in oklch, var(--line-soft) 82%, white);
  border-radius: 20px;
  padding: 18px 20px;
  background: color-mix(in oklch, var(--bg-field) 90%, white);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.72);
}

.detail-section h4 {
  margin: 0 0 12px;
  font-size: 18px;
  color: var(--ink-title);
}

.detail-section ul {
  margin: 0;
  padding-left: 1.25em;
  display: grid;
  gap: 12px;
  color: var(--ink-body);
  line-height: 1.8;
}

.completion-strip {
  display: inline-flex;
  align-items: center;
  justify-self: start;
  min-height: 34px;
  padding: 0 14px;
  border-radius: 999px;
  background: color-mix(in oklch, var(--bg-field) 92%, white);
  color: var(--ink-muted);
  font-size: 13px;
}
</style>
