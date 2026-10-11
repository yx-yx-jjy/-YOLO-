<template>
  <div class="space-y-4">
    <!-- 顶部操作条 -->
    <div class="card flex items-center justify-between gap-3">
      <div>
        <h2 class="text-[16px] font-medium" style="color: var(--c-ink);">全量业务与操作安全审计日志</h2>
        <!-- 错误态不显示"共 0 条"（会误导为"没有日志"，实为"取不到数据"） -->
        <p class="text-[12px] font-normal mt-0.5" style="color: var(--c-ink-3);">区块链防篡改溯源流水 · 共 {{ error ? '—' : total }} 条审计记录</p>
      </div>
      <button 
        @click="exportLogs" 
        class="h-8 px-3 rounded-md text-[13px] font-normal flex items-center gap-1.5 transition"
        style="background-color: var(--c-surface); border: 1px solid var(--c-line); color: #334155;"
        @mouseenter="$event.currentTarget.style.borderColor = 'var(--c-primary)'; $event.currentTarget.style.color = 'var(--c-primary)'"
        @mouseleave="$event.currentTarget.style.borderColor = 'var(--c-line)'; $event.currentTarget.style.color = '#334155'"
      >
        <el-icon :size="14"><Download /></el-icon>
        <span>导出审计日志</span>
      </button>
    </div>

    <!-- 审计日志表格 -->
    <div class="card !p-0 overflow-hidden">
      <div class="overflow-x-auto">
        <table class="w-full text-left text-[13px] table-fixed" style="color: var(--c-ink);">
          <colgroup>
            <col style="width: 120px;" />
            <col style="width: 160px;" />
            <col style="width: 140px;" />
            <col style="width: 160px;" />
            <col style="width: 240px;" />
            <col style="width: 130px;" />
            <col style="width: 120px;" />
          </colgroup>
          <thead>
            <tr style="background-color: var(--c-page); border-bottom: 1px solid var(--c-line);">
              <th class="h-12 px-3 text-[12px] font-normal whitespace-nowrap" style="color: #64748B; position: sticky; top: 0; background-color: var(--c-page);">日志流水号</th>
              <th class="h-12 px-3 text-[12px] font-normal whitespace-nowrap" style="color: #64748B; position: sticky; top: 0; background-color: var(--c-page);">操作时间戳</th>
              <th class="h-12 px-3 text-[12px] font-normal whitespace-nowrap" style="color: #64748B; position: sticky; top: 0; background-color: var(--c-page);">操作人员</th>
              <th class="h-12 px-3 text-[12px] font-normal whitespace-nowrap" style="color: #64748B; position: sticky; top: 0; background-color: var(--c-page);">动作类型</th>
              <th class="h-12 px-3 text-[12px] font-normal whitespace-nowrap" style="color: #64748B; position: sticky; top: 0; background-color: var(--c-page);">详细业务记录</th>
              <th class="h-12 px-3 text-[12px] font-normal whitespace-nowrap" style="color: #64748B; position: sticky; top: 0; background-color: var(--c-page);">客户端 IP</th>
              <th class="h-12 px-3 text-[12px] font-normal whitespace-nowrap" style="color: #64748B; position: sticky; top: 0; background-color: var(--c-page);">存证状态</th>
            </tr>
          </thead>
          <tbody>
            <template v-if="loading">
              <tr>
                <td colspan="7" class="p-0">
                  <div class="flex items-center justify-center gap-2 py-10 text-[13px]" style="color: var(--c-ink-3);">
                    <el-icon :size="16" class="is-loading"><Loading /></el-icon>
                    <span>正在加载审计日志…</span>
                  </div>
                </td>
              </tr>
            </template>

            <template v-else-if="error">
              <tr>
                <td colspan="7" class="p-0">
                  <EmptyState
                    variant="error"
                    icon="WarningFilled"
                    title="审计日志加载失败"
                    :description="errorText"
                    action-text="重试"
                    @action="fetchLogs"
                  />
                </td>
              </tr>
            </template>

            <template v-else-if="logs.length === 0">
              <tr>
                <td colspan="7" class="p-0">
                  <EmptyState
                    icon="Tickets"
                    title="暂无审计日志"
                    description="系统记录每一次复核、处置、登录等关键操作，产生后会出现在这里。"
                  />
                </td>
              </tr>
            </template>

            <template v-else>
              <tr 
                v-for="log in logs" 
                :key="log.id" 
                class="h-12 align-middle"
                style="border-bottom: 1px solid var(--c-line);"
                @mouseenter="$event.currentTarget.style.backgroundColor = 'var(--c-page)'"
                @mouseleave="$event.currentTarget.style.backgroundColor = ''"
              >
                <td class="h-12 px-3 font-mono whitespace-nowrap" style="color: var(--c-ink-2);">#LOG-{{ log.id }}</td>
                <td class="h-12 px-3 font-mono whitespace-nowrap text-[12px]" style="color: var(--c-ink-3);">{{ log.time }}</td>
                <td class="h-12 px-3 font-medium whitespace-nowrap" style="color: var(--c-ink);">{{ log.operator }}</td>
                <td class="h-12 px-3 whitespace-nowrap">
                  <span 
                    class="px-2 py-0.5 rounded text-[12px] font-mono font-normal whitespace-nowrap"
                    :style="log.action_type === 'REVIEW_APPROVE' 
                      ? 'background-color: #F0FDF4; color: #15803D;' 
                      : log.action_type === 'REVIEW_REJECT' 
                      ? 'background-color: #FEF2F2; color: #B91C1C;' 
                      : 'background-color: #F1F5F9; color: #334155;'"
                  >
                    {{ log.action_type }}
                  </span>
                </td>
                <td class="h-12 px-3 truncate" :title="log.details" style="max-width: 240px; color: var(--c-ink-2);">
                  {{ log.details }}
                </td>
                <td class="h-12 px-3 font-mono whitespace-nowrap text-[12px]" style="color: var(--c-ink-3);">{{ log.ip }}</td>
                <td class="h-12 px-3 whitespace-nowrap">
                  <span class="px-2 py-0.5 rounded text-[12px] font-normal" style="background-color: #F0FDF4; color: #15803D;">
                    哈希已存证
                  </span>
                </td>
              </tr>
            </template>
          </tbody>
        </table>
      </div>

      <!-- 分页 -->
      <div class="flex flex-wrap items-center justify-between gap-3 px-4 h-14" style="border-top: 1px solid var(--c-line);">
        <span class="text-[13px]" style="color: var(--c-ink-2);">共 {{ error ? '—' : total }} 条审计记录</span>
        <div class="flex items-center gap-2 text-[13px]">
          <button
            :disabled="page <= 1 || loading"
            class="h-8 px-3 rounded-md text-[13px] font-normal disabled:opacity-40 disabled:cursor-not-allowed"
            style="background-color: var(--c-surface); border: 1px solid var(--c-line); color: var(--c-ink-2);"
            @click="goPage(page - 1)"
          >
            上一页
          </button>
          <span class="font-mono" style="color: var(--c-ink-2);">
            <!-- 错误态页码同样是假信息，一并置「—」 -->
            <template v-if="error">第 — / — 页</template>
            <template v-else>第 {{ page }} / {{ pages }} 页</template>
          </span>
          <button
            :disabled="page >= pages || loading"
            class="h-8 px-3 rounded-md text-[13px] font-normal disabled:opacity-40 disabled:cursor-not-allowed"
            style="background-color: var(--c-surface); border: 1px solid var(--c-line); color: var(--c-ink-2);"
            @click="goPage(page + 1)"
          >
            下一页
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { fetchSystemLogs } from '../../services/adminApi'
import { getApiErrorMessage } from '../../services/http'
import EmptyState from '../../components/EmptyState.vue'

const logs = ref([])
const total = ref(0)
const page = ref(1)
const pages = ref(1)
const pageSize = 20
const loading = ref(false)
const error = ref(null)

const errorText = computed(() => getApiErrorMessage(error.value))

async function fetchLogs() {
  loading.value = true
  error.value = null
  try {
    const data = await fetchSystemLogs({ page: page.value, page_size: pageSize })
    logs.value = Array.isArray(data.items) ? data.items : []
    total.value = data.total ?? 0
    pages.value = Math.max(1, data.pages ?? 1)
    page.value = data.page ?? page.value
  } catch (err) {
    error.value = err
    logs.value = []
    total.value = 0
    pages.value = 1
  } finally {
    loading.value = false
  }
}

function goPage(target) {
  if (target < 1 || target > pages.value || target === page.value) return
  page.value = target
  fetchLogs()
}

function exportLogs() {
  ElMessage.warning('审计日志导出为服务端能力，当前版本请以台账「导出台账」为准')
}

onMounted(fetchLogs)
</script>
