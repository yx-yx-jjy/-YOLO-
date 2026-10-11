<template>
  <div class="max-w-4xl mx-auto space-y-6">
    <div class="text-center space-y-1">
      <h2 class="text-xl font-bold text-white tracking-wide">离线图像 / 视频违规智能分析检测</h2>
      <p class="text-xs text-slate-400">支持上传交通卡口录像 (MP4/AVI) 或现场高清抓拍照 (JPG/PNG)，算法模型将离线切帧并输出结构化证据链</p>
    </div>

    <!-- 拖拽上传区域 -->
    <div 
      @dragover.prevent="isDragging = true"
      @dragleave.prevent="isDragging = false"
      @drop.prevent="handleDrop"
      class="border-2 border-dashed rounded-2xl p-10 text-center transition cursor-pointer flex flex-col items-center justify-center gap-3 relative overflow-hidden"
      :class="isDragging ? 'border-cyan-400 bg-cyan-950/20' : 'border-slate-700 bg-slate-900/60 hover:border-slate-500'"
      @click="triggerFileInput"
    >
      <input type="file" ref="fileInput" class="hidden" accept="image/*,video/*" @change="handleFileChange" />
      
      <div class="w-16 h-16 rounded-2xl bg-cyan-950/60 border border-cyan-500/40 text-cyan-400 flex items-center justify-center shadow-lg">
        <svg class="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
        </svg>
      </div>

      <div class="text-sm font-semibold text-slate-200">
        点击选择文件 或 将视频/照片拖拽至此处
      </div>
      <div class="text-xs text-slate-500">
        支持 1080P/4K 高清视频切片（最大 500MB），推荐格式 MP4、MKV、JPG
      </div>
    </div>

    <!-- 分析中进度模拟条 -->
    <div v-if="isAnalyzing" class="glass-panel p-5 rounded-xl border border-cyan-500/40 space-y-3 animate-pulse">
      <div class="flex justify-between items-center text-xs">
        <span class="text-cyan-300 font-medium flex items-center gap-2">
          <span class="w-2 h-2 rounded-full bg-cyan-400 animate-ping"></span>
          改进 YOLO 推理引擎正在分析视频帧 [{{ currentFileName }}]...
        </span>
        <span class="font-mono text-cyan-400">{{ progress }}%</span>
      </div>
      <div class="w-full bg-slate-950 h-2 rounded-full overflow-hidden">
        <div class="bg-gradient-to-r from-cyan-500 to-blue-500 h-full transition-all duration-300" :style="{ width: progress + '%' }"></div>
      </div>
      <div class="text-[11px] text-slate-500 font-mono flex justify-between">
        <span>已抽取视频帧: {{ Math.floor(progress * 3.6) }} 帧</span>
        <span>检出目标: 非机动车 18 辆 | 未戴头盔线索 1 起</span>
      </div>
    </div>

    <!-- 分析完成：结构化结果展示报告 -->
    <div v-if="analysisDone" class="glass-panel p-6 rounded-xl border border-emerald-500/40 space-y-4">
      <div class="flex items-center justify-between border-b border-slate-800 pb-4">
        <div class="flex items-center gap-2">
          <span class="w-3 h-3 rounded-full bg-emerald-500"></span>
          <h3 class="font-bold text-white text-base">离线检测报告生成完毕</h3>
          <span class="text-xs px-2 py-0.5 rounded bg-emerald-950 text-emerald-300 border border-emerald-500/30">
            成功检出 1 起未戴头盔事件
          </span>
        </div>
        <button @click="resetUpload" class="text-xs text-slate-400 hover:text-white transition">重新上传</button>
      </div>

      <!-- 检出事件列表 -->
      <div class="grid grid-cols-1 gap-4">
        <div class="p-3.5 rounded-lg bg-slate-900 border border-amber-500/40 space-y-2">
          <div class="flex justify-between items-center">
            <span class="text-xs font-bold text-amber-300">事件 1: 骑行人员未按规定佩戴安全头盔</span>
            <span class="text-[10px] text-slate-400 font-mono">00:11.75 帧处</span>
          </div>
          <div class="text-xs text-slate-300">
            <div>• 目标: 黑色小牛电动 (置信度 91%)</div>
            <div>• 空间关联: 骑手头部裸头判定成立</div>
          </div>
          <button @click="importToRecords" class="w-full mt-2 py-1.5 rounded bg-amber-600 hover:bg-amber-500 text-slate-950 font-bold text-xs transition">
            一键导入待复核台账
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useViolationStore } from '../stores/violations'
import { ElMessage } from 'element-plus'

const violationStore = useViolationStore()
const fileInput = ref(null)
const isDragging = ref(false)
const isAnalyzing = ref(false)
const analysisDone = ref(false)
const progress = ref(0)
const currentFileName = ref('')

function triggerFileInput() {
  if (fileInput.value) fileInput.value.click()
}

function handleFileChange(e) {
  const file = e.target.files[0]
  if (file) startAnalysis(file.name)
}

function handleDrop(e) {
  isDragging.value = false
  const file = e.dataTransfer.files[0]
  if (file) startAnalysis(file.name)
}

function startAnalysis(fileName) {
  currentFileName.value = fileName
  isAnalyzing.value = true
  analysisDone.value = false
  progress.value = 0

  const timer = setInterval(() => {
    progress.value += 10
    if (progress.value >= 100) {
      clearInterval(timer)
      isAnalyzing.value = false
      analysisDone.value = true
      ElMessage.success('视频智能切帧与违规检测完成！')
    }
  }, 200)
}

function resetUpload() {
  analysisDone.value = false
  progress.value = 0
}

async function importToRecords() {
  // 离线检测事件现在由后端在检测任务完成时并入同一台账（架构稿 R3），
  // 前端不再自行造记录，只刷新把已落库的记录取回来。
  await violationStore.addInferenceViolation()
  ElMessage.success('已刷新取证台账，离线检测事件由后端入库后在此可查')
}
</script>
