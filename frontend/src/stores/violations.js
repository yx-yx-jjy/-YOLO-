import { defineStore } from 'pinia'
import {
  fetchLedgerRecords,
  fetchLedgerRecord,
  submitReview,
  submitDisposition,
  submitBatchReview
} from '../services/ledgerApi'
import { fetchOverview, fetchByCamera } from '../services/statsApi'
import { toLocalTimeString } from '../services/http'
import { CONFIDENCE_BANDS } from '../utils/confidence'

/**
 * 处置闭环状态（复核入卷之后的"后半程"）。
 * 之前系统到"已确认入卷"就断了，处置状态机把 告知 → 处理 → 归档 补上。
 */
export const DISPOSITION_LABELS = {
  to_notify: '待告知',
  notified: '已告知',
  disposed: '已处置',
  archived: '已归档'
}

/** 处置状态徽章配色（台账页与处置工作台共用，避免两处写两套） */
export const DISPOSITION_BADGES = {
  to_notify: { text: '待告知', color: '#B45309', bg: '#FFFBEB' },
  notified: { text: '已告知', color: '#1D4ED8', bg: '#EFF6FF' },
  disposed: { text: '已处置', color: '#15803D', bg: '#F0FDF4' },
  archived: { text: '已归档', color: '#475569', bg: '#F1F5F9' }
}

/** 处置方式候选：与《道路交通安全法》对非机动车违法的常见处理口径一致 */
export const DISPOSITION_METHODS = ['警告处罚', '罚款处罚', '安全教育学习', '现场拦查处置']

const DEFAULT_PAGE_SIZE = 10
const EXPORT_PAGE_SIZE = 100
// 导出循环翻页的安全上限：防止 pages 异常时无限翻页
const EXPORT_MAX_PAGES = 500

/** 置信度分档 → 接口 min_confidence / max_confidence（分档口径与全站一致：<70% / 70–90% / >90%） */
// CONFIDENCE_BANDS 已移至 utils/confidence.js（全站唯一事实来源）。
// 阈值按「判定可信度」的真实分布用四分位点标定，依据见那个文件的头部注释。

/** 时间范围 → 起始本地时间字符串（含边界）；'all' 不带此参数 */
const RANGE_HOURS = { '24h': 24, '7d': 24 * 7 }

function rangeStartTime(range) {
  const hours = RANGE_HOURS[range]
  if (!hours) return undefined
  return toLocalTimeString(new Date(Date.now() - hours * 3600 * 1000))
}

const EMPTY_DISPOSITION = {
  status: null,
  method: '',
  notified_at: '',
  disposed_at: '',
  handler: '',
  remark: '',
  history: []
}

/** 后端记录统一补全，避免页面取值时炸掉（details / review_history / disposition） */
function normalizeDisposition(record) {
  const source = record && record.disposition
  if (!source || typeof source !== 'object') {
    return { ...EMPTY_DISPOSITION, history: [] }
  }
  return {
    ...EMPTY_DISPOSITION,
    ...source,
    history: Array.isArray(source.history) ? [...source.history] : []
  }
}

function normalizeRecord(record) {
  if (!record || typeof record !== 'object') return record
  return {
    ...record,
    details: record.details || {},
    review_history: Array.isArray(record.review_history) ? record.review_history : [],
    disposition: normalizeDisposition(record)
  }
}

export function describeCategory() {
  return '未按规定佩戴安全头盔'
}

export const useViolationStore = defineStore('violations', {
  state: () => ({
    /* ── 台账列表：服务端分页，records 即"当前页" ── */
    records: [],
    total: 0,
    page: 1,
    pageSize: DEFAULT_PAGE_SIZE,
    pages: 1,
    listLoading: false,
    listError: null,

    /* ── 大屏 / 摄像头页的"最新若干条"，独立于台账分页 ── */
    recentRecords: [],
    recentLoading: false,
    recentError: null,

    /* ── 摘要统计：唯一来源是 /api/stats/overview ── */
    overview: null,
    overviewLoading: false,
    overviewError: null,

    /** 按卡口聚合（大屏地图热力 / TOP 榜） */
    byCamera: [],
    byCameraError: null,

    selectedRecord: null,
    isModalOpen: false,

    /* ── 筛选条件（全部作为请求参数传给后端，不在前端过滤全量） ── */
    filterStatus: 'all', // 'all' | 'pending' | 'approved' | 'rejected'
    filterCategory: 'all', // 'all' | 'helmet'
    keyword: '',
    timeRange: 'all', // 'all' | '24h' | '7d'
    confidenceBand: 'all', // 'all' | 'low' | 'mid' | 'high'
    dispositionStatus: 'all' // 'all' | 'to_notify' | 'notified' | 'disposed' | 'archived'
  }),
  getters: {
    /** 兼容旧引用：当前页记录 */
    filteredRecords: (state) => state.records,

    /** 摘要未就绪时返回 null，让界面显示「—」而不是假装是 0 */
    pendingCount: (state) => (state.overview ? state.overview.status.pending : null),
    approvedCount: (state) => (state.overview ? state.overview.status.approved : null),
    rejectedCount: (state) => (state.overview ? state.overview.status.rejected : null),
    reviewedCount: (state) => (
      state.overview ? state.overview.status.approved + state.overview.status.rejected : null
    ),
    totalRecords: (state) => (state.overview ? state.overview.total : null),

    toNotifyCount: (state) => (state.overview ? state.overview.disposition.to_notify : null),
    notifiedCount: (state) => (state.overview ? state.overview.disposition.notified : null),
    disposedCount: (state) => (state.overview ? state.overview.disposition.disposed : null),
    archivedCount: (state) => (state.overview ? state.overview.disposition.archived : null),
    /** 待处置 = 已入卷但还没走完处理流程（待告知 + 已告知未处理） */
    pendingDispositionCount: (state) => (
      state.overview
        ? state.overview.disposition.to_notify + state.overview.disposition.notified
        : null
    ),
    reviewRate: (state) => (state.overview ? state.overview.review_rate : null),
    dispositionRate: (state) => (state.overview ? state.overview.disposition_rate : null),
    lowConfidenceCount: (state) => (state.overview ? state.overview.low_confidence : null),
    avgConfidence: (state) => (state.overview ? state.overview.avg_confidence : null),

    /** 兼容旧 MetricCards 的 stats 形状 */
    stats: (state) => ({
      totalVehicles: state.overview ? state.overview.total : null,
      noHelmetCount: state.overview ? state.overview.total : null,
      complianceRate: null
    })
  },
  actions: {
    /** 组装列表请求参数：筛选条件 + 分页 */
    buildListParams() {
      const band = CONFIDENCE_BANDS[this.confidenceBand] || {}
      return {
        page: this.page,
        page_size: this.pageSize,
        status: this.filterStatus !== 'all' ? this.filterStatus : undefined,
        category: this.filterCategory !== 'all' ? this.filterCategory : undefined,
        disposition_status: this.dispositionStatus !== 'all' ? this.dispositionStatus : undefined,
        keyword: this.keyword.trim() || undefined,
        start_time: rangeStartTime(this.timeRange),
        min_confidence: band.min_confidence,
        max_confidence: band.max_confidence,
        sort: 'capture_time_desc'
      }
    },

    /* ── 台账列表 ── */
    async fetchRecords() {
      this.listLoading = true
      this.listError = null
      try {
        const data = await fetchLedgerRecords(this.buildListParams())
        this.records = Array.isArray(data.items) ? data.items.map(normalizeRecord) : []
        this.total = data.total ?? 0
        this.page = data.page ?? this.page
        this.pageSize = data.page_size ?? this.pageSize
        this.pages = Math.max(1, data.pages ?? 1)
      } catch (error) {
        // 失败时清空列表并保留错误：页面据此渲染错误态，而不是空白表格 / 0 条
        this.listError = error
        this.records = []
        this.total = 0
        this.pages = 1
      } finally {
        this.listLoading = false
      }
    },

    /* ── 大屏 / 摄像头页最新记录 ── */
    async fetchRecentRecords(limit = 12) {
      this.recentLoading = true
      this.recentError = null
      try {
        const data = await fetchLedgerRecords({ page: 1, page_size: limit, sort: 'capture_time_desc' })
        this.recentRecords = Array.isArray(data.items) ? data.items.map(normalizeRecord) : []
      } catch (error) {
        this.recentError = error
        this.recentRecords = []
      } finally {
        this.recentLoading = false
      }
    },

    /* ── 摘要统计 ── */
    async fetchOverview() {
      this.overviewLoading = true
      this.overviewError = null
      try {
        this.overview = await fetchOverview()
      } catch (error) {
        this.overviewError = error
        this.overview = null
      } finally {
        this.overviewLoading = false
      }
    },

    /* ── 按卡口聚合 ── */
    async fetchByCamera(range = '24h') {
      this.byCameraError = null
      try {
        const data = await fetchByCamera(range)
        this.byCamera = Array.isArray(data.items) ? data.items : []
      } catch (error) {
        this.byCameraError = error
        this.byCamera = []
      }
    },

    /** 台账页与摘要一起刷新（失败不互相牵连） */
    async refreshAll() {
      await Promise.allSettled([this.fetchRecords(), this.fetchOverview()])
    },

    /** 大屏/摄像头页刷新入口 */
    async refreshDashboard() {
      await Promise.allSettled([
        this.fetchOverview(),
        this.fetchRecentRecords(12),
        this.fetchByCamera('24h')
      ])
    },

    /* ── 分页 ── */
    async setPage(target) {
      this.page = Math.max(1, target)
      await this.fetchRecords()
    },
    async setPageSize(size) {
      this.pageSize = size
      this.page = 1
      await this.fetchRecords()
    },
    /** 筛选条件变化后从第一页重新拉取 */
    async applyFilters() {
      this.page = 1
      await this.fetchRecords()
    },
    resetFilters() {
      this.filterStatus = 'all'
      this.filterCategory = 'all'
      this.keyword = ''
      this.timeRange = 'all'
      this.confidenceBand = 'all'
      this.dispositionStatus = 'all'
    },

    /* ── 复核 / 处置：一律调后端落库，再用返回值更新本地项 ── */
    applyUpdatedRecord(record) {
      if (!record) return
      const next = normalizeRecord(record)
      const index = this.records.findIndex(item => item.id === next.id)
      if (index !== -1) this.records.splice(index, 1, next)
      const recentIndex = this.recentRecords.findIndex(item => item.id === next.id)
      if (recentIndex !== -1) this.recentRecords.splice(recentIndex, 1, next)
      if (this.selectedRecord && this.selectedRecord.id === next.id) this.selectedRecord = next
    },

    /**
     * 复核动作统一出口。
     * 注意：这里不再在前端拼 review_remark / push review_history —— 留给后端落库，
     * 返回的 Record 已带最新 review_history（只增不覆盖）。
     */
    async submitReviewAction(id, body) {
      const updated = await submitReview(id, body)
      this.applyUpdatedRecord(updated)
      await Promise.allSettled([this.fetchRecords(), this.fetchOverview()])
      return updated
    },

    // 人工复核：通过（确认入卷）。categoryOverride 对应接口的 category_override。
    async approveRecord(id, reviewerName, remark = '', reviewerBadge = '', categoryOverride = null) {
      return this.submitReviewAction(id, {
        action: 'approve',
        reviewer: reviewerName,
        badge: reviewerBadge || '',
        remark: remark || '',
        category_override: categoryOverride || null
      })
    },
    // 人工复核：驳回（误报剔除）
    async rejectRecord(id, reviewerName, remark = '', reviewerBadge = '') {
      return this.submitReviewAction(id, {
        action: 'reject',
        reviewer: reviewerName,
        badge: reviewerBadge || '',
        remark: remark || ''
      })
    },
    // 撤销复核：退回"待人工复核"，原判定与撤销理由都留在后端轨迹里
    async revokeReview(id, reviewerName, remark, reviewerBadge = '') {
      return this.submitReviewAction(id, {
        action: 'revoke',
        reviewer: reviewerName,
        badge: reviewerBadge || '',
        remark: remark || ''
      })
    },

    /** 批量复核：走后端 batch-review，返回 { succeeded, failed } */
    async batchReview(action, ids, reviewer, badge = '', remark = '') {
      const result = await submitBatchReview({ action, ids, reviewer, badge, remark })
      await Promise.allSettled([this.fetchRecords(), this.fetchOverview()])
      return result
    },

    async submitDispositionAction(id, body) {
      const updated = await submitDisposition(id, body)
      this.applyUpdatedRecord(updated)
      await Promise.allSettled([this.fetchRecords(), this.fetchOverview()])
      return updated
    },

    /** 告知当事人：待告知 → 已告知 */
    async markNotified(id, operator, remark = '') {
      return this.submitDispositionAction(id, {
        action: 'notify',
        operator,
        remark: remark || ''
      })
    },
    /** 作出处理：→ 已处置（此前未告知的由后端补轨迹，状态链不留空档） */
    async markDisposed(id, operator, method, remark = '') {
      return this.submitDispositionAction(id, {
        action: 'dispose',
        operator,
        method: method || '',
        remark: remark || ''
      })
    },
    /** 结案归档：→ 已归档 */
    async archiveDisposition(id, operator, remark = '') {
      return this.submitDispositionAction(id, {
        action: 'archive',
        operator,
        remark: remark || ''
      })
    },

    /* ── 证据单 ── */
    async openEvidenceModal(record) {
      if (!record) return
      this.selectedRecord = normalizeRecord(record)
      this.isModalOpen = true
      // 列表项可能不含完整轨迹/图片地址，打开后补拉一次详情
      try {
        const detail = await fetchLedgerRecord(record.id)
        if (this.isModalOpen && this.selectedRecord && this.selectedRecord.id === record.id) {
          this.selectedRecord = normalizeRecord(detail)
        }
      } catch {
        // 详情补拉失败不影响弹窗（列表项已带核心字段），不阻塞复核操作
      }
    },
    closeEvidenceModal() {
      this.isModalOpen = false
      this.selectedRecord = null
    },

    /**
     * 离线/实时检测事件现在由后端在任务完成时并入同一台账（架构稿 R3），
     * 前端不再自行造记录 —— 这里只刷新，把后端已落库的记录取回来。
     */
    async addInferenceViolation() {
      await this.refreshAll()
      return null
    },

    /**
     * 导出 CSV：覆盖"筛选后的全部数据"而不是当前页。
     * 方案：按 page_size=100（契约上限）循环翻页拉全量后再拼 CSV。
     * 理由：契约把 page_size 上限锁在 100，循环翻页不依赖后端支持超大 page_size，
     * 且每次只回一页、服务端内存可控；翻页带安全上限，避免 pages 异常时死循环。
     * @returns {Promise<number>} 实际导出条数
     */
    async exportRecordsToCSV() {
      const headers = ["违规编号", "发生时间", "卡口", "目标追踪ID", "违规类型", "AI置信度", "复核状态", "复核人", "复核时间", "复核意见", "处置状态", "处置方式", "处置时间", "处置人"]
      const baseParams = this.buildListParams()
      const collected = []
      let page = 1
      let pages = 1

      do {
        const data = await fetchLedgerRecords({ ...baseParams, page, page_size: EXPORT_PAGE_SIZE })
        collected.push(...(Array.isArray(data.items) ? data.items : []))
        pages = Math.max(1, data.pages ?? 1)
        page += 1
      } while (page <= pages && page <= EXPORT_MAX_PAGES)

      const rows = collected.map(record => {
        const d = record.disposition || {}
        return [
          record.id,
          record.capture_time,
          record.camera_id,
          `#${record.track_id}`,
          `"${record.violation_type}"`,
          record.confidence,
          record.status === 'approved' ? '已确认入卷' : (record.status === 'rejected' ? '误报已剔除' : '待人工复核'),
          record.reviewer || '未审核',
          record.review_time || '-',
          `"${record.review_remark || '-'}"`,
          d.status ? (DISPOSITION_LABELS[d.status] || d.status) : '未进入处置',
          d.method || '-',
          d.disposed_at || d.notified_at || '-',
          d.handler || '-'
        ]
      })

      const csvContent = "\uFEFF" + [headers.join(","), ...rows.map(e => e.join(","))].join("\n")
      const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" })
      const url = URL.createObjectURL(blob)
      const link = document.createElement("a")
      link.setAttribute("href", url)
      link.setAttribute("download", `非机动车违规取证台账_${toLocalTimeString().slice(0, 10)}.csv`)
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
      URL.revokeObjectURL(url)
      return rows.length
    }
  }
})
