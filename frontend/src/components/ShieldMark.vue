<template>
  <!--
    Element Plus 图标库没有盾牌图形（ShieldCheck / Shield 都不存在），
    这里用内联 stroke SVG 保留交管执法的盾牌意象。
    颜色跟随 currentColor，尺寸由 size 决定。
  -->
  <svg
    :width="size"
    :height="size"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    stroke-width="1.8"
    stroke-linecap="round"
    stroke-linejoin="round"
    aria-hidden="true"
  >
    <path d="M12 3 20 6.5v5c0 4.7-3.4 8.6-8 10-4.6-1.4-8-5.3-8-10v-5L12 3Z" />
    <path d="m8.8 11.8 2.4 2.4 4.2-4.4" />
  </svg>
</template>

<script setup>
defineProps({
  size: {
    type: [Number, String],
    default: 24
  }
})
</script>
