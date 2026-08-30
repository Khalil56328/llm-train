<template>
  <div class="dataset-plaza">
    <PageHeaderCard
      title="数据集广场"
      desc="一站式开放数据资源池，覆盖多领域多场景的公开数据集，支持零门槛获取与直接调用，赋能模型训练、模型推理、模型评测全流程。"
    />

    <SearchFilter
      v-model:model-value="keyword"
      placeholder="数据集名称"
      :show-create="false"
      @search="fetchData"
      @reset="handleReset"
    >
      <template #filters>
        <el-select v-model="filterType" placeholder="数据集类型" clearable style="width: 180px" @change="fetchData">
          <el-option label="训练数据集" value="training" />
          <el-option label="评测数据集" value="evaluation" />
        </el-select>
        <el-select v-model="filterDataType" placeholder="数据类型" clearable style="width: 180px" @change="fetchData">
          <el-option v-for="d in dataTypes" :key="d.value" :label="d.label" :value="d.value" />
        </el-select>
      </template>
    </SearchFilter>

    <div v-loading="loading" class="plaza-grid">
      <div
        v-for="item in tableData"
        :key="item.id"
        class="plaza-card"
      >
        <div class="card-icon">
          <el-icon :size="36"><DataBoard /></el-icon>
        </div>
        <div class="card-body">
          <div class="card-title">{{ item.name }}</div>
          <div class="card-subtitle" :title="item.description || ''">{{ item.description || '暂无描述' }}</div>
          <div class="card-tag">
            <el-tag type="danger" size="small">{{ getDataTypeLabel(item.dataType) }}</el-tag>
          </div>
          <div class="card-meta">
            <span class="meta-owner">{{ item.ownerName || 'zhadmin' }}</span>
            <span class="meta-date">{{ formatDate(item.createdAt) }}</span>
          </div>
        </div>
        <div class="card-actions">
          <el-tooltip content="详情" placement="top">
            <el-button link size="small" @click="openDetailDialog(item)">
              <el-icon><Document /></el-icon>
            </el-button>
          </el-tooltip>
          <el-tooltip content="下载" placement="top">
            <el-button link size="small" @click="downloadDataset(item)">
              <el-icon><Download /></el-icon>
            </el-button>
          </el-tooltip>
        </div>
      </div>
      <div v-if="!loading && !tableData.length" class="empty">
        <el-empty description="暂无数据集" />
      </div>
    </div>

    <div v-if="total > 0" class="pagination">
      <el-pagination
        v-model:current-page="pageIndex"
        v-model:page-size="pageSize"
        :page-sizes="[12, 24, 48]"
        :total="total"
        layout="total, sizes, prev, pager, next, jumper"
        background
        @current-change="fetchData"
        @size-change="fetchData"
      />
    </div>

    <el-dialog v-model="detailVisible" title="数据集详情" width="640px" class="custom-modal">
      <div v-if="detail" class="detail">
        <el-descriptions :column="2" border>
          <el-descriptions-item label="数据集名称">{{ detail.name }}</el-descriptions-item>
          <el-descriptions-item label="数据类型">{{ getDataTypeLabel(detail.dataType) }}</el-descriptions-item>
          <el-descriptions-item label="数据集分类">{{ detail.category || '训练数据集' }}</el-descriptions-item>
          <el-descriptions-item label="是否公开">{{ detail.isPublic ? '是' : '否' }}</el-descriptions-item>
          <el-descriptions-item label="文件数">{{ detail.fileCount ?? 0 }}</el-descriptions-item>
          <el-descriptions-item label="数据大小">{{ formatFileSize(detail.size || 0) }}</el-descriptions-item>
          <el-descriptions-item label="创建人">{{ detail.ownerName || 'zhadmin' }}</el-descriptions-item>
          <el-descriptions-item label="归属用户">{{ detail.ownerName || 'AI租户' }}</el-descriptions-item>
          <el-descriptions-item label="创建时间" :span="2">{{ formatDate(detail.createdAt) }}</el-descriptions-item>
          <el-descriptions-item label="数据集描述" :span="2">{{ detail.description || detail.name }}</el-descriptions-item>
        </el-descriptions>
      </div>
      <template #footer>
        <el-button type="primary" @click="detailVisible = false">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { DataBoard, Document, Download } from '@element-plus/icons-vue'
import PageHeaderCard from '@/components/common/PageHeaderCard.vue'
import SearchFilter from '@/components/common/SearchFilter.vue'
import { formatDate, formatFileSize } from '@/utils'
import { getPlazaDatasets, getDatasetDetail, downloadDataset as downloadApi } from '@/api/dataset'
import type { Dataset } from '@/types'

const router = useRouter()

const keyword = ref('')
const filterType = ref('')
const filterDataType = ref('')
const tableData = ref<Dataset[]>([])
const total = ref(0)
const pageIndex = ref(1)
const pageSize = ref(12)
const loading = ref(false)

const detailVisible = ref(false)
const detail = ref<Dataset | null>(null)

const dataTypes = [
  { label: '有监督微调SFT', value: 'SFT' },
  { label: '偏好对齐DPO', value: 'DPO' },
  { label: '偏好对齐KTO', value: 'KTO' },
  { label: 'GRPO(VerL)', value: 'GRPO(VerL)' },
  { label: 'GRPO(swift)', value: 'GRPO(swift)' },
  { label: 'GSPO(swift)', value: 'GSPO(swift)' },
  { label: '预训练(CPT)', value: 'CPT' },
  { label: 'OpenCompass', value: 'OpenCompass' },
]

async function fetchData() {
  loading.value = true
  try {
    const data = await getPlazaDatasets({
      pageIndex: pageIndex.value,
      pageSize: pageSize.value,
      keyword: keyword.value || undefined,
      dataset_type: filterType.value || undefined,
      data_type: filterDataType.value || undefined,
    })
    tableData.value = data.list
    total.value = data.total
  } finally {
    loading.value = false
  }
}

function handleReset() {
  keyword.value = ''
  filterType.value = ''
  filterDataType.value = ''
  pageIndex.value = 1
  fetchData()
}

function getDataTypeLabel(v: string | undefined) {
  return dataTypes.find((d) => d.value === v)?.label || v || '-'
}

async function openDetailDialog(row: Dataset) {
  try {
    detail.value = await getDatasetDetail(row.id)
    detailVisible.value = true
  } catch {
    /* noop */
  }
}

async function downloadDataset(row: Dataset) {
  try {
    await downloadApi(row.id, `${row.name}.zip`)
    ElMessage.success('已开始下载')
  } catch {
    /* 下载失败时 request 层已提示 */
  }
}

onMounted(fetchData)
</script>

<style lang="scss" scoped>
.dataset-plaza {
  .plaza-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
    gap: 16px;
    background: $bg-color-white;
    border: 1px solid $border-color-light;
    border-radius: $border-radius-large;
    padding: 16px;
    min-height: 200px;
  }
  .plaza-card {
    border: 1px solid $border-color-light;
    border-radius: 6px;
    padding: 16px;
    background: $bg-color-white;
    position: relative;
    transition: all 0.2s;
    display: flex;
    flex-direction: column;
    gap: 8px;
    &:hover {
      border-color: $color-primary-light;
      box-shadow: 0 4px 12px rgba(230, 57, 70, 0.08);
    }
    .card-icon {
      color: $color-primary;
    }
    .card-body {
      flex: 1;
    }
    .card-title {
      font-size: 14px;
      font-weight: 600;
      color: $text-primary;
    }
    .card-subtitle {
      font-size: 12px;
      color: $text-secondary;
      margin-top: 2px;
      display: -webkit-box;
      -webkit-box-orient: vertical;
      -webkit-line-clamp: 2;
      overflow: hidden;
      word-break: break-all;
    }
    .card-tag {
      margin-top: 8px;
    }
    .card-meta {
      margin-top: 8px;
      display: flex;
      justify-content: space-between;
      font-size: 12px;
      color: $text-secondary;
    }
    .card-actions {
      position: absolute;
      top: 8px;
      right: 8px;
      display: flex;
      gap: 4px;
      :deep(.el-icon) {
        color: $color-primary;
        font-size: 16px;
      }
    }
  }
  .empty {
    grid-column: 1 / -1;
  }
  .pagination {
    margin-top: 16px;
    display: flex;
    justify-content: flex-end;
  }
  .detail { padding: 8px 12px; }
}
</style>