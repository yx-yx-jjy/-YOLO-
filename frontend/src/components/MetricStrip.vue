<template>
  <section
    class="metric-strip"
    :style="{ '--metric-cols': items.length || 1 }"
    :aria-label="ariaLabel"
  >
    <div v-for="item in items" :key="item.label" class="metric-strip__cell">
      <div class="metric-strip__label">{{ item.label }}</div>
      <div class="metric-strip__value" :style="{ color: toneColor(item.tone) }">
        <span>{{ formatValue(item.value) }}</span>
        <span v-if="item.unit" class="metric-strip__unit">{{ item.unit }}</span>
      </div>
      <div v-if="item.hint" class="metric-strip__hint">{{ item.hint }}</div>
    </div>
  </section>
</template>

<script setup>
/**
 * 页面概览条：一行并排 3–5 个关键指标，回答"当前状态怎么样"。
 * 整条是一个卡片、内部用 1px 分隔线分格，而不是 N 张独立卡片 ——
 * 语义上它们是一组并列指标，视觉上也不该被 gap 拆散。
 */
defineProps({
  items: {
    type: Array,
    default: () => []
  },
  ariaLabel: {
    type: String,
    default: '关键指标概览'
  }
})

// 语义色只允许出现在数值上（规范 §1 的三色仅用于状态表达）
const TONE_COLORS = {
  default: 'var(--c-ink)',
  warning: '#B45309',
  success: '#15803D',
  danger: '#B91C1C'
}

function toneColor(tone) {
  return TONE_COLORS[tone] || TONE_COLORS.default
}

function formatValue(value) {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return value.toLocaleString('zh-CN')
  }
  return value ?? '—'
}
</script>

<style scoped>
.metric-strip {
  display: grid;
  grid-template-columns: repeat(var(--metric-cols, 4), minmax(0, 1fr));
  background: var(--c-surface);
  border: 1px solid var(--c-line);
  border-radius: 10px;
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
  overflow: hidden;
}

.metric-strip__cell {
  min-width: 0;
  padding: 16px;
  border-left: 1px solid var(--c-line);
}

.metric-strip__cell:first-child {
  border-left: 0;
}

.metric-strip__label {
  overflow: hidden;
  color: var(--c-ink-3);
  font-size: 12px;
  line-height: 18px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.metric-strip__value {
  /* flex + gap 负责数值与单位的间距：模板里的换行空白会被忽略，
     不会出现 "88.2 %" 这种中间多一个空格的写法 */
  display: flex;
  align-items: baseline;
  gap: 4px;
  margin-top: 6px;
  font-size: 26px;
  font-weight: 500;
  line-height: 34px;
  letter-spacing: -0.02em;
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}

.metric-strip__unit {
  color: var(--c-ink-3);
  font-size: 12px;
  font-weight: 400;
  line-height: 18px;
  letter-spacing: 0;
}

.metric-strip__hint {
  margin-top: 2px;
  overflow: hidden;
  color: var(--c-ink-3);
  font-size: 12px;
  line-height: 18px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* 窄屏降为两列，避免数字被压到换行 */
@media (max-width: 1180px) {
  .metric-strip {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .metric-strip__cell:nth-child(odd) {
    border-left: 0;
  }

  .metric-strip__cell:nth-child(n + 3) {
    border-top: 1px solid var(--c-line);
  }
}
</style>
