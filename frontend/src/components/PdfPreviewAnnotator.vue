<template>
  <el-card>
    <template #header>{{ headerTitle }}</template>
    <div v-if="isPdfDoc && pdfUrl && !fallback" class="pdf-toolbar">
      <el-button size="small" @click="prevPage" :disabled="page <= 1">上一页</el-button>
      <span>第 {{ page }} / {{ pageCount }} 页</span>
      <el-button size="small" @click="nextPage" :disabled="page >= pageCount">下一页</el-button>
      <el-button size="small" @click="zoomOut">-</el-button>
      <span>{{ Math.round(scale * 100) }}%</span>
      <el-button size="small" @click="zoomIn">+</el-button>
      <el-button size="small" @click="fitWidth">适应宽度</el-button>
      <el-button size="small" @click="rotateLeft">左转</el-button>
      <el-button size="small" @click="rotateRight">右转</el-button>
    </div>
    <div class="pdf-box" v-loading="loading">
      <div v-if="isPdfDoc && pdfUrl && !fallback" class="pdf-stage-wrap">
        <div ref="stageRef" class="pdf-stage">
          <div class="canvas-overlay-wrap">
            <canvas ref="canvasRef" class="pdf-canvas"></canvas>
            <div class="annotation-layer">
              <div
                v-for="(item, idx) in currentAnnotations"
                :key="idx"
                class="box-mark"
                :class="{ focused: isAnnotationFocused(item) }"
                :style="annotationStyle(item, idx)"
                :title="item.description"
              >
                <span class="mark-text">{{ item.description }}</span>
              </div>
            </div>
          </div>
        </div>
        <div class="annotation-side">
          <el-empty v-if="!currentAnnotations.length" description="当前页无批注" />
          <div v-else class="note-list">
            <div v-for="(item, idx) in currentAnnotations" :key="`note-${idx}`" class="note-card" :style="noteCardStyle(item)">
              <div class="note-meta">
                <div class="note-meta-main">
                  <span class="note-tag">批注 {{ String(idx + 1).padStart(2, '0') }}</span>
                  <span class="note-risk" :style="noteRiskStyle(item)">{{ riskLabel(item?.risk_level) }}</span>
                </div>
                <span class="note-loc">{{ noteLocation(item) }}</span>
              </div>
              <p class="note-main">{{ readableNoteText(item.description) }}</p>
              <div v-if="item.question" class="note-follow-wrap">
                <p class="note-follow-label">建议继续思考</p>
                <p class="note-follow">{{ readableQuestionText(item.question) }}</p>
              </div>
            </div>
          </div>
        </div>
      </div>
      <div v-else-if="isWordDoc" class="word-preview">
        <el-alert :closable="false" type="info" :title="documentHint" />
        <pre v-if="previewText" class="word-text">{{ previewText }}</pre>
        <iframe v-else-if="resolvedUrl" class="pdf-iframe" :src="embedUrl" title="file-preview"></iframe>
        <el-empty v-else description="暂无可预览的Word内容" />
        <div v-if="annotations.length" class="word-annotation-list">
          <div v-for="(item, idx) in annotations" :key="`word-note-${idx}`" class="note-card" :style="noteCardStyle(item)">
            <div class="note-meta">
              <div class="note-meta-main">
                <span class="note-tag">批注 {{ String(idx + 1).padStart(2, '0') }}</span>
                <span class="note-risk" :style="noteRiskStyle(item)">{{ riskLabel(item?.risk_level) }}</span>
              </div>
              <span class="note-loc">{{ noteLocation(item) }}</span>
            </div>
            <p class="note-main">{{ readableNoteText(item.description) }}</p>
            <div v-if="item.question" class="note-follow-wrap">
              <p class="note-follow-label">建议继续思考</p>
              <p class="note-follow">{{ readableQuestionText(item.question) }}</p>
            </div>
          </div>
        </div>
      </div>
      <iframe v-else-if="resolvedUrl" class="pdf-iframe" :src="embedUrl" title="file-preview"></iframe>
      <el-empty v-else description="请先上传PDF/Word方案" />
    </div>
  </el-card>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, shallowRef, watch } from 'vue';
import * as pdfjsLib from 'pdfjs-dist';
import workerSrc from 'pdfjs-dist/build/pdf.worker.min.mjs?url';

pdfjsLib.GlobalWorkerOptions.workerSrc = workerSrc;

const props = defineProps({
  pdfUrl: { type: String, default: '' },
  annotations: { type: Array, default: () => [] },
  documentText: { type: String, default: '' },
  focusKeyword: { type: String, default: '' }
});

const fileExt = computed(() => {
  const path = String(props.pdfUrl || '').split('?')[0].toLowerCase();
  const idx = path.lastIndexOf('.');
  return idx >= 0 ? path.slice(idx) : '';
});
const isPdfDoc = computed(() => fileExt.value === '.pdf' || String(props.pdfUrl || '').startsWith('blob:'));
const isWordDoc = computed(() => fileExt.value === '.doc' || fileExt.value === '.docx');
const headerTitle = computed(() => (isWordDoc.value ? 'Word预览与问题标注' : 'PDF预览与问题标注'));
const documentHint = computed(() => '当前为Word文档，采用页面化预览。');
const previewText = computed(() => String(props.documentText || '').trim());
const embedUrl = computed(() => {
  if (!resolvedUrl.value) {
    return '';
  }
  if (isPdfDoc.value || String(resolvedUrl.value).startsWith('blob:')) {
    return resolvedUrl.value;
  }
  if (/^https?:\/\//i.test(resolvedUrl.value)) {
    return `https://view.officeapps.live.com/op/embed.aspx?src=${encodeURIComponent(resolvedUrl.value)}`;
  }
  return resolvedUrl.value;
});

const normalizeToMediaPath = (pathValue) => {
  let normalizedPath = String(pathValue || '').trim();
  if (!normalizedPath) {
    return '';
  }
  if (normalizedPath.includes('%25')) {
    try {
      normalizedPath = decodeURIComponent(normalizedPath);
    } catch (_) {
      // keep original path when decode fails
    }
  }

  normalizedPath = normalizedPath.replace(/^[.\/]+/, '');
  if (!normalizedPath.startsWith('media/')) {
    normalizedPath = `media/${normalizedPath}`;
  }
  return `/${normalizedPath}`.replace(/\/+/g, '/');
};

const resolvePdfUrl = (rawUrl) => {
  if (!rawUrl) {
    return '';
  }
  if (rawUrl.startsWith('blob:')) {
    return rawUrl;
  }

  const backendOrigin = (() => {
    const configured = String(import.meta.env.VITE_BACKEND_ORIGIN || '').trim();
    const fallback = (typeof window !== 'undefined' && window.location?.origin) ? window.location.origin : '';
    const isLoopbackHost = (hostname) => ['127.0.0.1', 'localhost', '0.0.0.0'].includes(String(hostname || '').toLowerCase());

    const getSafeOrigin = (origin) => {
      if (!origin || !/^https?:\/\//i.test(origin)) {
        return '';
      }
      try {
        const parsed = new URL(origin);
        return parsed.origin;
      } catch (_) {
        return '';
      }
    };

    const configuredOrigin = getSafeOrigin(configured);
    const fallbackOrigin = getSafeOrigin(fallback);

    if (!configuredOrigin) {
      return fallbackOrigin;
    }
    if (!fallbackOrigin) {
      return configuredOrigin;
    }

    try {
      const configuredHost = new URL(configuredOrigin).hostname;
      const runtimeHost = new URL(fallbackOrigin).hostname;
      if (!isLoopbackHost(runtimeHost) && isLoopbackHost(configuredHost)) {
        return fallbackOrigin;
      }
    } catch (_) {
      return fallbackOrigin;
    }

    return configuredOrigin;
  })();

  // Always normalize media URLs to backend origin in production.
  if (/^https?:\/\//i.test(rawUrl)) {
    try {
      const parsed = new URL(rawUrl);
      let mediaPath = parsed.pathname;
      if (!mediaPath.startsWith('/media/')) {
        mediaPath = normalizeToMediaPath(mediaPath);
      }
      if (!mediaPath) {
        return '';
      }
      if (import.meta.env.DEV && mediaPath.startsWith('/media/')) {
        return `${mediaPath}${parsed.search}${parsed.hash}`;
      }
      return backendOrigin ? `${backendOrigin}${mediaPath}${parsed.search}${parsed.hash}` : `${mediaPath}${parsed.search}${parsed.hash}`;
    } catch (_) {
      return rawUrl;
    }
  }

  const normalizedPath = normalizeToMediaPath(rawUrl);
  if (!normalizedPath) {
    return '';
  }

  if (import.meta.env.DEV && normalizedPath.startsWith('/media/')) {
    return normalizedPath;
  }
  return backendOrigin ? `${backendOrigin}${normalizedPath}` : normalizedPath;
};

const pdfDoc = shallowRef(null);
const canvasRef = ref(null);
const page = ref(1);
const pageCount = ref(1);
const scale = ref(1.1);
const loading = ref(false);
const resolvedUrl = ref('');
const fallback = ref(false);
const stageRef = ref(null);
const fitToWidth = ref(true);
const manualRotation = ref(0);
const activeFocusKeyword = ref('');
const annotationBoxes = ref([]);
const pageTextIndex = shallowRef(null);
let resizeObserver = null;

const appendCacheBuster = (url) => {
  if (!url || url.startsWith('blob:')) {
    return url;
  }
  const sep = url.includes('?') ? '&' : '?';
  return `${url}${sep}v=${Date.now()}`;
};

const currentAnnotations = computed(() => props.annotations.filter((item) => (item.page || 1) === page.value));

const normalizedRotation = (rotation) => {
  const num = Number(rotation);
  if (!Number.isFinite(num)) return 0;
  return ((num % 360) + 360) % 360;
};

const effectiveRotation = (pdfPage) => {
  const base = normalizedRotation(pdfPage?.rotate);
  return ((base + manualRotation.value) % 360 + 360) % 360;
};

const clampRatio = (raw, fallback, min = 0.01, max = 0.98) => {
  const num = Number(raw);
  if (!Number.isFinite(num)) return fallback;
  if (num < min) return min;
  if (num > max) return max;
  return num;
};

const resolveRiskPalette = (riskLevel) => {
  const risk = String(riskLevel || '').toLowerCase();
  if (risk === 'high') {
    return {
      border: '#d14334',
      fill: 'rgba(209, 67, 52, 0.22)',
      glow: 'rgba(209, 67, 52, 0.34)',
      accent: '#ff988b',
      cardBg: 'linear-gradient(180deg, #fff4f1 0%, #ffe0d8 100%)',
      cardBorder: 'rgba(209, 67, 52, 0.24)',
      cardText: '#6b2118',
      mutedText: '#8e4a40',
      tagBg: 'rgba(255, 255, 255, 0.72)',
      tagText: '#8c2b1f',
      divider: 'rgba(209, 67, 52, 0.18)',
      badgeBg: 'rgba(209, 67, 52, 0.12)',
      badgeText: '#b12f21',
      shadow: 'rgba(209, 67, 52, 0.18)',
      label: '高风险'
    };
  }
  if (risk === 'medium') {
    return {
      border: '#d48a1d',
      fill: 'rgba(212, 138, 29, 0.20)',
      glow: 'rgba(212, 138, 29, 0.30)',
      accent: '#ffd08a',
      cardBg: 'linear-gradient(180deg, #fff8eb 0%, #ffe9bd 100%)',
      cardBorder: 'rgba(212, 138, 29, 0.24)',
      cardText: '#6e4710',
      mutedText: '#8b662d',
      tagBg: 'rgba(255, 255, 255, 0.70)',
      tagText: '#8a5a15',
      divider: 'rgba(212, 138, 29, 0.16)',
      badgeBg: 'rgba(212, 138, 29, 0.12)',
      badgeText: '#9c6716',
      shadow: 'rgba(170, 109, 20, 0.18)',
      label: '中风险'
    };
  }
  return {
    border: '#2f6edb',
    fill: 'rgba(47, 110, 219, 0.18)',
    glow: 'rgba(47, 110, 219, 0.28)',
    accent: '#9fc4ff',
    cardBg: 'linear-gradient(180deg, #f3f8ff 0%, #deebff 100%)',
    cardBorder: 'rgba(47, 110, 219, 0.20)',
    cardText: '#18407d',
    mutedText: '#49689a',
    tagBg: 'rgba(255, 255, 255, 0.70)',
    tagText: '#2657a8',
    divider: 'rgba(47, 110, 219, 0.14)',
    badgeBg: 'rgba(47, 110, 219, 0.12)',
    badgeText: '#2458b5',
    shadow: 'rgba(47, 110, 219, 0.14)',
    label: '低风险'
  };
};

const isAnnotationFocused = (item) => !!(activeFocusKeyword.value && _annotationMatch(item, activeFocusKeyword.value));

const normalizeTextForMatch = (raw) => String(raw || '')
  .toLowerCase()
  .replace(/\s+/g, '')
  .replace(/[，。、“”‘’！？；：,.!?;:()[\]{}<>《》【】'"`~^\\/_+=|-]/g, '');

const safeNumber = (raw, fallbackValue = 0) => {
  const value = Number(raw);
  return Number.isFinite(value) ? value : fallbackValue;
};

const buildSearchQueries = (rawSnippet) => {
  const normalized = normalizeTextForMatch(rawSnippet);
  if (!normalized) return [];
  const tokens = [normalized];
  if (normalized.length > 22) tokens.unshift(normalized.slice(0, 22));
  if (normalized.length > 36) tokens.unshift(normalized.slice(0, 30));
  if (normalized.length > 50) tokens.push(normalized.slice(-24));
  return [...new Set(tokens.filter((item) => item.length >= 4))]
    .sort((a, b) => b.length - a.length);
};

const buildPageTextIndex = (pdfPage, viewport, textContent) => {
  const items = Array.isArray(textContent?.items) ? textContent.items : [];
  const rects = [];
  const charToRect = [];
  let normalizedText = '';

  items.forEach((item) => {
    const raw = String(item?.str || '');
    const normalized = normalizeTextForMatch(raw);
    if (!normalized) return;

    const tx = pdfjsLib.Util.transform(viewport.transform, item.transform || [1, 0, 0, 1, 0, 0]);
    const x = safeNumber(tx[4], 0);
    const y = safeNumber(tx[5], 0);
    const height = Math.max(
      8,
      Math.hypot(safeNumber(tx[2], 0), safeNumber(tx[3], 0)),
      safeNumber(item?.height, 0) * safeNumber(viewport?.scale, 1)
    );
    const width = Math.max(6, safeNumber(item?.width, 0) * safeNumber(viewport?.scale, 1));

    const rect = {
      left: Math.max(0, x),
      top: Math.max(0, y - height),
      right: Math.max(0, x + width),
      bottom: Math.max(0, y),
      width,
      height
    };
    const rectIndex = rects.push(rect) - 1;

    normalizedText += normalized;
    for (let i = 0; i < normalized.length; i += 1) {
      charToRect.push(rectIndex);
    }
  });

  return {
    pdfPage,
    viewport,
    normalizedText,
    charToRect,
    rects
  };
};

const resolveMatchRect = (textIndex, start, end) => {
  const fromRect = textIndex.charToRect[start];
  const toRect = textIndex.charToRect[Math.max(start, end - 1)];
  if (fromRect == null || toRect == null) return null;

  const lo = Math.min(fromRect, toRect);
  const hi = Math.max(fromRect, toRect);
  let left = Number.POSITIVE_INFINITY;
  let top = Number.POSITIVE_INFINITY;
  let right = 0;
  let bottom = 0;

  for (let i = lo; i <= hi; i += 1) {
    const rect = textIndex.rects[i];
    if (!rect) continue;
    left = Math.min(left, rect.left);
    top = Math.min(top, rect.top);
    right = Math.max(right, rect.right);
    bottom = Math.max(bottom, rect.bottom);
  }

  if (!Number.isFinite(left) || !Number.isFinite(top) || right <= left || bottom <= top) return null;
  return {
    left: Math.max(0, left - 2),
    top: Math.max(0, top - 2),
    width: Math.max(18, right - left + 4),
    height: Math.max(14, bottom - top + 4)
  };
};

const rectCenter = (rect) => ({
  x: safeNumber(rect?.left, 0) + safeNumber(rect?.width, 0) / 2,
  y: safeNumber(rect?.top, 0) + safeNumber(rect?.height, 0) / 2
});

const rectMatchScore = (candidate, hintRect) => {
  if (!hintRect) return 0;
  const a = rectCenter(candidate);
  const b = rectCenter(hintRect);
  const hintW = Math.max(18, safeNumber(hintRect?.width, 18));
  const hintH = Math.max(14, safeNumber(hintRect?.height, 14));
  const dx = Math.abs(a.x - b.x) / hintW;
  const dy = Math.abs(a.y - b.y) / hintH;
  const widthRatio = Math.max(
    safeNumber(candidate?.width, 18) / hintW,
    hintW / Math.max(18, safeNumber(candidate?.width, 18))
  );
  const heightRatio = Math.max(
    safeNumber(candidate?.height, 14) / hintH,
    hintH / Math.max(14, safeNumber(candidate?.height, 14))
  );
  return dx + dy + (widthRatio - 1) * 0.35 + (heightRatio - 1) * 0.35;
};

const findRectBySnippet = (item, textIndex, hintRect = null) => {
  if (!textIndex || !textIndex.normalizedText || !textIndex.rects.length) return null;
  const candidates = buildSearchQueries(item?.snippet);
  if (!candidates.length) return null;

  let bestRect = null;
  let bestScore = Number.POSITIVE_INFINITY;

  for (const query of candidates) {
    let cursor = 0;
    let matchCount = 0;
    while (cursor >= 0) {
      const start = textIndex.normalizedText.indexOf(query, cursor);
      if (start < 0) break;
      const end = Math.min(textIndex.normalizedText.length, start + query.length);
      const rect = resolveMatchRect(textIndex, start, end);
      if (rect) {
        const score = rectMatchScore(rect, hintRect) - query.length * 0.015;
        if (score < bestScore) {
          bestScore = score;
          bestRect = rect;
        }
        if (!hintRect) {
          return rect;
        }
      }
      cursor = start + 1;
      matchCount += 1;
      if (matchCount >= 80) break;
    }

    if (!hintRect && bestRect) {
      return bestRect;
    }
  }

  return bestRect;
};

const buildFallbackRect = (item, canvasWidth, canvasHeight) => {
  const topRatio = clampRatio(item?.y_ratio ?? item?.ratio, 0.08, 0.01, 0.95);
  const leftRatio = clampRatio(item?.x_ratio ?? item?.left_ratio, 0.05, 0.01, 0.88);
  const spanRatio = clampRatio(item?.span_ratio, 0.24, 0.04, 0.92);
  const widthRatio = clampRatio(item?.width_ratio, Math.min(0.92, 0.18 + spanRatio * 0.85), 0.12, 0.95);
  const heightRatio = clampRatio(item?.height_ratio, Math.min(0.34, 0.05 + spanRatio * 0.42), 0.04, 0.42);
  const left = Math.min(leftRatio, Math.max(0.01, 0.98 - widthRatio));
  const top = Math.min(topRatio, Math.max(0.01, 0.98 - heightRatio));
  const w = Math.max(18, Math.round(canvasWidth * widthRatio));
  const h = Math.max(14, Math.round(canvasHeight * heightRatio));
  const l = Math.max(0, Math.round(canvasWidth * left));
  const t = Math.max(0, Math.round(canvasHeight * top));
  return { left: l, top: t, width: w, height: h };
};

const clampRectToCanvas = (rect, canvasWidth, canvasHeight) => {
  const width = Math.max(18, Math.min(canvasWidth, Math.round(rect?.width || 0)));
  const height = Math.max(14, Math.min(canvasHeight, Math.round(rect?.height || 0)));
  const left = Math.max(0, Math.min(canvasWidth - width, Math.round(rect?.left || 0)));
  const top = Math.max(0, Math.min(canvasHeight - height, Math.round(rect?.top || 0)));
  return { left, top, width, height };
};

const recalcAnnotationBoxes = () => {
  const canvas = canvasRef.value;
  if (!canvas) {
    annotationBoxes.value = [];
    return;
  }
  const canvasWidth = Math.max(1, Number(canvas.width || 0));
  const canvasHeight = Math.max(1, Number(canvas.height || 0));
  annotationBoxes.value = currentAnnotations.value.map((item) => {
    const fallbackRect = buildFallbackRect(item, canvasWidth, canvasHeight);
    const matched = findRectBySnippet(item, pageTextIndex.value, fallbackRect);
    return clampRectToCanvas(matched || fallbackRect, canvasWidth, canvasHeight);
  });
};

const readableNoteText = (value) => String(value || '')
  .replace(/\s+/g, ' ')
  .replace(/^[\-\*•]\s*/, '')
  .replace(/^\d+[.)、]\s*/, '')
  .trim();

const readableQuestionText = (value) => {
  const text = readableNoteText(value);
  if (!text) return '';
  return /[？?]$/.test(text) ? text : `${text}？`;
};

const annotationStyle = (item, idx) => {
  const box = annotationBoxes.value[idx];
  const palette = resolveRiskPalette(item?.risk_level);
  const focused = isAnnotationFocused(item);

  return {
    top: `${box?.top ?? 0}px`,
    left: `${box?.left ?? 0}px`,
    width: `${box?.width ?? 18}px`,
    height: `${box?.height ?? 14}px`,
    border: `2px solid ${palette.border}`,
    backgroundColor: palette.fill,
    boxShadow: focused ? `0 0 0 2px ${palette.glow}, inset 0 0 0 1px ${palette.glow}` : `0 0 0 1px ${palette.glow}`
  };
};

const noteCardStyle = (item) => {
  const palette = resolveRiskPalette(item?.risk_level);
  const focused = activeFocusKeyword.value && _annotationMatch(item, activeFocusKeyword.value);
  return {
    '--note-accent': palette.accent,
    '--note-text': palette.cardText,
    '--note-muted': palette.mutedText,
    '--note-tag-bg': palette.tagBg,
    '--note-tag-text': palette.tagText,
    '--note-divider': palette.divider,
    background: palette.cardBg,
    borderColor: palette.cardBorder,
    color: palette.cardText,
    boxShadow: focused
      ? `0 0 0 2px ${palette.glow}, 0 14px 28px ${palette.shadow}`
      : `0 10px 22px ${palette.shadow}`
  };
};

const riskLabel = (riskLevel) => resolveRiskPalette(riskLevel).label;

const noteRiskStyle = (item) => {
  const palette = resolveRiskPalette(item?.risk_level);
  return {
    background: palette.badgeBg,
    color: palette.badgeText,
    borderColor: palette.cardBorder
  };
};

const noteLocation = (item) => {
  const pageNo = Number(item?.page || 1);
  const paragraph = Number(item?.paragraph || 0);
  if (paragraph > 0) {
    return `第 ${pageNo} 页 · 第 ${paragraph} 段`;
  }
  return `第 ${pageNo} 页`;
};

const _textHit = (a, b) => {
  const left = String(a || '').trim().toLowerCase();
  const right = String(b || '').trim().toLowerCase();
  if (!left || !right) return false;
  if (right.length < 3) return false;
  return left.includes(right) || right.includes(left);
};

const _annotationMatch = (item, keyword) => {
  if (!keyword) return false;
  return _textHit(item?.description, keyword) || _textHit(item?.question, keyword) || _textHit(item?.snippet, keyword);
};

const focusByText = async (keyword) => {
  const key = String(keyword || '').trim();
  if (!key) return false;
  const idx = (props.annotations || []).findIndex((item) => _annotationMatch(item, key));
  if (idx < 0) return false;
  const hit = props.annotations[idx] || {};
  activeFocusKeyword.value = key;
  const targetPage = Number(hit.page || 1);
  if (targetPage !== page.value && targetPage >= 1 && targetPage <= pageCount.value) {
    page.value = targetPage;
    await nextTick();
    await renderPage();
  }
  return true;
};

defineExpose({ focusByText });

const renderPage = async () => {
  if (!pdfDoc.value || !canvasRef.value) {
    return;
  }
  loading.value = true;
  try {
    const pdfPage = await pdfDoc.value.getPage(page.value);
    let targetScale = Number(scale.value || 1);
    const rotation = effectiveRotation(pdfPage);
    if (fitToWidth.value && stageRef.value) {
      const baseViewport = pdfPage.getViewport({ scale: 1, rotation });
      const availableWidth = Math.max(280, Number(stageRef.value.clientWidth || 0) - 20);
      targetScale = availableWidth / Math.max(1, Number(baseViewport.width || 1));
      targetScale = Math.max(0.55, Math.min(2.5, targetScale));
      scale.value = Number(targetScale.toFixed(2));
    }
    const viewport = pdfPage.getViewport({ scale: targetScale, rotation });
    const canvas = canvasRef.value;
    const ctx = canvas.getContext('2d');
    canvas.height = viewport.height;
    canvas.width = viewport.width;
    await pdfPage.render({ canvasContext: ctx, viewport }).promise;
    try {
      const textContent = await pdfPage.getTextContent();
      pageTextIndex.value = buildPageTextIndex(pdfPage, viewport, textContent);
    } catch (_) {
      pageTextIndex.value = null;
    }
    recalcAnnotationBoxes();
  } finally {
    loading.value = false;
  }
};

const loadPdf = async () => {
  if (!props.pdfUrl) {
    pdfDoc.value = null;
    resolvedUrl.value = '';
    fallback.value = false;
    return;
  }
  loading.value = true;
  fallback.value = false;
  try {
    const baseUrl = resolvePdfUrl(props.pdfUrl);
    if (!baseUrl) {
      fallback.value = true;
      return;
    }
    resolvedUrl.value = baseUrl;

    if (!isPdfDoc.value) {
      pdfDoc.value = null;
      fallback.value = true;
      return;
    }

    const loadUrl = appendCacheBuster(baseUrl);
    pdfDoc.value = await pdfjsLib.getDocument({
      url: loadUrl,
      withCredentials: false
    }).promise;
    pageCount.value = pdfDoc.value.numPages || 1;
    page.value = 1;
    fitToWidth.value = true;
    manualRotation.value = 0;
    await nextTick();
    await renderPage();
  } catch (err) {
    // 304/缓存、CORS、worker 等异常时，回退到浏览器原生 iframe 预览。
    console.warn('PDF.js 加载失败，切换 iframe 预览:', err);
    fallback.value = true;
  } finally {
    loading.value = false;
  }
};

const prevPage = async () => {
  if (page.value > 1) {
    page.value -= 1;
    await renderPage();
  }
};

const nextPage = async () => {
  if (page.value < pageCount.value) {
    page.value += 1;
    await renderPage();
  }
};

const zoomIn = async () => {
  fitToWidth.value = false;
  scale.value = Math.min(2.2, scale.value + 0.1);
  await renderPage();
};

const zoomOut = async () => {
  fitToWidth.value = false;
  scale.value = Math.max(0.6, scale.value - 0.1);
  await renderPage();
};

const rotateLeft = async () => {
  fitToWidth.value = false;
  manualRotation.value = ((manualRotation.value - 90) % 360 + 360) % 360;
  await renderPage();
};

const rotateRight = async () => {
  fitToWidth.value = false;
  manualRotation.value = (manualRotation.value + 90) % 360;
  await renderPage();
};

const fitWidth = async () => {
  fitToWidth.value = true;
  await renderPage();
};

watch(() => props.pdfUrl, loadPdf, { immediate: true });
watch(currentAnnotations, () => {
  recalcAnnotationBoxes();
}, { deep: true });
watch(() => props.focusKeyword, (val) => {
  if (!val) {
    activeFocusKeyword.value = '';
    return;
  }
  focusByText(val);
});

watch(stageRef, (el, oldEl) => {
  if (!resizeObserver) return;
  if (oldEl) {
    resizeObserver.unobserve(oldEl);
  }
  if (el) {
    resizeObserver.observe(el);
  }
});

onMounted(() => {
  if (typeof ResizeObserver === 'undefined') return;
  resizeObserver = new ResizeObserver(async () => {
    if (!pdfDoc.value || !fitToWidth.value || fallback.value || !isPdfDoc.value) {
      return;
    }
    await renderPage();
  });
  if (stageRef.value) {
    resizeObserver.observe(stageRef.value);
  }
});

onBeforeUnmount(() => {
  if (resizeObserver) {
    resizeObserver.disconnect();
    resizeObserver = null;
  }
});
</script>

<style scoped>
.pdf-toolbar {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
  flex-wrap: wrap;
  padding: 8px 10px;
  border: 1px solid color-mix(in oklch, var(--line-soft) 80%, white);
  border-radius: 14px;
  background: color-mix(in oklch, var(--bg-panel) 92%, white);
}

.pdf-toolbar > span {
  color: var(--ink-body);
  font-size: 13px;
  font-weight: 620;
}

.pdf-toolbar :deep(.el-button) {
  min-height: 34px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 620;
}

.pdf-box {
  min-height: clamp(480px, 72vh, 1080px);
}

.pdf-stage {
  position: relative;
  overflow: auto;
  display: flex;
  justify-content: center;
  align-items: flex-start;
  flex: 1;
}

.pdf-stage-wrap {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(220px, 26vw);
  gap: 10px;
  align-items: start;
}

.pdf-canvas {
  display: block;
  box-shadow: 0 10px 24px color-mix(in oklch, var(--accent) 12%, transparent);
  border-radius: 8px;
}

.canvas-overlay-wrap {
  position: relative;
  display: inline-block;
}

.pdf-iframe {
  width: 100%;
  min-height: clamp(520px, 74vh, 1100px);
  border: none;
}

.annotation-layer {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
}

.box-mark {
  position: absolute;
  min-width: 28px;
  min-height: 22px;
  border-radius: 4px;
  padding: 2px 3px;
  font-size: 11px;
  line-height: 1.35;
  transition: box-shadow 0.2s ease, background-color 0.2s ease;
}

.box-mark.focused {
  backdrop-filter: saturate(1.05);
}

.mark-text {
  display: none;
}

.annotation-side {
  border: 1px solid color-mix(in oklch, var(--line-soft) 82%, white);
  border-radius: 16px;
  padding: 12px;
  max-height: clamp(340px, 74vh, 1000px);
  overflow-y: auto;
  background: linear-gradient(
    180deg,
    color-mix(in oklch, var(--accent) 6%, white) 0%,
    color-mix(in oklch, var(--bg-panel) 98%, white) 100%
  );
}

.note-list {
  display: grid;
  gap: 12px;
}

.note-card {
  width: 100%;
  border: 1px solid rgba(255, 255, 255, 0.24);
  border-radius: 16px;
  padding: 14px 16px;
  color: #ffffff;
  font-size: 13px;
  line-height: 1.72;
  box-sizing: border-box;
  position: relative;
}

.note-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 10px;
  margin-bottom: 10px;
  font-size: 11px;
  line-height: 1.4;
}

.note-meta-main {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.note-tag {
  display: inline-flex;
  align-items: center;
  padding: 0 8px;
  min-height: 22px;
  border-radius: 999px;
  background: var(--note-tag-bg, rgba(255, 255, 255, 0.14));
  color: var(--note-tag-text, currentColor);
  font-weight: 750;
  letter-spacing: 0.04em;
}

.note-risk {
  display: inline-flex;
  align-items: center;
  min-height: 22px;
  padding: 0 8px;
  border-radius: 999px;
  border: 1px solid transparent;
  font-weight: 750;
  letter-spacing: 0.02em;
}

.note-loc {
  color: var(--note-muted, rgba(255, 255, 255, 0.88));
}

.note-main,
.note-follow {
  margin: 0;
}

.note-main {
  font-size: 14px;
  font-weight: 680;
}

.note-follow-wrap {
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px solid var(--note-divider, rgba(255, 255, 255, 0.18));
}

.note-follow-label {
  margin: 0 0 4px;
  color: var(--note-muted, rgba(255, 255, 255, 0.76));
  font-size: 12px;
  letter-spacing: 0.04em;
}

.note-follow {
  color: var(--note-text, rgba(255, 255, 255, 0.94));
}

.word-preview {
  display: grid;
  gap: 10px;
}

.word-text {
  margin: 0;
  max-height: clamp(340px, 74vh, 1000px);
  overflow: auto;
  white-space: pre-wrap;
  line-height: 1.72;
  background: color-mix(in oklch, var(--bg-field) 84%, white);
  border: 1px solid color-mix(in oklch, var(--line-soft) 84%, white);
  border-radius: 12px;
  padding: 12px;
  font-size: 14px;
  color: var(--ink-body);
}


.word-annotation-list {
  display: grid;
  gap: 12px;
}

@media (max-width: 980px) {
  .pdf-toolbar {
    gap: 6px;
    padding: 8px;
  }

  .pdf-toolbar :deep(.el-button) {
    min-height: var(--touch-target);
    font-size: 13px;
  }

  .pdf-toolbar > span {
    font-size: 12px;
  }

  .pdf-stage-wrap {
    grid-template-columns: 1fr;
    gap: 8px;
  }

  .annotation-side {
    max-height: none;
    padding: 10px;
  }
}

@media (max-width: 640px) {
  .pdf-box {
    min-height: clamp(420px, 64vh, 960px);
  }

  .pdf-toolbar :deep(.el-button) {
    flex: 1 1 calc(50% - 6px);
  }

  .note-list {
    gap: 10px;
  }

  .note-card {
    border-radius: 14px;
    padding: 12px;
    font-size: 12px;
  }

  .note-main {
    font-size: 13px;
  }
}
</style>

