<template>
  <div class="space-y-4">
    <!-- 顶部状态栏与筛选条件 -->
    <div class="glass-panel p-4 rounded-xl border border-slate-800 flex flex-wrap items-center justify-between gap-4">
      <div class="flex items-center gap-2">
        <span class="text-sm font-bold text-white flex items-center gap-1.5">
          <svg class="w-4 h-4 text-cyan-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" /></svg>
          违规取证台账与人工复核中心
        </span>
        <span class="text-xs text-slate-400 font-mono">（共 {{ violationStore.filteredRecords.length }} 条记录）</span>
      </div>

      <!-- 状态筛选 Tabs -->
      <div class="flex items-center bg-slate-900 border border-slate-700/80 rounded-lg p-1 text-xs">
        <button 
          @click="violationStore.filterStatus = 'all'"
          :class="violationStore.filterStatus === 'all' ? 'bg-cyan-600 text-white font-semibold' : 'text-slate-400 hover:text-white'"
          class="px-3 py-1 rounded transition"
        >
          全部 ({{ violationStore.records.length }})
        </button>
        <button 
          @click="violationStore.filterStatus = 'pending'"
          :class="violationStore.filterStatus === 'pending' ? 'bg-amber-600 text-white font-semibold' : 'text-slate-400 hover:text-white'"
          class="px-3 py-1 rounded transition flex items-center gap-1"
        >
          <span>待复核</span>
          <span class="px-1.5 py-0.2 rounded-full bg-rose-500 text-white text-[10px] font-bold">
            {{ violationStore.pendingCount }}
          </span>
        </button>
        <button 
          @click="violationStore.filterStatus = 'approved'"
          :class="violationStore.filterStatus === 'approved' ? 'bg-emerald-600 text-white font-semibold' : 'text-slate-400 hover:text-white'"
          class="px-3 py-1 rounded transition"
        >
          已确认入卷 ({{ violationStore.approvedCount }})
        </button>
        <button 
          @click="violationStore.filterStatus = 'rejected'"
          :class="violationStore.filterStatus === 'rejected' ? 'bg-slate-700 text-white font-semibold' : 'text-slate-400 hover:text-white'"
          class="px-3 py-1 rounded transition"
        >
          误报剔除 ({{ violationStore.rejectedCount }})
        </button>
      </div>

      <!-- 导出 Excel/CSV 按钮 -->
      <div class="flex items-center gap-2">
        <select 
          v-model="violationStore.filterCategory" 
          class="bg-slate-900 border border-slate-700 rounded-lg px-2.5 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-cyan-500"
        >
          <option value="all">所有违规大类</option>
          <option value="helmet">仅未戴头盔</option>
        </select>

        <button 
          @click="violationStore.exportRecordsToCSV" 
          class="px-3.5 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white font-medium text-xs shadow-md transition flex items-center gap-1.5"
        >
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" /></svg>
          <span>导出台账 (Excel/CSV)</span>
        </button>
      </div>
    </div>

    <!-- 违规表格 -->
    <div class="glass-panel rounded-xl overflow-hidden border border-slate-800">
      <div class="overflow-x-auto">
        <table class="w-full text-left text-xs text-slate-300">
          <thead class="bg-slate-900/90 text-slate-400 border-b border-slate-800 text-[11px] uppercase font-mono tracking-wider">
            <tr>
              <th class="py-3 px-4">违规编号</th>
              <th class="py-3 px-4">捕获时间</th>
              <th class="py-3 px-4">监控点位</th>
              <th class="py-3 px-4">违规类型与判定</th>
              <th class="py-3 px-4">目标特征与车辆</th>
              <th class="py-3 px-4">复核状态</th>
              <th class="py-3 px-4">复核人 / 备注</th>
              <th class="py-3 px-4 text-center">操作</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-slate-800/60 font-sans">
            <tr 
              v-for="row in violationStore.filteredRecords" 
              :key="row.id"
              class="hover:bg-slate-900/60 transition group"
            >
              <td class="py-3.5 px-4 font-mono font-bold text-cyan-400">
                {{ row.id }}
              </td>
              <td class="py-3.5 px-4 font-mono text-slate-300">
                {{ row.capture_time }}
              </td>
              <td class="py-3.5 px-4 text-slate-300">
                {{ row.camera_id }}
              </td>
              <td class="py-3.5 px-4">
                <span 
                  class="px-2 py-0.5 rounded text-[11px] font-semibold border bg-amber-500/20 text-amber-300 border-amber-500/40"
                >
                  {{ row.violation_type }}
                </span>
              </td>
              <td class="py-3.5 px-4 text-slate-300">
                <div class="font-medium text-slate-200">{{ row.details.plate_or_vehicle }}</div>
                <div class="text-[11px] text-slate-500 font-mono">Track #{{ row.track_id }}</div>
              </td>
              <td class="py-3.5 px-4">
                <span 
                  v-if="row.status === 'pending'" 
                  class="px-2 py-0.5 rounded text-[11px] bg-amber-500/20 text-amber-300 border border-amber-500/40 font-medium"
                >
                  ● 待人工复核
                </span>
                <span 
                  v-else-if="row.status === 'approved'" 
                  class="px-2 py-0.5 rounded text-[11px] bg-emerald-500/20 text-emerald-400 border border-emerald-500/40 font-medium"
                >
                  ✓ 已确认入卷
                </span>
                <span 
                  v-else 
                  class="px-2 py-0.5 rounded text-[11px] bg-slate-700 text-slate-300 border border-slate-600 font-medium"
                >
                  ✕ 误报已剔除
                </span>
              </td>
              <td class="py-3.5 px-4 text-slate-400 max-w-[220px]">
                <div v-if="row.reviewer" class="text-slate-200 font-medium text-[11px]">
                  {{ row.reviewer }}
                </div>
                <div class="text-[10px] text-slate-500 truncate" :title="row.review_remark">
                  {{ row.review_remark || '未填写' }}
                </div>
              </td>
              <td class="py-3.5 px-4 text-center whitespace-nowrap">
                <div class="flex items-center justify-center gap-1.5">
                  <button 
                    @click="violationStore.openEvidenceModal(row)"
                    class="px-2.5 py-1 rounded bg-cyan-600/80 hover:bg-cyan-500 text-white font-medium text-xs shadow transition"
                  >
                    {{ row.status === 'pending' ? '人工复核 ⚖️' : '调取证据 🔎' }}
                  </button>
                  <button
                    @click="open12123(row)"
                    class="px-2 py-1 rounded bg-blue-600/20 hover:bg-blue-600/30 text-blue-400 border border-blue-500/40 text-xs transition flex items-center gap-1"
                    title="查看交管12123移动端电子处罚告知单"
                  >
                    <span>📱 告知单</span>
                  </button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- 交管12123 移动端电子告知单仿真弹窗 -->
    <Traffic12123Notice v-model:visible="noticeVisible" :record="selectedRow" />
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useViolationStore } from '../stores/violations'
import Traffic12123Notice from '../components/Traffic12123Notice.vue'

const violationStore = useViolationStore()
const noticeVisible = ref(false)
const selectedRow = ref(null)

function open12123(row) {
  selectedRow.value = row
  noticeVisible.value = true
}
</script>
