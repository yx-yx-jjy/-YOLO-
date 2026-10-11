<template>
  <div class="space-y-4">
    <div class="card flex flex-wrap items-center justify-between gap-3">
      <div>
        <h2 class="text-[16px] font-medium" style="color: var(--c-ink);">
          {{ isImage ? '交通抓拍图片违规识别' : '道路监控视频违规分析' }}
        </h2>
        <p class="text-[12px] mt-0.5" style="color: var(--c-ink-3);">
          {{ isImage ? '智能目标识别 · 人车空间关联 · 违规规则判定' : '多帧连续确认 · 轨迹关联 · 违规关键帧取证' }}
        </p>
      </div>

      <div class="flex items-center gap-2">
        <span
          class="inline-flex h-8 items-center gap-1.5 rounded-md px-2.5 text-[12px]"
          :style="modelReady
            ? 'background:#F0FDF4;color:#15803D;border:1px solid #BBF7D0'
            : 'background:#FFF7ED;color:#C2410C;border:1px solid #FED7AA'"
        >
          <i class="h-1.5 w-1.5 rounded-full" :class="modelReady ? 'bg-green-600' : 'bg-orange-600'"></i>
          {{ healthLoading ? '检查引擎...' : (modelReady ? '检测引擎已就绪' : '检测引擎未就绪') }}
        </span>
        <button class="h-8 rounded-md border px-3 text-[12px]" style="border-color:var(--c-line);color:var(--c-ink-2)" @click="loadHealth">
          重新检查
        </button>
      </div>
    </div>

    <MetricStrip :items="kpiItems" :aria-label="isImage ? '图片识别概览' : '视频识别概览'" />

    <div
      v-if="health && !modelReady"
      class="rounded-md border px-4 py-3 text-[13px]"
      style="border-color:#FED7AA;background:#FFF7ED;color:#9A3412"
    >
      <div class="font-medium">推理服务已连接，但定制权重尚未部署</div>
      <div class="mt-1 text-[12px]">{{ health.model.message }}</div>
      <div class="mt-1 text-[12px]">模型需包含：电动车/车辆、人员、头盔、未戴头盔四组语义类别。</div>
    </div>

    <div v-else-if="healthError" class="rounded-md border px-4 py-3 text-[13px]" style="border-color:#FECACA;background:#FEF2F2;color:#B91C1C">
      {{ healthError }}。启动命令：在 backend 目录运行 <span class="font-mono">.\run.ps1</span>
    </div>

    <div class="grid grid-cols-12 gap-4">
      <section class="col-span-7 space-y-4">
        <div class="card space-y-3">
          <div class="flex items-center justify-between border-b pb-2" style="border-color:var(--c-line)">
            <span class="text-[13px] font-medium" style="color:var(--c-ink)">{{ selectedFile?.name || '选择待检测文件' }}</span>
            <span v-if="selectedFile" class="font-mono text-[12px]" style="color:var(--c-ink-3)">{{ formatBytes(selectedFile.size) }}</span>
          </div>

          <label
            v-if="!previewUrl"
            class="flex h-96 cursor-pointer flex-col items-center justify-center gap-3 rounded-lg border-2 border-dashed transition"
            style="border-color:var(--c-line);background:var(--c-page)"
            @dragover.prevent
            @drop.prevent="handleDrop"
          >
            <el-icon :size="36" style="color:var(--c-primary)"><UploadFilled /></el-icon>
            <span class="text-[14px] font-medium" style="color:var(--c-ink)">选择或拖入{{ isImage ? '图片' : '视频' }}</span>
            <span class="text-[12px]" style="color:var(--c-ink-3)">{{ acceptHint }}</span>
            <input class="hidden" type="file" :accept="accept" @change="handleFileInput" />
          </label>

          <div v-else class="relative h-96 overflow-hidden rounded-lg" style="background-color: var(--c-page);">
            <img v-if="isImage" :src="displayImageUrl" class="h-full w-full object-contain" alt="检测图像预览" />
            <video v-else :src="previewUrl" class="h-full w-full object-contain" controls preload="metadata"></video>
            <span v-if="job?.status === 'completed' && isImage" class="absolute left-3 top-3 rounded bg-emerald-700 px-2 py-1 text-[11px] text-white">识别标注结果</span>
          </div>

          <div class="flex items-center justify-between gap-3">
            <label class="h-8 cursor-pointer rounded-md border px-3 text-[12px] leading-8" style="border-color:var(--c-line);color:var(--c-ink-2)">
              更换文件
              <input class="hidden" type="file" :accept="accept" @change="handleFileInput" />
            </label>
            <button
              class="h-8 rounded-md px-4 text-[13px] text-white disabled:cursor-not-allowed disabled:opacity-50 transition cursor-pointer"
              style="background:var(--c-primary)"
              :disabled="!selectedFile || running"
              @click="startDetection"
            >
              {{ running ? '正在分析...' : '开始违规检测' }}
            </button>
          </div>

          <div v-if="running" class="space-y-1.5">
            <div class="flex justify-between text-[12px]" style="color:var(--c-ink-3)">
              <span>{{ job?.stage || (uploadProgress < 100 ? '正在上传文件' : '等待推理') }}</span>
              <span class="font-mono">{{ totalProgress }}%</span>
            </div>
            <div class="h-2 overflow-hidden rounded-full bg-slate-200">
              <div class="h-full transition-all" :style="{ width: `${totalProgress}%`, backgroundColor: 'var(--c-primary)' }"></div>
            </div>
          </div>

          <div v-if="job?.status === 'failed'" class="rounded-md bg-red-50 px-3 py-2 text-[12px] text-red-700">
            {{ job.error?.message || '分析失败' }}
          </div>
        </div>

        <!-- 最近处理：本会话内已完成的检测。空的时候也保留区块并给出引导，
             之前整块隐藏，使用者会以为功能没做。 -->
        <div class="card !p-0 overflow-hidden">
          <div class="flex h-12 items-center justify-between px-4" style="border-bottom:1px solid var(--c-line)">
            <h3 class="text-[14px] font-medium" style="color:var(--c-ink)">最近处理</h3>
            <span class="text-[12px]" style="color:var(--c-ink-3)">仅本机当前会话</span>
          </div>
          <ul v-if="recentJobs.length">
            <li
              v-for="item in recentJobs"
              :key="item.id"
              class="flex h-12 items-center justify-between gap-3 px-4 last:border-b-0"
              style="border-bottom:1px solid var(--c-line)"
            >
              <div class="min-w-0 flex-1">
                <div class="text-[13px] truncate" style="color:var(--c-ink)" :title="item.fileName">{{ item.fileName }}</div>
                <div class="text-[12px] font-mono" style="color:var(--c-ink-3)">{{ item.time }} · 检出目标 {{ item.objects }} 个</div>
              </div>
              <span
                class="whitespace-nowrap rounded px-2 py-0.5 text-[12px]"
                :style="item.violations > 0
                  ? 'background-color:#FFFBEB;color:#B45309'
                  : 'background-color:#F0FDF4;color:#15803D'"
              >
                {{ item.violations > 0 ? `疑似违规 ${item.violations} 起` : '未发现违规' }}
              </span>
            </li>
          </ul>
          <EmptyState
            v-else
            compact
            icon="Document"
            title="本会话还没有处理记录"
            description="上传文件开始一次识别，处理完成后会出现在这里，可用于快速回看。"
          />
        </div>
      </section>

      <aside class="col-span-5">
        <div class="card flex min-h-[472px] flex-col">
          <div class="flex items-center justify-between border-b pb-2" style="border-color:var(--c-line)">
            <h3 class="text-[14px] font-medium" style="color:var(--c-ink)">检测结论</h3>
            <button v-if="result" class="text-[12px]" style="color:var(--c-primary)" @click="downloadJson">导出 JSON</button>
          </div>

          <!-- 未出结果时显示处理流程：既回答"点了之后会发生什么"，也是运行中的进度指示 -->
          <template v-if="!result">
            <p class="pt-3 text-[12px] leading-5" style="color:var(--c-ink-3)">
              {{ running
                ? '正在分析，请保持本页开启。'
                : '上传文件后系统按下列流程处理。分析结果仅作为疑似违规线索，须经人工复核后方可入卷。' }}
            </p>

            <div class="flex flex-1 flex-col justify-center">
              <ol class="pipeline">
                <li
                  v-for="(step, index) in pipelineSteps"
                  :key="step.key"
                  class="pipeline__item"
                  :class="`is-${stepStates[index]}`"
                >
                  <span class="pipeline__dot">
                    <el-icon v-if="stepStates[index] === 'done'" :size="11"><Check /></el-icon>
                    <template v-else>{{ index + 1 }}</template>
                  </span>
                  <div class="pipeline__body">
                    <div class="pipeline__label">{{ step.label }}</div>
                    <div class="pipeline__desc">{{ step.desc }}</div>
                    <div v-if="stepStates[index] === 'active' && stageText" class="pipeline__stage">
                      {{ stageText }}
                    </div>
                  </div>
                </li>
              </ol>
            </div>
          </template>

          <template v-else>
            <div class="grid grid-cols-3 gap-2 py-3">
              <div class="rounded-md bg-slate-50 p-2 text-center"><div class="text-[11px] text-slate-500">违规事件</div><div class="mt-0.5 font-mono text-lg font-medium text-red-700">{{ result.summary.violations }}</div></div>
              <div class="rounded-md bg-slate-50 p-2 text-center"><div class="text-[11px] text-slate-500">{{ isImage ? '检出目标' : '采样帧' }}</div><div class="mt-0.5 font-mono text-lg font-medium text-slate-800">{{ isImage ? result.summary.objects : result.sampled_frames }}</div></div>
              <div class="rounded-md bg-slate-50 p-2 text-center"><div class="text-[11px] text-slate-500">人工复核</div><div class="mt-0.5 font-mono text-lg font-medium text-amber-700">必需</div></div>
            </div>

            <div v-if="result.events.length === 0" class="rounded-md border border-green-200 bg-green-50 px-3 py-3 text-[13px] text-green-700">
              未检出满足规则的明确违规事件。该结论不代表绝对合规，低置信度和遮挡目标仍需抽查。
            </div>

            <div class="max-h-[340px] space-y-2 overflow-y-auto pr-1">
              <article v-for="(event, index) in result.events" :key="`${event.code}-${index}`" class="rounded-md border border-amber-200 bg-amber-50 p-3">
                <img v-if="event.evidence_url" :src="event.evidence_url" class="mb-2 h-28 w-full rounded object-cover" alt="违规关键帧" />
                <div class="flex items-start justify-between gap-2">
                  <div class="text-[13px] font-medium text-amber-900">{{ event.title }}</div>
                  <span class="shrink-0 rounded bg-white px-1.5 py-0.5 font-mono text-[11px] text-amber-800">{{ Math.round(event.confidence * 100) }}%</span>
                </div>
                <div class="mt-1 text-[12px] text-amber-800">
                  <span v-if="event.timestamp_seconds !== undefined">时间 {{ formatTime(event.timestamp_seconds) }} · </span>
                  头盔状态：未佩戴
                </div>
                <div v-if="event.note" class="mt-1 text-[11px] text-amber-700">{{ event.note }}</div>
                <button class="mt-2 h-7 w-full rounded bg-amber-700 text-[12px] text-white" @click="addToReview(event)">加入待复核台账</button>
              </article>
            </div>
          </template>
        </div>
      </aside>
    </div>

    <div v-if="isImage && result?.detections?.length" class="card !p-0 overflow-hidden">
      <div class="border-b p-4 text-[14px] font-medium" style="border-color:var(--c-line);color:var(--c-ink)">检测目标明细</div>
      <table class="w-full text-left text-[12px]">
        <thead class="bg-slate-50 text-slate-500"><tr><th class="px-4 py-2">类别</th><th class="px-4 py-2">置信度</th><th class="px-4 py-2">目标框 [x1, y1, x2, y2]</th><th class="px-4 py-2">轨迹 ID</th></tr></thead>
        <tbody>
          <tr v-for="(item, index) in result.detections" :key="index" class="border-t" style="border-color:var(--c-line)">
            <td class="px-4 py-2 font-medium">{{ item.class_name }}</td>
            <td class="px-4 py-2 font-mono">{{ (item.confidence * 100).toFixed(1) }}%</td>
            <td class="px-4 py-2 font-mono text-slate-500">{{ item.bbox.join(', ') }}</td>
            <td class="px-4 py-2 font-mono text-slate-500">{{ item.track_id ?? '-' }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useViolationStore } from '../stores/violations'
import { createDetection, getDetection, getInferenceHealth, getApiErrorMessage } from '../services/detectionApi'
import MetricStrip from './MetricStrip.vue'
import EmptyState from './EmptyState.vue'

const props = defineProps({
  mode: { type: String, required: true, validator: value => ['image', 'video'].includes(value) }
})

const violationStore = useViolationStore()
const health = ref(null)
const healthError = ref('')
const healthLoading = ref(false)
const selectedFile = ref(null)
const previewUrl = ref('')
const uploadProgress = ref(0)
const job = ref(null)
const stopped = ref(false)

const isImage = computed(() => props.mode === 'image')
const accept = computed(() => isImage.value ? '.jpg,.jpeg,.png,.webp,image/*' : '.mp4,.avi,.mov,.mkv,video/*')
const acceptHint = computed(() => isImage.value ? '支持 JPG、PNG、WEBP' : '支持 MP4、AVI、MOV、MKV，最大 500 MB')
const modelReady = computed(() => health.value?.model?.ready === true)
const result = computed(() => job.value?.result || null)
const running = computed(() => ['uploading', 'queued', 'running'].includes(job.value?.status))
const totalProgress = computed(() => job.value?.status === 'uploading' ? Math.round(uploadProgress.value * 0.15) : Math.max(15, job.value?.progress || 0))
const displayImageUrl = computed(() => result.value?.annotated_url || previewUrl.value)

// 概览条数据源：本会话累计（可核实），加上台账里的待复核积压
const sessionStats = ref({ files: 0, objects: 0, violations: 0 })

const kpiItems = computed(() => [
  {
    label: isImage.value ? '本会话已检图片' : '本会话已分析视频',
    value: sessionStats.value.files,
    unit: isImage.value ? '张' : '段'
  },
  {
    label: '累计检出目标',
    value: sessionStats.value.objects,
    unit: '个'
  },
  {
    label: '疑似违规线索',
    value: sessionStats.value.violations,
    unit: '起',
    tone: sessionStats.value.violations > 0 ? 'warning' : 'default'
  },
  {
    label: '待人工复核',
    value: violationStore.pendingCount,
    unit: '起',
    tone: violationStore.pendingCount > 0 ? 'warning' : (violationStore.pendingCount == null ? 'default' : 'success')
  }
])

/* ── 检测流程说明 ──────────────────────────────────────
   给用户看的是业务阶段，不是引擎内部步骤。
   后端 job.stage 的原文里带引擎名称（"正在加载 YOLO 模型"），
   所以这里不回显原文，只从里面提取"已分析 X / Y 个采样帧"这类纯进度信息。 */
const pipelineSteps = computed(() => isImage.value
  ? [
      { key: 'upload', label: '上传文件', desc: '支持 JPG / PNG / WEBP' },
      { key: 'detect', label: '智能识别与判定', desc: '识别人员、车辆与头盔，判定违规' },
      { key: 'evidence', label: '生成标注证据', desc: '输出带目标框的标注图与坐标明细' },
      { key: 'review', label: '人工复核', desc: '转入台账，由执勤民警确认入卷' }
    ]
  : [
      { key: 'upload', label: '上传文件', desc: '支持 MP4 / AVI / MOV / MKV，最大 500 MB' },
      { key: 'detect', label: '逐帧识别与轨迹关联', desc: '跨帧关联同一目标，排除瞬时误检' },
      { key: 'evidence', label: '生成取证事件', desc: '连续多帧确认后输出关键帧证据' },
      { key: 'review', label: '人工复核', desc: '转入台账，由执勤民警确认入卷' }
    ])

const stageText = computed(() => {
  const status = job.value?.status
  if (status === 'uploading') return `正在上传 · ${Math.round(uploadProgress.value)}%`
  if (status === 'queued') return '已排队，等待分析引擎'
  if (status === 'running') {
    const progress = job.value?.progress || 0
    if (isImage.value) {
      return progress < 75 ? '正在识别图片中的目标' : '正在执行违规关联判定'
    }
    const matched = String(job.value?.stage || '').match(/已分析\s*(\d+)\s*\/\s*(\d+)/)
    return matched ? `已分析 ${matched[1]} / ${matched[2]} 个采样帧` : '正在逐帧分析视频'
  }
  if (status === 'completed') return '分析完成'
  if (status === 'failed') return '分析中断'
  return ''
})

const stepStates = computed(() => {
  const steps = pipelineSteps.value
  const status = job.value?.status
  const progress = job.value?.progress ?? 0

  if (!status) return steps.map(() => 'idle')
  if (status === 'failed') return steps.map((_, index) => (index === 0 ? 'failed' : 'idle'))

  const activeIndex = status === 'uploading'
    ? 0
    : (status === 'running' && progress >= 100 ? 2 : (status === 'completed' ? steps.length - 1 : 1))

  return steps.map((_, index) => {
    if (index < activeIndex) return 'done'
    if (index === activeIndex) return 'active'
    return 'idle'
  })
})

/* 最近处理：仅本机当前会话，刷新即清空，避免展示无从核实的历史数据 */
const recentJobs = ref([])

async function loadHealth() {
  healthLoading.value = true
  healthError.value = ''
  try {
    health.value = await getInferenceHealth()
  } catch (error) {
    health.value = null
    healthError.value = getApiErrorMessage(error)
  } finally {
    healthLoading.value = false
  }
}

function selectFile(file) {
  if (!file) return
  const matchesMode = isImage.value ? file.type.startsWith('image/') : file.type.startsWith('video/')
  if (!matchesMode) return ElMessage.error(`请选择${isImage.value ? '图片' : '视频'}文件`)
  if (previewUrl.value) URL.revokeObjectURL(previewUrl.value)
  selectedFile.value = file
  previewUrl.value = URL.createObjectURL(file)
  uploadProgress.value = 0
  job.value = null
  if (!modelReady.value) loadHealth()
}

function handleFileInput(event) {
  selectFile(event.target.files?.[0])
  event.target.value = ''
}

function handleDrop(event) { selectFile(event.dataTransfer.files?.[0]) }

async function startDetection() {
  if (!selectedFile.value || running.value) return
  if (!modelReady.value) {
    await loadHealth()
    if (!modelReady.value) {
      ElMessage.warning(health.value?.model?.message || '模型服务未就绪，请点击右上角重新检查')
      return
    }
  }
  stopped.value = false
  uploadProgress.value = 0
  job.value = { status: 'uploading', progress: 0, stage: '正在上传文件' }
  try {
    job.value = await createDetection(selectedFile.value, value => { uploadProgress.value = value })
    await pollJob(job.value.id)
  } catch (error) {
    job.value = { status: 'failed', error: { message: getApiErrorMessage(error) } }
    ElMessage.error(job.value.error.message)
  }
}

async function pollJob(jobId) {
  while (!stopped.value) {
    const nextJob = await getDetection(jobId)
    job.value = nextJob
    if (nextJob.status === 'completed') {
      const summary = nextJob.result?.summary || {}
      const objects = summary.objects ?? nextJob.result?.sampled_frames ?? 0
      const violations = summary.violations ?? 0

      sessionStats.value.files += 1
      sessionStats.value.objects += objects
      sessionStats.value.violations += violations

      recentJobs.value.unshift({
        id: nextJob.id,
        fileName: selectedFile.value?.name || '未命名文件',
        time: new Date().toLocaleTimeString('zh-CN', { hour12: false }),
        objects,
        violations
      })
      recentJobs.value = recentJobs.value.slice(0, 3)

      ElMessage.success(`检测完成，共发现 ${violations} 个疑似违规事件`)
      return
    }
    if (nextJob.status === 'failed') {
      ElMessage.error(nextJob.error?.message || '检测失败')
      return
    }
    await new Promise(resolve => window.setTimeout(resolve, 800))
  }
}

async function addToReview(event) {
  // 离线/实时检测的确认事件由后端在任务完成时并入同一台账（架构稿 R3），
  // 前端不再自行造记录，只刷新把后端已落库的记录取回来。
  await violationStore.addInferenceViolation(event, selectedFile.value?.name || '上传文件')
  ElMessage.success('本次检测结果已写入台账，可在「检测历史与复核」中查看并复核')
}

function downloadJson() {
  const blob = new Blob([JSON.stringify(result.value, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = `detection_${job.value.id}.json`
  link.click()
  URL.revokeObjectURL(url)
}

function formatBytes(bytes) {
  return bytes < 1024 * 1024 ? `${(bytes / 1024).toFixed(1)} KB` : `${(bytes / 1024 / 1024).toFixed(1)} MB`
}

function formatTime(seconds) {
  const minutes = Math.floor(seconds / 60)
  return `${String(minutes).padStart(2, '0')}:${(seconds % 60).toFixed(1).padStart(4, '0')}`
}

onMounted(loadHealth)
onBeforeUnmount(() => {
  stopped.value = true
  if (previewUrl.value) URL.revokeObjectURL(previewUrl.value)
})
</script>

<style scoped>
/* ── 处理流程步骤条 ── */
.pipeline {
  margin: 0;
  padding: 0;
  list-style: none;
}

.pipeline__item {
  position: relative;
  display: flex;
  gap: 12px;
  padding-bottom: 16px;
}

.pipeline__item:last-child {
  padding-bottom: 0;
}

/* 连接线：从当前圆点底部延伸到下一个圆点 */
.pipeline__item:not(:last-child)::before {
  position: absolute;
  top: 22px;
  left: 9px;
  width: 1px;
  height: calc(100% - 22px);
  background-color: var(--c-line);
  content: '';
}

.pipeline__dot {
  position: relative;
  z-index: 1;
  display: flex;
  width: 20px;
  height: 20px;
  flex: 0 0 20px;
  align-items: center;
  justify-content: center;
  border: 1px solid var(--c-line);
  border-radius: 50%;
  background-color: var(--c-surface);
  color: var(--c-ink-3);
  font-size: 11px;
  font-variant-numeric: tabular-nums;
}

.pipeline__item.is-done .pipeline__dot {
  border-color: #15803D;
  background-color: #15803D;
  color: #FFFFFF;
}

.pipeline__item.is-active .pipeline__dot {
  border-color: var(--c-primary);
  background-color: var(--c-primary);
  color: #FFFFFF;
}

.pipeline__item.is-failed .pipeline__dot {
  border-color: #B91C1C;
  background-color: #B91C1C;
  color: #FFFFFF;
}

/* 已走完的一段连接线也转绿，整条进度一眼可读 */
.pipeline__item.is-done:not(:last-child)::before {
  background-color: #15803D;
  opacity: 0.35;
}

.pipeline__body {
  min-width: 0;
  padding-top: 1px;
}

.pipeline__label {
  color: var(--c-ink-3);
  font-size: 13px;
  font-weight: 500;
  line-height: 18px;
}

.pipeline__item.is-done .pipeline__label {
  color: var(--c-ink-2);
}

.pipeline__item.is-active .pipeline__label {
  color: var(--c-ink);
}

.pipeline__desc {
  margin-top: 1px;
  color: var(--c-ink-3);
  font-size: 12px;
  line-height: 18px;
}

.pipeline__stage {
  display: inline-block;
  margin-top: 4px;
  padding: 1px 6px;
  border-radius: 4px;
  background-color: var(--c-primary-weak);
  color: var(--c-primary);
  font-size: 12px;
  line-height: 18px;
}
</style>
