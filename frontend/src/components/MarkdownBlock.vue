<template>
  <div class="markdown-block" v-html="html"></div>
</template>

<script setup>
import { computed } from 'vue';
import MarkdownIt from 'markdown-it';

const props = defineProps({
  content: {
    type: String,
    default: ''
  }
});

const markdown = new MarkdownIt({
  html: false,
  linkify: true,
  breaks: true,
  typographer: true
});

const html = computed(() => markdown.render(String(props.content || '')));
</script>

<style scoped>
.markdown-block {
  line-height: 1.68;
  color: inherit;
  word-break: break-word;
}

.markdown-block :deep(h1),
.markdown-block :deep(h2),
.markdown-block :deep(h3),
.markdown-block :deep(h4) {
  margin: 0.3em 0 0.5em;
  line-height: 1.3;
  letter-spacing: 0.01em;
}

.markdown-block :deep(p) {
  margin: 0 0 0.5em;
}

.markdown-block :deep(p:last-child) {
  margin-bottom: 0;
}

.markdown-block :deep(ul),
.markdown-block :deep(ol) {
  margin: 0.35em 0 0.5em;
  padding-left: 1.2em;
}

.markdown-block :deep(li) {
  margin: 0.15em 0;
}

.markdown-block :deep(table) {
  width: 100%;
  border-collapse: separate;
  border-spacing: 0;
  margin: 0.5em 0;
  font-size: 13px;
  border: 1px solid color-mix(in oklch, var(--line-soft) 80%, white);
  border-radius: 8px;
  overflow: hidden;
}

.markdown-block :deep(th),
.markdown-block :deep(td) {
  border-bottom: 1px solid color-mix(in oklch, var(--line-soft) 72%, white);
  padding: 6px 8px;
  text-align: left;
  vertical-align: top;
}

.markdown-block :deep(tr:last-child td) {
  border-bottom: none;
}

.markdown-block :deep(th) {
  background: color-mix(in oklch, var(--bg-field) 85%, white);
  color: var(--ink-muted);
  font-weight: 650;
}

.markdown-block :deep(code) {
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, "Liberation Mono", monospace;
  background: color-mix(in oklch, var(--bg-field) 84%, white);
  border-radius: 6px;
  padding: 1px 5px;
  font-size: 12px;
}

.markdown-block :deep(pre) {
  margin: 0.5em 0;
  padding: 10px;
  border-radius: 8px;
  overflow: auto;
  background: color-mix(in oklch, var(--bg-field) 74%, white);
}

.markdown-block :deep(pre code) {
  background: transparent;
  padding: 0;
}

.markdown-block :deep(blockquote) {
  margin: 0.5em 0;
  padding: 4px 10px;
  border-left: 3px solid var(--accent);
  color: var(--ink-muted);
  background: color-mix(in oklch, var(--bg-main) 90%, white);
}

.markdown-block :deep(a) {
  color: var(--accent);
  text-decoration: underline;
}
</style>
