<template>
  <div class="data-table-wrap">
    <!-- 表格 -->
    <el-table
      v-loading="loading"
      :data="data"
      :border="border"
      :stripe="stripe"
      :height="height"
      :row-key="rowKey"
      :expand-row-keys="expandRowKeys as any"
      @selection-change="onSelectionChange"
      @sort-change="onSortChange as any"
      @expand-change="onExpandChange as any"
      class="data-table"
    >
      <!-- 展开列 -->
      <el-table-column v-if="$slots.expand" type="expand" width="48">
        <template #default="{ row }">
          <slot name="expand" :row="row" />
        </template>
      </el-table-column>

      <!-- 多选列 -->
      <el-table-column
        v-if="showSelection"
        type="selection"
        width="50"
        align="center"
      />

      <!-- 序号列 -->
      <el-table-column
        v-if="showIndex"
        type="index"
        label="序号"
        width="60"
        align="center"
      />

      <!-- 动态列 -->
      <template v-for="col in columns" :key="col.prop">
        <el-table-column
          :prop="col.prop"
          :label="col.label"
          :width="col.width"
          :min-width="col.minWidth"
          :align="col.align || 'left'"
          :sortable="col.sortable"
          :fixed="col.fixed"
          :show-overflow-tooltip="col.showOverflowTooltip !== false"
        >
          <template v-if="col.type" #default="{ row }">
            <!-- 状态标签 -->
            <el-tag
              v-if="col.type === 'status' && col.statusMap"
              :type="(col.statusColorMap?.[row[col.prop]] as any) || 'info'"
              size="small"
            >
              {{ col.statusMap[row[col.prop]] || row[col.prop] }}
            </el-tag>

            <!-- 时间格式化 -->
            <span v-else-if="col.type === 'datetime'">
              {{ formatDate(row[col.prop]) }}
            </span>

            <!-- 通用 formatter -->
            <span v-else-if="col.type === 'formatter' && col.formatter">
              {{ col.formatter(row[col.prop], row) }}
            </span>

            <!-- 自定义渲染 -->
            <slot v-else-if="col.type === 'custom' && col.slot" :name="col.slot" :row="row" />
          </template>

          <!-- 自定义插槽渲染 -->
          <template v-else-if="col.slot" #default="{ row }">
            <slot :name="col.slot" :row="row" />
          </template>
        </el-table-column>
      </template>

      <!-- 操作列 -->
      <el-table-column v-if="$slots.actions" label="操作" :width="actionWidth" align="left" fixed="right" class-name="action-column">
        <template #default="{ row }">
          <slot name="actions" :row="row" />
        </template>
      </el-table-column>

      <!-- 空状态 -->
      <template #empty>
        <el-empty description="暂无数据" :image-size="emptyImageSize" />
      </template>
    </el-table>

    <!-- 分页 -->
    <div v-if="showPagination && total > 0" class="data-table-pagination">
      <el-pagination
        v-model:current-page="currentPage"
        v-model:page-size="currentPageSize"
        :page-sizes="[10, 20, 50, 100]"
        :total="total"
        layout="total, sizes, prev, pager, next, jumper"
        background
        @size-change="handleSizeChange"
        @current-change="handlePageChange"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import type { TableColumnCtx } from 'element-plus'

export interface ColumnConfig {
  prop: string
  label: string
  width?: number | string
  minWidth?: number | string
  align?: 'left' | 'center' | 'right'
  type?: 'status' | 'datetime' | 'custom' | 'formatter'
  formatter?: (value: unknown, row: Record<string, unknown>) => string
  statusMap?: Record<string, string>
  statusColorMap?: Record<string, string>
  sortable?: boolean | 'custom'
  fixed?: boolean | 'left' | 'right'
  slot?: string
  showOverflowTooltip?: boolean
}

const props = withDefaults(
  defineProps<{
    data: Record<string, unknown>[]
    columns: ColumnConfig[]
    loading?: boolean
    total?: number
    page?: number
    pageSize?: number
    border?: boolean
    stripe?: boolean
    height?: string | number
    rowKey?: string
    showPagination?: boolean
    showSelection?: boolean
    showIndex?: boolean
    actionWidth?: number | string
    emptyImageSize?: number
  }>(),
  {
    loading: false,
    total: 0,
    page: 1,
    pageSize: 20,
    border: false,
    stripe: true,
    showPagination: true,
    showSelection: false,
    showIndex: false,
    actionWidth: 180,
    emptyImageSize: 80,
    rowKey: 'id',
  }
)

const emit = defineEmits<{
  'update:page': [page: number]
  'update:pageSize': [size: number]
  'page-change': [page: number]
  'size-change': [size: number]
  'selection-change': [rows: Record<string, unknown>[]]
  'sort-change': [sort: { prop: string; order: string }]
  'expand-change': [payload: { row: Record<string, unknown>; expanded: Record<string, unknown>[] }]
}>()

const currentPage = ref(props.page)
const currentPageSize = ref(props.pageSize)
const expandRowKeys = ref<(string | number)[]>([])

watch(
  () => props.page,
  (val) => { currentPage.value = val }
)
watch(
  () => props.pageSize,
  (val) => { currentPageSize.value = val }
)

function handlePageChange(page: number) {
  emit('update:page', page)
  emit('page-change', page)
}

function handleSizeChange(size: number) {
  emit('update:pageSize', size)
  emit('size-change', size)
}

function onSelectionChange(rows: Record<string, unknown>[]) {
  emit('selection-change', rows)
}

function onSortChange(sort: { prop: string; order: string }) {
  emit('sort-change', sort)
}

function onExpandChange(row: Record<string, unknown>, expanded: Record<string, unknown>[]) {
  expandRowKeys.value = expanded.map((r) => r[props.rowKey] as string | number)
  emit('expand-change', { row, expanded })
}

function formatDate(val: string | Date): string {
  if (!val) return '-'
  return new Date(val).toLocaleString('zh-CN')
}
</script>

<style lang="scss" scoped>
.data-table-wrap {
  background: $bg-color-white;
  border: 1px solid $border-color-light;
  border-radius: $border-radius-large;
  overflow: hidden;

  .data-table {
    :deep(.el-table__header th) {
      background-color: $bg-card-header;
      color: $text-primary;
      font-weight: 600;
      font-size: 13px;
    }

    :deep(.el-table__body td) {
      font-size: 13px;
    }

    // 操作列按钮样式
    :deep(.action-column) {
      .cell {
        display: flex;
        align-items: center;
        gap: 4px;
        flex-wrap: nowrap;
      }

      .el-button {
        padding: 0;
        font-size: 13px;
        height: auto;
        color: $color-primary;

        &:hover {
          color: $color-primary-light;
        }

        &.el-button--danger {
          color: $color-danger;

          &:hover {
            color: #f56c6c;
          }
        }
      }

      .el-divider--vertical {
        margin: 0 2px;
      }
    }
  }

  .data-table-pagination {
    padding: 16px 20px;
    display: flex;
    justify-content: flex-end;
    border-top: 1px solid $border-color-lighter;
  }
}
</style>
