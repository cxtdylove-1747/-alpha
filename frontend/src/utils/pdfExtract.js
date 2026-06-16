import * as pdfjsLib from 'pdfjs-dist';
import workerSrc from 'pdfjs-dist/build/pdf.worker.min.mjs?url';

pdfjsLib.GlobalWorkerOptions.workerSrc = workerSrc;

const normalizeToMediaPath = (pathValue) => {
  let normalizedPath = String(pathValue || '').trim();
  if (!normalizedPath) {
    return '';
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

  const backendOrigin = (() => {
    const configured = String(import.meta.env.VITE_BACKEND_ORIGIN || '').trim();
    const fallback = (typeof window !== 'undefined' && window.location?.origin) ? window.location.origin : '';
    let origin = configured || fallback;
    if (!/^https?:\/\//i.test(origin)) {
      origin = fallback;
    }
    return String(origin || '').replace(/\/+$/, '');
  })();

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
  if (import.meta.env.DEV) {
    return normalizedPath;
  }
  return backendOrigin ? `${backendOrigin}${normalizedPath}` : normalizedPath;
};

export const extractPdfPagesFromUrl = async (pdfUrl, maxPages = 100) => {
  const resolved = resolvePdfUrl(pdfUrl);
  if (!resolved) {
    return [];
  }
  const doc = await pdfjsLib.getDocument({ url: resolved, withCredentials: false }).promise;
  const limit = Math.min(doc.numPages || 0, maxPages);
  const pages = [];
  for (let pageNo = 1; pageNo <= limit; pageNo += 1) {
    const page = await doc.getPage(pageNo);
    const content = await page.getTextContent();
    const text = (content.items || [])
      .map((item) => item?.str || '')
      .join(' ')
      .replace(/\s+/g, ' ')
      .trim();
    pages.push({ page: pageNo, text });
  }
  return pages;
};
