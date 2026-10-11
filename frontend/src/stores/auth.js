import { defineStore } from 'pinia'
import { login as loginApi } from '../services/authApi'

// token 存 sessionStorage：刷新不丢、关标签页即清。
// 不再写死假 token 字符串——token 由后端 /api/auth/login 下发。
const TOKEN_KEY = 'traffic.auth.token'
const USER_KEY = 'traffic.auth.user'

function readStoredUser() {
  try {
    const raw = sessionStorage.getItem(USER_KEY)
    return raw ? JSON.parse(raw) : null
  } catch {
    return null
  }
}

export const useAuthStore = defineStore('auth', {
  state: () => ({
    currentUser: readStoredUser(),
    token: sessionStorage.getItem(TOKEN_KEY) || null,
    isLoggedIn: Boolean(sessionStorage.getItem(TOKEN_KEY) && readStoredUser())
  }),
  getters: {
    isAdmin: (state) => state.currentUser?.role === 'admin',
    isOfficer: (state) => state.currentUser?.role === 'officer',
    /** 群众端演示账号：与执法账号分开，不能拿警察账号去看市民记录 */
    isCitizen: (state) => state.currentUser?.role === 'citizen',
    roleLabel: (state) => ({
      admin: '系统管理员',
      officer: '执勤执法人员',
      citizen: '市民用户'
    })[state.currentUser?.role] || '未登录'
  },
  actions: {
    /**
     * 登录：角色一律以**后端返回的 user.role 为准**。
     * 登录页那个"执勤/管理员"按钮只是决定用哪个演示账号，不再决定权限，
     * 否则会出现"用警官账号登录却拿到管理员权限"。
     */
    async login(username, password) {
      const { token, user } = await loginApi(username, password)
      if (!token || !user) {
        throw new Error('登录响应缺少 token 或 user')
      }
      this.token = token
      this.currentUser = user
      this.isLoggedIn = true
      sessionStorage.setItem(TOKEN_KEY, token)
      sessionStorage.setItem(USER_KEY, JSON.stringify(user))
      return user
    },

    /**
     * 【演示开关】仅本地切换身份，不具备真实鉴权意义。
     * 后端目前未做接口级权限校验，这里只是把当前用户的 role 改成 admin/officer，
     * 用于演示侧边栏「系统控制台」的显隐。生产构建里不出现该入口。
     */
    switchRole(role) {
      if (!this.currentUser) return
      const nextRole = role === 'admin' ? 'admin' : 'officer'
      this.currentUser = { ...this.currentUser, role: nextRole }
      sessionStorage.setItem(USER_KEY, JSON.stringify(this.currentUser))
    },

    logout() {
      this.isLoggedIn = false
      this.currentUser = null
      this.token = null
      sessionStorage.removeItem(TOKEN_KEY)
      sessionStorage.removeItem(USER_KEY)
    },

    updatePassword() {
      return true
    }
  }
})
