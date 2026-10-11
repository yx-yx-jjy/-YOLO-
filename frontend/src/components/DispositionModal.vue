<template>
  <div
    v-if="visible && record"
    class="fixed inset-0 z-50 flex items-center justify-center p-4"
    style="background-color: rgba(15, 23, 42, 0.45);"
    @click.self="close"
  >
    <div class="card max-w-4xl w-full p-5 space-y-4 relative" style="box-shadow: 0 4px 16px rgba(15, 23, 42, 0.08);">
      <button
        @click="close"
        class="absolute top-4 right-4 p-1 rounded-md transition"
        style="color: var(--c-ink-3);"
        title="关闭"
        @mouseenter="$event.currentTarget.style.backgroundColor = 'var(--c-page)'; $event.currentTarget.style.color = 'var(--c-ink)'"
        @mouseleave="$event.currentTarget.style.backgroundColor = ''; $event.currentTarget.style.color = 'var(--c-ink-3)'"
      >
        <el-icon :size="18"><Close /></el-icon>
      </button>

      <!-- 标题行 -->
      <div class="flex flex-wrap items-center gap-3 pr-8">
        <h3 class="text-[16px] font-medium" style="color: var(--c-ink);">违规处置工作台</h3>
        <span class="font-mono text-[12px] px-2 py-0.5 rounded" style="background-color: var(--c-page); border: 1px solid var(--c-line); color: var(--c-ink-2);">
          {{ record.id }}
        </span>
        <span class="px-2 py-0.5 rounded text-[12px] font-normal whitespace-nowrap" style="background-color: #F0FDF4; color: #15803D;">
          已确认入卷
        </span>
        <span
          class="px-2 py-0.5 rounded text-[12px] font-normal whitespace-nowrap"
          :style="{ backgroundColor: badge.bg, color: badge.color }"
        >
          {{ badge.text }}
        </span>
      </div>

      <!-- 状态步骤指示器：一眼看出这条线索走到流程的第几步 -->
      <div class="flex items-center gap-1.5 flex-wrap" style="border-top: 1px solid var(--c-line); padding-top: 12px;">
        <template v-for="(step, index) in STEPS" :key="step.key">
          <div class="flex items-center gap-1.5">
            <span
              class="w-2 h-2 rounded-full flex-shrink-0"
              :style="{ backgroundColor: index <= stepIndex ? '#15803D' : 'var(--c-line)' }"
            ></span>
            <span
              class="text-[12px]"
              :style="{ color: index <= stepIndex ? 'var(--c-ink)' : 'var(--c-ink-3)' }"
            >
              {{ step.label }}
            </span>
          </div>
          <span
            v-if="index < STEPS.length - 1"
            class="h-px w-8 flex-shrink-0"
            :style="{ backgroundColor: index < stepIndex ? '#15803D' : 'var(--c-line)' }"
          ></span>
        </template>
      </div>

      <div class="grid grid-cols-2 gap-4">
        <!-- 左：案件要点 -->
        <div class="space-y-3">
          <div class="text-[12px]" style="color: var(--c-ink-3);">案件要点</div>

          <div class="rounded-[10px] p-3 space-y-2" style="background-color: var(--c-page); border: 1px solid var(--c-line);">
            <div v-for="item in caseItems" :key="item.label" class="flex items-start justify-between gap-3">
              <span class="text-[12px] flex-shrink-0" style="color: var(--c-ink-3);">{{ item.label }}</span>
              <span
                class="text-[13px] text-right truncate"
                :style="{ color: item.color || 'var(--c-ink)', fontFamily: item.mono ? 'var(--font-mono, ui-monospace, monospace)' : 'inherit' }"
                :title="String(item.value)"
              >
                {{ item.value }}
              </span>
            </div>
          </div>

          <div class="text-[12px] leading-5" style="color: var(--c-ink-3);">
            当事人联系方式以路面核查登记为准，本系统不存储身份证号等个人敏感信息；告知与处理结果仅记录办理状态与时间。
          </div>

          <button
            @click="openEvidence"
            class="h-8 px-3 rounded-md text-[13px] font-normal flex items-center gap-1.5"
            style="background-color: var(--c-surface); border: 1px solid var(--c-line); color: #334155;"
            @mouseenter="$event.currentTarget.style.borderColor = 'var(--c-primary)'"
            @mouseleave="$event.currentTarget.style.borderColor = 'var(--c-line)'"
          >
            <el-icon :size="14"><Document /></el-icon>
            <span>查看现场证据单</span>
          </button>
        </div>

        <!-- 右：处置流程时间线 + 当前动作 -->
        <div class="space-y-3">
          <div class="text-[12px]" style="color: var(--c-ink-3);">处置流程留痕</div>

          <ol class="space-y-3">
            <li v-for="(step, index) in timeline" :key="index" class="flex gap-2.5">
              <span class="w-1.5 h-1.5 rounded-full mt-1.5 flex-shrink-0" style="background-color: #15803D;"></span>
              <div class="min-w-0">
                <div class="text-[13px] font-medium" style="color: var(--c-ink);">{{ step.title }}</div>
                <div class="text-[12px] font-mono" style="color: var(--c-ink-3);">{{ step.time }}<template v-if="step.operator"> · {{ step.operator }}</template></div>
                <div v-if="step.remark" class="text-[12px] leading-5" style="color: var(--c-ink-2);">{{ step.remark }}</div>
              </div>
            </li>
            <li v-if="timeline.length === 0" class="text-[12px]" style="color: var(--c-ink-3);">暂无处置轨迹</li>
          </ol>

          <!-- 当前环节操作区 -->
          <div class="rounded-[10px] p-3 space-y-2" style="background-color: var(--c-page); border: 1px solid var(--c-line);">
            <template v-if="status === 'to_notify'">
              <div class="flex items-center justify-between">
                <div class="text-[13px] font-medium" style="color: var(--c-ink);">第一步 · 告知当事人</div>
                <button
                  type="button"
                  @click="show12123Notice = true"
                  class="text-[12px] font-medium text-blue-600 hover:text-blue-800 hover:underline flex items-center gap-1 cursor-pointer"
                  title="以交管12123移动端App样式预览向当事人推送的电子告知单"
                >
                  <span>📱 预览12123告知单</span>
                </button>
              </div>
              <select
                v-model="notifyChannel"
                class="w-full h-8 px-2 rounded-md text-[13px] focus:outline-none"
                style="background-color: var(--c-surface); border: 1px solid var(--c-line); color: var(--c-ink-2);"
              >
                <option v-for="channel in NOTIFY_CHANNELS" :key="channel" :value="channel">{{ channel }}</option>
              </select>
              <input
                v-model="notifyRemark"
                type="text"
                placeholder="告知情况备注（选填）"
                class="w-full h-8 px-2 rounded-md text-[13px] focus:outline-none"
                style="background-color: var(--c-surface); border: 1px solid var(--c-line); color: var(--c-ink);"
              />
              <button
                @click="doNotify"
                class="w-full h-8 rounded-md text-[13px] font-normal text-white"
                style="background-color: var(--c-primary);"
              >
                确认已告知当事人
              </button>
            </template>

            <template v-else-if="status === 'notified'">
              <div class="text-[13px] font-medium" style="color: var(--c-ink);">第二步 · 作出处理</div>
              <select
                v-model="method"
                class="w-full h-8 px-2 rounded-md text-[13px] focus:outline-none"
                style="background-color: var(--c-surface); border: 1px solid var(--c-line); color: var(--c-ink-2);"
              >
                <option v-for="item in DISPOSITION_METHODS" :key="item" :value="item">{{ item }}</option>
              </select>
              <input
                v-model="disposeRemark"
                type="text"
                placeholder="处理说明（选填）"
                class="w-full h-8 px-2 rounded-md text-[13px] focus:outline-none"
                style="background-color: var(--c-surface); border: 1px solid var(--c-line); color: var(--c-ink);"
              />
              <button
                @click="doDispose"
                class="w-full h-8 rounded-md text-[13px] font-normal text-white"
                style="background-color: var(--c-primary);"
              >
                提交处理结果
              </button>
            </template>

            <template v-else-if="status === 'disposed'">
              <div class="text-[13px] font-medium" style="color: var(--c-ink);">第三步 · 结案归档</div>
              <div class="text-[12px] leading-5" style="color: var(--c-ink-2);">
                处理结果已登记：{{ record.disposition?.method || '—' }}。归档后该记录不再出现在待处置列表。
              </div>
              <button
                @click="doArchive"
                class="w-full h-8 rounded-md text-[13px] font-normal text-white"
                style="background-color: var(--c-primary);"
              >
                结案归档
              </button>
            </template>

            <template v-else>
              <div class="text-[13px] font-medium" style="color: var(--c-ink);">处置已完成</div>
              <div class="text-[12px] leading-5" style="color: var(--c-ink-2);">
                该记录已于 {{ record.disposition?.disposed_at || '—' }} 归档结案，如需修改请先在台账中撤销复核后重新走流程。
              </div>
            </template>
          </div>
        </div>
      </div>
    </div>
  </div>

  <!-- 交管12123 移动端电子告知单仿真弹窗 -->
  <!-- 执法端处置工作台的告知书预览：不出现当事人操作 -->
  <Traffic12123Notice v-model:visible="show12123Notice" :record="record" mode="officer" />
</template>

<script setup>
import { computed, onUnmounted, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import {
  useViolationStore,
  DISPOSITION_BADGES,
  DISPOSITION_METHODS
} from '../stores/violations'
import { useAuthStore } from '../stores/auth'
import { getApiErrorMessage } from '../services/http'
import { cameraName } from '../data/cameras'
import Traffic12123Notice from './Traffic12123Notice.vue'

const props = defineProps({
  visible: { type: Boolean, default: false },
  record: { type: Object, default: null }
})
const emit = defineEmits(['update:visible'])

const violationStore = useViolationStore()
const authStore = useAuthStore()

const show12123Notice = ref(false)
// 告知渠道：只列送达方式。违法行为代码（8076）属于执法文书要素，
// 混进渠道列表会让民警误以为"渠道=代码"，代码已在告知书正文与送达短信中体现。
const NOTIFY_CHANNELS = ['交管12123移动端推送', '短信告知', '电话告知', '现场告知', '邮寄送达']

/** 处置流程四步：顺序固定，当前走到第几步由 disposition.status 决定 */
const STEPS = [
  { key: 'to_notify', label: '待告知' },
  { key: 'notified', label: '已告知' },
  { key: 'disposed', label: '已处置' },
  { key: 'archived', label: '已归档' }
]

const notifyChannel = ref(NOTIFY_CHANNELS[0])
const notifyRemark = ref('')
const method = ref(DISPOSITION_METHODS[0])
const disposeRemark = ref('')

const operator = computed(() => authStore.currentUser?.real_name || '当前用户')
const status = computed(() => props.record?.disposition?.status || null)
const badge = computed(() => DISPOSITION_BADGES[status.value] || { text: '未进入处置', color: '#94A3B8', bg: '#F1F5F9' })
const stepIndex = computed(() => STEPS.findIndex(step => step.key === status.value))

function spotLabel(row) {
  const raw = row?.camera_id || ''
  const direction = raw.split('-').slice(2).join('-')
  const name = cameraName(raw)
  return direction ? `${name} · ${direction}` : name
}

// 置信度分档色值统一取自 utils/confidence.js（全站唯一事实来源）
const caseItems = computed(() => {
  const row = props.record
  if (!row) return []
  // 不再展示「判定可信度」：处置工作台的读者是复核民警，
  // 案件要点只列事实与流程信息，算法指标在台账列表与复核弹窗里看即可。
  return [
    { label: '卡口', value: spotLabel(row) },
    { label: '抓拍时间', value: row.capture_time, mono: true },
    { label: '追踪编号', value: row.track_id ? `Track #${row.track_id}` : '—', mono: true },
    { label: '违规类型', value: row.violation_type },
    { label: '目标车辆', value: row.details?.plate_or_vehicle || '—' },
    { label: '复核人', value: row.reviewer || '—' }
  ]
})

const ACTION_TITLES = {
  create: '复核确认入卷，转入处置流程',
  notify: '已告知当事人',
  dispose: '已作出处理决定',
  archive: '已结案归档'
}

const timeline = computed(() =>
  (props.record?.disposition?.history || []).map(item => ({
    title: ACTION_TITLES[item.action] || item.action,
    time: item.time || '—',
    operator: item.operator || '',
    remark: item.remark || ''
  }))
)

function close() {
  emit('update:visible', false)
}

function openEvidence() {
  if (props.record) violationStore.openEvidenceModal(props.record)
}

async function doNotify() {
  try {
    const result = await violationStore.markNotified(
      props.record.id,
      operator.value,
      `${notifyChannel.value}：${notifyRemark.value || '已告知当事人违法事实、处理依据与办理地点'}`
    )
    if (result) Object.assign(props.record, result)
    ElMessage.success('已登记告知结果，进入处理环节')
  } catch (error) {
    ElMessage.error(`告知登记失败：${getApiErrorMessage(error)}`)
  }
}

async function doDispose() {
  try {
    const result = await violationStore.markDisposed(
      props.record.id,
      operator.value,
      method.value,
      disposeRemark.value ? `${method.value}：${disposeRemark.value}` : ''
    )
    if (result) Object.assign(props.record, result)
    ElMessage.success(`已登记处理结果：${method.value}`)
  } catch (error) {
    ElMessage.error(`处理结果登记失败：${getApiErrorMessage(error)}`)
  }
}

async function doArchive() {
  try {
    const result = await violationStore.archiveDisposition(props.record.id, operator.value)
    if (result) Object.assign(props.record, result)
    ElMessage.success('已结案归档，处置闭环完成')
  } catch (error) {
    ElMessage.error(`归档失败：${getApiErrorMessage(error)}`)
  }
}

/* Esc 关闭：证据单打开时不抢 Esc，交给它自己关 */
function handleKeydown(event) {
  if (event.key !== 'Escape') return
  const tag = (event.target?.tagName || '').toLowerCase()
  if (tag === 'input' || tag === 'textarea' || tag === 'select') return
  if (violationStore.isModalOpen) return
  close()
}

watch(() => props.visible, value => {
  if (value) {
    notifyRemark.value = ''
    disposeRemark.value = ''
    method.value = props.record?.disposition?.method || DISPOSITION_METHODS[0]
    window.addEventListener('keydown', handleKeydown)
  } else {
    window.removeEventListener('keydown', handleKeydown)
  }
})

onUnmounted(() => window.removeEventListener('keydown', handleKeydown))
</script>
