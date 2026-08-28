<template>
  <div class="dataset-file-panel">
    <div v-if="dataset" class="header-info">
      <div class="left">
        <span class="info-item">目录数据集<span class="dataset-name">{{ dataset.name }}</span></span>
        <span class="separator">|</span>
        <span class="version-filter">
          <span class="version-label">版本</span>
          <el-select
            v-model="currentVersionId"
            placeholder="全部版本"
            clearable
            size="default"
            style="width: 180px"
            @change="handleVersionChange"
          >
            <el-option
              v-for="v in versions"
              :key="v.id"
              :label="v.isDefault ? `${v.version}（默认）` : v.version"
              :value="v.id"
            />
          </el-select>
        </span>
        <span class="separator">|</span>
        <span class="stat">文件数量{{ stats.fileCount }},</span>
        <span class="stat success">成功{{ stats.success }},</span>
        <span class="stat danger">失败{{ stats.failed }},</span>
        <span class="stat warning">处理中{{ stats.processing }}</span>
      </div>
      <div class="right">
        <el-select v-model="filterStatus" placeholder="文件状态" clearable style="width: 140px" @change="fetchFiles">
          <el-option label="成功" value="success" />
          <el-option label="处理中" value="processing" />
          <el-option label="失败" value="failed" />
        </el-select>
        <el-input v-model="filterKeyword" placeholder="文件名称" clearable style="width: 180px" @clear="fetchFiles" @keyup.enter="fetchFiles" />
        <el-button type="primary" @click="fetchFiles">
          <el-icon><Search /></el-icon><span>搜索</span>
        </el-button>
        <el-button @click="handleReset">
          <el-icon><Refresh /></el-icon><span>重置</span>
        </el-button>
        <el-button type="primary" @click="openUploadDialog">
          <el-icon><Plus /></el-icon><span>数据添加</span>
        </el-button>
      </div>
    </div>

    <div class="files-layout">
      <!-- 左侧：采集任务（按用户上传批次聚合） -->
      <div class="collect-task-panel">
        <el-table
          :data="collectTasks"
          :border="false"
          class="collect-table"
          v-loading="tasksLoading"
        >
          <el-table-column label="采集任务" align="center" min-width="150">
            <template #default="{ row }">
              <span class="task-name" :title="row.taskName">{{ formatTaskTime(row.taskName) }}</span>
            </template>
          </el-table-column>
          <el-table-column label="状态" align="center" width="88">
            <template #default="{ row }">
              <el-tag :type="taskStatusType(row.status)" size="small">{{ taskStatusText(row.status) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="采集方式" align="center" width="96">
            <template #default="{ row }">
              {{ sourceText(row.source) }}
            </template>
          </el-table-column>
          <el-table-column label="文件数" align="center" width="72">
            <template #default="{ row }">
              <span>{{ row.successCount }}/{{ row.fileCount }}</span>
            </template>
          </el-table-column>
          <!-- 空态：保留表头，与右侧 DataTable 结构一致，两侧高度自然对齐 -->
          <template #empty>
            <el-empty description="暂无采集任务" :image-size="60" />
          </template>
        </el-table>
      </div>

      <!-- 右侧：文件列表 -->
      <div class="file-table-panel">
        <DataTable
          :data="files"
          :columns="columns"
          :loading="loading"
          :total="total"
          :show-index="true"
          :show-pagination="true"
          :empty-image-size="60"
          v-model:page="pageIndex"
          v-model:page-size="pageSize"
          @page-change="fetchFiles"
          @size-change="fetchFiles"
          :action-width="80"
        >
          <template #fileName="{ row }">
            <a class="link" @click="downloadFile(row as DatasetFile)">{{ (row as DatasetFile).fileName }}</a>
          </template>
          <template #actions="{ row }">
            <el-button type="danger" link size="small" @click="deleteFile(row as DatasetFile)">删除</el-button>
          </template>
        </DataTable>
      </div>
    </div>

    <!-- 数据添加弹窗 -->
    <el-dialog v-model="uploadDialog" title="添加数据文件" width="560px" class="custom-modal">
      <el-form label-width="100px">
        <el-form-item label="上传版本">
          <el-select v-model="uploadVersionId" style="width: 100%" :disabled="uploading">
            <el-option
              v-for="v in versions"
              :key="v.id"
              :label="v.isDefault ? `${v.version}（默认）` : v.version"
              :value="v.id"
            />
          </el-select>
          <div class="version-tip">文件将上传到所选版本，缺省为默认版本</div>
        </el-form-item>
        <el-form-item label="数据来源">
          <el-select v-model="uploadSource" style="width: 100%">
            <el-option label="本地上传" value="local_upload" />
            <el-option label="ModelScope 下载" value="modelscope" />
          </el-select>
        </el-form-item>

        <!-- ModelScope 仓库输入 -->
        <template v-if="uploadSource === 'modelscope'">
          <el-form-item label="数据集仓库">
            <el-input
              v-model="modelscopeRepo"
              placeholder="请输入 ModelScope 数据集仓库 ID"
              clearable
              :disabled="uploading"
            >
            </el-input>
          </el-form-item>
          <el-form-item label="子路径">
            <el-input
              v-model="modelscopeSubPath"
              placeholder="可选，仓库内子文件/目录，留空自动挑选主数据文件"
              clearable
              :disabled="uploading"
            />
          </el-form-item>
          <div class="modelscope-tip">
            <el-alert type="info" :closable="false" show-icon>
              <template #title>
                支持 swift/alpaca-cleaned、AI-ModelScope/alpaca-gpt4-data-zh 等
                数据集仓库。仓库内 CSV 将自动转换为 MS-Swift 标准的 JSONL 格式入库。
              </template>
            </el-alert>
          </div>
        </template>

        <!-- 本地上传 -->
        <template v-if="uploadSource === 'local_upload'">
          <el-upload
            drag
            multiple
            :auto-upload="false"
            v-model:file-list="uploadFileList"
            class="upload-dragger"
            :disabled="uploading"
          >
            <el-icon class="upload-icon"><UploadFilled /></el-icon>
            <div class="el-upload__text">拖拽文件或点击上传</div>
          </el-upload>
          <div class="example-links">
            <span>示例下载：</span>
            <a @click="downloadExample('sft')">SFT 格式示例</a>
            <a @click="downloadExample('cpt')">CPT 格式示例</a>
          </div>
          <div class="csv-tip">提示：上传的 CSV 文件会自动转换为 JSONL 训练格式。</div>
        </template>

        <div v-if="uploadJobs.length" class="upload-jobs">
          <div v-for="job in uploadJobs" :key="job.uid" class="upload-job">
            <span class="job-name" :title="job.name">{{ job.name }}</span>
            <el-progress
              v-if="job.status === 'uploading' || job.status === 'pending'"
              :percentage="job.percent"
              :stroke-width="6"
              class="job-progress"
            />
            <el-tag v-else-if="job.status === 'success'" type="success" size="small">成功</el-tag>
            <el-tag v-else type="danger" size="small">失败</el-tag>
            <el-button v-if="job.status === 'failed'" type="primary" link size="small" @click="retryJob(job)">重试</el-button>
          </div>
        </div>
      </el-form>
      <template #footer>
        <el-button @click="closeUploadDialog">取消</el-button>
        <el-button type="primary" :loading="uploading" @click="submitUpload">
          {{ uploadSource === 'modelscope' ? '下载' : '提交' }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { UploadUserFile } from 'element-plus'
import { Search, Refresh, Plus, UploadFilled } from '@element-plus/icons-vue'
import DataTable, { type ColumnConfig } from '@/components/common/DataTable.vue'
import { formatFileSize } from '@/utils'
import {
  getDatasetDetail,
  getDatasetFiles,
  getDatasetFileStats,
  uploadDatasetFile,
  deleteDatasetFile,
  getCollectTasks,
  getDatasetVersions,
  downloadDatasetFile,
  downloadTemplate,
  importFromModelscope,
} from '@/api/dataset'
import type { Dataset, DatasetFile, DatasetVersion, CollectTask, DatasetFileSource } from '@/types'

const props = defineProps<{ datasetId: string }>()
const route = useRoute()

const dataset = ref<Dataset | null>(null)
const files = ref<DatasetFile[]>([])
const total = ref(0)
const stats = reactive({ fileCount: 0, success: 0, failed: 0, processing: 0, totalSize: 0 })

const pageIndex = ref(1)
const pageSize = ref(10)
const loading = ref(false)
const filterStatus = ref('')
const filterKeyword = ref('')

// 版本维度
const versions = ref<DatasetVersion[]>([])
const currentVersionId = ref('')

// 采集任务（按批次聚合）
const collectTasks = ref<CollectTask[]>([])
const tasksLoading = ref(false)

interface UploadJob {
  uid: number
  name: string
  raw: File
  status: 'pending' | 'uploading' | 'success' | 'failed'
  percent: number
  error?: string
}

const uploadDialog = ref(false)
const uploadSource = ref<DatasetFileSource>('local_upload')
const uploading = ref(false)
const uploadVersionId = ref('')
const uploadFileList = ref<UploadUserFile[]>([])
const uploadJobs = ref<UploadJob[]>([])

// ModelScope 下载
const modelscopeRepo = ref('')
const modelscopeSubPath = ref('')
const modelscopeExample = ref('')

let uidSeq = Date.now()

const columns: ColumnConfig[] = [
  { prop: 'fileName', label: '文件名称', minWidth: 220, slot: 'fileName' },
  {
    prop: 'versionId',
    label: '所属版本',
    width: 110,
    type: 'formatter',
    formatter: (v: unknown) => {
      const id = v as string
      if (!id) return '-'
      return versions.value.find((x) => x.id === id)?.version || id.slice(0, 8)
    },
  },
  {
    prop: 'status',
    label: '状态',
    width: 90,
    type: 'status',
    statusMap: { success: '成功', processing: '处理中', failed: '失败' },
    statusColorMap: { success: 'success', processing: 'warning', failed: 'danger' },
  },
  {
    prop: 'sampleCount',
    label: '样本数',
    width: 100,
    type: 'formatter',
    formatter: (v: unknown) => ((v as number) ?? 0).toLocaleString(),
  },
  {
    prop: 'size',
    label: '文件大小',
    width: 110,
    type: 'formatter',
    formatter: (v: unknown) => formatFileSize((v as number) || 0),
  },
  { prop: 'createdAt', label: '上传时间', width: 170, type: 'datetime' },
]

function sourceText(source?: string) {
  if (source === 'platform') return '平台数据'
  if (source === 'modelscope') return 'ModelScope'
  return '本地上传'
}

function onPickExample(repo: string) {
  modelscopeRepo.value = repo
}

function taskStatusText(status: string) {
  const map: Record<string, string> = { success: '成功', failed: '失败', processing: '处理中' }
  return map[status] || status
}

function taskStatusType(status: string) {
  if (status === 'success') return 'success'
  if (status === 'failed') return 'danger'
  return 'warning'
}

// 与文件列表上传时间列（DataTable 的 datetime 类型）保持一致的展示格式：2026/8/18 17:38:11
function formatTaskTime(val?: string | null) {
  if (!val) return '-'
  const d = new Date(val)
  if (Number.isNaN(d.getTime())) return val
  return d.toLocaleString('zh-CN')
}

async function fetchDataset() {
  dataset.value = await getDatasetDetail(props.datasetId)
}

async function fetchVersions() {
  versions.value = await getDatasetVersions(props.datasetId)
  // 初始选中：路由指定版本 > 默认版本 > 全部
  if (!currentVersionId.value) {
    const qv = route.query.versionId
    if (typeof qv === 'string' && versions.value.some((v) => v.id === qv)) {
      currentVersionId.value = qv
    } else {
      const def = versions.value.find((v) => v.isDefault)
      currentVersionId.value = def?.id || ''
    }
  }
}

async function fetchStats() {
  const s = await getDatasetFileStats(props.datasetId, {
    versionId: currentVersionId.value || undefined,
  })
  Object.assign(stats, s)
}

async function fetchCollectTasks() {
  tasksLoading.value = true
  try {
    collectTasks.value = await getCollectTasks(props.datasetId, {
      versionId: currentVersionId.value || undefined,
    })
  } finally {
    tasksLoading.value = false
  }
}

async function fetchFiles() {
  loading.value = true
  try {
    const data = await getDatasetFiles(props.datasetId, {
      pageIndex: pageIndex.value,
      pageSize: pageSize.value,
      keyword: filterKeyword.value || undefined,
      status: filterStatus.value || undefined,
      versionId: currentVersionId.value || undefined,
    })
    files.value = data.list
    total.value = data.total
  } finally {
    loading.value = false
  }
}

function handleVersionChange() {
  pageIndex.value = 1
  fetchFiles()
  fetchStats()
  fetchCollectTasks()
}

function handleReset() {
  filterKeyword.value = ''
  filterStatus.value = ''
  pageIndex.value = 1
  fetchFiles()
}

// ===== 上传 =====
function openUploadDialog() {
  uploadFileList.value = []
  uploadJobs.value = []
  modelscopeRepo.value = ''
  modelscopeSubPath.value = ''
  modelscopeExample.value = ''
  uploadSource.value = 'local_upload'
  // 上传目标版本：默认当前筛选版本，未筛选则为默认版本
  uploadVersionId.value = currentVersionId.value || versions.value.find((v) => v.isDefault)?.id || ''
  uploadDialog.value = true
}

function closeUploadDialog() {
  if (uploading.value) return
  uploadDialog.value = false
}

// 上传全部成功：绕过 uploading 守卫直接关闭弹窗并清空文件列表，避免重复提交
function finishUploadSuccess() {
  uploadDialog.value = false
  uploadFileList.value = []
  uploadJobs.value = []
}

let activeBatchId = ''

async function uploadOne(job: UploadJob, batchId: string) {
  const form = new FormData()
  form.append('file', job.raw, job.name)
  form.append('source', uploadSource.value)
  form.append('batch_id', batchId)
  if (uploadVersionId.value) form.append('version_id', uploadVersionId.value)
  await uploadDatasetFile(props.datasetId, form, (p) => {
    job.percent = p
  })
}

async function submitModelscope() {
  const repo = modelscopeRepo.value.trim()
  if (!repo) {
    ElMessage.warning('请输入 ModelScope 数据集仓库 ID')
    return
  }
  if (!repo.includes('/')) {
    ElMessage.warning('仓库 ID 应为「所有者/仓库名」格式，例如 swift/alpaca-cleaned')
    return
  }
  uploading.value = true
  try {
    const form = new FormData()
    form.append('repo_id', repo)
    form.append('sub_dir_path', modelscopeSubPath.value.trim())
    form.append('source', 'modelscope')
    form.append('batch_id', `modelscope_${uidSeq}_${Math.random().toString(36).slice(2, 8)}`)
    if (uploadVersionId.value) form.append('version_id', uploadVersionId.value)
    const res = await importFromModelscope(props.datasetId, form)
    const failed = (res.files || []).filter((f) => f.status === 'failed')
    if (!failed.length) {
      ElMessage.success(`ModelScope 数据集下载成功，共 ${res.files?.length || 0} 个文件`)
    } else {
      ElMessage.warning(`下载完成，其中 ${failed.length} 个文件失败`)
    }
    finishUploadSuccess()
    await fetchFiles()
    await fetchStats()
    await fetchCollectTasks()
  } catch (e) {
    ElMessage.error((e as Error)?.message || 'ModelScope 下载失败')
  } finally {
    uploading.value = false
  }
}

async function submitUpload() {
  // ModelScope 模式：走仓库下载
  if (uploadSource.value === 'modelscope') {
    await submitModelscope()
    return
  }

  if (!uploadFileList.value.length) {
    ElMessage.warning('请选择文件')
    return
  }
  uploading.value = true
  activeBatchId = `batch_${uidSeq}_${Math.random().toString(36).slice(2, 8)}`
  const batchFiles: UploadJob[] = uploadFileList.value
    .filter((f) => !!f.raw)
    .map((f, i) => ({
      uid: f.uid ?? uidSeq + i,
      name: f.name,
      raw: f.raw as File,
      status: 'pending' as const,
      percent: 0,
    }))
  if (!batchFiles.length) {
    uploading.value = false
    ElMessage.warning('请选择文件')
    return
  }
  uploadJobs.value = batchFiles
  try {
    await runConcurrent(batchFiles, 3)
    const failed = uploadJobs.value.filter((j) => j.status === 'failed')
    if (failed.length === 0) {
      ElMessage.success('上传成功')
      finishUploadSuccess()
    } else {
      ElMessage.warning(`${failed.length} 个文件上传失败，可点击重试`)
    }
    await fetchFiles()
    await fetchStats()
    await fetchCollectTasks()
  } finally {
    uploading.value = false
  }
}

async function runConcurrent(jobs: UploadJob[], limit: number) {
  let idx = 0
  const workers = Array.from({ length: Math.min(limit, jobs.length) }, async () => {
    while (idx < jobs.length) {
      const job = jobs[idx]
      idx += 1
      job.status = 'uploading'
      job.percent = 0
      try {
        await uploadOne(job, activeBatchId)
        job.status = 'success'
      } catch (e) {
        job.status = 'failed'
        job.error = (e as Error)?.message || '上传失败'
      }
    }
  })
  await Promise.all(workers)
}

async function retryJob(job: UploadJob) {
  job.status = 'uploading'
  job.percent = 0
  try {
    await uploadOne(job, activeBatchId)
    job.status = 'success'
    const failed = uploadJobs.value.filter((j) => j.status === 'failed')
    if (failed.length === 0) {
      ElMessage.success('上传成功')
      finishUploadSuccess()
    }
    await fetchFiles()
    await fetchStats()
    await fetchCollectTasks()
  } catch (e) {
    job.status = 'failed'
    job.error = (e as Error)?.message || '上传失败'
  }
}

function downloadExample(name: string) {
  downloadTemplate(name)
}

// ===== 下载 / 删除 =====
function downloadFile(row: DatasetFile) {
  if (!row.storagePath) {
    ElMessage.info('该文件无存储路径')
    return
  }
  // 使用 blob + token 下载，避免 window.open 鉴权失败
  downloadDatasetFile(props.datasetId, row.id, row.fileName).catch(() => {})
}

async function deleteFile(row: DatasetFile) {
  await ElMessageBox.confirm(`确定删除文件「${row.fileName}」吗？`, '提示', { type: 'warning' })
  await deleteDatasetFile(row.id)
  ElMessage.success('删除成功')
  await fetchFiles()
  await fetchStats()
  await fetchCollectTasks()
}

onMounted(async () => {
  await fetchDataset()
  await fetchVersions()
  await Promise.all([fetchFiles(), fetchStats(), fetchCollectTasks()])
})
</script>

<style lang="scss" scoped>
.dataset-file-panel {
  .header-info {
    background: $bg-color-white;
    border: 1px solid $border-color-light;
    border-radius: $border-radius-large;
    padding: 14px 20px;
    margin-bottom: 16px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    flex-wrap: wrap;
    gap: 12px;

    .left {
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 14px;
      color: $text-regular;

      .info-item {
        color: $text-primary;
      }
      .dataset-name {
        color: $color-primary;
        margin-left: 4px;
        font-weight: 500;
      }
      .separator {
        color: $border-color;
      }
      .stat.success {
        color: $color-success;
      }
      .stat.danger {
        color: $color-danger;
      }
      .stat.warning {
        color: $color-warning;
      }
    }

    .right {
      display: flex;
      align-items: center;
      gap: 8px;
    }
  }

  .files-layout {
    display: grid;
    grid-template-columns: 40% 1fr;
    gap: 16px;
    align-items: start;
  }

  // 与右侧文件列表（DataTable）样式保持一致：表头背景色、字体颜色、cell 内边距均相同
  .collect-task-panel {
    background: $bg-color-white;
    border: 1px solid $border-color-light;
    border-radius: $border-radius-large;
    overflow: hidden;
    min-width: 0;

    :deep(.collect-table) {
      width: 100%;
      .el-table__header th {
        background-color: $bg-card-header;
        color: $text-primary;
        font-weight: 600;
        font-size: 13px;
      }

      .el-table__cell {
        font-size: 13px;
      }
    }

    .task-name {
      display: inline-block;
      max-width: 100%;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
      vertical-align: middle;
    }
  }

  .file-table-panel {
    min-width: 0;
  }

  .upload-dragger {
    width: 100%;
    :deep(.el-upload-dragger) {
      width: 100%;
      height: 120px;
    }
  }

  .example-links {
    margin-top: 12px;
    color: $text-secondary;
    font-size: 13px;
    a {
      color: $color-primary;
      margin: 0 8px;
      text-decoration: underline;
      cursor: pointer;
    }
  }

  .modelscope-tip {
    margin-top: 12px;
  }

  .csv-tip {
    margin-top: 10px;
    color: $text-secondary;
    font-size: 12px;
  }

  .upload-jobs {
    margin-top: 12px;
    max-height: 200px;
    overflow-y: auto;
    border: 1px solid $border-color-light;
    border-radius: 4px;
    padding: 8px;

    .upload-job {
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 4px 0;

      .job-name {
        flex: 0 0 40%;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
        font-size: 13px;
        color: $text-primary;
      }
      .job-progress {
        flex: 1;
      }
    }
  }

  :deep(.link) {
    color: $color-primary;
    cursor: pointer;
    &:hover {
      text-decoration: underline;
    }
  }
}
</style>
