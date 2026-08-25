<template>
  <div class="training-dataset">
    <PageHeaderCard
      title="训练数据集"
      desc="面向模型训练场景，提供集中式数据管理服务，支持多版本管控、数据导入导出等功能，实现训练数据全生命周期标准化管理。"
    />

    <!-- 搜索过滤区 -->
    <SearchFilter
      v-model:model-value="keyword"
      placeholder="数据集名称"
      @search="fetchData"
      @reset="handleReset"
      @create="openCreateDialog"
    >
      <template #filters>
        <el-select v-model="filterCategory" placeholder="数据集分类" clearable style="width: 180px" @change="fetchData">
          <el-option v-for="c in categories" :key="c.value" :label="c.label" :value="c.value" />
        </el-select>
        <el-select v-model="filterDataType" placeholder="数据类型" clearable style="width: 180px" @change="fetchData">
          <el-option v-for="d in dataTypes" :key="d.value" :label="d.label" :value="d.value" />
        </el-select>
      </template>
    </SearchFilter>

    <!-- 数据表 -->
    <DataTable
      :data="tableData"
      :columns="columns"
      :loading="loading"
      :total="total"
      :show-index="true"
      v-model:page="pageIndex"
      v-model:page-size="pageSize"
      @page-change="fetchData"
      @size-change="fetchData"
    >
      <template #name="{ row }">
        <a class="link" @click="goFiles(row as Dataset)">{{ (row as Dataset).name }}</a>
      </template>
      <template #category="{ row }">{{ getCategoryLabel((row as Dataset).category) }}</template>
      <template #dataType="{ row }">{{ getDataTypeLabel((row as Dataset).dataType) }}</template>
      <template #actions="{ row }">
        <el-button type="primary" link size="small" @click="openDetailDialog(row as Dataset)">详情</el-button>
        <el-dropdown trigger="click">
          <el-button type="primary" link size="small">
            更多 <el-icon><ArrowDown /></el-icon>
          </el-button>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item @click="goFiles(row as Dataset)">文件列表</el-dropdown-item>
              <el-dropdown-item @click="openEditDialog(row as Dataset)">编辑</el-dropdown-item>
              <el-dropdown-item @click="deleteDataset(row as Dataset)">删除</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </template>
    </DataTable>

    <!-- 创建/编辑数据集 -->
    <el-dialog
      v-model="dialogVisible"
      :title="editingId ? '编辑训练数据集' : '创建训练数据集'"
      width="640px"
      class="custom-modal"
      :close-on-click-modal="false"
    >
      <el-form :model="formData" label-width="100px">
        <el-form-item label="数据集名称" required>
          <el-input v-model="formData.name" placeholder="请输入数据集名称" />
        </el-form-item>
        <el-form-item label="数据集分类" required>
          <el-select v-model="formData.category" placeholder="请选择" style="width: 100%">
            <el-option v-for="c in categories" :key="c.value" :label="c.label" :value="c.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="数据类型" required>
          <el-radio-group v-model="formData.dataType">
            <el-radio v-for="d in dataTypes" :key="d.value" :value="d.value">{{ d.label }}</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="是否公开">
          <el-switch v-model="formData.isPublic" />
        </el-form-item>
        <el-form-item label="数据集描述">
          <el-input v-model="formData.description" type="textarea" :rows="3" placeholder="请输入描述" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSave">提交</el-button>
      </template>
    </el-dialog>

    <!-- 数据集详情 -->
    <el-dialog v-model="detailVisible" title="数据集详情" width="640px" class="custom-modal">
      <div v-if="detail" class="detail">
        <el-descriptions :column="2" border>
          <el-descriptions-item label="数据集名称">{{ detail.name }}</el-descriptions-item>
          <el-descriptions-item label="数据类型">{{ getDataTypeLabel(detail.dataType) }}</el-descriptions-item>
          <el-descriptions-item label="数据集分类">{{ getCategoryLabel(detail.category) }}</el-descriptions-item>
          <el-descriptions-item label="是否公开">{{ detail.isPublic ? '是' : '否' }}</el-descriptions-item>
          <el-descriptions-item label="文件数">{{ detail.fileCount ?? 0 }}</el-descriptions-item>
          <el-descriptions-item label="文件大小">{{ formatFileSize(detail.size || 0) }}</el-descriptions-item>
          <el-descriptions-item label="创建人">{{ detail.ownerName || '-' }}</el-descriptions-item>
          <el-descriptions-item label="归属用户">{{ detail.ownerName || 'AI租户' }}</el-descriptions-item>
          <el-descriptions-item label="创建时间" :span="2">{{ formatDate(detail.createdAt) }}</el-descriptions-item>
          <el-descriptions-item label="数据集描述" :span="2">{{ detail.description || '-' }}</el-descriptions-item>
        </el-descriptions>
      </div>
      <template #footer>
        <el-button type="primary" @click="detailVisible = false">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ArrowDown } from '@element-plus/icons-vue'
import PageHeaderCard from '@/components/common/PageHeaderCard.vue'
import SearchFilter from '@/components/common/SearchFilter.vue'
import DataTable, { type ColumnConfig } from '@/components/common/DataTable.vue'
import { formatDate, formatFileSize } from '@/utils'
import {
  getDatasetList,
  createDataset,
  updateDataset,
  deleteDataset as deleteDatasetApi,
  getDatasetDetail,
} from '@/api/dataset'
import type { Dataset } from '@/types'

const router = useRouter()

const categories = [
  { label: '文本生成', value: '文本生成' },
  { label: '图像生成', value: '图像生成' },
  { label: '代码生成', value: '代码生成' },
]

const dataTypes = [
  { label: '有监督微调SFT', value: 'SFT' },
  { label: '偏好对齐KTO', value: 'KTO' },
  { label: '偏好对齐DPO', value: 'DPO' },
  { label: 'GRPO(VerL)', value: 'GRPO(VerL)' },
  { label: '预训练(CPT)', value: 'CPT' },
  { label: 'GRPO(swift)', value: 'GRPO(swift)' },
  { label: 'GSPO(swift)', value: 'GSPO(swift)' },
]

const keyword = ref('')
const filterCategory = ref('')
const filterDataType = ref('')
const loading = ref(false)
const tableData = ref<Dataset[]>([])
const total = ref(0)
const pageIndex = ref(1)
const pageSize = ref(10)

const dialogVisible = ref(false)
const editingId = ref<string | null>(null)
const detailVisible = ref(false)
const detail = ref<Dataset | null>(null)

const formData = reactive({
  name: '',
  category: '文本生成',
  dataType: 'SFT',
  isPublic: false,
  description: '',
})

const columns: ColumnConfig[] = [
  { prop: 'name', label: '数据集名称', minWidth: 180, slot: 'name' },
  { prop: 'category', label: '数据集分类', minWidth: 120, slot: 'category' },
  { prop: 'dataType', label: '数据类型', minWidth: 150, slot: 'dataType' },
  {
    prop: 'isPublic',
    label: '是否公开',
    width: 90,
    type: 'status',
    statusMap: { true: '是', false: '否' },
    statusColorMap: { true: 'success', false: 'info' },
  },
  {
    prop: 'size',
    label: '文件大小',
    width: 110,
    type: 'formatter',
    formatter: (v: unknown) => formatFileSize((v as number) || 0),
  },
  { prop: 'ownerName', label: '归属用户', minWidth: 120 },
  { prop: 'createdAt', label: '创建时间', width: 170, type: 'datetime' },
]

async function fetchData() {
  loading.value = true
  try {
    const data = await getDatasetList({
      pageIndex: pageIndex.value,
      pageSize: pageSize.value,
      keyword: keyword.value || undefined,
      category: filterCategory.value || undefined,
      data_type: filterDataType.value || undefined,
      dataset_type: 'training',
    })
    tableData.value = data.list
    total.value = data.total
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

function handleReset() {
  keyword.value = ''
  filterCategory.value = ''
  filterDataType.value = ''
  pageIndex.value = 1
  fetchData()
}

function openCreateDialog() {
  editingId.value = null
  Object.assign(formData, {
    name: '',
    category: '文本生成',
    dataType: 'SFT',
    isPublic: false,
    description: '',
  })
  dialogVisible.value = true
}

async function openEditDialog(row: Dataset) {
  try {
    const d = await getDatasetDetail(row.id)
    editingId.value = d.id
    Object.assign(formData, {
      name: d.name,
      category: d.category,
      dataType: d.dataType,
      isPublic: d.isPublic,
      description: d.description || '',
    })
    dialogVisible.value = true
  } catch {
    /* noop */
  }
}

async function openDetailDialog(row: Dataset) {
  try {
    detail.value = await getDatasetDetail(row.id)
    detailVisible.value = true
  } catch {
    /* noop */
  }
}

async function handleSave() {
  if (!formData.name) return ElMessage.warning('请输入数据集名称')
  try {
    const payload = {
      name: formData.name,
      category: formData.category,
      data_type: formData.dataType,
      is_public: formData.isPublic,
      description: formData.description,
      type: 'training',
      source: 'upload',
    }
    if (editingId.value) {
      await updateDataset(editingId.value, payload)
      ElMessage.success('编辑成功')
    } else {
      await createDataset(payload)
      ElMessage.success('创建成功')
    }
    dialogVisible.value = false
    fetchData()
  } catch {
    /* noop */
  }
}

async function deleteDatasetAction(row: Dataset) {
  await ElMessageBox.confirm(`确定删除数据集「${row.name}」吗？`, '提示', { type: 'warning' })
  await deleteDatasetApi(row.id)
  ElMessage.success('删除成功')
  fetchData()
}

async function deleteDataset(row: Dataset) {
  try {
    await deleteDatasetAction(row)
  } catch {
    /* noop */
  }
}

function goFiles(row: Dataset) {
  router.push({ name: 'data-training-files', params: { id: row.id } })
}

function getCategoryLabel(v: string) {
  return categories.find((c) => c.value === v)?.label || v || '-'
}
function getDataTypeLabel(v: string | undefined) {
  return dataTypes.find((d) => d.value === v)?.label || v || '-'
}

onMounted(fetchData)
</script>

<style lang="scss" scoped>
.training-dataset {
  :deep(.link) {
    color: $color-primary;
    cursor: pointer;
    &:hover {
      text-decoration: underline;
    }
  }
}
.detail {
  padding: 8px 12px;
}
</style>