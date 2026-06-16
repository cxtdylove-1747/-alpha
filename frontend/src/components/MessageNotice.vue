<template>
  <el-card class="message-notice">
    <template #header>消息通知</template>
    <el-empty v-if="!items.length" description="暂无消息" />
    <div v-for="(item, idx) in items" :key="item.id" class="notice-item notice-tile" :style="toneStyle(idx)">
      <div class="notice-title-row">
        <strong>{{ item.title }}</strong>
        <span class="notice-tone" :style="toneBadgeStyle(idx)">{{ toneLabel(idx) }}</span>
      </div>
      <p>{{ item.content }}</p>
      <small>{{ item.created_at_text || toLocalText(item.created_at) }}</small>
    </div>
  </el-card>
</template>

<script setup>
const toLocalText = (value) => {
  if (!value) {
    return '';
  }
  const date = new Date(value);
  const p = (n) => `${n}`.padStart(2, '0');
  return `${date.getFullYear()}-${p(date.getMonth() + 1)}-${p(date.getDate())} ${p(date.getHours())}:${p(date.getMinutes())}:${p(date.getSeconds())}`;
};

const toneStyle = (idx) => {
  const tones = [
    { bg: 'linear-gradient(135deg, rgba(22, 93, 255, 0.09), rgba(255, 255, 255, 0.92))', border: 'rgba(22, 93, 255, 0.14)' },
    { bg: 'linear-gradient(135deg, rgba(0, 180, 42, 0.09), rgba(255, 255, 255, 0.92))', border: 'rgba(0, 180, 42, 0.14)' },
    { bg: 'linear-gradient(135deg, rgba(255, 125, 0, 0.09), rgba(255, 255, 255, 0.92))', border: 'rgba(255, 125, 0, 0.14)' },
    { bg: 'linear-gradient(135deg, rgba(245, 63, 63, 0.09), rgba(255, 255, 255, 0.92))', border: 'rgba(245, 63, 63, 0.14)' }
  ];
  const tone = tones[idx % tones.length];
  return { background: tone.bg, borderColor: tone.border };
};

const toneBadgeStyle = (idx) => {
  const badges = [
    { bg: 'rgba(22, 93, 255, 0.12)', color: 'var(--brand-primary)' },
    { bg: 'rgba(0, 180, 42, 0.12)', color: 'var(--brand-accent-green)' },
    { bg: 'rgba(255, 125, 0, 0.12)', color: 'var(--brand-accent-orange)' },
    { bg: 'rgba(245, 63, 63, 0.12)', color: 'var(--brand-accent-red)' }
  ];
  const tone = badges[idx % badges.length];
  return { background: tone.bg, color: tone.color };
};

const toneLabel = (idx) => {
  const labels = ['重要', '完成', '提醒', '关注'];
  return labels[idx % labels.length];
};

defineProps({
  items: {
    type: Array,
    default: () => []
  }
});
</script>

<style scoped>
.message-notice {
  border-radius: 8px;
}

.notice-tile {
  margin-bottom: 10px;
  padding: 12px;
  border-radius: 12px;
  border: 1px solid transparent;
  box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.3);
}

.notice-title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.notice-tone {
  display: inline-flex;
  align-items: center;
  padding: 3px 8px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 600;
}

.notice-tile p {
  margin: 10px 0 6px;
}
</style>
