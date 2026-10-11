<!-- 群众端违法记录卡：执法端台账与群众端的呈现差异集中在这里 -->
<template>
  <article class="rounded-xl overflow-hidden" style="background: #FFFFFF; box-shadow: 0 1px 3px rgba(15,23,42,0.06);">
    <!-- 状态条：一眼看出这条要不要处理 -->
    <div class="px-4 py-2.5 flex items-center justify-between gap-2" :style="{ background: statusBg }">
      <span class="text-[12px] font-medium" :style="{ color: statusFg }">{{ statusText }}</span>
      <span class="text-[11px] font-mono" style="color:#64748B;">{{ record.id }}</span>
    </div>

    <div class="p-4">
      <p class="text-[15px] font-medium" style="line-height:1.6;">{{ violationTitle }}</p>
      <p class="text-[12px] mt-1.5" style="color:#64748B; line-height:1.7;">
        {{ localTime }}<br />
        {{ spotLabel }}
      </p>

      <!-- 金额只在【文书已送达】后出现。
           注意区分两个状态：
             to_notify 待告知 → 文书还没送到当事人手上，此时亮金额等于提前告知处罚
             notified  已告知 → 已送达，当事人确实该知道罚多少
           这与「查看详情」的门控（未送达点不开告知书）保持一致。 -->
      <div
        v-if="showAmount"
        class="mt-3 px-3 py-2.5 rounded-lg flex items-center justify-between"
        style="background:#FEF2F2;"
      >
        <span class="text-[12px]" style="color:#991B1B;">拟处以罚款</span>
        <span class="text-[13px]"><span class="text-[20px] font-medium" style="color:#B91C1C;">50</span> 元</span>
      </div>

      <div class="mt-3.5 flex items-center gap-2">
        <button
          @click="$emit('detail', record)"
          :disabled="!isServed"
          class="h-9 px-3.5 rounded-lg text-[13px] disabled:opacity-50 disabled:cursor-not-allowed"
          :style="isServed
            ? 'background:#1D4ED8; color:#FFFFFF;'
            : 'background:#F1F5F9; color:#94A3B8; border:1px solid #E2E8F0;'"
        >
          {{ isServed ? '查看详情' : '待送达' }}
        </button>
        <button
          v-if="isServed"
          @click="$emit('appeal', record)"
          class="h-9 px-3.5 rounded-lg text-[13px]"
          style="background:#FFFFFF; border:1px solid #CBD5E1; color:#334155;"
        >
          我要申诉
        </button>
      </div>
    </div>
  </article>
</template>

<script setup>
import { computed } from 'vue'
import { cameraName } from '../data/cameras'

const props = defineProps({
  record: { type: Object, required: true }
})
defineEmits(['detail', 'appeal'])

/** 已送达 = 处置流程走到「已告知」及以后。未送达时当事人看不到文书内容。 */
const isServed = computed(() => {
  const s = props.record.disposition?.status
  return s === 'notified' || s === 'disposed' || s === 'archived'
})

/** 只有已送达的才亮金额——文书没送到就先报罚款，属于提前告知处罚 */
const showAmount = computed(() => props.record.disposition?.status === 'notified')

/**
 * 状态文案用群众语言，不用内部术语。
 * 对照：archived/disposed → 「已处理完毕」而不是「已归档/已处置」；
 *       notified → 「待处理罚款」；to_notify → 「待交警送达」（文书还没到手，不能说"待缴款"）。
 */
const statusText = computed(() => {
  const s = props.record.disposition?.status
  if (s === 'archived' || s === 'disposed') return '已处理完毕'
  if (s === 'notified') return '待处理罚款'
  if (s === 'to_notify') return '待交警送达'
  return '待交警处理'
})

const statusBg = computed(() => {
  const t = statusText.value
  if (t === '已处理完毕') return '#F0FDF4'
  if (t === '待处理罚款') return '#FEF2F2'
  return '#FFFBEB'
})

const statusFg = computed(() => {
  const t = statusText.value
  if (t === '已处理完毕') return '#15803D'
  if (t === '待处理罚款') return '#B91C1C'
  return '#B45309'
})

const localTime = computed(() => {
  const raw = props.record.capture_time
  if (!raw) return '时间未记录'
  return String(raw).replace('T', ' ').slice(0, 16)
})

const spotLabel = computed(() => {
  const raw = props.record.camera_id || ''
  const direction = props.record.direction
    || raw.match(/[（(]([^（）()]+)[）)]\s*$/)?.[1]
    || raw.split('-').slice(2).join('-')
  const name = cameraName(raw)
  return direction ? `${name} ${direction}` : name
})

const violationTitle = computed(() => {
  const category = props.record.category || 'helmet'
  if (category === 'passenger') return '乘坐人未佩戴安全头盔'
  if (category === 'both') return '驾驶人与乘坐人均未佩戴安全头盔'
  return '驾驶非机动车未佩戴安全头盔'
})
</script>