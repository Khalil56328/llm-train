<template>
  <div class="image-management">
    <PageHeaderCard title="镜像管理" desc="管理训练与推理所需的基础镜像资源，供算子版本、训练任务选择使用。" />

    <!-- 镜像概览 -->
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
            placeholder="搜索镜像名称"
            clearable
            class="filter-input"
            @keyup.enter="handleSearch"
            @clear="handleSearch"
          />
          <el-select
            v-model="query.resource_type"
            placeholder="资源类型"
            clearable
            class="filter-select"
            @change="handleSearch"
          >
            <el-option label="CPU" value="CPU" />
            <el-option label="GPU" value="GPU" />
          </el-select>
          <el-button type="primary" @click="handleSearch">查询</el-button>
        </div>
        <el-button type="primary" @click="openDialog()">
          <el-icon style="margin-right: 4px"><Plus /></el-icon>
          新增镜像
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
      :title="form.id ? '编辑镜像' : '新增镜像'"
      width="560px"
      :close-on-click-modal="false"
    >
      <el-form ref="formRef" :model="form" :rules="rules" label-width="90px">
        <el-form-item label="镜像名称" prop="name">
          <el-input v-model="form.name" placeholder="请输入镜像名称，如 ModelScope 宿主机环境镜像" maxlength="100" />
        </el-form-item>
        <el-form-item label="镜像地址" prop="address">
          <el-input v-model="form.address" placeholder="如 registry.xxx.com/train/pytorch:2.1.0-cu121" maxlength="500" />
        </el-form-item>
        <el-form-item label="资源类型" prop="resource_type">
          <el-radio-group v-model="form.resource_type">
            <el-radio value="CPU">CPU</el-radio>
            <el-radio value="GPU">GPU</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="描述" prop="description">
          <el-input
            v-model="form.description"
            type="textarea"
            :rows="3"
            placeholder="镜像用途说明（可选）"
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
import { Box, Cpu } from '@element-plus/icons-vue'
import PageHeaderCard from '@/components/common/PageHeaderCard.vue'
import DataTable, { type ColumnConfig } from '@/components/common/DataTable.vue'
import { fetchImageList, createImage, updateImage, deleteImage } from '@/api/ops'
import type { DockerImage } from '@/types'

const loading = ref(false)
const saving = ref(false)
const tableData = ref<DockerImage[]>([])
const total = ref(0)

const query = reactive({
  pageIndex: 1,
  pageSize: 10,
  keyword: '',
  resource_type: '' as string,
})

const columns: ColumnConfig[] = [
  { prop: 'name', label: '镜像名称', minWidth: 180 },
  { prop: 'address', label: '镜像地址', minWidth: 280 },
  { prop: 'resource_type', label: '资源类型', width: 100, type: 'formatter', formatter: (value) => String(value || 'CPU') },
  { prop: 'description', label: '描述', minWidth: 180 },
  { prop: 'created_at', label: '创建时间', width: 170, type: 'datetime' },
]

const stats = computed(() => [
  { label: '镜像总数', value: total.value, icon: 'Box', bg: 'linear-gradient(135deg, #e63946, #f56c6c)' },
  { label: 'CPU 镜像', value: cpuCount.value, icon: 'Cpu', bg: 'linear-gradient(135deg, #409eff, #79bbff)' },
  { label: 'GPU 镜像', value: gpuCount.value, icon: 'Cpu', bg: 'linear-gradient(135deg, #67c23a, #95d475)' },
  { label: '当前页', value: tableData.value.length, icon: 'Box', bg: 'linear-gradient(135deg, #e6a23c, #eebe77)' },
])

const cpuCount = computed(() => tableData.value.filter((i) => i.resource_type === 'CPU').length)
const gpuCount = computed(() => tableData.value.filter((i) => i.resource_type === 'GPU').length)

const dialogVisible = ref(false)
const formRef = ref<FormInstance>()
const form = reactive<{
  id: string
  name: string
  address: string
  resource_type: 'CPU' | 'GPU'
  description: string
}>({
  id: '',
  name: '',
  address: '',
  resource_type: 'CPU',
  description: '',
})

const rules: FormRules = {
  name: [{ required: true, message: '请输入镜像名称', trigger: 'blur' }],
  address: [{ required: true, message: '请输入镜像地址', trigger: 'blur' }],
  resource_type: [{ required: true, message: '请选择资源类型', trigger: 'change' }],
}

async function loadData() {
  loading.value = true
  try {
    const res = await fetchImageList({
      pageIndex: query.pageIndex,
      pageSize: query.pageSize,
      keyword: query.keyword || undefined,
      resource_type: query.resource_type || undefined,
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

function openDialog(row?: DockerImage) {
  form.id = row?.id || ''
  form.name = row?.name || ''
  form.address = row?.address || ''
  form.resource_type = (row?.resource_type as 'CPU' | 'GPU') || 'CPU'
  form.description = row?.description || ''
  dialogVisible.value = true
}

async function handleSave() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return
  saving.value = true
  try {
    if (form.id) {
      await updateImage(form.id, {
        name: form.name,
        address: form.address,
        resource_type: form.resource_type,
        description: form.description,
      })
      ElMessage.success('镜像更新成功')
    } else {
      await createImage({
        name: form.name,
        address: form.address,
        resource_type: form.resource_type,
        description: form.description,
      })
      ElMessage.success('镜像创建成功')
    }
    dialogVisible.value = false
    loadData()
  } finally {
    saving.value = false
  }
}

async function handleDelete(row: DockerImage) {
  await ElMessageBox.confirm(`确定删除镜像「${row.name}」吗？删除后不可恢复。`, '删除确认', {
    type: 'warning',
    confirmButtonText: '删除',
    cancelButtonText: '取消',
  })
  await deleteImage(row.id)
  ElMessage.success('镜像删除成功')
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
</style>
