<template>
  <!--
    统一的空 / 异常态占位。
    "没有数据"和"加载失败"是两种完全不同的情况，之前全站都是"什么都不显示"，
    使用者分不清是没查到、还是坏了、还是本来就没有。这里把它们区分开。
  -->
  <div class="flex flex-col items-center justify-center text-center" :style="{ padding: compact ? '24px 16px' : '40px 16px' }">
    <div
      class="rounded-full flex items-center justify-center mb-3"
      :style="{
        width: compact ? '36px' : '44px',
        height: compact ? '36px' : '44px',
        backgroundColor: variant === 'error' ? '#FEF2F2' : 'var(--c-page)'
      }"
    >
      <el-icon :size="compact ? 18 : 22" :style="{ color: variant === 'error' ? '#B91C1C' : 'var(--c-ink-3)' }">
        <component :is="icon" />
      </el-icon>
    </div>

    <div class="text-[14px] font-medium" :style="{ color: variant === 'error' ? '#B91C1C' : 'var(--c-ink-2)' }">
      {{ title }}
    </div>

    <p
      v-if="description"
      class="text-[12px] font-normal mt-1"
      style="max-width: 380px; line-height: 18px; color: var(--c-ink-3);"
    >
      {{ description }}
    </p>

    <button
      v-if="actionText"
      class="mt-3 h-8 px-3 rounded-md text-[13px] font-normal"
      style="background-color: var(--c-surface); border: 1px solid var(--c-line); color: #334155;"
      @mouseenter="$event.currentTarget.style.borderColor = 'var(--c-primary)'; $event.currentTarget.style.color = 'var(--c-primary)'"
      @mouseleave="$event.currentTarget.style.borderColor = 'var(--c-line)'; $event.currentTarget.style.color = '#334155'"
      @click="$emit('action')"
    >
      {{ actionText }}
    </button>
  </div>
</template>

<script setup>
defineProps({
  // 图标名取自 @element-plus/icons-vue，必须是实际存在的名字，否则会静默渲染成空元素
  icon: { type: String, default: 'Document' },
  title: { type: String, default: '暂无数据' },
  description: { type: String, default: '' },
  actionText: { type: String, default: '' },
  variant: { type: String, default: 'empty' }, // empty | error
  compact: { type: Boolean, default: false }
})

defineEmits(['action'])
</script>
