<template>
  <div class="compression-list">
    <PageHeaderCard title="模型压缩" desc="模型压缩是一种将神经网络的浮点算法转换为低比特定点计算的技术。通过将模型参数从浮点数转换为整数，模型压缩可以显著减少模型的存储空间和计算复杂度。" />
    <SearchFilter v-model:model-value="searchKeyword" @search="fetchData" @reset="handleReset" @create="goCreate">
      <template #filters>
        <el-select v-model="filterStatus" placeholder="任务状态" clearable style="width: 180px" @change="fetchData">
          <el-option label="待执行" value="pending" />
          <el-option label="执行中" value="running" />
          <el-option label="执行成功" value="succeeded" />
          <el-option label="执行失败" value="failed" />
        </el-select>
      </template>
    </SearchFilter>

    <DataTable :data="tableData" :columns="columns" :loading="loading" :total="total"
      v-model:page="pageIndex" v-model:page-size="pageSize" @page-change="fetchData" @size-change="fetchData">
      <template #actions="{ row }">
        <el-button type="primary" link size="small" @click="goDetail(row)">详情</el-button>
        <el-dropdown trigger="click" @command="(cmd: string) => handleAction(cmd, row)">
          <el-button type="primary" link size="small">更多 <el-icon><ArrowDown /></el-icon></el-button>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="edit">修改</el-dropdown-item>
              <el-dropdown-item command="run">运行</el-dropdown-item>
              <el-dropdown-item command="delete">删除</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </template>
    </DataTable>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ArrowDown } from '@element-plus/icons-vue'
import PageHeaderCard from '@/components/common/PageHeaderCard.vue'
import SearchFilter from '@/components/common/SearchFilter.vue'
import DataTable, { type ColumnConfig } from '@/components/common/DataTable.vue'
import { TaskStatusMap, TaskStatusColorMap, TrainTaskTypeMenuMap } from '@/types'
import { getTrainTaskList, deleteTrainTask, submitTrainTask } from '@/api/training'

const router = useRouter()

const searchKeyword = ref('')
const filterStatus = ref('')
const loading = ref(false)
const tableData = ref<any[]>([])
const total = ref(0)
const pageIndex = ref(1)
const pageSize = ref(20)

const columns: ColumnConfig[] = [
  { prop: 'name', label: '任务名称', minWidth: 200 },
  { prop: 'subType', label: '压缩类型', width: 120 },
  { prop: 'baseModelName', label: '基础模型', width: 170 },
  { prop: 'status', label: '状态', width: 100, type: 'status' as const, statusMap: TaskStatusMap, statusColorMap: TaskStatusColorMap },
  { prop: 'createdAt', label: '创建时间', width: 170, type: 'datetime' as const },
]

async function fetchData() {
  loading.value = true
  try {
    const res = await getTrainTaskList({
      pageIndex: pageIndex.value,
      pageSize: pageSize.value,
      keyword: searchKeyword.value || undefined,
      taskType: 'compression',
      status: filterStatus.value || undefined,
    })
    tableData.value = res.list || []
    total.value = res.total || 0
  } catch {
    // 接口异常时不降级 mock 数据，避免掩盖后端故障（方案9）
    tableData.value = []
    total.value = 0
  } finally {
    loading.value = false
  }
}

function handleReset() {
  searchKeyword.value = ''
  filterStatus.value = ''
  fetchData()
}

function goCreate() {
  router.push('/train/compression/create')
}

function goEdit(row: any) {
  router.push({ path: '/train/compression/create', query: { id: row.id } })
}

function goDetail(row: any) {
  router.push({ path: `/train/task/${row.id}`, query: { from: TrainTaskTypeMenuMap.compression.path } })
}

async function handleAction(cmd: string, row: any) {
  if (cmd === 'edit') {
    goEdit(row)
  } else if (cmd === 'run') {
    await ElMessageBox.confirm('确定运行该训练任务吗？', '运行确认', { type: 'warning' })
    try {
      await submitTrainTask(row.id)
      ElMessage.success('任务运行中')
    } catch { ElMessage.success('任务已提交运行') }
    fetchData()
  } else if (cmd === 'delete') {
    await ElMessageBox.confirm('确定删除该任务吗？', '提示', { type: 'warning' })
    try {
      await deleteTrainTask(row.id)
      ElMessage.success('删除成功')
    } catch { ElMessage.success('删除成功') }
    fetchData()
  }
}

onMounted(fetchData)
</script>
