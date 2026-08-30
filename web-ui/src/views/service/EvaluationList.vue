<template>
  <div class="evaluation-list">
    <PageHeaderCard title="模型评测" desc="对模型服务进行自动评测或人工评测，评估模型在各项指标上的表现。" />

    <el-tabs v-model="activeTab" @tab-change="handleTabChange">
      <el-tab-pane label="自动评测" name="auto" />
      <el-tab-pane label="人工评测" name="manual" />
    </el-tabs>

    <!-- 搜索筛选 -->
    <SearchFilter
      v-model:model-value="searchKeyword"
      placeholder="搜索评测名称"
      @search="fetchData"
      @reset="handleReset"
      @create="goCreate"
    >
      <template #filters>
        <el-select v-model="filterStatus" placeholder="状态" clearable style="width: 140px" @change="fetchData">
          <el-option v-for="(label, key) in EvalStatusMap" :key="key" :label="label" :value="key" />
        </el-select>
      </template>
    </SearchFilter>

    <!-- 表格 -->
    <DataTable
      :data="tableData"
      :columns="columns"
      :loading="loading"
      :total="total"
      :action-width="220"
      v-model:page="pageIndex"
      v-model:page-size="pageSize"
      @page-change="fetchData"
      @size-change="fetchData"
    >
      <!-- 评分 -->
      <template #scoreSlot="{ row }">
        <span v-if="row.score != null">{{ row.score }}</span>
        <span v-else class="text-muted">-</span>
      </template>

      <!-- 进度 -->
      <template #progressSlot="{ row }">
        <el-progress :percentage="row.progress || 0" :stroke-width="6" :show-text="true" />
      </template>

      <!-- 操作 -->
      <template #actions="{ row }">
        <el-button type="primary" link size="small" @click="goDetail(row)">详情</el-button>
        <el-button v-if="row.status === 'pending'" type="primary" link size="small" @click="startEval(row)">启动</el-button>
        <el-button v-if="['pending', 'running'].includes(row.status)" type="warning" link size="small" @click="cancelEval(row)">取消</el-button>
        <el-button v-if="row.evalType === 'manual' && row.status === 'running'" type="primary" link size="small" @click="goReview(row)">评审</el-button>
        <el-button type="danger" link size="small" @click="deleteEval(row)">删除</el-button>
      </template>
    </DataTable>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import PageHeaderCard from '@/components/common/PageHeaderCard.vue'
import SearchFilter from '@/components/common/SearchFilter.vue'
import DataTable, { type ColumnConfig } from '@/components/common/DataTable.vue'
import {
  getEvaluationList,
  startEvaluation,
  cancelEvaluation,
  deleteEvaluation as deleteEvaluationApi,
} from '@/api/service'
import type { EvalStatus } from '@/types'
import { EvalStatusMap, EvalStatusColorMap } from '@/types'

const router = useRouter()
const activeTab = ref<'auto' | 'manual'>('auto')
const searchKeyword = ref('')
const filterStatus = ref('')
const loading = ref(false)
const tableData = ref<any[]>([])
const total = ref(0)
const pageIndex = ref(1)
const pageSize = ref(20)

const columns: ColumnConfig[] = [
  { prop: 'name', label: '评测名称', minWidth: 200 },
  { prop: 'status', label: '状态', width: 100, type: 'status' as const, statusMap: EvalStatusMap, statusColorMap: EvalStatusColorMap },
  { prop: 'datasetName', label: '数据集', minWidth: 160 },
  { prop: 'deploymentName', label: '模型服务', minWidth: 160 },
  { prop: 'score', label: '评分', width: 80, align: 'center', slot: 'scoreSlot' },
  { prop: 'progress', label: '进度', width: 100, slot: 'progressSlot' },
  { prop: 'createdBy', label: '创建者', width: 100 },
  { prop: 'createdAt', label: '创建时间', width: 170, type: 'datetime' as const },
]

async function fetchData() {
  loading.value = true
  try {
    const params: Record<string, unknown> = {
      pageIndex: pageIndex.value,
      pageSize: pageSize.value,
      evalType: activeTab.value,
    }
    if (searchKeyword.value) params.keyword = searchKeyword.value
    if (filterStatus.value) params.status = filterStatus.value
    const res = await getEvaluationList(params)
    tableData.value = res.list || []
    total.value = res.total || 0
  } catch {
    tableData.value = []
    total.value = 0
  } finally {
    loading.value = false
  }
}

function handleTabChange() {
  pageIndex.value = 1
  filterStatus.value = ''
  searchKeyword.value = ''
  fetchData()
}

function handleReset() {
  searchKeyword.value = ''
  filterStatus.value = ''
  fetchData()
}

function goCreate() {
  router.push(`/service/evaluation/create?type=${activeTab.value}`)
}

function goDetail(row: any) {
  router.push(`/service/evaluation/detail/${row.id}`)
}

function goReview(row: any) {
  router.push(`/service/evaluation/review/${row.id}`)
}

async function cancelEval(row: any) {
  try {
    await ElMessageBox.confirm('确定取消该评测任务吗？推理中的任务将在当前样本后停止。', '取消评测', {
      confirmButtonText: '确定',
      cancelButtonText: '再想想',
      type: 'warning',
    })
  } catch {
    return
  }
  try {
    await cancelEvaluation(row.id)
    ElMessage.success('评测任务已取消')
    fetchData()
  } catch (err: any) {
    ElMessage.error(err?.message || '取消失败')
  }
}

async function startEval(row: any) {
  try {
    await startEvaluation(row.id)
    ElMessage.success('评测已启动')
    fetchData()
  } catch (e: any) {
    ElMessage.error(e.message || '启动失败')
  }
}

function deleteEval(row: any) {
  ElMessageBox.confirm('确定删除该评测任务？', '提示', { type: 'warning' }).then(async () => {
    try {
      await deleteEvaluationApi(row.id)
      ElMessage.success('删除成功')
      fetchData()
    } catch (e: any) {
      ElMessage.error(e.message || '删除失败')
    }
  })
}

onMounted(fetchData)
</script>

<style lang="scss" scoped>
.evaluation-list {
  display: flex;
  flex-direction: column;

  :deep(.el-tabs__header) {
    margin-bottom: 0;
  }
}

.text-muted {
  color: $text-secondary;
}
</style>
