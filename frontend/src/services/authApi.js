// 认证接口封装
// 契约见 deliverables/db-migration/01-改造架构方案.md §4.3

import { http } from './http'

/**
 * 登录
 * @returns {Promise<{ token:string, user:{ id, username, real_name, badge_number, role, department } }>}
 */
export async function login(username, password) {
  const { data } = await http.post('/auth/login', { username, password })
  return data
}
