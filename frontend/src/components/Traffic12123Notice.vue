<template>
  <div
    v-if="visible && currentRecord"
    class="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-4 overflow-y-auto"
    style="background-color: rgba(15, 23, 42, 0.65);"
    @click.self="close"
  >
    <div
      class="relative w-full max-w-lg flex flex-col my-auto"
      style="background: var(--c-surface, #0F172A); border-radius: var(--border-radius-xl, 16px); border: 0.5px solid rgba(255,255,255,0.14); overflow: hidden; max-height: 94vh;"
    >
      <!-- 顶部工具条：不属于文书本体，打印时隐藏。
           内容随视角变化 —— 民警要"下发/归档"，市民只要"留存"。 -->
      <div class="no-print px-4 py-3 flex items-center justify-between gap-3" style="border-bottom: 0.5px solid rgba(255,255,255,0.1); background: rgba(2,6,23,0.5);">
        <div class="flex items-center gap-2 min-w-0">
          <div class="w-6 h-6 rounded-md text-white flex items-center justify-center text-[11px] flex-shrink-0" style="background: var(--c-primary, #1D4ED8);">12123</div>
          <div class="min-w-0">
            <div class="text-[13px] font-medium truncate" style="color: #F1F5F9;">
              行政处罚告知书<span v-if="isOfficerView && !isServed"> · 未送达预览</span>
            </div>
            <div class="text-[11px] truncate" style="color: #94A3B8; font-family: var(--font-mono, monospace);">
              文书编号 {{ documentNo }}
            </div>
          </div>
        </div>

        <div class="flex items-center gap-1.5 flex-shrink-0">
          <!-- 告知短信是执法侧动作：民警生成后下发给当事人。市民端不应该出现。 -->
          <button
            v-if="isOfficerView"
            @click="copySmsText"
            class="h-7 px-2.5 rounded text-[11px] flex items-center gap-1 transition disabled:opacity-50 disabled:cursor-not-allowed"
            style="color: #CBD5E1; background: rgba(255,255,255,0.06); border: 0.5px solid rgba(255,255,255,0.14);"
            :disabled="!canSend"
            :title="canSend ? '生成下发给当事人的告知短信正文' : '文书送达后才可下发告知短信'"
          >
            <el-icon :size="12"><DocumentCopy /></el-icon>
            <span>告知短信</span>
          </button>
          <button
            @click="printNotice"
            class="h-7 px-2.5 rounded text-[11px] text-white flex items-center gap-1 transition"
            style="background: var(--c-primary, #1D4ED8);"
            :title="isOfficerView ? '打印或导出为正式纸质文书' : '保存或打印本文书'"
          >
            <el-icon :size="12"><Printer /></el-icon>
            <span>{{ isOfficerView ? '打印/导出' : '保存/打印' }}</span>
          </button>
          <button
            @click="close"
            class="w-7 h-7 rounded-lg flex items-center justify-center transition"
            style="color: #94A3B8; background: transparent; border: 0.5px solid rgba(255,255,255,0.12);"
            aria-label="关闭"
          >
            <el-icon :size="16"><Close /></el-icon>
          </button>
        </div>
      </div>

      <!-- 文书区：滚动发生在手机壳【内部】。
         手机壳原本是 overflow-hidden（为圆角裁角），内容超出就被裁掉且外层量不出来
         （外层 scrollHeight 恒等于 clientHeight，是假象）。
         正确做法：壳自身 overflow-y-auto + min-h-0，外层文档区不再承担滚动。 -->
      <div class="p-3 sm:p-5 flex justify-center flex-1 min-h-0" style="background: #F8FAFC;">
        <div
          id="notice-shell"
          class="w-full max-w-[390px] bg-white shadow-lg flex flex-col min-h-0"
          style="border-radius: 24px; border: 0.5px solid #E2E8F0; color: #0F172A; overflow-y: auto;"
        >

          <!-- 状态栏 -->
          <div class="pt-2 px-5 pb-1 flex justify-between items-center text-[11px] select-none bg-white" style="color: #64748B;">
            <span>{{ statusTime }}</span>
            <div class="flex items-center gap-1.5">
              <span>中国移动 5G</span>
              <svg class="w-3.5 h-3.5" style="color: #475569;" fill="currentColor" viewBox="0 0 24 24"><path d="M12 3c-4.97 0-9 4.03-9 9 0 2.12.74 4.07 1.97 5.61L12 22l7.03-4.39C20.26 16.07 21 14.12 21 12c0-4.97-4.03-9-9-9z"/></svg>
              <span>100%</span>
            </div>
          </div>

          <!-- App 顶栏：只保留品牌与标题，不再用「违法处理详情」这类内部页面名 -->
          <div class="px-4 py-2.5 bg-white flex items-center gap-1.5 select-none" style="border-bottom: 0.5px solid #F1F5F9; color: #334155;">
            <span class="w-4 h-4 cursor-pointer flex items-center justify-center" @click="close">
              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M15 19l-7-7 7-7" /></svg>
            </span>
            <span class="text-sm">行政处罚告知书</span>
          </div>

          <!-- 文书本体（打印区域） -->
          <div id="notice-document" class="px-6 py-5 bg-white text-[13px] leading-relaxed" style="color: #0F172A;">

            <!-- 未复核拦截：认定尚未成立时不出具罚款文书 -->
            <section
              v-if="!canIssue"
              class="mb-4 px-4 py-4"
              style="background: #FEF2F2; border: 1px solid #FECACA; border-radius: 8px;"
            >
              <div class="flex items-center gap-2 mb-2">
                <el-icon :size="16" style="color: #B91C1C;"><WarningFilled /></el-icon>
                <span class="text-[13px] font-medium" style="color: #B91C1C;">本记录尚未人工复核，不能生成告知书</span>
              </div>
              <p class="text-[12px] m-0 leading-6" style="color: #991B1B;">
                当前状态为「待人工复核」，检测引擎的判定只是线索，违法事实尚未经执法民警确认。
                请先完成复核：确认属实后点「人工复核 → 确认入卷」，误报请点「剔除」。
              </p>
              <div class="mt-3 pt-3 text-[12px] leading-6" style="border-top: 1px solid #FECACA; color: #7F1D1D;">
                <div>判定置信度：<span class="font-medium">{{ confidenceText }}</span></div>
                <div>算法判定：{{ currentRecord.violation_type || '未按规定佩戴安全头盔' }}</div>
                <div>复核民警：{{ currentRecord.reviewer || '尚未分配' }}</div>
              </div>
            </section>

            <!-- 已入卷但未送达：文书预览，加未送达水印提示 -->
            <section
              v-else-if="!isServed"
              class="no-print mb-4 px-3.5 py-2.5"
              style="background: #FFFBEB; border: 1px solid #FDE68A; border-radius: 8px;"
            >
              <p class="text-[12px] m-0 leading-6" style="color: #854F0B;">
                <span class="font-medium">未送达预览。</span>
                本文书内容已生成但尚未送达当事人，需在处置流程执行「告知」后才生效。
                当事人此时不应看到本文书。
              </p>
            </section>

            <!-- 抬头 -->
            <header class="text-center pb-3.5" style="border-bottom: 0.5px solid #CBD5E1;">
              <p class="text-[12px] m-0" style="color: #64748B;">武汉市公安局交通管理局</p>
              <h2 class="text-[16px] font-medium mt-1 mb-0">
                行政处罚告知书
                <span
                  v-if="!isServed"
                  class="ml-1.5 px-1.5 py-0.5 rounded text-[11px] font-normal align-middle"
                  style="background: #FEF3C7; color: #92400E;"
                >未送达</span>
                <span
                  v-else
                  class="ml-1.5 px-1.5 py-0.5 rounded text-[11px] font-normal align-middle"
                  style="background: #DBEAFE; color: #1E40AF;"
                >已送达</span>
              </h2>
              <p class="text-[11px] mt-1.5 mb-0" style="color: #94A3B8; font-family: var(--font-mono, monospace);">{{ documentNo }}</p>
            </header>

            <!-- 被告知人 -->
            <section class="mt-4 pb-3.5" style="border-bottom: 0.5px solid #E2E8F0;">
              <p class="text-[11px] mt-0 mb-1.5" style="color: #94A3B8;">被告知人</p>
              <p class="m-0" style="line-height: 1.75;">
                <span class="font-medium">{{ subjectVehicle }}</span>
                <span style="color: #94A3B8;"> · </span>
                <span style="color: #64748B;">身份信息未登记</span>
              </p>
              <p class="text-[11px] mt-1.5 mb-0" style="color: #64748B; line-height: 1.6;">
                本记录由卡口设备非现场采集，系统未采集驾驶人姓名及证件信息。若您并非该车驾驶人，请于期限内向本机关说明情况。
              </p>
            </section>

            <!-- 一、事实认定 -->
            <section class="mt-4">
              <h3 class="text-[13px] font-medium mt-0 mb-1.5">一、事实认定</h3>
              <p class="m-0" style="line-height: 1.85;">
                您于 <span class="font-medium" style="color: #B91C1C;">{{ captureTimeCn }}</span>，
                在<span class="font-medium" style="color: #B91C1C;">{{ spotName }} {{ spotDirection }}</span>路段，
                驾驶非机动车{{ factClause }}。
              </p>
              <p class="text-[11px] mt-1.5 mb-0" style="color: #64748B;" v-if="consecutiveFrames">
                该车辆连续 {{ consecutiveFrames }} 帧影像均记录到上述行为。
              </p>
            </section>

            <!-- 二、证据 -->
            <section class="mt-4">
              <h3 class="text-[13px] font-medium mt-0 mb-2">二、证据</h3>

              <div v-if="hasEvidence">
                <div class="flex gap-2">
                  <figure class="flex-1 m-0 overflow-hidden" style="background: #0F172A; border-radius: var(--border-radius-md, 8px);">
                    <img
                      :src="evidenceUrl"
                      alt="卡口自动抓拍的现场影像"
                      class="w-full h-32 object-contain"
                    />
                  </figure>
                  <div v-if="evidenceSecondaryUrl" class="flex-1 overflow-hidden" style="border-radius: var(--border-radius-md, 8px);">
                    <img
                      :src="evidenceSecondaryUrl"
                      alt="卡口全景参照影像"
                      class="w-full h-32 object-cover"
                    />
                  </div>
                </div>
                <figcaption class="text-[11px] mt-2 mb-0" style="color: #64748B; line-height: 1.6;">
                  上述影像由卡口设备自动抓拍并归档，原始文件未经编辑，可于交管 12123 核验。
                </figcaption>
              </div>

              <!-- 缺失态：不能拿占位符糊弄当事人 -->
              <div
                v-else
                class="px-3 py-4 text-center"
                style="background: #F8FAFC; border: 0.5px solid #E2E8F0; border-radius: var(--border-radius-md, 8px);"
              >
                <el-icon :size="20" style="color: #94A3B8;"><Picture /></el-icon>
                <p class="text-[12px] mt-1.5 mb-1" style="color: #475569;">本记录未附带现场影像</p>
                <p class="text-[11px] m-0" style="color: #94A3B8; line-height: 1.6;">
                  该记录由历史数据导入，未保存抓拍图。您可要求本机关出示原始影像，或依法申请复核。
                </p>
              </div>
            </section>

            <!-- 三、拟作出的处罚 -->
            <section class="mt-4">
              <h3 class="text-[13px] font-medium mt-0 mb-2">三、拟作出的行政处罚</h3>
              <div class="px-3.5 py-3" style="background: #F8FAFC; border-radius: var(--border-radius-md, 8px);">
                <div class="flex items-baseline gap-2">
                  <span class="text-[13px]">罚款</span>
                  <span class="text-[24px] font-medium" style="color: #B91C1C;">50</span>
                  <span class="text-[13px]">元</span>
                  <span class="text-[12px] ml-1" style="color: #64748B;">（情节较轻的，可并处警告）</span>
                </div>

                <!-- 法律依据默认折叠：处罚决定才是主信息，条文是支撑 -->
                <div class="mt-2.5">
                  <button
                    @click="lawOpen = !lawOpen"
                    class="inline-flex items-center gap-1 text-[12px] px-0 py-0 transition"
                    style="color: var(--c-primary, #1D4ED8); background: transparent; border: none;"
                    :aria-expanded="lawOpen"
                  >
                    <span>{{ lawOpen ? '收起处罚依据' : '查看处罚依据' }}</span>
                    <svg class="w-3 h-3 transition-transform" :style="{ transform: lawOpen ? 'rotate(180deg)' : 'none' }" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M6 9l6 6 6-6" /></svg>
                  </button>
                  <div v-if="lawOpen" class="mt-2 text-[12px]" style="color: #334155; line-height: 1.8;">
                    <p class="m-0">违反：《中华人民共和国道路交通安全法》第五十一条、《武汉市非机动车管理办法》第十九条。</p>
                    <p class="m-0">依据：《中华人民共和国道路交通安全法》第八十九条、《武汉市非机动车管理办法》第三十一条。</p>
                    <p class="m-0" style="color: #64748B;">违法行为代码：8076</p>
                  </div>
                </div>
              </div>
            </section>

            <!-- 四、权利告知：告知书不可替代的部分 -->
            <section class="mt-4 px-3.5 py-3" style="background: #EFF6FF; border-radius: var(--border-radius-md, 8px);">
              <h3 class="text-[13px] font-medium mt-0 mb-1.5" style="color: #1E40AF;">四、您依法享有的权利</h3>
              <ol class="m-0 pl-4 text-[12.5px]" style="color: #1F2937; line-height: 1.9;">
                <li>自收到本告知书之日起 <span class="font-medium">7 日内</span>，可向本机关提交书面陈述与申辩，本机关将依法复核。</li>
                <li>对本处罚决定不服，可在 <span class="font-medium">60 日内</span>申请行政复议，或在 <span class="font-medium">6 个月内</span>向人民法院提起行政诉讼。</li>
                <li>符合条件的，可向本机关申请听证，本机关将依法组织。</li>
              </ol>
              <p class="text-[11px] mt-2 mb-0" style="color: #1E40AF; line-height: 1.6;">
                本告知书为拟处罚告知，最终处罚决定另行送达。未依法申辩的，本机关将按上述依据作出决定。
              </p>
            </section>

            <!-- 五、履行方式 -->
            <section class="mt-4">
              <h3 class="text-[13px] font-medium mt-0 mb-1.5">五、履行方式与期限</h3>
              <p class="m-0" style="line-height: 1.85;">
                收到处罚决定书后，请于 <span class="font-medium">15 日内</span>通过交管 12123 或指定银行网点缴纳罚款。
                逾期未缴纳的，将依法强制执行。
              </p>
            </section>

            <!-- 签收与落款 -->
            <section class="mt-5 pt-3.5" style="border-top: 0.5px solid #E2E8F0;">
              <p class="text-[11px] m-0 mb-3" style="color: #94A3B8;">当事人签收</p>
              <div class="flex gap-6">
                <div class="flex-1">
                  <div class="h-4"></div>
                  <div class="text-[11px]" style="color: #94A3B8; border-top: 0.5px solid #CBD5E1;">签名</div>
                </div>
                <div class="flex-1">
                  <div class="h-4"></div>
                  <div class="text-[11px]" style="color: #94A3B8; border-top: 0.5px solid #CBD5E1;">签收日期</div>
                </div>
              </div>

              <div class="mt-4 text-right">
                <p class="m-0 text-[12px]">武汉市公安局交通管理局</p>
                <p class="m-0 mt-0.5 text-[12px]" style="color: #64748B;">{{ issueDateCn }}</p>
              </div>
            </section>

            <!-- 存证链：降级为可核验结论，不再暴露哈希明细 -->
            <footer class="mt-4 pt-2.5 flex items-center justify-between" style="border-top: 0.5px solid #E2E8F0;">
              <p class="text-[11px] m-0" style="color: #94A3B8;">本记录已电子签名，可在交管 12123 核验</p>
              <div class="w-8 h-8 flex items-center justify-center" style="background: #F8FAFC; border: 0.5px solid #CBD5E1; border-radius: 4px;">
                <svg class="w-full h-full" style="color: #334155;" fill="currentColor" viewBox="0 0 24 24">
                  <path d="M2 2h8v8H2V2zm2 2v4h4V4H4zm10-2h8v8h-8V2zm2 2v4h4V4h-4zM2 14h8v8H2v-8zm2 2v4h4v-4H4zm14-2h4v2h-4v-2zm-4 0h2v4h-2v-4zm4 4h4v4h-4v-4zm-4 2h2v2h-2v-2zm0-4h2v2h-2v-2zm4-6h2v2h-2V8zm-2 2h2v2h-2v-2zm-6 2h2v2h-2v-2zm-2 2h2v2h-2v-2zm2 2h2v2h-2v-2zm2-2h2v2h-2v-2z"/>
                </svg>
              </div>
            </footer>
          </div>

          <!-- 当事人侧操作区：**只在市民视角出现**。
               执法端弹这个窗是给民警核对文书内容用的，
               民警既不会替当事人申辩、也不会缴罚款，
               在执法端显示这些按钮属于角色错位。
               另外"发送短信提醒"本身就是执法侧动作，市民端也不该有。 -->
          <div
            v-if="isCitizenView"
            class="no-print px-4 py-3.5 space-y-2.5 select-none"
            style="border-top: 0.5px solid #E2E8F0; background: #FFFFFF;"
          >
            <button
              v-if="canSend"
              @click="onDispute"
              class="w-full py-2.5 rounded-xl text-[14px] font-medium transition"
              style="background: var(--c-primary, #1D4ED8); color: #FFFFFF;"
            >
              提交陈述申辩
            </button>
            <button
              v-else
              disabled
              class="w-full py-2.5 rounded-xl text-[14px] cursor-not-allowed"
              style="background: #E2E8F0; color: #94A3B8;"
            >
              尚未送达，暂不可操作
            </button>
            <div class="flex items-center justify-center gap-4 text-[12px]" style="color: canSend ? 'var(--c-primary, #1D4ED8)' : '#CBD5E1';">
              <span :class="canSend ? 'cursor-pointer hover:underline' : 'cursor-not-allowed'" @click="canSend && onPay()">缴纳罚款</span>
              <span style="color: #CBD5E1;">|</span>
              <span :class="canSend ? 'cursor-pointer hover:underline' : 'cursor-not-allowed'" @click="canSend && onDispute()">申请复核</span>
            </div>
            <p class="text-[11px] m-0 text-center" style="color: #94A3B8;">
              {{ canSend ? '本文书由系统生成，最终处罚决定另行送达' : '本文书尚未送达，不具备法律效力' }}
            </p>
          </div>

          <!-- 执法端：只作存档提示，不提供当事人操作 -->
          <div
            v-else
            class="no-print px-4 py-3 select-none"
            style="border-top: 0.5px solid #E2E8F0; background: #FFFFFF;"
          >
            <p class="text-[11px] m-0 text-center" style="color: #94A3B8;">
              以上为当事人收到的文书内容预览{{ isServed ? '' : '（尚未送达）' }}
            </p>
          </div>

          <div class="h-4 bg-white flex items-center justify-center pb-1">
            <div class="w-28 h-1 rounded-full" style="background: #CBD5E1;"></div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Close, DocumentCopy, Picture, Printer, WarningFilled } from '@element-plus/icons-vue'
import { cameraName } from '../data/cameras'

/**
 * 拟处罚金额（元）。
 * 台账表未设罚款金额列，此处为非现场告知阶段的法定上限档，
 * 上线时应改为从后端处罚标准配置读取。
 */
const FINE_AMOUNT = 50

const props = defineProps({
  visible: { type: Boolean, default: false },
  record: { type: Object, default: null },
  /**
   * 视角：谁在看这份文书。默认 officer —— 执法端调用点更多，
   * 且万一漏传，默认少给当事人操作总比默认多给执法端当事人操作安全。
   *   officer 民警核对文书内容：有「告知短信/打印导出」，无当事人操作
   *   citizen 当事人阅读并办理：有「申辩/缴款/复核」，无下发类动作
   */
  mode: {
    type: String,
    default: 'officer',
    validator: (v) => ['officer', 'citizen'].includes(v)
  }
})

const emit = defineEmits(['update:visible', 'close'])

const isOfficerView = computed(() => props.mode === 'officer')
const isCitizenView = computed(() => props.mode === 'citizen')

const currentRecord = computed(() => props.record || {})

/**
 * 文书门槛：违法认定必须先经人工复核，才谈得上对当事人作出拟处罚告知。
 *   status=pending  待人工复核 → 认定不成立，禁止生成告知书
 *   status=rejected 误报已剔除 → 永不生成
 *   status=approved 已确认入卷 → 可以生成，但「送达」之前只是内部预览
 * 送达以处置状态为准（notified / disposed / archived）。
 */
const canIssue = computed(() => currentRecord.value.status === 'approved')

const isServed = computed(() => {
  const disp = currentRecord.value.disposition?.status
  return disp === 'notified' || disp === 'disposed' || disp === 'archived'
})

/** 只有文书已送达，当事人侧动作（申辩/缴款/短信）才成立 */
const canSend = computed(() => canIssue.value && isServed.value)

const confidenceText = computed(() => {
  const c = currentRecord.value.confidence
  if (typeof c !== 'number' || !Number.isFinite(c)) return '未记录'
  return `${Math.round(c * 100)}%`
})

/** 法律依据默认折叠 */
const lawOpen = ref(false)
watch(() => props.visible, (v) => { if (v) lawOpen.value = false })

function close() {
  emit('update:visible', false)
  emit('close')
}

/* ── Esc 关闭：按 ESC 时焦点可能在文书内的可点元素上，
   不能只在 isModalOpen 为真时挂载，否则焦点转移后就失灵。 ── */
function handleKeydown(event) {
  if (event.key !== 'Escape' || !props.visible) return
  const el = document.activeElement
  // 输入类控件里按 ESC（如 Element 弹窗）不抢，交给它自己处理
  if (el && (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA' || el.isContentEditable)) return
  close()
}
onMounted(() => window.addEventListener('keydown', handleKeydown))
onUnmounted(() => window.removeEventListener('keydown', handleKeydown))

/* ── 时间：统一 localTimeString 口径，不用 toISOString（会早 8 小时） ── */

function parseCaptureTime(raw) {
  if (!raw) return null
  const m = String(raw).match(/^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2})/)
  if (!m) return null
  return { y: m[1], mo: m[2], d: m[3], h: m[4], mi: m[5] }
}

const statusTime = computed(() => {
  const d = new Date()
  return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
})

/** 2026年10月09日 15时36分 */
const captureTimeCn = computed(() => {
  const t = parseCaptureTime(currentRecord.value.capture_time)
  if (!t) return '时间未记录'
  return `${t.y}年${t.mo}月${t.d}日 ${t.h}时${t.mi}分`
})

/** 2026 年 10 月 9 日 —— 落款用 */
const issueDateCn = computed(() => {
  const t = parseCaptureTime(currentRecord.value.capture_time) || (() => {
    const d = new Date()
    return { y: d.getFullYear(), mo: String(d.getMonth() + 1).padStart(2, '0'), d: String(d.getDate()).padStart(2, '0') }
  })()
  return `${t.y} 年 ${Number(t.mo)} 月 ${Number(t.d)} 日`
})

/* ── 地点：台账 camera_id 是机器编号，屏显必须用人读的地名 ── */

const spotName = computed(() => cameraName(currentRecord.value.camera_id || '') || '武汉市交通卡口')

/**
 * 方向有三档来源，逐级兜底：
 *   1. direction 列（种子数据有）
 *   2. camera_label 里的括号，如「CAM-02: 科技园区主干道卡口 (北向)」（实时抓拍记录）
 *   3. camera_id 用 - 分隔的第 3 段（如 CAM-01-南向非机动车道）
 * 都没有才显示「行车方向未记录」——不编造。
 */
const spotDirection = computed(() => {
  const r = currentRecord.value
  if (r.direction) return r.direction

  const label = String(r.camera_id || '')
  const inParen = label.match(/[（(]([^（）()]+)[）)]\s*$/)
  if (inParen) return inParen[1].trim()

  const seg = label.split('-').slice(2).join('-').trim()
  return seg || '行车方向未记录'
})

/* ── 被告知人：台账无身份字段，只能落到车辆特征 ── */

/**
 * 车辆特征在 `details.plate_or_vehicle` 里（API 契约），不在顶层。
 * ⚠️ 这里原先读的是顶层 `r.plate_or_vehicle`，字段不存在 →
 * 文书永远显示「车辆特征未记录」，当事人无法据此辨认是不是自己的车。
 * 与 HistoryReview / EvidenceModal / DispositionModal 的取值路径保持一致。
 */
const subjectVehicle = computed(() => {
  const r = currentRecord.value
  // details.plate_or_vehicle 形如「深蓝轻便电摩 [鄂A·E8821]」——
  // 含车型描述 + 车牌，比单给车牌更利于当事人辨认是不是自己的车，故优先。
  const raw = r.details?.plate_or_vehicle || r.plate_no || r.plate_or_vehicle || ''
  return `车辆：${raw || '非机动车（车辆特征未记录）'}`
})

/** 违法条款的人话表述 */
const factClause = computed(() => {
  const category = currentRecord.value.category || 'helmet'
  if (category === 'passenger') return '，乘坐人未按规定佩戴安全头盔'
  if (category === 'both') return '，驾驶人与乘坐人均未按规定佩戴安全头盔'
  return '未按规定佩戴安全头盔'
})

const consecutiveFrames = computed(() => {
  const n = currentRecord.value.consecutive_frames
  return Number.isFinite(n) && n > 0 ? n : null
})

/* ── 证据 ── */

const evidenceUrl = computed(() => {
  const r = currentRecord.value
  return r.evidence_url || r.roi_url || ''
})

/** 第二张只在同一记录的连续帧里取，避免拿同一张图充数 */
const evidenceSecondaryUrl = computed(() => {
  const r = currentRecord.value
  return r.roi_url && r.roi_url !== r.evidence_url ? r.roi_url : ''
})

const hasEvidence = computed(() => Boolean(evidenceUrl.value))

/**
 * 文书编号：由记录号派生（台账没有独立文书号列）。
 * `EV-20261003-0046` → `武交违告〔2026〕第 10046 号`
 * 演示记录的尾段是 4 位十进制流水，可能带前导零，toUpperCase() 会把数字原样保留，
 * 但非数字字符会变成 NaN，所以必须先剥掉分隔符再校验。
 */
const documentNo = computed(() => {
  const id = String(currentRecord.value.id || '')
  const tail = id.replace(/^EV-/, '').replace(/\D/g, '')
  const t = parseCaptureTime(currentRecord.value.capture_time)
  const year = t ? t.y : String(new Date().getFullYear())
  const serial = tail.length ? String(Number(tail.slice(-6))) : '0'
  return `武交违告〔${year}〕第 ${serial} 号`
})

/* ── 当事人侧动作 ── */

function copySmsText() {
  const text = `【武汉交警】您的非机动车于 ${captureTimeCn.value} 在 ${spotName.value}${spotDirection.value}路段${factClause.value}，被卡口设备记录（代码8076）。请登录"交管12123"查看《行政处罚告知书》并依法处理。【武汉市公安局交通管理局】`
  navigator.clipboard.writeText(text)
    .then(() => ElMessage.success('已复制告知短信正文至剪贴板'))
    .catch(() => ElMessageBox.alert(text, '告知短信正文', { confirmButtonText: '关闭' }))
}

function onDispute() {
  ElMessageBox.prompt(
    '陈述申辩将提交至武汉交警人工复核中心，由复核民警重新核验。若您并非该车驾驶人，请一并说明。',
    '提交陈述申辩',
    {
      confirmButtonText: '提交申辩',
      cancelButtonText: '取消',
      inputPlaceholder: '例如：当时已佩戴头盔 / 该车并非本人使用 / 车辆特征与描述不符'
    }
  ).then(({ value }) => {
    if (value) ElMessage.success('申辩已提交至人工复核中心，请在 7 日内等待复核结果。')
  }).catch(() => {})
}

function onPay() {
  ElMessageBox.confirm(
    `拟处罚金额：¥${FINE_AMOUNT}.00 元\n\n依法应在收到处罚决定书后 15 日内缴纳。此处为流程演示，不会发生真实扣款。`,
    '缴纳罚款',
    { confirmButtonText: '继续', cancelButtonText: '取消', type: 'info' }
  ).then(() => {
    ElMessage.success('【演示】已进入非税收入电子缴费流程，实际扣款需处罚决定书送达后进行。')
  }).catch(() => {})
}

function printNotice() {
  window.print()
}
</script>

<style scoped>
/* 打印：只输出文书本体，去掉仿真手机外框与操作按钮 */
@media print {
  body * {
    visibility: hidden;
  }
  #notice-document, #notice-document * {
    visibility: visible;
  }
  #notice-document {
    position: absolute;
    left: 0;
    top: 0;
    width: 100%;
    padding: 12mm 16mm;
    background: #FFFFFF;
  }
  @page {
    size: A4;
    margin: 0;
  }
}
</style>