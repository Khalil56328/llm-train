<template>
  <div class="resource-pool">
    <PageHeaderCard title="资源管理" desc="管理训练与推理所需的计算资源池，供训练任务、模型推理选择使用。" />

    <!-- 资源概览 -->
    <div class="stats-row">
      <div class="stat-card" v-for="s in stats" :key="s.label">
        <div class="stat-icon" :style="{ background: s.bg }">
          <el-icon :size="22"><component :is="s.icon" /></el-icon>
        </div>
        <div class="stat-info">
          <div class="stat-value">{{ s.value }}</div>
          <div class="stat-label">{{ s.label }}</div>
        </div>
      </div>
    </div>

    <div class="content-card">
      <div class="toolbar">
        <div class="filters">
          <el-input
            v-model="query.keyword"
            placeholder="搜索资源池名称"
            clearable
            class="filter-input"
            @keyup.enter="handleSearch"
            @clear="handleSearch"
          />
          <el-select
            v-model="query.status"
            placeholder="状态"
            clearable
            class="filter-select"
            @change="handleSearch"
          >
            <el-option label="启用" value="active" />
            <el-option label="停用" value="inactive" />
          </el-select>
          <el-button type="primary" @click="handleSearch">查询</el-button>
        </div>
        <el-button type="primary" @click="openDialog()">
          <el-icon style="margin-right: 4px"><Plus /></el-icon>
          新增资源池
        </el-button>
      </div>

      <DataTable
        :data="tableData"
        :columns="columns"
        :total="total"
        :page="query.pageIndex"
        :page-size="query.pageSize"
        :loading="loading"
        action-width="140"
        @page-change="handlePageChange"
        @size-change="handleSizeChange"
      >
        <template #actions="{ row }">
          <el-button link type="primary" @click="openDialog(row as any)">编辑</el-button>
          <el-divider direction="vertical" />
          <el-button link type="danger" @click="handleDelete(row as any)">删除</el-button>
        </template>
      </DataTable>
    </div>

    <!-- 新增/编辑弹框 -->
    <el-dialog
      v-model="dialogVisible"
      :title="form.id ? '编辑资源池' : '新增资源池'"
      width="600px"
      :close-on-click-modal="false"
    >
      <el-form ref="formRef" :model="form" :rules="rules" label-width="120px">
        <el-form-item label="资源池名称" prop="name">
          <el-input v-model="form.name" placeholder="请输入资源池名称，如 GPU-A100 训练池" maxlength="100" />
        </el-form-item>
        <el-form-item label="GPU类型" prop="gpu_type">
          <el-select v-model="form.gpu_type" placeholder="请选择 GPU 类型" style="width: 100%" allow-create filterable>
            <el-option label="A100 80G" value="A100 80G" />
            <el-option label="H800 80G" value="H800 80G" />
            <el-option label="V100 32G" value="V100 32G" />
            <el-option label="A10 24G" value="A10 24G" />
          </el-select>
        </el-form-item>
        <el-form-item label="节点数" prop="node_count">
          <el-input-number v-model="form.node_count" :min="1" :max="9999" style="width: 100%" />
        </el-form-item>
        <el-form-item label="GPU总数" prop="total_gpu">
          <el-input-number v-model="form.total_gpu" :min="0" :max="99999" style="width: 100%" />
        </el-form-item>
        <el-form-item label="可用GPU数" prop="available_gpu">
          <el-input-number v-model="form.available_gpu" :min="0" :max="99999" style="width: 100%" />
        </el-form-item>
        <el-form-item label="状态" prop="status">
          <el-radio-group v-model="form.status">
            <el-radio value="active">启用</el-radio>
            <el-radio value="inactive">停用</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="描述" prop="description">
          <el-input
            v-model="form.description"
            type="textarea"
            :rows="3"
            placeholder="资源池用途说明（可选）"
            maxlength="500"
            show-word-limit
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="handleSave">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import { Box, Cpu, Monitor } from '@element-plus/icons-vue'
import PageHeaderCard from '@/components/common/PageHeaderCard.vue'
import DataTable, { type ColumnConfig } from '@/components/common/DataTable.vue'
import { fetchResourcePoolList, createResourcePool, updateResourcePool, deleteResourcePool } from '@/api/ops'
import type { ResourcePool } from '@/types'

const loading = ref(false)
const saving = ref(false)
const tableData = ref<ResourcePool[]>([])
const total = ref(0)

const query = reactive({
  pageIndex: 1,
  pageSize: 10,
  keyword: '',
  status: '' as string,
})

const statusMap: Record<string, string> = { active: '启用', inactive: '停用' }
const statusColorMap: Record<string, string> = { active: 'success', inactive: 'info' }

const columns: ColumnConfig[] = [
  { prop: 'name', label: '资源池名称', minWidth: 180 },
  { prop: 'gpu_type', label: 'GPU类型', width: 110 },
  { prop: 'node_count', label: '节点数', width: 90, align: 'center' },
  { prop: 'total_gpu', label: 'GPU总数', width: 100, align: 'center' },
  {
    prop: 'available_gpu',
    label: '可用GPU数',
    width: 140,
    type: 'formatter',
    formatter: (value, row) => `${value} / ${row.total_gpu ?? 0}`,
  },
  { prop: 'status', label: '状态', width: 90, type: 'status', statusMap, statusColorMap },
  { prop: 'description', label: '描述', minWidth: 180 },
  { prop: 'created_at', label: '创建时间', width: 170, type: 'datetime' },
]

const stats = computed(() => [
  { label: '资源池总数', value: total.value, icon: 'Box', bg: 'linear-gradient(135deg, #e63946, #f56c6c)' },
  { label: 'GPU 总数', value: gpuTotal.value, icon: 'Cpu', bg: 'linear-gradient(135deg, #409eff, #79bbff)' },
  { label: '可用 GPU', value: gpuAvailable.value, icon: 'Cpu', bg: 'linear-gradient(135deg, #67c23a, #95d475)' },
  { label: '节点总数', value: nodeTotal.value, icon: 'Monitor', bg: 'linear-gradient(135deg, #e6a23c, #eebe77)' },
])

const gpuTotal = computed(() => tableData.value.reduce((sum, i) => sum + (i.total_gpu || 0), 0))
const gpuAvailable = computed(() => tableData.value.reduce((sum, i) => sum + (i.available_gpu || 0), 0))
const nodeTotal = computed(() => tableData.value.reduce((sum, i) => sum + (i.node_count || 0), 0))

const dialogVisible = ref(false)
const formRef = ref<FormInstance>()
const form = reactive<{
  id: string
  name: string
  gpu_type: string
  node_count: number
  total_gpu: number
  available_gpu: number
  status: 'active' | 'inactive'
  description: string
}>({
  id: '',
  name: '',
  gpu_type: '',
  node_count: 1,
  total_gpu: 0,
  available_gpu: 0,
  status: 'active',
  description: '',
})

const rules: FormRules = {
  name: [{ required: true, message: '请输入资源池名称', trigger: 'blur' }],
  gpu_type: [{ required: true, message: '请选择 GPU 类型', trigger: 'change' }],
  node_count: [{ required: true, message: '请输入节点数', trigger: 'blur' }],
  total_gpu: [{ required: true, message: '请输入 GPU 总数', trigger: 'blur' }],
  available_gpu: [
    { required: true, message: '请输入可用 GPU 数', trigger: 'blur' },
    {
      validator: (_rule, value, callback) => {
        if (value > form.total_gpu) callback(new Error('可用 GPU 数不能大于 GPU 总数'))
        else callback()
      },
      trigger: 'blur',
    },
  ],
}

async function loadData() {
  loading.value = true
  try {
    const res = await fetchResourcePoolList({
      pageIndex: query.pageIndex,
      pageSize: query.pageSize,
      keyword: query.keyword || undefined,
      status: query.status || undefined,
    })
    tableData.value = res.list
    total.value = res.total
  } finally {
    loading.value = false
  }
}

function handleSearch() {
  query.pageIndex = 1
  loadData()
}

function handlePageChange(page: number) {
  query.pageIndex = page
  loadData()
}

function handleSizeChange(size: number) {
  query.pageSize = size
  query.pageIndex = 1
  loadData()
}

function openDialog(row?: ResourcePool) {
  form.id = row?.id || ''
  form.name = row?.name || ''
  form.gpu_type = row?.gpu_type || ''
  form.node_count = row?.node_count || 1
  form.total_gpu = row?.total_gpu || 0
  form.available_gpu = row?.available_gpu || 0
  form.status = (row?.status as 'active' | 'inactive') || 'active'
  form.description = row?.description || ''
  dialogVisible.value = true
}

async function handleSave() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return
  saving.value = true
  try {
    const payload = {
      name: form.name,
      gpu_type: form.gpu_type,
      node_count: form.node_count,
      total_gpu: form.total_gpu,
      available_gpu: form.available_gpu,
      status: form.status,
      description: form.description,
    }
    if (form.id) {
      await updateResourcePool(form.id, payload)
      ElMessage.success('资源池更新成功')
    } else {
      await createResourcePool(payload)
      ElMessage.success('资源池创建成功')
    }
    dialogVisible.value = false
    loadData()
  } finally {
    saving.value = false
  }
}

async function handleDelete(row: ResourcePool) {
  await ElMessageBox.confirm(`确定删除资源池「${row.name}」吗？删除后不可恢复。`, '删除确认', {
    type: 'warning',
    confirmButtonText: '删除',
    cancelButtonText: '取消',
  })
  await deleteResourcePool(row.id)
  ElMessage.success('资源池删除成功')
  if (tableData.value.length === 1 && query.pageIndex > 1) {
    query.pageIndex -= 1
  }
  loadData()
}

onMounted(loadData)
</script>

<style lang="scss" scoped>
.stats-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
  margin-bottom: 20px;
}

.stat-card {
  background: $bg-color-white;
  border: 1px solid $border-color-light;
  border-radius: $border-radius-large;
  padding: 20px;
  display: flex;
  align-items: center;
  gap: 16px;

  .stat-icon {
    width: 52px;
    height: 52px;
    border-radius: 12px;
    display: flex;
    align-items: center;
    justify-content: center;
    color: #fff;
  }

  .stat-info {
    .stat-value { font-size: 26px; font-weight: 700; color: $text-primary; }
    .stat-label { font-size: $font-size-mini; color: $text-secondary; }
  }
}

.content-card {
  background: $bg-color-white;
  border: 1px solid $border-color-light;
  border-radius: $border-radius-large;
  padding: 20px;
}

.toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
  gap: 12px;
  flex-wrap: wrap;

  .filters {
    display: flex;
    align-items: center;
    gap: 12px;

    .filter-input { width: 220px; }
    .filter-select { width: 140px; }
  }
}

:deep(.el-form-item__label) {
  white-space: nowrap;
}
</style>
