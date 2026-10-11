// 统一 HTTP 客户端（全站 API 层入口）
//
// 约定：
//  - baseURL 固定走 `/api`，由 vite dev proxy 反代到后端 8000；不写死 localhost。
//  - 后端 DB 不可用时返回 HTTP 503 + { detail: { code, message, hint } }；
//    写接口未鉴权/凭证失效时返回 HTTP 401 + { detail: { code:"UNAUTHORIZED", message, hint } }。
//    这里统一把它们（以及其它后端结构化 detail）解析成中文友好提示，
//    并抛出可被页面捕获的 ApiError —— 绝不吞掉错误、绝不静默返回空数据。
//  - 时间戳一律本地时间字符串 `YYYY-MM-DD HH:MM:SS`，禁止 toISOString()（UTC 会早 8 小时）。

import axios from 'axios'

export const http = axios.create({
  baseURL: '/api',
  timeout: 30_000
})

/* ── 请求拦截器：附带登录令牌 ──
 * 6 个写接口（复核 / 处置 / 批量复核 / 新建用户 / 冻结解冻 / 重置密码）后端会校验，
 * 必须带上 `Authorization: Bearer <token>`；只读接口带上也无害，后端忽略。
 * 键名与 stores/auth.js 的 TOKEN_KEY 保持一致；此处**直读 sessionStorage**，
 * 不 import auth store（否则 auth → authApi → http 会形成循环依赖）。
 */
const AUTH_TOKEN_KEY = 'traffic.auth.token'

http.interceptors.request.use(config => {
  try {
    const token = sessionStorage.getItem(AUTH_TOKEN_KEY)
    if (token) {
      config.headers = config.headers || {}
      config.headers.Authorization = `Bearer ${token}`
    }
  } catch {
    // sessionStorage 不可用（隐私模式等）时按"无令牌"处理，不阻断请求
  }
  return config
})

/** 统一的 API 错误类型：页面用 try/catch 捕获，用 getApiErrorMessage 取中文文案 */
export class ApiError extends Error {
  constructor(message, { code = null, hint = '', status = null, cause = null } = {}) {
    super(message)
    this.name = 'ApiError'
    this.code = code
    this.hint = hint
    this.status = status
    this.cause = cause
  }
}

const DB_UNAVAILABLE_TEXT = '台账数据库暂不可用'
const DB_UNAVAILABLE_HINT = '请检查 backend/storage/traffic.db 是否被其它程序占用，或目录写权限'

const UNAUTHORIZED_TEXT = '登录状态已失效，请重新登录'
const UNAUTHORIZED_HINT = '请先登录，或检查令牌是否过期'

http.interceptors.response.use(
  response => response,
  error => {
    const status = error?.response?.status ?? null
    const detail = error?.response?.data?.detail

    let code = null
    let message = ''
    let hint = ''

    if (detail && typeof detail === 'object') {
      code = detail.code || null
      message = detail.message || ''
      hint = detail.hint || ''
    } else if (typeof detail === 'string') {
      message = detail
    }

    if (code === 'DB_UNAVAILABLE') {
      message = message || DB_UNAVAILABLE_TEXT
      hint = hint || DB_UNAVAILABLE_HINT
    }

    // 写接口鉴权失败：与 DB_UNAVAILABLE 并列处理，映射成可读中文提示。
    // 注意：本层只负责给出"明确提示"，**不做自动跳转登录页**——
    // 登录页自身请求失败时再跳登录页会形成跳转死循环，是否跳转由页面/team-lead 决定。
    if (code === 'UNAUTHORIZED' || status === 401) {
      message = message || UNAUTHORIZED_TEXT
      hint = hint || UNAUTHORIZED_HINT
    }

    if (!message) {
      if (error?.code === 'ERR_NETWORK') {
        message = '无法连接后端服务，请确认已启动（127.0.0.1:8000）'
      } else if (status === 404) {
        message = '请求的数据不存在（可能已被删除）'
      } else if (status === 409) {
        message = '当前状态不允许该操作'
      } else if (status >= 500) {
        message = '服务端处理失败，请稍后重试'
      } else {
        message = error?.message || '请求失败'
      }
    }

    return Promise.reject(new ApiError(message, { code, hint, status, cause: error }))
  }
)

/** 取中文错误文案（列表页错误态、ElMessage 都用它） */
export function getApiErrorMessage(error) {
  if (error instanceof ApiError) {
    return error.hint ? `${error.message}（${error.hint}）` : error.message
  }
  const detail = error?.response?.data?.detail
  if (detail && typeof detail === 'object' && detail.message) return detail.message
  if (typeof detail === 'string') return detail
  if (error?.code === 'ERR_NETWORK') return '无法连接后端服务，请确认已启动（127.0.0.1:8000）'
  return error?.message || '请求失败'
}

/**
 * 本地时间字符串。注意不要用 toISOString()——那是 UTC，
 * 在 GMT+8 下会把时间显示得比实际早 8 小时（本项目已踩过这个坑）。
 */
export function toLocalTimeString(date = new Date()) {
  const pad = value => String(value).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} `
    + `${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`
}

/** 去掉 undefined / null / 空串，避免把空参数塞进 query */
export function cleanParams(params = {}) {
  const out = {}
  Object.keys(params).forEach(key => {
    const value = params[key]
    if (value === undefined || value === null || value === '') return
    out[key] = value
  })
  return out
}
