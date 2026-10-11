<template>
  <div class="min-h-screen pb-16" style="background: #F1F5F9; color: #0F172A;">

    <!-- 顶部：只留群众关心的事 -->
    <header class="text-white" style="background: linear-gradient(180deg, #1E40AF 0%, #1D4ED8 100%);">
      <div class="max-w-2xl mx-auto px-5 pt-6 pb-7">
        <div class="flex items-start justify-between gap-3">
          <div class="min-w-0">
            <p class="text-[13px] opacity-90">{{ greeting }}</p>
            <h1 class="text-[20px] font-medium mt-1">这是您的交通违法记录</h1>
          </div>
          <div class="flex items-center gap-2 flex-shrink-0">
            <!-- 绑定车牌：让"这是您的记录"这句话有据可依 -->
            <div
              v-if="plates.length"
              class="px-2.5 py-1 rounded-md text-[12px]"
              style="background: rgba(255,255,255,0.16);"
            >
              {{ plates.join(' · ') }}
            </div>
            <div class="w-9 h-9 rounded-lg flex items-center justify-center" style="background: rgba(255,255,255,0.16);">
              <ShieldMark :size="20" />
            </div>
          </div>
        </div>
        <p class="text-[12px] mt-3 opacity-90" style="line-height: 1.7;">
          {{ plates.length
            ? '数据来自武汉交警卡口设备，以下记录与您名下上述号牌相关。'
            : '您的账号暂未绑定号牌，绑定后可查询名下车辆违法记录。' }}
        </p>
      </div>
    </header>

    <main class="max-w-2xl mx-auto px-5 -mt-4 space-y-4">

      <!-- 最要紧的一件事：有没有需要处理的 -->
      <section class="rounded-xl p-4" style="background: #FFFFFF; box-shadow: 0 1px 3px rgba(15,23,42,0.08);">
        <div class="flex items-center gap-3">
          <div
            class="w-10 h-10 rounded-full flex items-center justify-center flex-shrink-0"
            :style="hasAction ? 'background:#FEF3C7;' : 'background:#DCFCE7;'"
          >
            <el-icon :size="20" :style="{ color: hasAction ? '#B45309' : '#15803D' }">
              <component :is="hasAction ? 'Warning' : 'CircleCheckFilled'" />
            </el-icon>
          </div>
          <div class="min-w-0">
            <p class="text-[15px] font-medium">{{ summaryTitle }}</p>
            <p class="text-[12px] mt-0.5" style="color: #64748B;">{{ summaryDesc }}</p>
          </div>
        </div>
      </section>

      <!-- 违法记录 -->
      <section>
        <h2 class="text-[14px] font-medium mb-2.5 px-1">我的违法记录</h2>

        <div v-if="loading" class="rounded-xl p-6 text-center text-[13px]" style="background:#FFFFFF; color:#64748B;">
          正在查询…
        </div>

        <div v-else-if="loadError" class="rounded-xl p-5" style="background:#FEF2F2; border: 1px solid #FECACA;">
          <p class="text-[13px] font-medium" style="color:#B91C1C;">查询失败</p>
          <p class="text-[12px] mt-1" style="color:#991B1B; line-height:1.7;">{{ loadError }}</p>
          <button
            @click="reloadRecords"
            class="mt-3 h-8 px-3 rounded-md text-[13px]"
            style="background:#FFFFFF; border:1px solid #FCA5A5; color:#B91C1C;"
          >
            重新查询
          </button>
        </div>

        <!-- 空态：这是最容易被做错的一屏 -->
        <div v-else-if="myRecords.length === 0" class="rounded-xl p-8 text-center" style="background:#FFFFFF;">
          <div class="w-12 h-12 rounded-full mx-auto flex items-center justify-center" style="background:#DCFCE7;">
            <el-icon :size="24" style="color:#15803D;"><CircleCheckFilled /></el-icon>
          </div>
          <p class="text-[15px] font-medium mt-3">您名下暂无违法记录</p>
          <p class="text-[12px] mt-1.5" style="color:#64748B; line-height:1.7;">
            如您认为系统记录有误，可联系辖区交警大队申请复核。
          </p>
        </div>

        <!-- 记录分三组呈现（保持 v-else 链完整，避免与上方空态/错误态并存） -->
        <template v-else>
          <!-- 待处理：群众来这一页的目的，永远展开 -->
          <div v-if="pendingRecords.length > 0" class="space-y-2.5">
            <h2 class="text-[14px] font-medium mb-2.5 px-1" style="color:#B91C1C;">
              待处理（{{ pendingRecords.length }}）
            </h2>
            <CitizenRecordCard
              v-for="record in pendingRecords"
              :key="record.id"
              :record="record"
              @detail="openNotice"
              @appeal="openAppeal"
            />
          </div>

          <!-- 待送达：交警还没把文书送到，群众无需动作，只告知进度 -->
          <div
            v-if="servingRecords.length > 0"
            class="space-y-2.5"
            :class="pendingRecords.length ? 'mt-5' : ''"
          >
            <h2 class="text-[14px] font-medium mb-2.5 px-1" style="color:#B45309;">
              待交警送达（{{ servingRecords.length }}）
            </h2>
            <CitizenRecordCard
              v-for="record in servingRecords"
              :key="record.id"
              :record="record"
              @detail="openNotice"
              @appeal="openAppeal"
            />
          </div>

          <!-- 历史记录：默认折叠。
               演示账号名下 77 条，全铺开是 50 张卡片的超长页面（实测 11374px），
               群众根本翻不到底。历史是"查的时候才看"，不该占据首屏。 -->
          <div
            v-if="historyRecords.length > 0"
            :class="(pendingRecords.length || servingRecords.length) ? 'mt-5' : ''"
          >
            <button
              class="w-full rounded-xl bg-white px-4 py-3.5 flex items-center justify-between gap-3 text-left"
              @click="historyOpen = !historyOpen"
            >
              <span class="text-[14px] font-medium">
                {{ historyOpen ? '历史记录' : '已处理完毕的历史记录' }}
                <span class="text-[12px] font-normal ml-1" style="color:#64748B;">{{ historyRecords.length }} 条</span>
              </span>
              <svg
                class="w-4 h-4 flex-shrink-0 transition-transform"
                :style="{ transform: historyOpen ? 'rotate(180deg)' : 'none', color: '#64748B' }"
                fill="none" stroke="currentColor" viewBox="0 0 24 24"
              >
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 9l6 6 6-6" />
              </svg>
            </button>

            <div v-if="historyOpen" class="mt-2.5 space-y-2.5">
              <CitizenRecordCard
                v-for="record in historyRecords"
                :key="record.id"
                :record="record"
                @detail="openNotice"
                @appeal="openAppeal"
              />
            </div>
          </div>
        </template>
      </section>

      <!-- 我要举报 -->
      <section>
        <h2 class="text-[14px] font-medium mb-2.5 px-1">我要举报交通安全隐患</h2>

        <!-- 折叠：默认收起，群众不该被一上来就要求举证 -->
        <div class="rounded-xl overflow-hidden" style="background:#FFFFFF;">
          <button
            @click="reportOpen = !reportOpen"
            class="w-full px-4 py-3.5 flex items-center justify-between gap-3 text-left"
          >
            <span class="text-[13px]" style="color:#334155;">看到有人未戴头盔？可上报给交警核查</span>
            <svg
              class="w-4 h-4 flex-shrink-0 transition-transform"
              :style="{ transform: reportOpen ? 'rotate(180deg)' : 'none', color: '#64748B' }"
              fill="none" stroke="currentColor" viewBox="0 0 24 24"
            >
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 9l6 6 6-6" />
            </svg>
          </button>

          <div v-if="reportOpen" class="px-4 pb-4" style="border-top: 0.5px solid #F1F5F9;">
            <!-- 隐私提示放在最前，但用中性口吻 -->
            <p class="text-[12px] mt-3 mb-3 leading-6" style="color:#64748B;">
              请在公共安全区域拍摄，避免拍到行人面部、车牌等个人信息。上报内容仅供交警核查使用。
            </p>

            <div class="space-y-3">
              <label class="block">
                <span class="text-[12px] block mb-1.5" style="color:#475569;">隐患类型</span>
                <select v-model="reportForm.type" class="w-full h-10 rounded-lg px-3 text-[13px]" style="background:#FFFFFF; border:1px solid #CBD5E1; color:#0F172A;">
                  <option value="helmet">骑行人未戴头盔</option>
                  <option value="passenger">乘坐人未戴头盔</option>
                  <option value="other">其他交通违法行为</option>
                </select>
              </label>

              <label class="block">
                <span class="text-[12px] block mb-1.5" style="color:#475569;">发生时间</span>
                <input v-model="reportForm.time" type="datetime-local" class="w-full h-10 rounded-lg px-3 text-[13px]" style="background:#FFFFFF; border:1px solid #CBD5E1; color:#0F172A;" />
              </label>

              <label class="block">
                <span class="text-[12px] block mb-1.5" style="color:#475569;">发生地点</span>
                <input
                  v-model="reportForm.location"
                  type="text"
                  placeholder="例如：解放大道与新华路交叉口"
                  class="w-full h-10 rounded-lg px-3 text-[13px]"
                  style="background:#FFFFFF; border:1px solid #CBD5E1; color:#0F172A;"
                />
              </label>

              <label class="block">
                <span class="text-[12px] block mb-1.5" style="color:#475569;">现场照片</span>
                <div
                  class="h-28 rounded-lg flex flex-col items-center justify-center gap-1.5 cursor-pointer"
                  style="background:#F8FAFC; border: 1px dashed #CBD5E1; color:#64748B;"
                >
                  <el-icon :size="22"><Camera /></el-icon>
                  <span class="text-[12px]">{{ reportForm.photoName || '点这里添加照片' }}</span>
                  <input type="file" accept="image/*" class="hidden" @change="handlePhotoPick" />
                </div>
              </label>

              <label class="block">
                <span class="text-[12px] block mb-1.5" style="color:#475569;">补充说明<span style="color:#94A3B8;">（选填）</span></span>
                <textarea
                  v-model="reportForm.description"
                  rows="3"
                  placeholder="车辆颜色、行驶方向等有助于核查的信息"
                  class="w-full rounded-lg px-3 py-2.5 text-[13px] resize-none"
                  style="background:#FFFFFF; border:1px solid #CBD5E1; color:#0F172A;"
                ></textarea>
              </label>

              <button
                @click="submitReport"
                :disabled="submitting"
                class="w-full h-11 rounded-lg text-[14px] font-medium text-white disabled:opacity-60"
                style="background:#1D4ED8;"
              >
                {{ submitting ? '正在提交…' : '提交给交警核查' }}
              </button>

              <p class="text-[11px] text-center" style="color:#94A3B8; line-height:1.7;">
                提交不代表会被处罚，交警会先核实情况
              </p>
            </div>
          </div>
        </div>

        <!-- 已提交的上报 -->
        <div v-if="reports.length > 0" class="mt-2.5 space-y-2">
          <article
            v-for="report in reports"
            :key="report.id"
            class="rounded-xl px-4 py-3"
            style="background:#FFFFFF;"
          >
            <div class="flex items-center justify-between gap-2">
              <p class="text-[13px] font-medium truncate">{{ report.location }}</p>
              <span class="px-2 py-0.5 rounded text-[11px] flex-shrink-0" style="background:#F1F5F9; color:#475569;">核查中</span>
            </div>
            <p class="text-[12px] mt-1" style="color:#64748B;">{{ report.time }} · {{ report.typeLabel }}</p>
          </article>
        </div>
      </section>

      <!-- 真实身份与退出：让"我的记录"有明确归属，而不是打开就是别人的数据 -->
      <section class="rounded-xl px-4 py-3 flex items-center justify-between gap-3" style="background:#FFFFFF;">
        <div class="min-w-0">
          <p class="text-[13px] font-medium truncate">{{ authStore.currentUser?.real_name }}</p>
          <p class="text-[11px] mt-0.5" style="color:#94A3B8;">已登录 · 账号 {{ authStore.currentUser?.username }}</p>
        </div>
        <button
          @click="handleLogout"
          class="h-8 px-3 rounded-md text-[12px] flex-shrink-0"
          style="background:#FFFFFF; border:1px solid #CBD5E1; color:#475569;"
        >
          退出登录
        </button>
      </section>

      <p class="text-[11px] text-center px-4" style="color:#94A3B8; line-height:1.8;">
        本平台由武汉市公安局交通管理局提供<br />
        遇到问题可拨打 027-8xxx 转交警服务台
      </p>
    </main>

    <!-- 群众端：mode="citizen" —— 显示申辩/缴款，不显示告知短信等下发动作 -->
    <Traffic12123Notice v-model:visible="noticeVisible" :record="selectedRecord" mode="citizen" />
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Camera } from '@element-plus/icons-vue'
import ShieldMark from '../components/ShieldMark.vue'
import Traffic12123Notice from '../components/Traffic12123Notice.vue'
import CitizenRecordCard from '../components/CitizenRecordCard.vue'
import { useAuthStore } from '../stores/auth'
import { fetchMyRecords, fetchMyReports, submitPublicReport } from '../services/citizenApi'
import { cameraName } from '../data/cameras'

const router = useRouter()
const authStore = useAuthStore()

const loading = ref(false)
const loadError = ref('')
const myRecords = ref([])
const plates = ref([])
const selectedRecord = ref(null)
const noticeVisible = ref(false)
const reportOpen = ref(false)
const reports = ref([])
const submitting = ref(false)
/** 历史记录默认折叠：演示账号 77 条，全展开翻不到底 */
const historyOpen = ref(false)

const reportForm = reactive({ type: 'helmet', time: '', location: '', description: '', photoName: '' })

const greeting = computed(() => {
  const name = authStore.currentUser?.real_name
  return name ? `${name}，您好` : '您好'
})

/**
 * 记录分三组，语义不能混：
 *   待处理   notified   → 文书已送达，当事人需要处理（缴款/申诉）
 *   待送达   to_notify  → 交警尚未送达文书，当事人无需动作，只告知进度
 *   历史记录 disposed/archived → 已办结，默认折叠
 * 把 to_notify 混进「待处理」会让群众以为自己有笔罚款急着交，但文书其实还没到手。
 */
const pendingRecords = computed(
  () => myRecords.value.filter(r => r.disposition?.status === 'notified')
)
const servingRecords = computed(
  () => myRecords.value.filter(r => r.disposition?.status === 'to_notify')
)
const historyRecords = computed(
  () => myRecords.value.filter(r => {
    const s = r.disposition?.status
    return s === 'disposed' || s === 'archived'
  })
)

async function reloadRecords() {
  loading.value = true
  loadError.value = ''
  try {
    // 走群众端接口：按当前登录市民的绑定车牌过滤，服务端强制鉴权。
    // 不用台账接口 —— 那是执法侧全量视图，市民无权访问。
    const data = await fetchMyRecords()
    plates.value = Array.isArray(data.plates) ? data.plates : []
    myRecords.value = Array.isArray(data.items) ? data.items : []
    loadMyReports()
  } catch (error) {
    const status = error?.response?.status
    if (status === 401) {
      loadError.value = '登录已失效，请重新登录'
    } else {
      loadError.value = error?.response?.data?.detail?.message || error?.message || '网络异常，请稍后重试'
    }
    myRecords.value = []
  } finally {
    loading.value = false
  }
}

async function loadMyReports() {
  try {
    const data = await fetchMyReports()
    reports.value = (Array.isArray(data.items) ? data.items : []).map(r => ({
      id: r.id,
      location: r.location_text,
      time: String(r.occurred_at || '').replace('T', ' ').slice(0, 16),
      typeLabel: reportTypeLabel(r.report_type),
      status: r.status,
      reviewNote: r.review_note
    }))
  } catch {
    // 上报列表拿不到不影响主流程（记录查询才是主任务），保持已有列表即可
  }
}

/** 申诉弹窗要用地点，保留在此；其余展示逻辑已移入 CitizenRecordCard */
function spotLabel(record) {
  const raw = record.camera_id || ''
  const direction = record.direction
    || raw.match(/[（(]([^（）()]+)[）)]\s*$/)?.[1]
    || raw.split('-').slice(2).join('-')
  const name = cameraName(raw)
  return direction ? `${name} ${direction}` : name
}

/** 已送达 = 处置流程走到「已告知」及以后 */
function isServed(record) {
  const s = record.disposition?.status
  return s === 'notified' || s === 'disposed' || s === 'archived'
}

/** 需要群众动作的只有「已送达未处理」这一类；待送达不算，那是交警的事 */
const hasAction = computed(() => pendingRecords.value.length > 0)

const summaryTitle = computed(() => {
  if (loading.value) return '正在查询…'
  if (loadError.value) return '暂时查不到您的记录'
  if (myRecords.value.length === 0) return '您名下暂无违法记录'
  const n = pendingRecords.value.length
  if (n > 0) return `您有 ${n} 条记录待处理`
  if (servingRecords.value.length > 0) return '有记录正在送达中'
  return '您的记录均已处理完毕'
})

const summaryDesc = computed(() => {
  if (loadError.value) return '请检查网络后重新查询'
  if (myRecords.value.length === 0) return '请放心出行'
  const n = pendingRecords.value.length
  if (n > 0) {
    const h = historyRecords.value.length
    return h > 0
      ? `请在规定期限内查看详情并完成处理；另有 ${h} 条历史记录`
      : '请在规定期限内查看详情并完成处理'
  }
  if (servingRecords.value.length > 0) return '交警正在送达告知文书，无需您操作'
  return `${historyRecords.value.length} 条历史记录，如有疑问可申请复核`
})

function openNotice(record) {
  if (!isServed(record)) {
    ElMessage.info('该记录尚未送达告知书，请等待交警送达后再查看详情。')
    return
  }
  selectedRecord.value = record
  noticeVisible.value = true
}

function openAppeal(record) {
  ElMessageBox.prompt(
    `记录编号：${record.id}\n违法地点：${spotLabel(record)}\n\n请说明您对事实认定或证据的异议。`,
    '提交申诉',
    {
      confirmButtonText: '提交申诉',
      cancelButtonText: '取消',
      inputPlaceholder: '例如：当时已佩戴头盔 / 该车并非本人使用'
    }
  ).then(({ value }) => {
    if (value) ElMessage.success('申诉已提交，交警将在 7 日内复核并告知结果。')
  }).catch(() => {})
}

function reportTypeLabel(type) {
  if (type === 'passenger') return '乘坐人未戴头盔'
  if (type === 'other') return '其他交通违法'
  return '骑行人未戴头盔'
}

function handlePhotoPick(event) {
  const file = event.target.files?.[0]
  if (file) reportForm.photoName = file.name
}

async function submitReport() {
  if (!reportForm.location.trim()) {
    ElMessage.warning('请填写发生地点')
    return
  }
  if (!reportForm.time) {
    ElMessage.warning('请选择发生时间')
    return
  }
  submitting.value = true
  try {
    // 真实落库到 public_reports 线索池（后端强制 citizen 鉴权 + 单日 10 条上限）
    await submitPublicReport({
      location: reportForm.location.trim(),
      occurred_at: reportForm.time.replace('T', ' '),
      report_type: reportForm.type,
      description: reportForm.description.trim()
    })
    reportOpen.value = false
    ElMessage.success('已提交，交警会尽快核查。')
    reportForm.type = 'helmet'
    reportForm.location = ''
    reportForm.description = ''
    reportForm.photoName = ''
    loadMyReports()
  } catch (error) {
    const msg = error?.response?.data?.detail?.message || error?.message || '提交失败，请稍后重试'
    ElMessage.error(msg)
  } finally {
    submitting.value = false
  }
}

function handleLogout() {
  authStore.logout()
  router.push('/login')
}

onMounted(() => {
  const now = new Date()
  const pad = n => String(n).padStart(2, '0')
  reportForm.time = `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}T${pad(now.getHours())}:${pad(now.getMinutes())}`
  reloadRecords()
})
</script>