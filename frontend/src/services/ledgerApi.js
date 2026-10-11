// 台账（Ledger）接口封装
// 契约见 deliverables/db-migration/01-改造架构方案.md §4.1

import { http, cleanParams } from './http'

/**
 * 台账列表（服务端分页 + 服务端筛选）
 * @param {object} params page / page_size / status / camera_id / category /
 *   disposition_status / start_time / end_time / min_confidence / max_confidence /
 *   keyword / sort
 * @returns {Promise<{items:Array,total:number,page:number,page_size:number,pages:number}>}
 */
export async function fetchLedgerRecords(params = {}) {
  const { data } = await http.get('/ledger/records', { params: cleanParams(params) })
  return data
}

/** 单条详情（含 review_history / disposition / evidence_url / roi_url） */
export async function fetchLedgerRecord(id) {
  const { data } = await http.get(`/ledger/records/${encodeURIComponent(id)}`)
  return data
}

/** 复核：body { action: 'approve'|'reject'|'revoke', reviewer, badge?, remark?, category_override? } */
export async function submitReview(id, body) {
  const { data } = await http.post(`/ledger/records/${encodeURIComponent(id)}/review`, body)
  return data
}

/** 处置：body { action: 'notify'|'dispose'|'archive', operator, method?, remark? } */
export async function submitDisposition(id, body) {
  const { data } = await http.post(`/ledger/records/${encodeURIComponent(id)}/disposition`, body)
  return data
}

/** 批量复核：body { action, ids:[], reviewer, badge?, remark? } → { succeeded:[], failed:[{id,reason}] } */
export async function submitBatchReview(body) {
  const { data } = await http.post('/ledger/records/batch-review', body)
  return data
}
