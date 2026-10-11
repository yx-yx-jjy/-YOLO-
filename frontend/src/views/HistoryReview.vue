<template>
  <div class="space-y-4">
    <!-- 顶部：标题 + 状态页签 + 关键词/时间/置信度筛选 + 导出 -->
    <div class="card space-y-3">
      <!-- 第一行 -->
      <div class="flex flex-wrap items-center justify-between gap-3">
        <div class="flex items-center gap-3">
          <h2 class="text-[16px] font-medium" style="color: var(--c-ink);">违规检测历史记录与人工复核中心</h2>
          <span class="text-[12px] font-mono" style="color: var(--c-ink-3);">
            <!-- 错误态不显示条数：显示「0 条」会让用户以为"只是没数据"，实际是"取不到数据" -->
            <template v-if="violationStore.listError">共 — 条</template>
            <template v-else-if="isNarrowed">筛出 {{ violationStore.total }} 条</template>
            <template v-else>共 {{ violationStore.total }} 条</template>
          </span>
        </div>

        <div class="flex items-center gap-2">
          <!-- 状态筛选 Tabs -->
          <div class="flex items-center gap-0.5 p-0.5 rounded-md text-[13px]" style="background-color: var(--c-page); border: 1px solid var(--c-line);">
            <button
              @click="violationStore.filterStatus = 'all'"
              class="px-3 py-1 rounded-md font-normal whitespace-nowrap"
              :style="violationStore.filterStatus === 'all'
                ? 'background-color: var(--c-surface); color: var(--c-primary); box-shadow: 0 1px 2px rgba(15,23,42,0.04);'
                : 'color: var(--c-ink-2);'"
            >
              全部 ({{ stat(violationStore.totalRecords) }})
            </button>
            <button
              @click="violationStore.filterStatus = 'pending'"
              class="px-3 py-1 rounded-md font-normal whitespace-nowrap flex items-center gap-1.5"
              :style="violationStore.filterStatus === 'pending'
                ? 'background-color: var(--c-surface); color: #B45309; box-shadow: 0 1px 2px rgba(15,23,42,0.04);'
                : 'color: var(--c-ink-2);'"
            >
              <span>待复核</span>
              <span
                v-if="violationStore.pendingCount > 0"
                class="px-1.5 py-0.5 rounded text-[12px] font-normal"
                style="background-color: #FFFBEB; color: #B45309;"
              >
                {{ violationStore.pendingCount }}
              </span>
            </button>
            <button
              @click="violationStore.filterStatus = 'approved'"
              class="px-3 py-1 rounded-md font-normal whitespace-nowrap"
              :style="violationStore.filterStatus === 'approved'
                ? 'background-color: var(--c-surface); color: #15803D; box-shadow: 0 1px 2px rgba(15,23,42,0.04);'
                : 'color: var(--c-ink-2);'"
            >
              已确认入卷 ({{ stat(violationStore.approvedCount) }})
            </button>
            <button
              @click="violationStore.filterStatus = 'rejected'"
              class="px-3 py-1 rounded-md font-normal whitespace-nowrap"
              :style="violationStore.filterStatus === 'rejected'
                ? 'background-color: var(--c-surface); color: var(--c-ink-2); box-shadow: 0 1px 2px rgba(15,23,42,0.04);'
                : 'color: var(--c-ink-2);'"
            >
              误报已剔除 ({{ stat(violationStore.rejectedCount) }})
            </button>
          </div>

          <!-- 处置状态 Tabs：与上方复核状态是两个维度（复核=事实是否成立，处置=文书走到哪步），
               归档记录是"已办结"的独立业务对象，不该只藏在下拉框里。 -->
          <div class="flex items-center gap-0.5 p-0.5 rounded-md text-[13px]" style="background-color: var(--c-page); border: 1px solid var(--c-line);">
            <button
              @click="violationStore.dispositionStatus = 'all'"
              class="px-3 py-1 rounded-md font-normal whitespace-nowrap"
              :style="violationStore.dispositionStatus === 'all'
                ? 'background-color: var(--c-surface); color: var(--c-primary); box-shadow: 0 1px 2px rgba(15,23,42,0.04);'
                : 'color: var(--c-ink-2);'"
            >
              处置进度
            </button>
            <button
              @click="violationStore.dispositionStatus = 'to_notify'"
              class="px-3 py-1 rounded-md font-normal whitespace-nowrap flex items-center gap-1.5"
              :style="violationStore.dispositionStatus === 'to_notify'
                ? 'background-color: var(--c-surface); color: #B45309; box-shadow: 0 1px 2px rgba(15,23,42,0.04);'
                : 'color: var(--c-ink-2);'"
            >
              <span>待告知</span>
              <span
                v-if="violationStore.toNotifyCount > 0"
                class="px-1.5 py-0.5 rounded text-[12px] font-normal"
                style="background-color: #FFFBEB; color: #B45309;"
              >
                {{ violationStore.toNotifyCount }}
              </span>
            </button>
            <button
              @click="violationStore.dispositionStatus = 'disposed'"
              class="px-3 py-1 rounded-md font-normal whitespace-nowrap flex items-center gap-1.5"
              :style="violationStore.dispositionStatus === 'disposed'
                ? 'background-color: var(--c-surface); color: #15803D; box-shadow: 0 1px 2px rgba(15,23,42,0.04);'
                : 'color: var(--c-ink-2);'"
            >
              <span>已处理</span>
              <span
                v-if="violationStore.disposedCount > 0"
                class="px-1.5 py-0.5 rounded text-[12px] font-normal"
                style="background-color: #F0FDF4; color: #15803D;"
              >
                {{ violationStore.disposedCount }}
              </span>
            </button>
            <button
              @click="violationStore.dispositionStatus = 'archived'"
              class="px-3 py-1 rounded-md font-normal whitespace-nowrap flex items-center gap-1.5"
              :style="violationStore.dispositionStatus === 'archived'
                ? 'background-color: var(--c-surface); color: #475569; box-shadow: 0 1px 2px rgba(15,23,42,0.04);'
                : 'color: var(--c-ink-2);'"
            >
              <span>已归档</span>
              <span
                v-if="violationStore.archivedCount > 0"
                class="px-1.5 py-0.5 rounded text-[12px] font-normal"
                style="background-color: #F1F5F9; color: #475569;"
              >
                {{ violationStore.archivedCount }}
              </span>
            </button>
          </div>

          <select
            v-model="violationStore.filterCategory"
            class="h-8 px-3 rounded-md text-[13px] font-normal focus:outline-none"
            style="background-color: var(--c-surface); border: 1px solid var(--c-line); color: var(--c-ink-2);"
          >
            <option value="all">所有违规类别</option>
            <option value="helmet">仅未戴头盔</option>
          </select>

          <button
            @click="handleExport"
            class="h-8 px-3 rounded-md text-[13px] font-normal flex items-center gap-1.5"
            style="background-color: var(--c-surface); border: 1px solid var(--c-line); color: #334155;"
            @mouseenter="$event.currentTarget.style.borderColor = 'var(--c-primary)'"
            @mouseleave="$event.currentTarget.style.borderColor = 'var(--c-line)'"
          >
            <el-icon :size="14"><Download /></el-icon>
            <span>导出台账</span>
          </button>
        </div>
      </div>

      <!-- 第二行：关键词 / 时间范围 / 置信度，筛选到 0 条时给一键还原 -->
      <div class="flex flex-wrap items-center gap-2 pt-3" style="border-top: 1px solid var(--c-line);">
        <div class="relative">
          <span class="absolute left-2.5 top-1/2 -translate-y-1/2 pointer-events-none" style="color: var(--c-ink-3);">
            <el-icon :size="14"><Search /></el-icon>
          </span>
          <input
            ref="searchInputRef"
            v-model="violationStore.keyword"
            type="text"
            placeholder="搜索编号 / 卡口 / 车辆 / 复核人"
            class="h-8 pl-8 pr-7 rounded-md text-[13px] font-normal focus:outline-none"
            style="width: 300px; background-color: var(--c-surface); border: 1px solid var(--c-line); color: var(--c-ink);"
            @focus="$event.currentTarget.style.borderColor = 'var(--c-primary)'"
            @blur="$event.currentTarget.style.borderColor = 'var(--c-line)'"
          />
          <button
            v-if="violationStore.keyword"
            @click="violationStore.keyword = ''"
            class="absolute right-2 top-1/2 -translate-y-1/2 text-[14px] leading-none"
            style="color: var(--c-ink-3);"
            title="清空关键词"
          >
            ×
          </button>
        </div>

        <select
          v-model="violationStore.timeRange"
          class="h-8 px-3 rounded-md text-[13px] font-normal focus:outline-none"
          style="background-color: var(--c-surface); border: 1px solid var(--c-line); color: var(--c-ink-2);"
        >
          <option value="all">全部时间</option>
          <option value="24h">近 24 小时</option>
          <option value="7d">近 7 天</option>
        </select>

        <select
          v-model="violationStore.confidenceBand"
          class="h-8 px-3 rounded-md text-[13px] font-normal focus:outline-none"
          style="background-color: var(--c-surface); border: 1px solid var(--c-line); color: var(--c-ink-2);"
        >
          <option value="all">全部置信度</option>
          <option value="high">高置信 &gt; 90%</option>
          <option value="mid">中置信 70%–90%</option>
          <option value="low">低置信 &lt; 70% · 需重点核验</option>
        </select>

        <!-- 处置状态下拉已移除：上方「处置进度」页签组覆盖了同样的字段，
     两个控件绑同一个 store 状态会让人以为能叠加筛选，实际后者会覆盖前者。 -->

        <button
          v-if="isNarrowed"
          @click="resetFilters"
          class="h-8 px-3 rounded-md text-[13px] font-normal"
          style="background-color: var(--c-surface); border: 1px solid var(--c-line); color: var(--c-ink-2);"
          @mouseenter="$event.currentTarget.style.borderColor = 'var(--c-primary)'; $event.currentTarget.style.color = 'var(--c-primary)'"
          @mouseleave="$event.currentTarget.style.borderColor = 'var(--c-line)'; $event.currentTarget.style.color = 'var(--c-ink-2)'"
        >
          清除筛选
        </button>

        <span class="ml-auto text-[12px] font-mono" style="color: var(--c-ink-3);">
          快捷键：/ 聚焦搜索 · Esc 清空
        </span>
      </div>
    </div>

    <MetricStrip :items="kpiItems" aria-label="复核台账概览" />

    <!-- 批量操作栏：仅在勾选后出现，不占常态版面 -->
    <div
      v-if="selectedIds.length > 0"
      class="card flex flex-wrap items-center justify-between gap-3"
      style="border-color: #C7D2FE; background-color: var(--c-primary-weak);"
    >
      <div class="flex items-center gap-2 text-[13px]" style="color: var(--c-ink);">
        <span>已选中</span>
        <span class="font-mono font-medium" style="color: var(--c-primary);">{{ selectedIds.length }}</span>
        <span>条记录</span>
        <span v-if="selectedPendingCount > 0" class="text-[12px]" style="color: #B45309;">
          （其中 {{ selectedPendingCount }} 条待复核）
        </span>
        <span v-if="selectedToNotifyCount > 0" class="text-[12px]" style="color: var(--c-primary);">
          （其中 {{ selectedToNotifyCount }} 条待告知）
        </span>
        <span v-if="selectedPendingCount === 0 && selectedToNotifyCount === 0" class="text-[12px]" style="color: var(--c-ink-3);">
          （所选记录已复核完成，如需修改请单条「撤销复核」）
        </span>
      </div>

      <div class="flex items-center gap-2">
        <button
          @click="batchApprove"
          :disabled="selectedPendingCount === 0"
          class="h-8 px-3 rounded-md text-[13px] font-normal text-white disabled:opacity-40 disabled:cursor-not-allowed"
          style="background-color: #15803D;"
        >
          批量确认入卷
        </button>
        <button
          @click="batchReject"
          :disabled="selectedPendingCount === 0"
          class="h-8 px-3 rounded-md text-[13px] font-normal disabled:opacity-40 disabled:cursor-not-allowed"
          style="background-color: var(--c-surface); border: 1px solid var(--c-line); color: #B91C1C;"
        >
          批量剔除误报
        </button>
        <button
          v-if="selectedToNotifyCount > 0"
          @click="batchNotify"
          class="h-8 px-3 rounded-md text-[13px] font-normal text-white"
          style="background-color: var(--c-primary);"
        >
          批量告知当事人
        </button>
        <button
          @click="clearSelection"
          class="h-8 px-3 rounded-md text-[13px] font-normal"
          style="background-color: var(--c-surface); border: 1px solid var(--c-line); color: var(--c-ink-2);"
        >
          取消选择
        </button>
      </div>
    </div>

    <!-- 违规表格 -->
    <div class="card !p-0 overflow-hidden">
      <!-- 表头行：标题 + 复核进度 -->
      <div class="flex flex-wrap items-center justify-between gap-3 px-4 h-14" style="border-bottom: 1px solid var(--c-line);">
        <h3 class="text-[14px] font-medium" style="color: var(--c-ink);">台账明细</h3>

        <div class="flex items-center gap-3">
          <span class="text-[12px]" style="color: var(--c-ink-3);">复核完成率</span>
          <div class="flex h-1.5 w-[180px] overflow-hidden rounded-full" style="background-color: var(--c-line);">
            <i
              v-for="segment in reviewSegments"
              :key="segment.label"
              :style="{ width: `${segment.pct}%`, backgroundColor: segment.color }"
            ></i>
          </div>
          <span class="text-[13px] font-mono font-medium" style="color: var(--c-ink);">{{ reviewProgress }}%</span>
          <span class="text-[12px]" style="color: var(--c-ink-3);">
            已处理 {{ processedCount }} / {{ stat(violationStore.totalRecords) }} 条
          </span>
        </div>
      </div>

      <div class="overflow-x-auto">
        <table class="w-full text-left text-[13px] table-fixed" style="color: var(--c-ink);">
          <colgroup>
            <col style="width: 40px;" />
            <col style="width: 140px;" />
            <col style="width: 160px;" />
            <col style="width: 196px;" />
            <col style="width: 160px;" />
            <col style="width: 84px;" />
            <col style="width: 272px;" />
            <col style="width: 100px;" />
            <col style="width: 84px;" />
            <col style="width: 150px;" />
            <col style="width: 118px;" />
          </colgroup>
          <thead>
            <tr style="background-color: var(--c-page); border-bottom: 1px solid var(--c-line);">
              <th class="h-12 px-3 sticky-head">
                <input
                  type="checkbox"
                  class="cursor-pointer"
                  style="accent-color: var(--c-primary);"
                  :checked="allSelected"
                  :indeterminate.prop="partiallySelected"
                  aria-label="全选当前页"
                  @change="toggleAll"
                />
              </th>
              <th class="h-12 px-3 text-[12px] font-normal whitespace-nowrap sticky-head" style="color: #64748B;">违规编号</th>
              <th class="h-12 px-3 text-[12px] font-normal whitespace-nowrap sticky-head" style="color: #64748B;">捕获时间</th>
              <th class="h-12 px-3 text-[12px] font-normal whitespace-nowrap sticky-head" style="color: #64748B;">卡口</th>
              <th class="h-12 px-3 text-[12px] font-normal whitespace-nowrap sticky-head" style="color: #64748B;">违规类型与判定</th>
              <th class="h-12 px-3 text-[12px] font-normal whitespace-nowrap text-center sticky-head" style="color: #64748B;">判定可信度</th>
              <th class="h-12 px-3 text-[12px] font-normal whitespace-nowrap sticky-head" style="color: #64748B;">目标特征与车辆</th>
              <th class="h-12 px-3 text-[12px] font-normal whitespace-nowrap sticky-head" style="color: #64748B;">复核状态</th>
              <th class="h-12 px-3 text-[12px] font-normal whitespace-nowrap sticky-head" style="color: #64748B;">处置状态</th>
              <th class="h-12 px-3 text-[12px] font-normal whitespace-nowrap sticky-head" style="color: #64748B;">复核人 / 备注</th>
              <th class="h-12 px-3 text-[12px] font-normal whitespace-nowrap text-center sticky-head sticky-actions" style="color: #64748B;">操作</th>
            </tr>
          </thead>
          <tbody>
            <!-- 加载态：数据异步化后必须有明确反馈，不再依赖"永不显示的骨架屏" -->
            <template v-if="violationStore.listLoading">
              <tr>
                <td colspan="11" class="p-0">
                  <div class="flex items-center justify-center gap-2 py-10 text-[13px]" style="color: var(--c-ink-3);">
                    <el-icon :size="16" class="is-loading"><Loading /></el-icon>
                    <span>正在加载台账数据…</span>
                  </div>
                </td>
              </tr>
            </template>

            <!-- 错误态：不渲染空白表格、不渲染 0 条 -->
            <template v-else-if="violationStore.listError">
              <tr>
                <td colspan="11" class="p-0">
                  <EmptyState
                    variant="error"
                    icon="WarningFilled"
                    title="台账数据加载失败"
                    :description="listErrorText"
                    action-text="重试"
                    @action="retryList"
                  />
                </td>
              </tr>
            </template>

            <!-- 空态 -->
            <template v-else-if="violationStore.records.length === 0">
              <tr>
                <td colspan="11" class="p-0">
                  <EmptyState
                    :icon="isNarrowed ? 'Search' : 'Document'"
                    :title="isNarrowed ? '当前筛选条件下没有匹配的记录' : '台账中还没有任何记录'"
                    :description="isNarrowed
                      ? '可以放宽时间范围或置信度区间，也可以清空关键词后再看。'
                      : '上传图片或视频开始一次检测，或在摄像头页面等待实时抓拍，产生的事件会自动进入待复核台账。'"
                    :action-text="isNarrowed ? '清除全部筛选条件' : ''"
                    @action="resetFilters"
                  />
                </td>
              </tr>
            </template>

            <template v-else>
              <tr v-for="row in violationStore.records" :key="row.id" class="h-12 align-middle row-body">
              <td class="h-12 px-3">
                <input
                  type="checkbox"
                  class="cursor-pointer"
                  style="accent-color: var(--c-primary);"
                  :checked="selectedIds.includes(row.id)"
                  :aria-label="`选择 ${row.id}`"
                  @change="toggleRow(row.id)"
                />
              </td>
              <td class="h-12 px-3 font-mono whitespace-nowrap" style="color: var(--c-ink);">
                {{ row.id }}
              </td>
              <td class="h-12 px-3 font-mono whitespace-nowrap" style="color: var(--c-ink-2);">
                {{ row.capture_time }}
              </td>
              <td class="h-12 px-3 whitespace-nowrap font-normal truncate" :title="row.camera_id" style="color: var(--c-ink-2);">
                {{ spotLabel(row) }}
              </td>
              <td class="h-12 px-3 whitespace-nowrap overflow-hidden" :title="row.violation_type">
                <span
                  class="inline-block max-w-full truncate px-2 py-0.5 rounded text-[12px] font-normal align-middle"
                  style="background-color: #F1F5F9; color: #334155;"
                >
                  {{ formatViolationType(row) }}
                </span>
              </td>
              <td class="h-12 px-2 whitespace-nowrap text-center align-middle">
                <span
                  v-if="row.confidence != null"
                  class="px-2 py-0.5 rounded text-[12px] font-normal leading-[18px] cursor-help"
                  :style="confidenceChipStyle(row.confidence)"
                  :title="`判定可信度 ${confidencePercent(row.confidence)} —— ${confidenceHint(row.confidence)}`"
                >{{ confidenceLabel(row.confidence) }}</span>
                <span v-else class="text-[13px]" style="color: var(--c-ink-3);">—</span>
              </td>
              <td class="h-12 px-3 whitespace-nowrap overflow-hidden">
                <div class="flex items-center gap-2">
                  <img
                    v-if="row.roi_url"
                    :src="row.roi_url"
                    alt="头部证据切片"
                    class="w-9 h-9 rounded object-cover flex-shrink-0"
                    style="border: 1px solid var(--c-line); background-color: var(--c-page);"
                    loading="lazy"
                    @error="(e) => (e.target.style.display = 'none')"
                  />
                  <div class="min-w-0">
                    <div class="text-[13px] font-normal truncate" :title="row.details.plate_or_vehicle" style="color: var(--c-ink);">{{ row.details.plate_or_vehicle }}</div>
                    <div class="text-[12px] font-mono truncate" style="color: var(--c-ink-3);">Track #{{ row.track_id }}</div>
                  </div>
                </div>
              </td>
              <td class="h-12 px-3 whitespace-nowrap">
                <span
                  v-if="row.status === 'pending'"
                  class="px-2 py-0.5 rounded text-[12px] font-normal whitespace-nowrap"
                  style="background-color: #FFFBEB; color: #B45309;"
                >
                  待人工复核
                </span>
                <span
                  v-else-if="row.status === 'approved'"
                  class="px-2 py-0.5 rounded text-[12px] font-normal whitespace-nowrap"
                  style="background-color: #F0FDF4; color: #15803D;"
                >
                  已确认入卷
                </span>
                <span
                  v-else
                  class="px-2 py-0.5 rounded text-[12px] font-normal whitespace-nowrap"
                  style="background-color: #F1F5F9; color: #475569;"
                >
                  误报已剔除
                </span>
              </td>
              <td class="h-12 px-3 whitespace-nowrap">
                <span
                  v-if="dispositionBadge(row)"
                  class="px-2 py-0.5 rounded text-[12px] font-normal whitespace-nowrap"
                  :style="{ backgroundColor: dispositionBadge(row).bg, color: dispositionBadge(row).color }"
                >
                  {{ dispositionBadge(row).text }}
                </span>
                <span v-else class="text-[12px]" style="color: var(--c-ink-3);" title="未进入处置流程（待复核或已剔除）">—</span>
              </td>
              <td class="h-12 px-3 truncate" :title="row.review_remark" style="max-width: 150px;">
                <div v-if="row.reviewer" class="text-[13px] font-medium" style="color: var(--c-ink);">
                  {{ row.reviewer }}
                </div>
                <div class="text-[12px] truncate" style="color: var(--c-ink-3);">
                  {{ row.review_remark || '—' }}
                </div>
              </td>
              <td class="h-12 px-2 text-center whitespace-nowrap sticky-actions">
                <div class="flex items-center justify-center gap-1.5">
                  <!-- 主操作：每行只有一个，随状态变化 -->
                  <button
                    v-if="row.status === 'pending'"
                    @click="violationStore.openEvidenceModal(row)"
                    class="h-8 px-2.5 rounded-md text-[13px] font-normal text-white flex-shrink-0"
                    style="background-color: var(--c-primary);"
                    @mouseenter="$event.currentTarget.style.backgroundColor = '#1E40AF'"
                    @mouseleave="$event.currentTarget.style.backgroundColor = 'var(--c-primary)'"
                  >
                    人工复核
                  </button>
                  <button
                    v-else-if="row.status === 'approved'"
                    @click="openDisposition(row)"
                    class="h-8 px-2.5 rounded-md text-[13px] font-normal text-white flex-shrink-0"
                    style="background-color: var(--c-primary);"
                    @mouseenter="$event.currentTarget.style.backgroundColor = '#1E40AF'"
                    @mouseleave="$event.currentTarget.style.backgroundColor = 'var(--c-primary)'"
                    :title="`处置：${row.disposition?.status ? '当前' + (DISPOSITION_LABELS[row.disposition.status] || '') : '待流转'}`"
                  >
                    处置
                  </button>
                  <button
                    v-else
                    @click="violationStore.openEvidenceModal(row)"
                    class="h-8 px-2.5 rounded-md text-[13px] font-normal flex-shrink-0"
                    style="background-color: var(--c-surface); border: 1px solid var(--c-line); color: #334155;"
                    @mouseenter="$event.currentTarget.style.borderColor = 'var(--c-primary)'"
                    @mouseleave="$event.currentTarget.style.borderColor = 'var(--c-line)'"
                  >
                    调取证据
                  </button>

                  <!-- 次要动作收进「更多」：告知书 / 处置单 / 证据，避免三个按钮横向挤爆操作列 -->
                  <el-dropdown
                    trigger="click"
                    placement="bottom-end"
                    @command="cmd => handleRowCommand(cmd, row)"
                  >
                    <button
                      class="h-8 w-8 rounded-md flex items-center justify-center flex-shrink-0"
                      style="border: 1px solid var(--c-line); color: var(--c-ink-2);"
                      title="更多操作"
                      @mouseenter="$event.currentTarget.style.borderColor = 'var(--c-primary)'; $event.currentTarget.style.color = 'var(--c-primary)'"
                      @mouseleave="$event.currentTarget.style.borderColor = 'var(--c-line)'; $event.currentTarget.style.color = 'var(--c-ink-2)'"
                    >
                      <el-icon :size="15"><MoreFilled /></el-icon>
                    </button>
                    <template #dropdown>
                      <el-dropdown-menu>
                        <!-- 告知书仅在人工复核入卷后可见：认定未成立时出具罚款文书不合法 -->
                        <el-dropdown-item v-if="row.status === 'approved'" command="notice">
                          <span class="flex items-center gap-1.5">
                            <el-icon :size="14"><Document /></el-icon>
                            告知书
                            <span
                              v-if="!isServed(row)"
                              class="px-1 py-0.5 rounded text-[11px]"
                              style="background-color: #FEF3C7; color: #92400E;"
                            >未送达</span>
                          </span>
                        </el-dropdown-item>
                        <el-dropdown-item v-if="row.status === 'approved'" command="disposition" divided>
                          <span class="flex items-center gap-1.5">
                            <el-icon :size="14"><Tickets /></el-icon>
                            处置单
                          </span>
                        </el-dropdown-item>
                        <el-dropdown-item command="evidence">
                          <span class="flex items-center gap-1.5">
                            <el-icon :size="14"><Picture /></el-icon>
                            证据详情
                          </span>
                        </el-dropdown-item>
                      </el-dropdown-menu>
                    </template>
                  </el-dropdown>
                </div>
              </td>
            </tr>
            </template>
          </tbody>
        </table>
      </div>

      <!-- 分页 -->
      <div class="flex flex-wrap items-center justify-between gap-3 px-4 h-14" style="border-top: 1px solid var(--c-line);">
        <span class="text-[13px]" style="color: var(--c-ink-2);">
          <!-- 错误态不显示条数（见上：0 条会误导为"没数据"） -->
          <template v-if="violationStore.listError">共 — 条记录</template>
          <template v-else>共 {{ violationStore.total }} 条记录</template>
          <span v-if="selectedIds.length > 0" style="color: var(--c-primary);"> · 已选 {{ selectedIds.length }} 条</span>
        </span>

        <div class="flex items-center gap-2 text-[13px]">
          <span style="color: var(--c-ink-3);">每页</span>
          <select
            v-model.number="pageSize"
            class="h-8 px-2 rounded-md text-[13px] font-normal focus:outline-none"
            style="background-color: var(--c-surface); border: 1px solid var(--c-line); color: var(--c-ink-2);"
          >
            <option :value="10">10 条</option>
            <option :value="20">20 条</option>
            <option :value="50">50 条</option>
          </select>

          <button
            :disabled="page <= 1"
            class="h-8 px-3 rounded-md text-[13px] font-normal disabled:opacity-40 disabled:cursor-not-allowed"
            style="background-color: var(--c-surface); border: 1px solid var(--c-line); color: var(--c-ink-2);"
            @click="page -= 1"
          >
            上一页
          </button>
          <span class="font-mono" style="color: var(--c-ink-2);">
            <!-- 错误态页码同样是"假信息"（第 1/1 页看着像有数据），一并置「—」 -->
            <template v-if="violationStore.listError">第 — / — 页</template>
            <template v-else>第 {{ page }} / {{ totalPages }} 页</template>
          </span>
          <button
            :disabled="page >= totalPages"
            class="h-8 px-3 rounded-md text-[13px] font-normal disabled:opacity-40 disabled:cursor-not-allowed"
            style="background-color: var(--c-surface); border: 1px solid var(--c-line); color: var(--c-ink-2);"
            @click="page += 1"
          >
            下一页
          </button>

          <!-- 直接跳页：台账上百页时逐页翻找一条编号太慢 -->
          <span class="ml-1" style="color: var(--c-ink-3);">跳至</span>
          <input
            v-model="pageInput"
            type="text"
            inputmode="numeric"
            :placeholder="String(page)"
            aria-label="跳转到指定页"
            class="h-8 w-[56px] px-2 rounded-md text-[13px] font-mono text-center focus:outline-none"
            style="background-color: var(--c-surface); border: 1px solid var(--c-line); color: var(--c-ink);"
            @keydown.enter="goToPage"
            @blur="goToPage"
          />
          <span style="color: var(--c-ink-3);">页</span>
        </div>
      </div>
    </div>

    <!-- 处置工作台：处置状态机的前端入口，与复核弹窗并列 -->
    <DispositionModal v-model:visible="dispositionVisible" :record="dispositionRecord" />

    <!-- 执法端预览：mode="officer" —— 民警核对文书内容，不出现当事人操作 -->
    <Traffic12123Notice
      v-model:visible="notice12123Visible"
      :record="notice12123Record"
      mode="officer"
    />
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useViolationStore, DISPOSITION_BADGES, DISPOSITION_LABELS } from '../stores/violations'
import { useAuthStore } from '../stores/auth'
import { getApiErrorMessage } from '../services/http'
import MetricStrip from '../components/MetricStrip.vue'
import EmptyState from '../components/EmptyState.vue'
import DispositionModal from '../components/DispositionModal.vue'
import Traffic12123Notice from '../components/Traffic12123Notice.vue'
import { cameraName } from '../data/cameras'

const violationStore = useViolationStore()
const authStore = useAuthStore()

const notice12123Visible = ref(false)
const notice12123Record = ref(null)

function open12123(row) {
  notice12123Record.value = row
  notice12123Visible.value = true
}

/**
 * 台账里存的是 `CAM-01-南向非机动车道` 这样的机器编号。
 * 对复核人来说"珞喻路-光谷广场口 · 南向非机动车道"才有意义，
 * 所以屏显用点位名 + 方向，原始编号留在 title 里备查。
 */
function spotLabel(row) {
  const raw = row.camera_id || ''
  const direction = raw.split('-').slice(2).join('-')
  const name = cameraName(raw)
  return direction ? `${name} · ${direction}` : name
}

/* ── 筛选：全部作为请求参数交给后端（服务端筛选 + 服务端分页） ──
   状态/类别/关键词/时间范围/置信度/处置状态都存 store，页签与下拉直接绑定 store 字段。 */
const pageInput = ref('')
const searchInputRef = ref(null)

// 分页/每页代理到 store：变化即触发服务端重新拉取
const page = computed({
  get: () => violationStore.page,
  set: value => { violationStore.setPage(value) }
})
const pageSize = computed({
  get: () => violationStore.pageSize,
  set: value => { violationStore.setPageSize(value) }
})
const totalPages = computed(() => violationStore.pages)

const isNarrowed = computed(() =>
  Boolean(violationStore.keyword.trim())
  || violationStore.timeRange !== 'all'
  || violationStore.confidenceBand !== 'all'
  || violationStore.dispositionStatus !== 'all'
)

async function resetFilters() {
  violationStore.resetFilters()
  clearSelection()
  await violationStore.applyFilters()
}

/* 列表错误态文案 + 重试 */
const listErrorText = computed(() => getApiErrorMessage(violationStore.listError))
function retryList() { violationStore.fetchRecords() }

/* 导出：覆盖筛选后的全部数据（store 内部循环翻页拉全量） */
async function handleExport() {
  try {
    const count = await violationStore.exportRecordsToCSV()
    ElMessage.success(`已导出 ${count} 条台账记录（当前筛选范围内的全部数据）`)
  } catch (error) {
    ElMessage.error(`导出失败：${getApiErrorMessage(error)}`)
  }
}

/* 摘要数字占位：未就绪时显示「—」，不假装是 0 */
function stat(value) {
  return value === null || value === undefined ? '—' : value
}

function goToPage() {
  const target = Math.round(Number(pageInput.value))
  pageInput.value = ''
  if (!Number.isFinite(target) || target < 1) return
  violationStore.setPage(Math.min(target, totalPages.value))
}

/* ── 键盘：/ 聚焦搜索，Esc 清空全部筛选 ── */
function handleKeydown(event) {
  const tag = (event.target?.tagName || '').toLowerCase()
  const typing = tag === 'input' || tag === 'select' || tag === 'textarea' || event.target?.isContentEditable

  if (event.key === '/' && !typing) {
    event.preventDefault()
    searchInputRef.value?.focus()
    return
  }
  if (event.key === 'Escape' && isNarrowed.value) {
    resetFilters()
  }
}

/* ── 批量选择（当前页） ── */
const selectedIds = ref([])
const currentPageRows = computed(() => violationStore.records)

const selectedPendingCount = computed(() =>
  currentPageRows.value.filter(row => selectedIds.value.includes(row.id) && row.status === 'pending').length
)

/* 选中记录里"已入卷但还没告知"的条数 —— 批量告知只对这些记录生效 */
const selectedToNotifyCount = computed(() =>
  currentPageRows.value.filter(row =>
    selectedIds.value.includes(row.id) && row.disposition?.status === 'to_notify'
  ).length
)

const allSelected = computed(() =>
  currentPageRows.value.length > 0 && currentPageRows.value.every(row => selectedIds.value.includes(row.id))
)

// 半选只在"选了但不是全选"时为真，否则全选时表头会错误地显示成半选状态
const partiallySelected = computed(() =>
  !allSelected.value && currentPageRows.value.some(row => selectedIds.value.includes(row.id))
)

function toggleRow(id) {
  const index = selectedIds.value.indexOf(id)
  if (index === -1) selectedIds.value.push(id)
  else selectedIds.value.splice(index, 1)
}

function toggleAll(event) {
  const pageIds = currentPageRows.value.map(row => row.id)
  if (event.target.checked) {
    pageIds.forEach(id => {
      if (!selectedIds.value.includes(id)) selectedIds.value.push(id)
    })
  } else {
    selectedIds.value = selectedIds.value.filter(id => !pageIds.includes(id))
  }
}

function clearSelection() {
  selectedIds.value = []
}

function currentReviewer() {
  return authStore.currentUser?.real_name || '当前用户'
}

function currentBadge() {
  return authStore.currentUser?.badge_number || ''
}

function pendingTargets() {
  return currentPageRows.value.filter(row => selectedIds.value.includes(row.id) && row.status === 'pending')
}

/**
 * 批量复核会一次性改动多条记录，而且撤销要逐条来 ——
 * 所以必须让复核人先看清楚"要改几条、改什么"，再确认。
 */
async function confirmBatch(text, title, confirmText) {
  try {
    await ElMessageBox.confirm(text, title, {
      type: 'warning',
      confirmButtonText: confirmText,
      cancelButtonText: '取消',
      confirmButtonClass: 'el-button--danger'
    })
    return true
  } catch {
    return false
  }
}

/** 批量复核统一走后端 batch-review，结果按 succeeded / failed 如实汇报 */
async function runBatchReview(action, label) {
  const targets = pendingTargets()
  if (!targets.length) return
  const ok = await confirmBatch(
    `即将把选中的 ${targets.length} 条待复核记录标记为「${label}」。\n该操作不可批量撤销，如需修改只能逐条「撤销复核」。`,
    `批量${label}`,
    `确认${label}`
  )
  if (!ok) return

  try {
    const result = await violationStore.batchReview(
      action,
      targets.map(row => row.id),
      currentReviewer(),
      currentBadge(),
      action === 'approve' ? '批量复核：违规事实成立，已确认入卷' : '批量复核：环境干扰或非违规误报，已剔除'
    )
    const succeeded = result?.succeeded?.length ?? 0
    const failed = result?.failed ?? []
    if (failed.length === 0) {
      ElMessage.success(`已${label} ${succeeded} 条，可在对应页签核对`)
    } else {
      ElMessage.warning(`已${label} ${succeeded} 条，${failed.length} 条失败：${failed[0]?.reason || '状态冲突'}`)
    }
  } catch (error) {
    ElMessage.error(`${label}失败：${getApiErrorMessage(error)}`)
  } finally {
    clearSelection()
  }
}

function batchApprove() { return runBatchReview('approve', '确认入卷') }
function batchReject() { return runBatchReview('reject', '剔除误报') }

/**
 * 批量告知当事人：复核入卷之后的第一步处置动作。
 * 无批量接口 —— 逐条落库，单条失败不影响其余，最后如实汇总。
 */
async function batchNotify() {
  const targets = currentPageRows.value.filter(row =>
    selectedIds.value.includes(row.id) && row.disposition?.status === 'to_notify'
  )
  if (!targets.length) return
  const ok = await confirmBatch(
    `即将把选中的 ${targets.length} 条记录标记为「已告知当事人」，推进到等待处理环节。\n请确认这些线索确实已完成告知。`,
    '批量告知当事人',
    '确认告知'
  )
  if (!ok) return

  const reviewer = currentReviewer()
  let succeeded = 0
  const failed = []
  for (const row of targets) {
    try {
      await violationStore.markNotified(row.id, reviewer, '批量处置：已通过短信告知当事人违法事实与办理地点')
      succeeded += 1
    } catch (error) {
      failed.push({ id: row.id, reason: getApiErrorMessage(error) })
    }
  }
  if (failed.length === 0) ElMessage.success(`已登记 ${succeeded} 条告知结果，可在「处置状态」列核对`)
  else ElMessage.warning(`已登记 ${succeeded} 条，${failed.length} 条失败：${failed[0]?.reason || '状态冲突'}`)
  clearSelection()
}

/* 筛选条件变化 → 回到第一页并重新拉取 */
watch(
  () => [
    violationStore.filterStatus,
    violationStore.filterCategory,
    violationStore.timeRange,
    violationStore.confidenceBand,
    violationStore.dispositionStatus
  ],
  () => {
    clearSelection()
    violationStore.applyFilters()
  }
)

/* 关键词防抖：边打字边请求会打爆后端，300ms 后再查 */
let keywordTimer = null
watch(() => violationStore.keyword, () => {
  clearSelection()
  window.clearTimeout(keywordTimer)
  keywordTimer = window.setTimeout(() => violationStore.applyFilters(), 300)
})

const route = useRoute()

/* 顶栏「待办中心」通过 query 把"要处理什么"带过来，例如 /history?status=pending&band=low */
function applyRouteQuery() {
  const { status, band, disposition } = route.query
  if (status === 'pending' || status === 'approved' || status === 'rejected') {
    violationStore.filterStatus = status
  }
  if (band === 'low' || band === 'mid' || band === 'high') {
    violationStore.confidenceBand = band
  }
  if (['to_notify', 'notified', 'disposed', 'archived'].includes(disposition)) {
    violationStore.dispositionStatus = disposition
  }
}

onMounted(() => {
  window.addEventListener('keydown', handleKeydown)
  applyRouteQuery()
  violationStore.refreshAll()
})

onUnmounted(() => {
  window.removeEventListener('keydown', handleKeydown)
  window.clearTimeout(keywordTimer)
})

watch(() => route.query, () => { applyRouteQuery() })

/* ── 概览条 & 复核进度（汇总数字来自 /api/stats/overview，不再从全量 records 派生） ── */
const processedCount = computed(() => (violationStore.reviewedCount ?? 0))

const reviewProgress = computed(() => {
  const total = violationStore.totalRecords
  if (!total) return 0
  return Math.round((processedCount.value / total) * 100)
})

const reviewSegments = computed(() => {
  const total = violationStore.totalRecords || 1
  const pending = violationStore.pendingCount || 0
  const approved = violationStore.approvedCount || 0
  const rejected = violationStore.rejectedCount || 0
  return [
    { label: '待复核', value: pending, color: '#B45309', pct: (pending / total) * 100 },
    { label: '已确认', value: approved, color: '#15803D', pct: (approved / total) * 100 },
    { label: '误报剔除', value: rejected, color: '#94A3B8', pct: (rejected / total) * 100 }
  ]
})

const kpiItems = computed(() => {
  const total = violationStore.totalRecords
  const pending = violationStore.pendingCount
  const pendingDisposition = violationStore.pendingDispositionCount
  const rate = violationStore.dispositionRate
  const pctOf = value => (total ? `占总量 ${Math.round((value / total) * 100)}%` : '')
  return [
    { label: '台账记录总量', value: total, unit: '条' },
    {
      label: '待人工复核',
      value: pending,
      unit: '起',
      tone: pending > 0 ? 'warning' : 'success',
      hint: pending == null ? '' : pctOf(pending)
    },
    {
      label: '已确认入卷',
      value: violationStore.approvedCount,
      unit: '起',
      tone: 'success',
      hint: violationStore.approvedCount == null ? '' : pctOf(violationStore.approvedCount)
    },
    {
      label: '待告知 / 待处理',
      value: pendingDisposition,
      unit: '起',
      tone: pendingDisposition > 0 ? 'warning' : 'success',
      hint: rate == null ? '' : `处置完成率 ${rate}%`
    },
    {
      label: '误报已剔除',
      value: violationStore.rejectedCount,
      unit: '起',
      hint: violationStore.rejectedCount == null ? '' : pctOf(violationStore.rejectedCount)
    }
  ]
})

// 置信度分档色值统一取自 utils/confidence.js（全站唯一事实来源）。
// 阈值按「判定可信度」的真实分布用四分位点标定（0.43 / 0.63），不是常见的 70/90，
// 原因见该文件头部注释（本指标上限仅约 0.71，旧的 70/90 会让几乎所有记录落进红档）。
import {
  confidenceLabel,
  confidencePercent,
  confidenceChipStyle,
  confidenceHint,
} from '../utils/confidence'

/* ── 处置闭环 ── */
// 未进入处置流程（待复核 / 误报剔除）返回 null：表格显示占位符，不渲染空徽章
function dispositionBadge(row) {
  const status = row.disposition?.status
  return status ? (DISPOSITION_BADGES[status] || null) : null
}

// 已送达 = 处置流程走到告知及以后；未送达的文书只是民警侧的内部预览
function isServed(row) {
  const status = row.disposition?.status
  return status === 'notified' || status === 'disposed' || status === 'archived'
}

/** 「更多」下拉的命令分发：把次要动作收进一个入口，避免操作列横向挤爆 */
function handleRowCommand(command, row) {
  if (command === 'notice') {
    open12123(row)
  } else if (command === 'disposition') {
    openDisposition(row)
  } else if (command === 'evidence') {
    violationStore.openEvidenceModal(row)
  }
}

const dispositionVisible = ref(false)
const dispositionRecord = ref(null)

function openDisposition(row) {
  dispositionRecord.value = row
  dispositionVisible.value = true
}

function formatViolationType(row) {
  return row.violation_type
}
</script>

<style scoped>
/* 操作列固定在右侧：表格总宽 1446px（11 列），窄视口下横向滚动时按钮依然可见。
   宽度按「内容实测所需」定，不再为凑某个整数总宽而压窄列（压窄会把车牌/复核人裁掉）。
   本列必须保持不透明背景，否则横向滚动时下层单元格会从固定列下面透出来。 */
.sticky-actions {
  position: sticky;
  right: 0;
  background-color: var(--c-surface);
  box-shadow: -10px 0 10px -10px rgba(15, 23, 42, 0.16);
}

.sticky-head {
  position: sticky;
  top: 0;
  background-color: var(--c-page);
}

tbody tr.row-body {
  border-bottom: 1px solid var(--c-line);
}

tbody tr.row-body:hover td {
  background-color: var(--c-page);
}

/* sticky 单元格自带背景，hover 时需要跟着变，否则会盖住行底色 */
tbody tr.row-body:hover .sticky-actions {
  background-color: var(--c-page);
}
</style>
