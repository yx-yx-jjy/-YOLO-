<template>
  <div class="grid grid-cols-12 gap-5">
    <!-- 左侧 8 列：视频流与 KPI 指标卡片 -->
    <section class="col-span-8 flex flex-col gap-4">
      <!-- 实时视频画布播放器 -->
      <VideoPlayer />

      <!-- 4 个 KPI 指标统计卡片 -->
      <MetricCards />
    </section>

    <!-- 右侧 4 列：实时违规抓拍流 + 早晚高峰趋势图 -->
    <aside class="col-span-4 flex flex-col gap-4">
      <!-- 实时违规取证事件流列表 -->
      <ViolationStream />

      <!-- 违规高发时段趋势小看板 (SVG 仿真/ECharts) -->
      <div class="glass-panel p-4 rounded-xl border border-slate-800">
        <div class="flex items-center justify-between text-xs mb-2.5">
          <span class="font-bold text-slate-200 flex items-center gap-1.5">
            <span class="w-2 h-2 rounded-full bg-rose-500"></span>
            今日违规高发时段波动趋势
          </span>
          <span class="text-[11px] text-slate-400 font-mono">早晚高峰警报频发</span>
        </div>
        <div class="h-28 w-full">
          <svg class="w-full h-full" viewBox="0 0 300 90">
            <line x1="0" y1="25" x2="300" y2="25" stroke="#1e293b" stroke-dasharray="4 4"/>
            <line x1="0" y1="55" x2="300" y2="55" stroke="#1e293b" stroke-dasharray="4 4"/>
            <!-- 曲线 -->
            <path d="M 0 80 Q 50 75, 80 45 T 120 20 T 160 60 T 200 70 T 240 18 T 280 50 L 300 55" fill="none" stroke="#f43f5e" stroke-width="2.5"/>
            <!-- 阴影 -->
            <path d="M 0 80 Q 50 75, 80 45 T 120 20 T 160 60 T 200 70 T 240 18 T 280 50 L 300 55 L 300 90 L 0 90 Z" fill="rgba(244, 63, 94, 0.15)"/>
            <!-- 标记点 -->
            <circle cx="120" cy="20" r="4" fill="#f43f5e"/>
            <text x="120" y="13" fill="#fda4af" font-size="8" text-anchor="middle" font-family="monospace">早高峰 08:30</text>
            <circle cx="240" cy="18" r="4" fill="#f43f5e"/>
            <text x="240" y="11" fill="#fda4af" font-size="8" text-anchor="middle" font-family="monospace">晚高峰 18:00</text>
          </svg>
        </div>
        <div class="flex justify-between text-[10px] text-slate-500 font-mono mt-1">
          <span>00:00</span>
          <span>06:00</span>
          <span>12:00</span>
          <span>18:00</span>
          <span>24:00</span>
        </div>
      </div>
    </aside>
  </div>
</template>

<script setup>
import VideoPlayer from '../components/VideoPlayer.vue'
import MetricCards from '../components/MetricCards.vue'
import ViolationStream from '../components/ViolationStream.vue'
</script>
