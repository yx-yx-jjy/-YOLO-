/**
 * 置信度分档：全站唯一事实来源。
 *
 * 为什么要集中：这些阈值原先散在 5 处（stores/violations.js 的 CONFIDENCE_BANDS、
 * HistoryReview / DispositionModal / ViolationAnalysis 各自的 confidenceColor()、
 * 以及后端 stats_service.py 的 LOW_CONFIDENCE_THRESHOLD），改一处就会不一致。
 *
 * ⚠️ 阈值为什么不是常见的 70 / 90：
 * 本项目的「判定可信度」取的是**证据链中最弱环节**的检测置信度（rules.py 的 min()），
 * 而瓶颈是**小目标**——头部在 1920 宽的卡口画面里往往只有几十像素，检测置信度天然偏低。
 * 实测 861 条真实抓拍：P25 = 43%、中位数 52%、P75 = 63%、**最高仅 71%**。
 * 也就是说 90% 以上的记录根本不可能出现，旧的「<70 红 / 70-90 橙 / >90 绿」
 * 会让几乎所有记录落进红档，颜色完全失去区分度。
 *
 * 因此这里按该指标的真实分布**用四分位点标定**：P25 = 0.43、P75 = 0.63。
 * 效果是红 / 橙 / 绿 ≈ 25% / 50% / 25%，三档都有意义。
 * 若将来改动了置信度的计算口径（例如改成加权融合），这两个值必须跟着重新标定。
 *
 * 后端同源常量：backend/app/services/stats_service.py 的 LOW_CONFIDENCE_THRESHOLD。
 */

/** 分档阈值（含确认过的口径依据，改动前先读上面的说明） */
export const CONFIDENCE_CUTOFF = Object.freeze({
  mid: 0.43,
  high: 0.63,
})

/**
 * 分档的数值边界，给后端筛选用（confidence 按 2 位小数存储）。
 * 相邻两档不留缝隙也不重叠：low ≤ 0.42 / 0.43–0.62 / ≥ 0.63。
 */
export const CONFIDENCE_BANDS = Object.freeze({
  low: { max_confidence: Number((CONFIDENCE_CUTOFF.mid - 0.01).toFixed(2)) },
  mid: {
    min_confidence: CONFIDENCE_CUTOFF.mid,
    max_confidence: Number((CONFIDENCE_CUTOFF.high - 0.01).toFixed(2)),
  },
  high: { min_confidence: CONFIDENCE_CUTOFF.high },
})

/** 色板：与 DESIGN-SPEC 的置信度分档上色约定一致 */
const TONES = Object.freeze({
  low: { fg: '#B91C1C', bg: '#FEF2F2' },
  mid: { fg: '#B45309', bg: '#FFFBEB' },
  high: { fg: '#15803D', bg: '#F0FDF4' },
})

/** 中文档位标签 */
const LABELS = Object.freeze({ low: '低', mid: '中', high: '高' })

/** 档位含义（给 tooltip / 说明用） */
const HINTS = Object.freeze({
  low: '证据链中存在明显薄弱环节，建议优先复核',
  mid: '证据链基本成立，按常规流程复核',
  high: '证据链各环节都较可靠',
})

/**
 * @param {number|null|undefined} confidence 0~1
 * @returns {'low'|'mid'|'high'|null} 无法判定时返回 null
 */
export function confidenceBand(confidence) {
  if (confidence == null || Number.isNaN(Number(confidence))) return null
  const value = Number(confidence)
  if (value < CONFIDENCE_CUTOFF.mid) return 'low'
  if (value < CONFIDENCE_CUTOFF.high) return 'mid'
  return 'high'
}

/** 文字颜色（保留旧函数名语义，供既有调用点平滑替换） */
export function confidenceColor(confidence) {
  const band = confidenceBand(confidence)
  return band ? TONES[band].fg : 'var(--c-ink-3)'
}

/** 分档标签：'低' / '中' / '高' */
export function confidenceLabel(confidence) {
  const band = confidenceBand(confidence)
  return band ? LABELS[band] : '—'
}

/** 分档 chip 的样式：{ color, backgroundColor } */
export function confidenceChipStyle(confidence) {
  const band = confidenceBand(confidence)
  if (!band) return { color: 'var(--c-ink-3)', backgroundColor: 'var(--c-page)' }
  return { color: TONES[band].fg, backgroundColor: TONES[band].bg }
}

/** 档位说明，用于 title 提示 */
export function confidenceHint(confidence) {
  const band = confidenceBand(confidence)
  return band ? HINTS[band] : ''
}

/** 百分比展示：四舍五入到整数，未知返回 '—' */
export function confidencePercent(confidence) {
  if (confidence == null || Number.isNaN(Number(confidence))) return '—'
  return `${Math.round(Number(confidence) * 100)}%`
}
