<template>
  <div class="grid grid-cols-3 gap-3.5">
    <!-- 卡片 1: 检测总量 -->
    <div class="glass-panel p-4 rounded-xl border border-slate-800/80 hover:border-slate-700 transition">
      <div class="flex items-center justify-between text-slate-400 text-xs mb-1.5 font-medium">
        <span>今日检测车辆总量</span>
        <span class="text-cyan-400 font-mono text-[11px] bg-cyan-950/60 px-1.5 py-0.5 rounded border border-cyan-800/40">Total</span>
      </div>
      <div class="text-2xl font-bold font-mono text-white flex items-baseline gap-2">
        <span>{{ stats.totalVehicles == null ? '—' : stats.totalVehicles.toLocaleString() }}</span>
      </div>
      <div class="text-[11px] text-slate-500 mt-1 flex items-center gap-1">
        <span class="w-1.5 h-1.5 rounded-full bg-emerald-500"></span>
        台账累计违规线索
      </div>
    </div>

    <!-- 卡片 2: 头盔佩戴率 -->
    <div class="glass-panel p-4 rounded-xl border border-slate-800/80 hover:border-slate-700 transition">
      <div class="flex items-center justify-between text-slate-400 text-xs mb-1.5 font-medium">
        <span>头盔综合合规佩戴率</span>
        <span class="text-emerald-400 font-mono text-[11px] bg-emerald-950/60 px-1.5 py-0.5 rounded border border-emerald-800/40">Compliance</span>
      </div>
      <div class="text-2xl font-bold font-mono text-emerald-400 flex items-baseline gap-2">
        <span>{{ stats.complianceRate == null ? '—' : stats.complianceRate + '%' }}</span>
      </div>
      <div class="text-[11px] text-slate-500 mt-1 flex items-center gap-1">
        <span class="w-1.5 h-1.5 rounded-full bg-emerald-400"></span>
        该口径后端暂未提供
      </div>
    </div>

    <!-- 卡片 3: 未戴头盔违规 -->
    <div class="glass-panel p-4 rounded-xl border border-slate-800/80 hover:border-slate-700 transition">
      <div class="flex items-center justify-between text-slate-400 text-xs mb-1.5 font-medium">
        <span>未戴安全头盔违规</span>
        <span class="text-amber-400 font-mono text-[11px] bg-amber-950/60 px-1.5 py-0.5 rounded border border-amber-800/40">No Helmet</span>
      </div>
      <div class="text-2xl font-bold font-mono text-amber-400 flex items-baseline gap-2">
        <span>{{ stats.noHelmetCount == null ? '—' : stats.noHelmetCount.toLocaleString() }}</span>
      </div>
      <div class="text-[11px] text-slate-500 mt-1 flex items-center gap-1">
        <span class="w-1.5 h-1.5 rounded-full bg-amber-400"></span>
        所有线索均进入人工复核队列
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useViolationStore } from '../stores/violations'

const violationStore = useViolationStore()
const stats = computed(() => violationStore.stats)
</script>
