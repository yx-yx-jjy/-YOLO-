<template>
  <div class="space-y-4">
    <!-- 顶部操作条 -->
    <div class="card flex items-center justify-between gap-3">
      <div>
        <h2 class="text-[16px] font-medium" style="color: var(--c-ink);">系统用户账号与权限管理</h2>
        <!-- 错误态不显示"共 0 个"（会误导为"没有用户"，实为"取不到数据"） -->
        <p class="text-[12px] font-normal mt-0.5" style="color: var(--c-ink-3);">
          共 {{ error ? '—' : total }} 个账号<template v-if="!error"> · 内部人员 {{ internalCount }} · 社会公众 {{ citizenCount }}</template>
        </p>
      </div>
      <button 
        @click="showAddDialog = true" 
        class="h-8 px-3 rounded-md text-[13px] font-normal text-white flex items-center gap-1.5 transition"
        style="background-color: var(--c-primary);"
        @mouseenter="$event.currentTarget.style.backgroundColor = '#4338CA'"
        @mouseleave="$event.currentTarget.style.backgroundColor = 'var(--c-primary)'"
      >
        <el-icon :size="14"><Plus /></el-icon>
        <span>新增执法账号</span>
      </button>
    </div>

    <!-- 用户管理表格 -->
    <div class="card !p-0 overflow-hidden">
      <div class="overflow-x-auto">
        <table class="w-full text-left text-[13px] table-fixed" style="color: var(--c-ink);">
          <colgroup>
            <col style="width: 120px;" />
            <col style="width: 130px;" />
            <col style="width: 160px;" />
            <col style="width: 160px;" />
            <col style="width: 120px;" />
            <col style="width: 110px;" />
            <col style="width: 160px;" />
            <col style="width: 150px;" />
          </colgroup>
          <thead>
            <tr style="background-color: var(--c-page); border-bottom: 1px solid var(--c-line);">
              <th class="h-12 px-3 text-[12px] font-normal whitespace-nowrap" style="color: #64748B; position: sticky; top: 0; background-color: var(--c-page);">用户编号</th>
              <th class="h-12 px-3 text-[12px] font-normal whitespace-nowrap" style="color: #64748B; position: sticky; top: 0; background-color: var(--c-page);">登录账号</th>
              <th class="h-12 px-3 text-[12px] font-normal whitespace-nowrap" style="color: #64748B; position: sticky; top: 0; background-color: var(--c-page);">真实姓名 (警号)</th>
              <th class="h-12 px-3 text-[12px] font-normal whitespace-nowrap" style="color: #64748B; position: sticky; top: 0; background-color: var(--c-page);">归属中队/部门</th>
              <th class="h-12 px-3 text-[12px] font-normal whitespace-nowrap" style="color: #64748B; position: sticky; top: 0; background-color: var(--c-page);">系统角色</th>
              <th class="h-12 px-3 text-[12px] font-normal whitespace-nowrap" style="color: #64748B; position: sticky; top: 0; background-color: var(--c-page);">账号状态</th>
              <th class="h-12 px-3 text-[12px] font-normal whitespace-nowrap" style="color: #64748B; position: sticky; top: 0; background-color: var(--c-page);">最近登录时间</th>
              <th class="h-12 px-3 text-[12px] font-normal whitespace-nowrap text-center" style="color: #64748B; position: sticky; top: 0; background-color: var(--c-page);">操作</th>
            </tr>
          </thead>
          <tbody>
            <template v-if="loading">
              <tr>
                <td colspan="8" class="p-0">
                  <div class="flex items-center justify-center gap-2 py-10 text-[13px]" style="color: var(--c-ink-3);">
                    <el-icon :size="16" class="is-loading"><Loading /></el-icon>
                    <span>正在加载用户列表…</span>
                  </div>
                </td>
              </tr>
            </template>

            <template v-else-if="error">
              <tr>
                <td colspan="8" class="p-0">
                  <EmptyState
                    variant="error"
                    icon="WarningFilled"
                    title="用户列表加载失败"
                    :description="errorText"
                    action-text="重试"
                    @action="fetchUserList"
                  />
                </td>
              </tr>
            </template>

            <template v-else-if="users.length === 0">
              <tr>
                <td colspan="8" class="p-0">
                  <EmptyState
                    icon="User"
                    title="暂无系统用户"
                    description="点击右上角「新增执法账号」创建第一个账号。"
                  />
                </td>
              </tr>
            </template>

            <template v-else>
              <template v-for="(user, index) in sortedUsers" :key="user.id">
                <!-- 分组行：角色与上一行不同时插入组标题 -->
                <tr v-if="index === 0 || sortedUsers[index - 1].role !== user.role" style="background-color: var(--c-page);">
                  <td colspan="8" class="py-2 px-3 whitespace-nowrap" style="border-bottom: 1px solid var(--c-line);">
                    <span class="text-[12px] font-medium" style="color: var(--c-ink-2);">{{ roleMeta(user.role).label }}</span>
                    <span class="text-[12px] font-mono ml-2" style="color: var(--c-ink-3);">{{ groupCount(user.role) }} 个</span>
                    <span class="text-[12px] ml-2" style="color: var(--c-ink-3);">· {{ roleMeta(user.role).groupHint }}</span>
                  </td>
                </tr>
              <tr
                class="h-12 align-middle"
                style="border-bottom: 1px solid var(--c-line);"
                @mouseenter="$event.currentTarget.style.backgroundColor = 'var(--c-page)'"
                @mouseleave="$event.currentTarget.style.backgroundColor = ''"
              >
                <td class="h-12 px-3 font-mono whitespace-nowrap" style="color: var(--c-ink-2);">#USR-{{ user.id }}</td>
                <td class="h-12 px-3 font-mono whitespace-nowrap" style="color: var(--c-ink);">{{ user.username }}</td>
                <td class="h-12 px-3 whitespace-nowrap">
                  <span class="font-medium" style="color: var(--c-ink);">{{ user.real_name }}</span>
                  <span class="text-[12px] font-mono ml-1" style="color: var(--c-ink-3);">({{ user.badge_number }})</span>
                </td>
                <td class="h-12 px-3 whitespace-nowrap" style="color: var(--c-ink-2);">{{ user.department }}</td>
                <td class="h-12 px-3 whitespace-nowrap">
                  <span
                    class="px-2 py-0.5 rounded text-[12px] font-normal whitespace-nowrap"
                    :style="roleMeta(user.role).chipStyle"
                  >{{ roleMeta(user.role).label }}</span>
                </td>
                <td class="h-12 px-3 whitespace-nowrap">
                  <span 
                    class="px-2 py-0.5 rounded text-[12px] font-normal whitespace-nowrap"
                    :style="user.status === 'active' 
                      ? 'background-color: #F0FDF4; color: #15803D;' 
                      : 'background-color: #FEF2F2; color: #B91C1C;'"
                  >
                    {{ user.status === 'active' ? '正常启用' : '已冻结' }}
                  </span>
                </td>
                <td class="h-12 px-3 font-mono whitespace-nowrap text-[12px]" style="color: var(--c-ink-3);">{{ user.last_login || '未登录' }}</td>
                <td class="h-12 px-3 text-center whitespace-nowrap space-x-1.5">
                  <button 
                    @click="toggleUserStatus(user)"
                    :disabled="actionPending === user.id"
                    class="h-7 px-2.5 rounded text-[12px] font-normal transition disabled:opacity-40 disabled:cursor-not-allowed"
                    :style="user.status === 'active' 
                      ? 'background-color: var(--c-surface); border: 1px solid var(--c-line); color: #B91C1C;' 
                      : 'background-color: var(--c-surface); border: 1px solid var(--c-line); color: #15803D;'"
                    @mouseenter="$event.currentTarget.style.backgroundColor = user.status === 'active' ? '#FEF2F2' : '#F0FDF4'"
                    @mouseleave="$event.currentTarget.style.backgroundColor = 'var(--c-surface)'"
                  >
                    {{ user.status === 'active' ? '冻结' : '解冻' }}
                  </button>
                  <button 
                    @click="resetPass(user)" 
                    :disabled="actionPending === user.id"
                    class="h-7 px-2.5 rounded text-[12px] font-normal transition disabled:opacity-40 disabled:cursor-not-allowed"
                    style="background-color: var(--c-surface); border: 1px solid var(--c-line); color: #334155;"
                    @mouseenter="$event.currentTarget.style.borderColor = 'var(--c-primary)'; $event.currentTarget.style.color = 'var(--c-primary)'"
                    @mouseleave="$event.currentTarget.style.borderColor = 'var(--c-line)'; $event.currentTarget.style.color = '#334155'"
                  >
                    重置密码
                  </button>
                </td>
              </tr>
              </template>
            </template>
          </tbody>
        </table>
      </div>
    </div>

    <!-- 弹窗：新增账号 -->
    <div v-if="showAddDialog" class="fixed inset-0 z-50 flex items-center justify-center p-4" style="background-color: rgba(15, 23, 42, 0.45);">
      <div class="card max-w-md w-full p-5 space-y-4" style="box-shadow: 0 4px 12px rgba(15, 23, 42, 0.08);">
        <h3 class="text-[14px] font-medium" style="color: var(--c-ink);">新增执法人员登录账号</h3>
        <div class="space-y-3 text-[13px]">
          <div>
            <label class="block text-[12px] mb-1" style="color: var(--c-ink-2);">登录用户名</label>
            <input 
              v-model="newUser.username" 
              type="text" 
              placeholder="例如 officer_wang" 
              class="w-full h-8 px-3 rounded-md text-[13px] focus:outline-none" 
              style="background-color: var(--c-surface); border: 1px solid var(--c-line); color: var(--c-ink);"
            />
          </div>
          <div>
            <label class="block text-[12px] mb-1" style="color: var(--c-ink-2);">真实姓名</label>
            <input 
              v-model="newUser.real_name" 
              type="text" 
              placeholder="例如 王建军 (警官)" 
              class="w-full h-8 px-3 rounded-md text-[13px] focus:outline-none" 
              style="background-color: var(--c-surface); border: 1px solid var(--c-line); color: var(--c-ink);"
            />
          </div>
          <div>
            <label class="block text-[12px] mb-1" style="color: var(--c-ink-2);">警号 / 工号</label>
            <input 
              v-model="newUser.badge_number" 
              type="text" 
              placeholder="例如 08433" 
              class="w-full h-8 px-3 rounded-md text-[13px] focus:outline-none" 
              style="background-color: var(--c-surface); border: 1px solid var(--c-line); color: var(--c-ink);"
            />
          </div>
          <div>
            <label class="block text-[12px] mb-1" style="color: var(--c-ink-2);">归属部门</label>
            <input 
              v-model="newUser.department" 
              type="text" 
              placeholder="交警支队一大队" 
              class="w-full h-8 px-3 rounded-md text-[13px] focus:outline-none" 
              style="background-color: var(--c-surface); border: 1px solid var(--c-line); color: var(--c-ink);"
            />
          </div>
        </div>
        <div class="flex justify-end gap-2 pt-2" style="border-top: 1px solid var(--c-line);">
          <button 
            @click="showAddDialog = false" 
            class="h-8 px-3 rounded-md text-[13px] font-normal"
            style="background-color: var(--c-surface); border: 1px solid var(--c-line); color: #334155;"
          >
            取消
          </button>
          <button 
            @click="addUser" 
            :disabled="creating"
            class="h-8 px-3 rounded-md text-[13px] font-normal text-white disabled:opacity-50 disabled:cursor-not-allowed"
            style="background-color: var(--c-primary);"
            @mouseenter="$event.currentTarget.style.backgroundColor = '#4338CA'"
            @mouseleave="$event.currentTarget.style.backgroundColor = 'var(--c-primary)'"
          >
            {{ creating ? '正在创建…' : '确认创建' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { fetchUsers, createUser, updateUserStatus, resetUserPassword } from '../../services/adminApi'
import { getApiErrorMessage } from '../../services/http'
import EmptyState from '../../components/EmptyState.vue'

const users = ref([])
const total = ref(0)
const loading = ref(false)
const error = ref(null)
const showAddDialog = ref(false)
const creating = ref(false)
const actionPending = ref(null)
const newUser = ref({ username: '', real_name: '', badge_number: '', department: '' })

const errorText = computed(() => getApiErrorMessage(error.value))

/* ── 角色元数据：本页唯一映射 ──
   原来这里是个二元三目（role === 'admin' ? '超级管理员' : '执勤执法人员'），
   只要 role 不是 admin 就一律显示「执勤执法人员」——于是 role=citizen 的
   社会公众账号（陈先生 / 赵女士）被错标成执法人员。后端 users.role 的取值是
   officer | admin | citizen（见 db/migrations/0002_citizen.py），改为查表。

   ⚠️ 角色**名称**必须与 stores/auth.js 的 roleLabel 保持一致（那里是全站顶栏/登录页
   用的叫法：系统管理员 / 执勤执法人员 / 市民用户）。本表只额外带了 chip 配色与分组说明。 */
const ROLE_META = {
  admin: {
    label: '系统管理员',
    groupHint: '系统运维与账号管理',
    chipStyle: 'background-color: var(--c-primary-weak); color: var(--c-primary);',
  },
  officer: {
    label: '执勤执法人员',
    groupHint: '路面执法与违规复核',
    chipStyle: 'background-color: #F1F5F9; color: #334155;',
  },
  citizen: {
    label: '市民用户',
    groupHint: '公众服务端账号，仅可查看本人车辆相关线索',
    chipStyle: 'background-color: #F1F5F9; color: #64748B;',
  },
}

/** 分组顺序：权限从高到低 */
const ROLE_ORDER = ['admin', 'officer', 'citizen']

function roleMeta(role) {
  return (
    ROLE_META[role] || {
      label: role || '未知角色',
      groupHint: '',
      chipStyle: 'background-color: #F1F5F9; color: #64748B;',
    }
  )
}

const groupCount = (role) => users.value.filter((user) => user.role === role).length

/** 按角色分组展示；同组内按用户编号升序 */
const sortedUsers = computed(() =>
  [...users.value].sort((a, b) => {
    const ai = ROLE_ORDER.indexOf(a.role)
    const bi = ROLE_ORDER.indexOf(b.role)
    return ((ai < 0 ? 99 : ai) - (bi < 0 ? 99 : bi)) || a.id - b.id
  })
)

const internalCount = computed(
  () => users.value.filter((user) => user.role === 'admin' || user.role === 'officer').length
)
const citizenCount = computed(() => users.value.filter((user) => user.role === 'citizen').length)

async function fetchUserList() {
  loading.value = true
  error.value = null
  try {
    const data = await fetchUsers({ page: 1, page_size: 100 })
    users.value = Array.isArray(data.items) ? data.items : []
    total.value = data.total ?? users.value.length
  } catch (err) {
    error.value = err
    users.value = []
    total.value = 0
  } finally {
    loading.value = false
  }
}

async function toggleUserStatus(user) {
  const nextStatus = user.status === 'active' ? 'disabled' : 'active'
  actionPending.value = user.id
  try {
    const updated = await updateUserStatus(user.id, nextStatus)
    // 用后端返回值更新本地行（也已重新拉取，避免只改本地状态刷新就回滚）
    if (updated && typeof updated === 'object') {
      Object.assign(user, updated)
    } else {
      user.status = nextStatus
    }
    ElMessage.success(`已${nextStatus === 'active' ? '解冻' : '冻结'}用户 ${user.real_name} 的账号`)
  } catch (err) {
    ElMessage.error(`账号状态更新失败：${getApiErrorMessage(err)}`)
  } finally {
    actionPending.value = null
  }
}

async function resetPass(user) {
  actionPending.value = user.id
  try {
    await resetUserPassword(user.id)
    ElMessage.success(`已将用户 ${user.real_name} 的密码重置为初始密码: 123456`)
  } catch (err) {
    ElMessage.error(`重置密码失败：${getApiErrorMessage(err)}`)
  } finally {
    actionPending.value = null
  }
}

async function addUser() {
  if (!newUser.value.username || !newUser.value.real_name) {
    ElMessage.warning('请填写完整的账号与姓名！')
    return
  }
  creating.value = true
  try {
    await createUser({
      username: newUser.value.username,
      real_name: newUser.value.real_name,
      badge_number: newUser.value.badge_number || '08499',
      role: 'officer',
      department: newUser.value.department || '交警支队',
      password: '123456'
    })
    showAddDialog.value = false
    newUser.value = { username: '', real_name: '', badge_number: '', department: '' }
    ElMessage.success('执法人员账号创建成功！（初始密码 123456）')
    await fetchUserList()
  } catch (err) {
    ElMessage.error(`账号创建失败：${getApiErrorMessage(err)}`)
  } finally {
    creating.value = false
  }
}

onMounted(fetchUserList)
</script>
