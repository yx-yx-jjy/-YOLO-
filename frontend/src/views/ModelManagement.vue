<template>
  <div class="space-y-4">
    <!-- 顶部状态栏 -->
    <div class="card flex flex-wrap items-center justify-between gap-3">
      <div>
        <h2 class="text-[16px] font-medium" style="color: var(--c-ink);">检测模型与识别性能管理</h2>
      </div>

      <div class="flex items-center gap-3 text-[13px]">
        <DemoBadge hint="参数量取自训练日志 summary 行（9,428,566）；计算量为 best.pt 在 960×960 下的实测值 48.5 G（训练日志里的 21.5 G 是默认 640 口径，不可用于 960）；mAP 取自 results.csv 最佳轮次（epoch 9）；本系统未改动 YOLO11s 网络结构，故不存在消融实验数据" />
        <span class="text-[12px]" style="color: var(--c-ink-3);">当前查看模型:</span>
        <select v-model="selectedModel" @change="switchModel" class="h-8 px-3 rounded-md text-[13px] font-normal focus:outline-none" style="background-color: var(--c-surface); border: 1px solid var(--c-line); color: var(--c-ink);">
          <option value="yolo11s">YOLO11s · helmet/no_helmet（当前部署）</option>
        </select>
        <button
          @click="refreshEngineStatus()"
          :disabled="probing"
          class="h-8 px-3 rounded-md text-[13px] font-normal text-white disabled:opacity-60"
          style="background-color: var(--c-primary);"
          @mouseenter="$event.currentTarget.style.backgroundColor = '#4338CA'"
          @mouseleave="$event.currentTarget.style.backgroundColor = 'var(--c-primary)'"
        >
          {{ probing ? '探测中…' : '重新探测引擎状态' }}
        </button>
      </div>
    </div>

    <MetricStrip :items="kpiItems" aria-label="检测引擎性能概览" />

    <!-- 3 个工程设计卡片（均为实际实现，非模型结构改动） -->
    <div class="grid grid-cols-3 gap-4 items-stretch">
      <div v-for="item in innovations" :key="item.tag" class="card h-full flex flex-col">
        <div class="flex items-center justify-between mb-2">
          <span class="text-[12px] font-normal" style="color: var(--c-ink-3);">{{ item.tag }}</span>
          <span class="px-2 py-0.5 rounded text-[12px] font-normal whitespace-nowrap" style="background-color: var(--c-primary-weak); color: var(--c-primary);">{{ item.badge }}</span>
        </div>
        <h3 class="text-[14px] font-medium mb-2" style="color: var(--c-ink);">{{ item.title }}</h3>
        <p class="text-[13px] font-normal flex-1" style="color: var(--c-ink-2); line-height: 20px;">
          {{ item.desc }}
        </p>
        <div class="mt-3 p-3 rounded-md text-[12px] font-mono space-y-1" style="background-color: var(--c-page); color: var(--c-ink-2);">
          <div>{{ item.stat1 }}</div>
          <div>{{ item.stat1Label }}: <span style="color: #15803D;">{{ item.stat1Value }}</span></div>
        </div>
      </div>
    </div>

    <!-- 引擎状态：读后端 /api/health 的真实返回，不再写死"已就绪 · GPU CUDA:0" -->
    <div class="text-[12px] font-mono" style="color: var(--c-ink-3);">
      {{ engineStatusText }}
    </div>

    <!-- 消融实验表 -->
    <div class="card !p-0 overflow-hidden">
      <div class="p-4" style="border-bottom: 1px solid var(--c-line);">
        <h3 class="text-[14px] font-medium flex items-center gap-2" style="color: var(--c-ink);">
          <el-icon :size="16"><DataLine /></el-icon>
          <span>模型参数规模与实测性能表</span>
          <span class="text-[12px] font-normal" style="color: var(--c-ink-3);">训练 / 验证 / 测试 = 7631 / 923 / 859 张，类别 helmet、no_helmet 两类</span>
        </h3>
      </div>

      <div class="overflow-x-auto">
        <table class="w-full text-left text-[13px] table-fixed" style="color: var(--c-ink);">
          <colgroup>
            <col style="width: 260px;" />
            <col style="width: 100px;" />
            <col style="width: 110px;" />
            <col style="width: 110px;" />
            <col style="width: 130px;" />
            <col style="width: 130px;" />
            <col style="width: 110px;" />
            <col style="width: 90px;" />
          </colgroup>
          <thead>
            <tr style="background-color: var(--c-page); border-bottom: 1px solid var(--c-line);">
              <th class="h-12 px-3 text-[12px] font-normal whitespace-nowrap" style="color: #64748B;">模型配置</th>
              <th class="h-12 px-3 text-[12px] font-normal whitespace-nowrap" style="color: #64748B;">输入分辨率</th>
              <th class="h-12 px-3 text-[12px] font-normal whitespace-nowrap text-right" style="color: #64748B;">参数量</th>
              <th class="h-12 px-3 text-[12px] font-normal whitespace-nowrap text-right" style="color: #64748B;">计算量</th>
              <th class="h-12 px-3 text-[12px] font-normal whitespace-nowrap text-right" style="color: #64748B;">mAP@50</th>
              <th class="h-12 px-3 text-[12px] font-normal whitespace-nowrap text-right" style="color: #64748B;">mAP@50-95</th>
              <th class="h-12 px-3 text-[12px] font-normal whitespace-nowrap text-right" style="color: #64748B;">推理速度</th>
              <th class="h-12 px-3 text-[12px] font-normal whitespace-nowrap text-center" style="color: #64748B;">状态</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in ablationRows" :key="row.name" class="h-12 align-middle" style="border-bottom: 1px solid var(--c-line);" @mouseenter="$event.currentTarget.style.backgroundColor = 'var(--c-page)'" @mouseleave="$event.currentTarget.style.backgroundColor = ''">
              <td class="h-12 px-3 whitespace-nowrap font-medium" style="color: var(--c-ink);">
                <div class="flex items-center gap-1.5">
                  <span v-if="isCurrent(row)" class="w-1.5 h-1.5 rounded-full" style="background-color: var(--c-primary);"></span>
                  <span>{{ row.name }}</span>
                </div>
              </td>
              <td class="h-12 px-3 font-mono whitespace-nowrap" style="color: var(--c-ink-2);">{{ row.res }}</td>
              <td class="h-12 px-3 font-mono whitespace-nowrap text-right" style="color: var(--c-ink-2);">{{ row.params }}</td>
              <td class="h-12 px-3 font-mono whitespace-nowrap text-right" style="color: var(--c-ink-2);">{{ row.flops }}</td>
              <td class="h-12 px-3 font-mono whitespace-nowrap text-right">
                <span style="color: var(--c-ink);">{{ row.map50 }}</span>
                <span v-if="row.map50Delta" class="ml-1" style="color: #15803D;">{{ row.map50Delta }}</span>
              </td>
              <td class="h-12 px-3 font-mono whitespace-nowrap text-right">
                <span style="color: var(--c-ink);">{{ row.map5095 }}</span>
                <span v-if="row.map5095Delta" class="ml-1" style="color: #15803D;">{{ row.map5095Delta }}</span>
              </td>
              <td class="h-12 px-3 font-mono whitespace-nowrap text-right" style="color: var(--c-ink-2);">{{ row.fps }}</td>
              <td class="h-12 px-3 text-center whitespace-nowrap">
                <span class="px-2 py-0.5 rounded text-[12px] font-normal" :style="isCurrent(row) ? 'background-color: var(--c-primary-weak); color: var(--c-primary);' : 'background-color: #F1F5F9; color: #475569;'">{{ row.status }}</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import MetricStrip from '../components/MetricStrip.vue'
import DemoBadge from '../components/DemoBadge.vue'
import { getInferenceHealth } from '../services/detectionApi'

const selectedModel = ref('yolo11s')
const probing = ref(false)
// 后端 /api/health 返回的 model 段；未探测到前为 null，界面显示"未连接"
const engine = ref(null)

/**
 * 三个工程设计要点。检测网络本身是官方 YOLO11s 原版结构，未做任何改动，
 * 因此这里不展示"模型改进点"，只展示确实做过的工作：数据集、输入尺寸、判定规则。
 */
const innovations = [
  {
    tag: '数据层',
    badge: '多源数据集构建',
    title: '公开集 + 实拍卡口图 + 人工精标三源合集',
    desc: '训练集由三部分合并：公开数据集 BikesHelmets（含增强副本）、清洗后的 VOC 格式骑行头盔集，以及武汉本地卡口实拍图的人工精标子集。统一按 YOLO 格式标注为 helmet 与 no_helmet 两类，训练/验证/测试三集互不交叉。',
    stat1: '数据划分: 7631 训练 / 923 验证 / 859 测试',
    stat1Label: '标注类别',
    stat1Value: 'helmet、no_helmet'
  },
  {
    tag: '输入层',
    badge: '远距离小目标适配',
    title: '训练与推理统一按 960×960 分辨率',
    desc: '交通卡口多为高空远距离视角，头盔与头部在整图中占比很小。检测时将输入从 VOC 常见的 640 提升到 960，直接扩大目标在网络输入中的像素占比。args.yaml 中 imgsz=960，训练与推理配置一致。',
    stat1: 'imgsz: 960（训练与推理一致）',
    stat1Label: '输入尺寸放大',
    stat1Value: '640 → 960'
  },
  {
    tag: '决策层',
    badge: '从属关系推理',
    title: '多目标从属关系推理引擎',
    desc: '检测到的人员与车辆框先做从属关系归并（同一人可能对应多个重叠的车框），再叠加骑行姿态与佩戴状态判定，输出是否违规、是否需要人工复核。规则实现在后端 rules.py，避免把误检直接当成执法依据。',
    stat1: '实现位置: backend/app/rules.py',
    stat1Label: '跟踪算法',
    stat1Value: 'ByteTrack'
  }
]

/**
 * 性能表：本系统只部署了一版权重，因此只有一行真实实测记录。
 * 网络结构为官方 YOLO11s 原版（181 层），未做消融，故不存在对照行。
 * 参数量 9,428,566 取自训练日志 summary 行。
 * ⚠️ 计算量：训练日志里的 "21.5 GFLOPs" 是 Ultralytics 按**默认 imgsz=640** 打印的，
 *   不能配在 960×960 这一行上。此处取 960 输入下的实测值：
 *   get_flops(best.pt, imgsz=960) = 48.48 G（同一权重在 640 下为 21.55 G）。
 * mAP 取自 results.csv 最佳轮次（全局第 19 轮＝续训段第 9 轮）。
 */
const ablationRows = [
  { name: 'YOLO11s（本系统部署）', res: '960×960', params: '9.43 M', flops: '48.5 G', map50: '78.60%', map50Delta: '', map5095: '52.52%', map5095Delta: '', fps: '未实测', status: '当前部署', active: true }
]

// 概览条直接读"当前查看"的那一行，避免与下方表格出现两套数字
function toNumber(value) {
  return Number(String(value).replace(/[^\d.]/g, '')) || 0
}

/** 下拉里只有一版权重，对应表中唯一一行 */
const MODEL_TO_ROW = {
  yolo11s: 'YOLO11s（本系统部署）'
}

function isCurrent(row) {
  return row.name === MODEL_TO_ROW[selectedModel.value]
}

const activeRow = computed(() =>
  ablationRows.find(isCurrent) || ablationRows.find(row => row.active)
)

const kpiItems = computed(() => {
  const row = activeRow.value
  if (!row) return []
  const map50 = toNumber(row.map50)
  return [
    { label: '检出准确率 mAP@50', value: map50.toFixed(2), unit: '%', hint: '最佳轮次 Epoch 9', tone: 'success' },
    { label: '定位准确率 mAP@50-95', value: toNumber(row.map5095).toFixed(2), unit: '%', hint: '最佳轮次 Epoch 9' },
    // 项目未做过测速基准，接口也不提供该值，如实留空而不是填一个估计值
    { label: '推理速度', value: '未实测', hint: '项目内无测速记录' },
    { label: '模型参数量', value: row.params.replace(' M', ''), unit: 'M 参数', hint: '官方 YOLO11s 原版结构' }
  ]
})

/**
 * 切换的只是"本页查看哪一版评估数据"。
 * 后端目前只有推理与健康检查接口，没有模型权重热切换能力，
 * 所以这里不再假装"已在显存中重新加载完毕"。
 */
function switchModel() {
  const row = activeRow.value
  ElMessage.info(`已切换查看口径为「${row ? row.name : selectedModel.value}」，仅影响本页展示，不改变后端实际加载的权重`)
}

/** 重新探测引擎状态：走真实的 /api/health */
async function refreshEngineStatus(silent = false) {
  if (probing.value) return
  probing.value = true
  try {
    const health = await getInferenceHealth()
    engine.value = health.model ?? null
    const ready = engine.value?.ready === true
    if (silent) return
    if (ready) {
      ElMessage.success('检测引擎已就绪，推理服务可用')
    } else {
      ElMessage.warning(engine.value?.message || '检测引擎已连接，但模型尚未就绪')
    }
  } catch {
    engine.value = null
    if (!silent) {
      ElMessage.warning('未能连接检测引擎，请确认后端服务已启动（127.0.0.1:8000）')
    }
  } finally {
    probing.value = false
  }
}

/** 引擎状态行：全部来自后端真实返回 */
const engineStatusText = computed(() => {
  const info = engine.value
  if (!info) return '引擎状态: 未连接（请确认后端服务已启动）'
  if (info.ready !== true) {
    return `引擎状态: 未就绪 · ${info.message || info.reason || '原因未知'}`
  }
  const device = info.device === 'cpu' || info.device === undefined
    ? 'CPU'
    : `GPU:${info.device}`
  const weightName = String(info.weights_path || '').split(/[\\/]/).pop() || '—'
  const classes = [...(info.custom_classes || []), ...(info.context_classes || [])]
  return `引擎状态: 已就绪 · 推理设备: ${device} · 权重: ${weightName} · 类别: ${classes.join(' / ') || '—'}`
})

onMounted(() => {
  refreshEngineStatus(true)
})
</script>
