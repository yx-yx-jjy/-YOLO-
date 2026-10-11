<template>
  <div class="glass-panel rounded-xl flex-1 flex flex-col overflow-hidden border border-slate-800">
    <!-- 头部 -->
    <div class="p-3.5 bg-slate-900/90 border-b border-slate-800 flex items-center justify-between">
      <div class="flex items-center gap-2">
        <span class="w-2.5 h-2.5 rounded-full bg-rose-500 animate-ping"></span>
        <h2 class="text-sm font-bold text-white tracking-wide">实时违规取证事件流</h2>
      </div>
      <span class="text-xs text-slate-400 font-mono">
        已抓拍 {{ total }} 起
      </span>
    </div>

    <!-- 违规卡片流列表 (可滚动) -->
    <div class="flex-1 p-3 space-y-2.5 overflow-y-auto max-h-[580px]">
      <div
        v-if="violationStore.recentLoading && !violationStore.recentRecords.length"
        class="text-center text-xs text-slate-500 py-8"
      >
        正在加载最新事件…
      </div>
      <div
        v-else-if="violationStore.recentError"
        class="text-center text-xs py-8"
        style="color: #F87171;"
      >
        数据加载失败：{{ errorText }}
      </div>
      <div
        v-else-if="!violationStore.recentRecords.length"
        class="text-center text-xs text-slate-500 py-8"
      >
        暂无实时违规事件
      </div>
      <div 
        v-for="item in violationStore.recentRecords" 
        :key="item.id"
        @click="violationStore.openEvidenceModal(item)"
        class="p-3 rounded-lg bg-slate-900/80 border transition cursor-pointer shadow-md group"
        :class="[
          item.status === 'pending' ? 'border-rose-500/40 hover:border-rose-400 hover:bg-slate-800/80' : 
          item.status === 'approved' ? 'border-emerald-500/30 hover:border-emerald-400 bg-slate-900/60' : 
          'border-slate-800 bg-slate-950/60 opacity-60'
        ]"
      >
        <div class="flex items-start justify-between">
          <span 
            class="px-2 py-0.5 rounded text-[11px] font-bold border bg-amber-500/20 text-amber-300 border-amber-500/30"
          >
            {{ item.violation_type }}
          </span>
          <span class="text-xs font-mono text-slate-400">
            {{ (item.capture_time || '').slice(11, 19) || '—' }}
          </span>
        </div>

        <div class="mt-2 flex gap-2.5">
          <!-- 仿真抓拍缩略图 -->
          <div class="w-16 h-14 rounded bg-slate-950 border border-slate-700 relative overflow-hidden flex-shrink-0 flex items-center justify-center">
            <svg class="w-7 h-7 text-slate-600" fill="currentColor" viewBox="0 0 20 20">
              <path fill-rule="evenodd" d="M4 3a2 2 0 00-2 2v10a2 2 0 002 2h12a2 2 0 002-2V5a2 2 0 00-2-2H4zm12 12H4l4-8 3 6 2-4 3 6z" clip-rule="evenodd"></path>
            </svg>
            <span 
              class="absolute bottom-0 right-0 text-[8px] px-1 font-bold"
              :class="item.status === 'approved' ? 'bg-emerald-600 text-white' : (item.status === 'rejected' ? 'bg-slate-700 text-slate-300' : 'bg-rose-600 text-white')"
            >
              {{ item.status === 'approved' ? '已入卷' : (item.status === 'rejected' ? '误报' : '待复核') }}
            </span>
          </div>

          <div class="flex-1 text-xs">
            <div class="text-slate-300 font-medium group-hover:text-cyan-300 transition flex items-center justify-between">
              <span>{{ item.id }}</span>
              <span class="font-mono text-cyan-400">Conf: {{ item.confidence == null ? '—' : (item.confidence * 100).toFixed(0) + '%' }}</span>
            </div>
            <div class="text-slate-400 text-[11px] mt-0.5 truncate">
              目标: {{ item.details?.plate_or_vehicle || '—' }} (#{{ item.track_id }})
            </div>
            <div class="text-[11px] mt-1 flex items-center gap-1 font-mono" :class="item.status === 'pending' ? 'text-rose-400 font-semibold' : 'text-slate-400'">
              <span>● 连续追踪 {{ item.details?.consecutive_frames ?? '—' }} 帧锁定</span>
              <span class="text-slate-600">|</span>
              <span class="text-cyan-400 underline">查看证据</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 底部操作与导航 -->
    <div class="p-3 bg-slate-900 border-t border-slate-800 flex justify-between items-center text-xs">
      <span class="text-slate-400">点击卡片调取电子证据链</span>
      <router-link to="/records" class="text-cyan-400 hover:text-cyan-300 font-medium transition flex items-center gap-1">
        <span>全部取证台账</span>
        <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" /></svg>
      </router-link>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted } from 'vue'
import { useViolationStore } from '../stores/violations'
import { getApiErrorMessage } from '../services/http'

const violationStore = useViolationStore()

// 服务端分页后 records 只是台账当前页，事件流取独立的"最新 N 条"
const total = computed(() => violationStore.recentRecords.length)
const errorText = computed(() => getApiErrorMessage(violationStore.recentError))

onMounted(() => {
  if (!violationStore.recentRecords.length) violationStore.fetchRecentRecords(20)
})
</script>
