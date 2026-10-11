<template>
  <div v-if="violationStore.isModalOpen && record" class="fixed inset-0 z-50 flex items-center justify-center p-4" style="background-color: rgba(15, 23, 42, 0.45);">
    <div class="card max-w-4xl w-full p-5 space-y-4 relative" style="box-shadow: 0 4px 16px rgba(15, 23, 42, 0.08);">
      
      <!-- 关闭按钮 -->
      <button 
        @click="violationStore.closeEvidenceModal" 
        class="absolute top-4 right-4 p-1 rounded-md transition"
        style="color: var(--c-ink-3);"
        @mouseenter="$event.currentTarget.style.backgroundColor = 'var(--c-page)'; $event.currentTarget.style.color = 'var(--c-ink)'"
        @mouseleave="$event.currentTarget.style.backgroundColor = ''; $event.currentTarget.style.color = 'var(--c-ink-3)'"
      >
        <el-icon :size="18"><Close /></el-icon>
      </button>

      <!-- 弹窗标题与状态 -->
      <div class="flex items-center gap-3 pr-8">
        <h3 class="text-[16px] font-medium" style="color: var(--c-ink);">非机动车违规取证证据单</h3>
        <span class="font-mono text-[12px] px-2 py-0.5 rounded" style="background-color: var(--c-page); border: 1px solid var(--c-line); color: var(--c-ink-2);">
          {{ record.id }}
        </span>
        
        <!-- 审核状态标签 (规范 §6.3) -->
        <span 
          v-if="record.status === 'pending'" 
          class="px-2 py-0.5 rounded text-[12px] font-normal whitespace-nowrap" 
          style="background-color: #FFFBEB; color: #B45309;"
        >
          待人工复核
        </span>
        <span 
          v-else-if="record.status === 'approved'" 
          class="px-2 py-0.5 rounded text-[12px] font-normal whitespace-nowrap" 
          style="background-color: #F0FDF4; color: #15803D;"
        >
          已确认入卷
        </span>
        <span
          v-else
          class="px-2 py-0.5 rounded text-[12px] font-normal whitespace-nowrap"
          style="background-color: #F1F5F9; color: #475569;"
        >
          误报已剔除
        </span>
      </div>

      <!-- 告知书入口已移除：本弹窗对「待人工复核」记录同样可打开，
           在这里挂告知书按钮必然点出"尚未复核不能生成告知书"的拦截块。
           告知书统一从「台账 → 更多 → 告知书」与「处置工作台 → 处置单」进入，
           两条路径都已按 status 做门控。 -->

      <!-- 双视窗对比证据栏 -->
      <div class="grid grid-cols-2 gap-4">
        <!-- 视窗 1：现场全景抓拍 -->
        <div class="space-y-1.5">
          <div class="text-[12px] flex justify-between items-center font-mono" style="color: var(--c-ink-3);">
            <div class="flex items-center gap-2">
              <span>现场全景高清图 (Wide Shot)</span>
              <button
                v-if="record.evidence_url && imageState === 'loaded'"
                type="button"
                @click="openImageViewer('evidence')"
                class="cursor-pointer text-[11px] px-1.5 py-0.2 rounded transition inline-flex items-center gap-1 font-sans"
                style="background-color: var(--c-page); border: 1px solid var(--c-line); color: var(--c-primary);"
                title="点击全屏查看原图，支持滚轮缩放与拖拽"
              >
                <el-icon :size="12"><ZoomIn /></el-icon>
                <span>双击放大</span>
              </button>
            </div>
            <span>{{ evidenceMeta }}</span>
          </div>
          <div
            class="h-56 rounded-[10px] relative flex items-center justify-center overflow-hidden group select-none"
            :class="record.evidence_url && imageState === 'loaded' ? 'cursor-zoom-in' : ''"
            style="background-color: var(--c-page); border: 1px solid var(--c-line);"
            @dblclick="openImageViewer('evidence')"
            @click="openImageViewer('evidence')"
            :title="record.evidence_url && imageState === 'loaded' ? '双击或点击放大现场高清全景图（支持滚轮缩放与拖拽）' : ''"
          >
            <img
              v-if="record.evidence_url"
              :src="record.evidence_url"
              class="w-full h-full object-contain select-none transition-opacity duration-150"
              :class="imageState === 'loaded' ? 'opacity-100' : 'opacity-0'"
              alt="现场全景抓拍"
              @load="onEvidenceLoad"
              @error="onEvidenceError"
            />

            <!-- 读取中：图未就绪时也要说清是在加载，而不是留一块空白 -->
            <div
              v-if="record.evidence_url && imageState === 'loading'"
              class="absolute inset-0 flex flex-col items-center justify-center gap-2"
            >
              <el-icon :size="22" class="is-loading" style="color: var(--c-ink-3);"><Loading /></el-icon>
              <span class="text-[12px]" style="color: var(--c-ink-3);">正在读取现场抓拍图...</span>
            </div>

            <!-- 读取失败 -->
            <div
              v-else-if="record.evidence_url && imageState === 'error'"
              class="absolute inset-0 flex flex-col items-center justify-center gap-1.5 px-8 text-center"
            >
              <el-icon :size="22" style="color: #B91C1C;"><Warning /></el-icon>
              <span class="text-[13px]" style="color: var(--c-ink-2);">现场抓拍图读取失败</span>
              <span class="text-[12px] leading-5" style="color: var(--c-ink-3);">存证文件可能已被清理，请以检测结论与坐标明细为准</span>
            </div>

            <!-- 该记录本身没有配图 -->
            <div
              v-else-if="!record.evidence_url"
              class="absolute inset-0 flex flex-col items-center justify-center gap-1.5 px-8 text-center"
            >
              <el-icon :size="22" style="color: var(--c-ink-3);"><Document /></el-icon>
              <span class="text-[13px]" style="color: var(--c-ink-2);">该记录未附带现场抓拍图</span>
              <span class="text-[12px] leading-5" style="color: var(--c-ink-3);">仅保留检测结论，请结合现场核查后判定</span>
            </div>

            <!-- 防伪水印：只在图确实读出来之后才挂 -->
            <div
              v-if="imageState === 'loaded'"
              class="absolute bottom-2 left-2 text-[11px] font-mono px-2 py-0.5 rounded shadow pointer-events-none"
              style="background-color: rgba(15, 23, 42, 0.85); color: #94A3B8; border: 1px solid var(--c-line);"
            >
              现场抓拍存证 · 时间戳已上链
            </div>

            <!-- 悬停放大提示胶囊（右上方） -->
            <div
              v-if="imageState === 'loaded'"
              class="absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity duration-150 pointer-events-none flex items-center gap-1 text-[11px] px-2 py-0.5 rounded shadow"
              style="background-color: rgba(15, 23, 42, 0.88); color: #F8FAFC; border: 1px solid rgba(255, 255, 255, 0.25);"
            >
              <el-icon :size="12"><ZoomIn /></el-icon>
              <span>双击或点击放大原图</span>
            </div>

            <!-- 低置信度：直接提醒复核人这张图要仔细看 -->
            <div
              v-if="imageState === 'loaded' && isLowConfidence"
              class="absolute top-2 left-2 text-[11px] px-2 py-0.5 rounded pointer-events-none"
              style="background-color: #FFFBEB; color: #B45309; border: 1px solid #B45309;"
            >
              置信度偏低，请重点核对
            </div>
          </div>
        </div>

        <!-- 视窗 2：局部特征放大切片 -->
        <div class="space-y-1.5">
          <div class="text-[12px] flex justify-between items-center font-mono" style="color: var(--c-ink-3);">
            <div class="flex items-center gap-2">
              <span>局部特征切片 (ROI Cropped)</span>
              <button
                v-if="record.roi_url"
                type="button"
                @click="openImageViewer('roi')"
                class="cursor-pointer text-[11px] px-1.5 py-0.2 rounded transition inline-flex items-center gap-1 font-sans"
                style="background-color: var(--c-page); border: 1px solid var(--c-line); color: var(--c-primary);"
                title="点击放大切片"
              >
                <el-icon :size="12"><ZoomIn /></el-icon>
                <span>双击放大</span>
              </button>
            </div>
            <span>空间拓扑关联判定</span>
          </div>
          <div class="h-56 rounded-[10px] overflow-hidden flex flex-col" style="background-color: var(--c-page); border: 1px solid var(--c-line);">
            <div
              class="h-36 min-h-0 relative flex items-center justify-center group select-none"
              :class="record.roi_url ? 'cursor-zoom-in' : ''"
              style="background-color: #0F172A;"
              @dblclick="openImageViewer('roi')"
              @click="openImageViewer('roi')"
              :title="record.roi_url ? '双击或点击放大局部切片（支持滚轮缩放与拖拽）' : ''"
            >
              <img
                v-if="record.roi_url"
                :src="record.roi_url"
                class="w-full h-full object-contain select-none"
                alt="违规目标局部放大图"
              />
              <div v-else class="text-[12px]" style="color: #94A3B8;">该记录未保存局部目标图</div>
              <span
                v-if="record.roi_url"
                class="absolute top-2 left-2 px-2 py-0.5 rounded text-[11px] font-medium pointer-events-none"
                style="background-color: rgba(185, 28, 28, 0.9); color: white;"
              >
                违规目标局部
              </span>

              <!-- 悬停放大提示胶囊（右上方） -->
              <div
                v-if="record.roi_url"
                class="absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity duration-150 pointer-events-none flex items-center gap-1 text-[11px] px-2 py-0.5 rounded shadow"
                style="background-color: rgba(15, 23, 42, 0.88); color: #F8FAFC; border: 1px solid rgba(255, 255, 255, 0.25);"
              >
                <el-icon :size="12"><ZoomIn /></el-icon>
                <span>双击放大切片</span>
              </div>
            </div>

            <div class="grid grid-cols-1 flex-1 min-h-0" style="border-top: 1px solid var(--c-line);">
              <!-- 头盔/裸头。字段缺失时如实显示"未记录"，不替数据下结论 -->
              <label
                class="flex items-center gap-1.5 px-2 min-w-0 transition-colors"
                :class="{ 'cursor-pointer': canEditTypes }"
                :style="{
                  backgroundColor: canEditTypes && typeChecked.helmet ? 'var(--c-surface)' : 'transparent'
                }"
              >
                <input
                  v-if="canEditTypes"
                  type="checkbox"
                  class="w-3.5 h-3.5 shrink-0 cursor-pointer"
                  style="accent-color: var(--c-primary);"
                  :checked="typeChecked.helmet"
                  :aria-label="`认定未按规定佩戴安全头盔`"
                  @change="toggleType('helmet')"
                />
                <span
                  class="px-2 py-1 rounded text-[11px] font-medium whitespace-nowrap"
                  :style="!helmetFact.known || isManualRemoved('helmet')
                    ? 'background-color: var(--c-page); color: var(--c-ink-3); border: 1px solid var(--c-line);'
                    : typeChecked.helmet
                      ? 'background-color: #FEF2F2; color: #B91C1C; border: 1px solid #B91C1C;'
                      : 'background-color: #F0FDF4; color: #15803D; border: 1px solid #15803D;'"
                >
                  {{ helmetFact.title }}
                </span>
                <div class="min-w-0">
                  <div class="text-[11px] font-medium" style="color: var(--c-ink);">
                    头部护具状态<span v-if="isManualAdded('helmet')" style="color: #B45309;"> · 人工补充</span><span v-else-if="isManualRemoved('helmet')" style="color: #64748B;"> · 已取消</span>
                  </div>
                  <div class="text-[10px] truncate" :title="helmetFact.detail" style="color: var(--c-ink-3);">{{ helmetFact.detail }}</div>
                </div>
              </label>

            </div>
          </div>
        </div>
      </div>

      <!-- 属性信息明细栏 -->
      <div class="p-3.5 rounded-md grid grid-cols-3 gap-3 text-[13px]" style="background-color: var(--c-page); border: 1px solid var(--c-line);">
        <div>
          <span style="color: var(--c-ink-3);">违规类型:</span>
          <span class="ml-1.5 font-medium" style="color: var(--c-ink);">{{ record.violation_type }}</span>
        </div>
        <div>
          <span style="color: var(--c-ink-3);">捕获时间:</span>
          <span class="ml-1.5 font-mono" style="color: var(--c-ink-2);">{{ record.capture_time }}</span>
        </div>
        <div>
          <span style="color: var(--c-ink-3);">判定可信度:</span>
          <span class="ml-1.5 font-mono font-medium" :style="{ color: confidenceTone }">{{ (record.confidence * 100).toFixed(1) }}%</span>
        </div>
        <div>
          <span style="color: var(--c-ink-3);">卡口:</span>
          <span class="ml-1.5 font-normal" style="color: var(--c-ink-2);">{{ record.camera_id }}</span>
        </div>
        <div>
          <span style="color: var(--c-ink-3);">车辆特征:</span>
          <span class="ml-1.5 font-normal" style="color: var(--c-ink-2);">{{ record.details.plate_or_vehicle }}</span>
        </div>
        <div>
          <span style="color: var(--c-ink-3);">连续跟踪:</span>
          <span class="ml-1.5 font-mono" style="color: var(--c-ink-2);">{{ record.details.consecutive_frames }} 帧持续确认</span>
        </div>
      </div>

      <!-- 人工复核操作区 (执法人员) -->
      <div v-if="record.status === 'pending'" class="p-3.5 rounded-md space-y-2" style="background-color: var(--c-primary-weak); border: 1px solid var(--c-line);">
        <div class="flex items-center justify-between">
          <span class="text-[13px] font-medium flex items-center gap-1.5" style="color: var(--c-primary);">
            <el-icon :size="14"><Edit /></el-icon>
            <span>人工复核审核通道</span>
          </span>
          <span class="text-[12px]" style="color: var(--c-ink-3);">复核人: {{ authStore.currentUser.real_name }}</span>
        </div>
        <div class="flex gap-2">
          <input 
            v-model="reviewComment" 
            type="text" 
            placeholder="填写复核备注（选填，例如：经核查违规属实）..." 
            class="flex-1 h-8 px-3 rounded-md text-[13px] focus:outline-none"
            style="background-color: var(--c-surface); border: 1px solid var(--c-line); color: var(--c-ink);"
          />
          <button 
            @click="handleApprove" 
            class="h-8 px-3.5 rounded-md text-[13px] font-normal text-white transition whitespace-nowrap"
            style="background-color: var(--c-primary);"
            @mouseenter="$event.currentTarget.style.backgroundColor = '#4338CA'"
            @mouseleave="$event.currentTarget.style.backgroundColor = 'var(--c-primary)'"
          >
            确认违规入卷
          </button>
          <button 
            @click="handleReject" 
            class="h-8 px-3 rounded-md text-[13px] font-normal transition whitespace-nowrap"
            style="background-color: var(--c-surface); border: 1px solid var(--c-line); color: #B91C1C;"
            @mouseenter="$event.currentTarget.style.backgroundColor = '#FEF2F2'"
            @mouseleave="$event.currentTarget.style.backgroundColor = 'var(--c-surface)'"
          >
            误报剔除
          </button>
        </div>
      </div>

      <!-- 复核轨迹：只要有历史就显示，撤销退回后也能看到"曾被判过又撤回" -->
      <div v-if="reviewTrail.length > 0" class="p-3.5 rounded-md space-y-2.5" style="background-color: var(--c-page); border: 1px solid var(--c-line);">
        <div class="flex items-center justify-between">
          <span class="text-[13px] font-medium" style="color: var(--c-ink);">复核轨迹</span>
          <span class="text-[12px]" style="color: var(--c-ink-3);">共 {{ reviewTrail.length }} 条 · 只增不改</span>
        </div>

        <ol class="review-trail">
          <li
            v-for="(entry, index) in reviewTrail"
            :key="index"
            class="review-trail__item"
            :class="`is-${entry.action}`"
          >
            <span class="review-trail__dot"></span>
            <div class="min-w-0 flex-1">
              <div class="flex flex-wrap items-center gap-x-2 gap-y-0.5">
                <span class="text-[12px] font-mono" style="color: var(--c-ink-3);">{{ entry.time }}</span>
                <span class="text-[12px]" style="color: var(--c-ink-2);">{{ displayReviewer(entry) }}</span>
                <span class="text-[12px] font-medium" :style="{ color: actionTone(entry.action) }">{{ actionLabel(entry.action) }}</span>
              </div>
              <div v-if="entry.remark" class="text-[12px] leading-5 mt-0.5" style="color: var(--c-ink-2);">
                {{ entry.remark }}
              </div>
            </div>
          </li>
          <li v-if="reviewTrail.length === 0" class="text-[12px]" style="color: var(--c-ink-3);">
            暂无复核记录
          </li>
        </ol>
      </div>

      <!-- 撤销复核：判定有误时的出口，撤销理由会追加到上方轨迹 -->
      <div v-if="record.status !== 'pending'" class="p-3.5 rounded-md space-y-2.5" style="background-color: var(--c-surface); border: 1px solid var(--c-line);">
        <div class="flex items-center justify-between gap-3">
          <span class="text-[12px] leading-5" style="color: var(--c-ink-3);">
            判定有误？撤销后该记录退回「待人工复核」，撤销理由会记入轨迹。
          </span>
          <button
            v-if="!revoking"
            @click="startRevoke"
            class="h-8 px-3 rounded-md text-[13px] font-normal whitespace-nowrap flex-shrink-0"
            style="background-color: var(--c-surface); border: 1px solid var(--c-line); color: #B45309;"
          >
            撤销复核
          </button>
        </div>

        <div v-if="revoking" class="space-y-2">
          <textarea
            v-model="revokeReason"
            rows="2"
            placeholder="请填写撤销理由（必填，将记入复核轨迹）"
            class="w-full px-3 py-2 rounded-md text-[13px] resize-none focus:outline-none"
            style="background-color: var(--c-surface); border: 1px solid var(--c-line); color: var(--c-ink);"
          ></textarea>
          <div class="flex justify-end gap-2">
            <button
              @click="cancelRevoke"
              class="h-8 px-3 rounded-md text-[13px] font-normal"
              style="background-color: var(--c-surface); border: 1px solid var(--c-line); color: #334155;"
            >
              取消
            </button>
            <button
              @click="handleRevoke"
              :disabled="!revokeReason.trim()"
              class="h-8 px-3.5 rounded-md text-[13px] font-normal text-white disabled:opacity-40 disabled:cursor-not-allowed"
              style="background-color: #B45309;"
            >
              确认撤销
            </button>
          </div>
        </div>
      </div>

      <!-- 底部控制栏 -->
      <div class="flex justify-between items-center text-[12px] pt-1">
        <span style="color: var(--c-ink-3);">按 ESC 键或右上角按钮关闭</span>
        <div class="flex gap-2">
          <button 
            @click="violationStore.closeEvidenceModal" 
            class="h-8 px-3 rounded-md text-[13px] font-normal transition"
            style="background-color: var(--c-surface); border: 1px solid var(--c-line); color: #334155;"
            @mouseenter="$event.currentTarget.style.borderColor = 'var(--c-primary)'; $event.currentTarget.style.color = 'var(--c-primary)'"
            @mouseleave="$event.currentTarget.style.borderColor = 'var(--c-line)'; $event.currentTarget.style.color = '#334155'"
          >
            返回
          </button>
          <button 
            @click="exportSingleReport" 
            class="h-8 px-3 rounded-md text-[13px] font-normal flex items-center gap-1.5 transition"
            style="background-color: var(--c-surface); border: 1px solid var(--c-line); color: #334155;"
            title="电子文书生成尚未接入，点击可查看当前可用的导出台账方式"
            @mouseenter="$event.currentTarget.style.borderColor = 'var(--c-primary)'; $event.currentTarget.style.color = 'var(--c-primary)'"
            @mouseleave="$event.currentTarget.style.borderColor = 'var(--c-line)'; $event.currentTarget.style.color = '#334155'"
          >
            <el-icon :size="14"><Document /></el-icon>
            <span>导出证据文书 (PDF)</span>
          </button>
        </div>
      </div>

    </div>
  </div>

  <!-- 高清证据大图全屏查看器（支持滚轮自由缩放、拖拽平移、旋转、双击还原） -->
  <el-image-viewer
    v-if="isViewerOpen"
    :url-list="viewerUrlList"
    :initial-index="viewerActiveIndex"
    :hide-on-click-modal="true"
    :teleported="true"
    @close="closeImageViewer"
  />
</template>

<script setup>
import { ref, computed, watch, onUnmounted } from 'vue'
import { useViolationStore } from '../stores/violations'
import { useAuthStore } from '../stores/auth'
import { getApiErrorMessage } from '../services/http'
import { ElMessage, ElMessageBox } from 'element-plus'

const violationStore = useViolationStore()
const authStore = useAuthStore()
const reviewComment = ref('')

const record = computed(() => violationStore.selectedRecord)

/* ── 图片高清查看器（双击 / 点击全屏无损放大、滚轮缩放、拖拽平移） ──── */
const isViewerOpen = ref(false)
const viewerActiveIndex = ref(0)

const viewerUrlList = computed(() => {
  const list = []
  if (record.value?.evidence_url) list.push(record.value.evidence_url)
  if (record.value?.roi_url) list.push(record.value.roi_url)
  return list
})

function openImageViewer(type = 'evidence') {
  if (!viewerUrlList.value.length) return
  if (type === 'roi' && record.value?.roi_url) {
    viewerActiveIndex.value = record.value?.evidence_url ? 1 : 0
  } else {
    viewerActiveIndex.value = 0
  }
  isViewerOpen.value = true
}

function closeImageViewer() {
  isViewerOpen.value = false
}

/* 违规类型确认：系统当前只识别未佩戴安全头盔。 */
const typeChecked = ref({ helmet: false })

// 引擎的原始判定，用来对比人工是否改动过
const engineChecked = computed(() => {
  return { helmet: record.value?.category === 'helmet' }
})

// 只有待复核的记录才能改；已判定的要先撤销复核
const canEditTypes = computed(() => record.value?.status === 'pending')

const selectedCategory = computed(() => {
  return typeChecked.value.helmet ? 'helmet' : null
})

function toggleType(key) {
  if (!canEditTypes.value) return
  typeChecked.value[key] = !typeChecked.value[key]
}

function isManualAdded(key) {
  return typeChecked.value[key] && !engineChecked.value[key]
}

function isManualRemoved(key) {
  return !typeChecked.value[key] && engineChecked.value[key]
}

/* ── 复核轨迹与撤销复核 ──────────────────────────────────
   已判定的记录不再"锁死"：可以撤销重判，但每次改动都往轨迹里追加一条，
   原判定不会被抹掉 —— 执法留痕的意义就在这里。 */
const reviewTrail = computed(() => record.value?.review_history || [])

/**
 * 头部护具状态。
 *
 * 新记录使用 helmet_status；兼容旧演示记录中的 driver_helmet 字段。
 */
const helmetFact = computed(() => {
  const details = record.value?.details || {}
  if (details.helmet_status === 'not_wearing') {
    return { known: true, violated: true, title: '未戴头盔', detail: '骑行人员未佩戴安全头盔' }
  }
  if (details.helmet_status === 'wearing') {
    return { known: true, violated: false, title: '正常佩戴', detail: '骑行人员已佩戴安全头盔' }
  }
  if (typeof details.driver_helmet !== 'boolean') {
    return { known: false, violated: false, title: '未记录', detail: '该来源未保留头盔判定字段' }
  }
  const violated = details.driver_helmet === false
  return {
    known: true,
    violated,
    title: violated ? '未戴头盔' : '正常佩戴',
    detail: violated ? '骑行人员未佩戴安全头盔' : '骑行人员已佩戴安全头盔'
  }
})

const ACTION_LABELS = {
  approve: '确认违规入卷',
  reject: '误报剔除',
  revoke: '撤销复核'
}

const ACTION_TONES = {
  approve: '#15803D',
  reject: '#475569',
  revoke: '#B45309'
}

function actionLabel(action) {
  return ACTION_LABELS[action] || action
}

function actionTone(action) {
  return ACTION_TONES[action] || 'var(--c-ink-2)'
}

// real_name 本身可能自带"(警官)"后缀，直接拼警号会变成"张建国 (警官) (08412)"
function displayReviewer(entry) {
  const name = entry.reviewer || ''
  if (!entry.badge) return name
  const cleaned = name.replace(/\s*[（(][^）)]*[）)]\s*$/, '').trim()
  return `${cleaned || name} (${entry.badge})`
}

const revoking = ref(false)
const revokeReason = ref('')

function startRevoke() {
  revoking.value = true
  revokeReason.value = ''
}

function cancelRevoke() {
  revoking.value = false
  revokeReason.value = ''
}

async function handleRevoke() {
  if (!record.value) return
  const reason = revokeReason.value.trim()
  if (!reason) return
  try {
    await violationStore.revokeReview(
      record.value.id,
      authStore.currentUser.real_name,
      reason,
      authStore.currentUser.badge_number
    )
    ElMessage.success(`已撤销 ${record.value.id} 的复核判定，该记录已退回待人工复核`)
    cancelRevoke()
  } catch (error) {
    ElMessage.error(`撤销复核失败：${getApiErrorMessage(error)}`)
  }
}

// 换一条记录：收起撤销表单、清掉备注，并把违规类型勾选重置为引擎判定
watch(() => record.value?.id, () => {
  revoking.value = false
  revokeReason.value = ''
  reviewComment.value = ''
  typeChecked.value = { ...engineChecked.value }
}, { immediate: true })

/* ── 证据图加载状态 ──────────────────────────────────────
   这里原先只有一个深色底容器：图在加载中、加载失败、以及这条记录
   压根没有配图，三种情况的观感完全一样，都是一块黑，看不出区别。 */
const imageState = ref('loading')
const evidenceSize = ref('')

const evidenceMeta = computed(() => {
  const camId = (record.value?.camera_id || '').split(':')[0].trim()
  return [evidenceSize.value || '待读取', camId].filter(Boolean).join(' · ')
})

// 置信度分档与台账列表保持一致 —— 色值统一取自 utils/confidence.js（唯一事实来源）
import { confidenceColor } from '../utils/confidence'
const confidenceTone = computed(() => confidenceColor(record.value?.confidence))

// 置信度不足一半，说明判定把握本身就不大，要提醒复核人重点核对
const isLowConfidence = computed(() => (record.value?.confidence ?? 1) < 0.5)

watch(
  () => record.value?.evidence_url,
  url => {
    evidenceSize.value = ''
    imageState.value = url ? 'loading' : 'empty'
  },
  { immediate: true }
)

function onEvidenceLoad(event) {
  const img = event.target
  evidenceSize.value = `${img.naturalWidth}×${img.naturalHeight}`
  imageState.value = 'loaded'
}

function onEvidenceError() {
  imageState.value = 'error'
}

async function handleApprove() {
  if (!record.value) return
  if (!selectedCategory.value) {
    ElMessage.warning('请至少勾选一项违规类型；若确认无违规，请点「误报剔除」')
    return
  }
  try {
    await violationStore.approveRecord(
      record.value.id,
      authStore.currentUser.real_name,
      reviewComment.value,
      authStore.currentUser.badge_number,
      selectedCategory.value
    )
    ElMessage.success(`已成功复核违规单 ${record.value.id}，已正式入卷存证！`)
    reviewComment.value = ''
  } catch (error) {
    ElMessage.error(`复核入卷失败：${getApiErrorMessage(error)}`)
  }
}

async function handleReject() {
  if (!record.value) return
  try {
    await ElMessageBox.confirm(
      `确定把 ${record.value.id} 判定为「误报已剔除」？\n该判定会写进复核轨迹，当事人如有异议可据此追溯。`,
      '剔除误报',
      { type: 'warning', confirmButtonText: '确认剔除', cancelButtonText: '取消' }
    )
  } catch {
    return
  }
  try {
    await violationStore.rejectRecord(
      record.value.id,
      authStore.currentUser.real_name,
      reviewComment.value,
      authStore.currentUser.badge_number
    )
    ElMessage.info(`已剔除记录 ${record.value.id}，标记为误报。`)
    reviewComment.value = ''
  } catch (error) {
    ElMessage.error(`剔除误报失败：${getApiErrorMessage(error)}`)
  }
}

/**
 * 电子文书 PDF 导出尚未接入。
 * 这里原先偷懒复用了 12123 告知书弹窗 —— 按钮写着「导出 PDF」却弹出手机仿真界面，
 * 属于假功能。告知书另有正���入口（台账「更多」、处置工作台），此处如实告知现状。
 */
function exportSingleReport() {
  ElMessage.info('电子文书 PDF 导出尚未接入。可在台账页用「导出台账 CSV」下载记录，或在处置工作台查看告知书预览。')
}

/* 按 ESC 关闭：优先退出大图查看器，再次按 ESC 才关闭证据单 */
function handleKeydown(event) {
  if (event.key !== 'Escape') return
  if (isViewerOpen.value) {
    event.preventDefault()
    isViewerOpen.value = false
    return
  }
  // 正在填写复核意见或撤销理由时不抢 ESC，避免误关弹窗丢内容
  const tag = (event.target?.tagName || '').toLowerCase()
  if (tag === 'textarea' || tag === 'input') return
  if (!violationStore.isModalOpen) return
  event.preventDefault()
  violationStore.closeEvidenceModal()
}

watch(
  () => violationStore.isModalOpen,
  open => {
    if (open) window.addEventListener('keydown', handleKeydown)
    else window.removeEventListener('keydown', handleKeydown)
  }
)

onUnmounted(() => window.removeEventListener('keydown', handleKeydown))
</script>

<style scoped>
.review-trail {
  margin: 0;
  padding: 0;
  list-style: none;
}

.review-trail__item {
  position: relative;
  display: flex;
  gap: 10px;
  padding-bottom: 10px;
}

.review-trail__item:last-child {
  padding-bottom: 0;
}

/* 连接线：从当前圆点连到下一条 */
.review-trail__item:not(:last-child)::before {
  position: absolute;
  top: 14px;
  left: 4px;
  width: 1px;
  height: calc(100% - 14px);
  background-color: var(--c-line);
  content: '';
}

.review-trail__dot {
  position: relative;
  z-index: 1;
  width: 9px;
  height: 9px;
  flex: 0 0 9px;
  margin-top: 4px;
  border-radius: 50%;
  background-color: var(--c-ink-3);
}

.review-trail__item.is-approve .review-trail__dot {
  background-color: #15803D;
}

.review-trail__item.is-reject .review-trail__dot {
  background-color: #475569;
}

.review-trail__item.is-revoke .review-trail__dot {
  background-color: #B45309;
}
</style>
