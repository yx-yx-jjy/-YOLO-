<template>
  <!--
    演示数据标注。
    在后端统计接口与数据库接入之前，页面上仍有一部分数字无法从台账派生
    （例如预测推演、训练指标）。与其把它们伪装成真实统计值，不如明确标出来 ——
    既对使用者诚实，也让"哪些数字可以拿去做决策"一目了然。
  -->
  <span
    class="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[12px] font-normal whitespace-nowrap"
    style="background-color: #FFFBEB; color: #B45309;"
    :title="hint"
  >
    <el-icon :size="12"><InfoFilled /></el-icon>
    <span>{{ label }}</span>
  </span>
</template>

<script setup>
defineProps({
  label: { type: String, default: '演示数据' },
  hint: { type: String, default: '该区域的数字尚未接入真实统计接口，请勿用于执法或考核决策' }
})
</script>
