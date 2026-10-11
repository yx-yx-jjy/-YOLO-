// 管理接口封装：用户 / 系统日志 / 卡口主数据
// 契约见 deliverables/db-migration/01-改造架构方案.md §4.3 §4.4 §4.5

import { http, cleanParams } from './http'

/** 用户列表：{ items:[User], total, page, page_size, pages }，User 字段为 last_login（非 last_login_at） */
export async function fetchUsers(params = {}) {
  const { data } = await http.get('/users', { params: cleanParams(params) })
  return data
}

/** 新建用户：body { username, real_name, badge_number, role, department, password } */
export async function createUser(body) {
  const { data } = await http.post('/users', body)
  return data
}

/** 冻结 / 解冻：body { status: 'active'|'disabled' } */
export async function updateUserStatus(id, status) {
  const { data } = await http.patch(`/users/${encodeURIComponent(id)}/status`, { status })
  return data
}

/** 重置密码（后端重置为 123456） */
export async function resetUserPassword(id) {
  const { data } = await http.post(`/users/${encodeURIComponent(id)}/reset-password`)
  return data
}

/** 系统操作日志：{ items:[Log], total, page, page_size, pages } */
export async function fetchSystemLogs(params = {}) {
  const { data } = await http.get('/system-logs', { params: cleanParams(params) })
  return data
}

/** 卡口主数据：{ items:[{ id, name, area, coords, heat_radius, active }] } */
export async function fetchCameras() {
  const { data } = await http.get('/cameras')
  return data
}
