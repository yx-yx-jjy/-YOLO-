<template>
  <div class="glass-panel rounded-xl overflow-hidden shadow-2xl relative flex flex-col border border-slate-800">
    <!-- 画面顶部工具栏 -->
    <div class="h-10 bg-slate-900/90 border-b border-slate-800/80 px-4 flex items-center justify-between text-xs">
      <div class="flex items-center gap-2.5">
        <span class="w-2 h-2 rounded-full bg-red-500 animate-ping"></span>
        <span class="text-slate-300 font-mono font-medium">LIVE 1080P | H.264 | RTSP-STREAM-CAM03</span>
        <span class="ml-2 px-1.5 py-0.5 rounded bg-slate-800 text-slate-400 border border-slate-700 font-mono">
          ByteTrack ID: {{ activeTracks }} Active
        </span>
      </div>

      <div class="flex items-center gap-3.5">
        <label class="flex items-center gap-1.5 cursor-pointer text-slate-300">
          <input type="checkbox" v-model="showHelmet" class="rounded accent-cyan-500" />
          <span>头盔/裸头</span>
        </label>
        <button 
          @click="handleSimulateViolation" 
          class="px-2.5 py-1 rounded bg-rose-600/90 hover:bg-rose-600 text-white font-medium text-xs transition flex items-center gap-1 shadow-sm active:scale-95"
        >
          <span class="w-1.5 h-1.5 rounded-full bg-white animate-pulse"></span>
          模拟触发新违规
        </button>
      </div>
    </div>

    <!-- 模拟监控画布 (16:9 比例) -->
    <div class="relative w-full h-[480px] bg-slate-950 flex items-center justify-center overflow-hidden">
      <!-- 仿真路面透视 SVG 背景 -->
      <svg class="absolute inset-0 w-full h-full object-cover opacity-30" viewBox="0 0 1000 600" preserveAspectRatio="none">
        <defs>
          <linearGradient id="roadGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stop-color="#1e293b"/>
            <stop offset="100%" stop-color="#070b14"/>
          </linearGradient>
        </defs>
        <rect width="1000" height="600" fill="url(#roadGrad)"/>
        <line x1="200" y1="600" x2="450" y2="220" stroke="#334155" stroke-width="2" stroke-dasharray="10 10"/>
        <line x1="500" y1="600" x2="500" y2="220" stroke="#475569" stroke-width="3" stroke-dasharray="20 15"/>
        <line x1="800" y1="600" x2="550" y2="220" stroke="#334155" stroke-width="2" stroke-dasharray="10 10"/>
        <rect x="340" y="320" width="320" height="15" fill="#1e293b" opacity="0.6"/>
        <rect x="320" y="350" width="360" height="18" fill="#1e293b" opacity="0.6"/>
      </svg>

      <!-- 仅展示头盔状态框；人员和车辆仅作为后台关联信息。 -->
      <div v-if="showHelmet" class="absolute left-[34%] top-[35%] border border-cyan-400 bg-cyan-400/25 w-[46px] h-[32px]">
        <span class="absolute -top-4 left-0 text-[8px] bg-cyan-500 text-slate-950 font-bold px-1 rounded">已戴头盔 0.96</span>
      </div>
      <div v-if="showHelmet" class="absolute right-[34%] top-[39%] border-2 border-red-500 bg-red-600/40 w-[52px] h-[36px] animate-pulse">
        <span class="absolute -top-4 -left-1 text-[9px] bg-red-600 text-white font-bold px-1 rounded shadow">未戴头盔</span>
      </div>

      <!-- 准星 UI 边框 -->
      <div class="absolute top-4 left-4 border-l-2 border-t-2 border-cyan-500 w-4 h-4"></div>
      <div class="absolute top-4 right-4 border-r-2 border-t-2 border-cyan-500 w-4 h-4"></div>
      <div class="absolute bottom-4 left-4 border-l-2 border-b-2 border-cyan-500 w-4 h-4"></div>
      <div class="absolute bottom-4 right-4 border-r-2 border-b-2 border-cyan-500 w-4 h-4"></div>

      <!-- 实时检测性能水印浮窗 -->
      <div class="absolute top-3 left-8 flex items-center gap-2.5 text-[11px] font-mono text-cyan-300/80 bg-slate-900/70 px-2.5 py-1 rounded border border-cyan-500/20 backdrop-blur">
        <span>FPS: {{ fps }}</span>
        <span>|</span>
        <span>Infer: 未实测</span>
        <span>|</span>
        <span>ByteTrack: 未实测</span>
        <span>|</span>
        <span>Resolution: 1920×1080</span>
      </div>
    </div>

    <!-- 视频底部控制台 -->
    <div class="p-3 bg-slate-900 border-t border-slate-800 flex items-center justify-between text-xs">
      <div class="flex items-center gap-2">
        <button 
          @click="togglePlay" 
          class="px-3 py-1.5 rounded text-white font-medium flex items-center gap-1.5 transition"
          :class="isPlaying ? 'bg-cyan-600 hover:bg-cyan-500' : 'bg-emerald-600 hover:bg-emerald-500'"
        >
          <span v-if="isPlaying">⏸ 暂停实时流</span>
          <span v-else>▶ 继续播放</span>
        </button>
        <button @click="snapFrame" class="px-3 py-1.5 rounded bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 transition">
          📷 手动截帧 (F8)
        </button>
      </div>

      <div class="flex items-center gap-6">
        <div class="flex items-center gap-2">
          <span class="text-slate-400">置信度阈值:</span>
          <input type="range" min="0.1" max="0.9" step="0.05" v-model="confThreshold" class="w-24 accent-cyan-500 cursor-pointer" />
          <span class="font-mono text-cyan-400 w-8">{{ confThreshold }}</span>
        </div>
        <div class="flex items-center gap-2">
          <span class="text-slate-400">IoU重叠阈值:</span>
          <input type="range" min="0.2" max="0.8" step="0.05" v-model="iouThreshold" class="w-20 accent-cyan-500 cursor-pointer" />
          <span class="font-mono text-cyan-400 w-8">{{ iouThreshold }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useViolationStore } from '../stores/violations'
import { triggerCameraSnapshot } from '../services/detectionApi'
import { ElMessage } from 'element-plus'

const violationStore = useViolationStore()

const isPlaying = ref(true)
const showHelmet = ref(true)
const confThreshold = ref(0.45)
const iouThreshold = ref(0.7)
const fps = ref(43.2)
const activeTracks = ref(6)

function togglePlay() {
  isPlaying.value = !isPlaying.value
  ElMessage.info(isPlaying.value ? '已恢复实时推理数据流' : '已暂停实时检测数据流')
}

function snapFrame() {
  ElMessage.success('已捕获当前高清监控帧并生成快照至本地静态目录！')
}

async function handleSimulateViolation() {
  // 检测事件现在由后端在任务完成时写入同一台账（架构稿 R3）：
  // 前端不再伪造记录，而是触发一次真实抓拍，再从后端把已落库的记录取回来。
  try {
    const record = await triggerCameraSnapshot('CAM-04')
    await Promise.allSettled([
      violationStore.fetchRecentRecords(12),
      violationStore.fetchOverview()
    ])
    ElMessage.warning({
      message: `⚠️ 触发新违规抓拍: 未按规定佩戴安全头盔 (#${record?.track_id ?? '—'})`,
      duration: 3000
    })
  } catch (err) {
    ElMessage.error(`抓拍失败：${err?.message || err}`)
  }
}
</script>
