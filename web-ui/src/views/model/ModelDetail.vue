<template>
  <div class="model-detail" v-loading="loading">
    <div class="detail-header">
      <el-page-header @back="goBack">
        <template #content>
          <span class="model-name">{{ modelData?.name || '模型详情' }}</span>
          <el-tag v-if="modelData?.type" size="small" type="info" style="margin-left: 8px">
            {{ ModelTypeMap[modelData.type as keyof typeof ModelTypeMap] || modelData.type }}
          </el-tag>
          <el-tag v-if="modelData?.isPublic" size="small" type="success" style="margin-left: 8px">公开</el-tag>
        </template>
      </el-page-header>
    </div>

    <div class="detail-body" v-if="modelData">
      <!-- 左侧：版本列表 -->
      <div class="version-sidebar">
        <div class="sidebar-header">
          <span class="sidebar-title">版本列表</span>
          <el-button type="primary" size="small" @click="openCreateVersion">
            <el-icon><Plus /></el-icon>
            新建版本
          </el-button>
        </div>
        <div class="version-list">
          <div
            v-for="v in versions"
            :key="v.id"
            class="version-item"
            :class="{ active: currentVersionId === v.id }"
            @click="selectVersion(v)"
          >
            <div class="version-name">
              <span>{{ v.version }}</span>
              <el-tag v-if="v.isDefault" size="small" type="success">默认</el-tag>
            </div>
            <div class="version-meta">
              <span v-if="v.framework">{{ v.framework }}</span>
              <span v-if="v.size">{{ formatSize(v.size) }}</span>
              <span>{{ v.fileCount || 0 }} 个文件</span>
            </div>
            <div class="version-status">
              <el-tag :type="versionStatusType(v.status)" size="small">{{ versionStatusText(v.status) }}</el-tag>
            </div>
            <div class="version-actions" v-if="!v.isDefault">
              <el-button link size="small" type="primary" @click.stop="setDefault(v.id)">设为默认</el-button>
              <el-button link size="small" type="danger" @click.stop="deleteVersion(v.id)">删除</el-button>
            </div>
          </div>
          <el-empty v-if="versions.length === 0" description="暂无版本" :image-size="60" />
        </div>
      </div>

      <!-- 右侧：内容区 -->
      <div class="detail-content">
        <el-tabs v-model="activeTab">
          <el-tab-pane label="模型介绍" name="intro">
            <div class="intro-section">
              <el-descriptions :column="2" border>
                <el-descriptions-item label="模型名称">{{ modelData.name }}</el-descriptions-item>
                <el-descriptions-item label="模型类型">{{ ModelTypeMap[modelData.type as keyof typeof ModelTypeMap] || modelData.type }}</el-descriptions-item>
                <el-descriptions-item label="规格">{{ ModelSpecMap[modelData.spec as keyof typeof ModelSpecMap] || modelData.spec }}</el-descriptions-item>
                <el-descriptions-item label="厂商">{{ modelData.vendor }}</el-descriptions-item>
                <el-descriptions-item label="当前版本">{{ modelData.version }}</el-descriptions-item>
                <el-descriptions-item label="状态">
                  <el-tag :type="modelData.status === 'active' ? 'success' : 'info'" size="small">{{ modelData.status === 'active' ? '正常' : '停用' }}</el-tag>
                </el-descriptions-item>
                <el-descriptions-item label="创建时间">{{ modelData.createdAt }}</el-descriptions-item>
                <el-descriptions-item label="是否公开">{{ modelData.isPublic ? '是' : '否' }}</el-descriptions-item>
                <el-descriptions-item label="描述" :span="2">{{ modelData.description || '暂无描述' }}</el-descriptions-item>
              </el-descriptions>
              <div class="intro-tags" v-if="parsedTags.length">
                <span class="tag-label">标签：</span>
                <el-tag v-for="tag in parsedTags" :key="tag" size="small" type="info" style="margin-right: 6px">{{ tag }}</el-tag>
              </div>
            </div>
          </el-tab-pane>

          <el-tab-pane label="模型文件" name="files">
            <div class="files-section" v-if="currentVersion">
              <div class="files-header">
                <span>当前版本：{{ currentVersion.version }}</span>
                <el-button type="primary" size="small" @click="openAddFile">
                  <el-icon><Plus /></el-icon>
                  添加文件
                </el-button>
              </div>
              <el-table :data="files" stripe style="width: 100%">
                <el-table-column prop="fileName" label="文件名" min-width="200" />
                <el-table-column prop="fileType" label="类型" width="120">
                  <template #default="{ row }">
                    <el-tag size="small">{{ row.fileType }}</el-tag>
                  </template>
                </el-table-column>
                <el-table-column prop="fileSize" label="大小" width="120">
                  <template #default="{ row }">{{ formatSize(row.fileSize) }}</template>
                </el-table-column>
                <el-table-column prop="status" label="状态" width="100">
                  <template #default="{ row }">
                    <el-tag :type="row.status === 'ready' ? 'success' : row.status === 'uploading' ? 'warning' : 'danger'" size="small">
                      {{ row.status === 'ready' ? '就绪' : row.status === 'uploading' ? '上传中' : '失败' }}
                    </el-tag>
                  </template>
                </el-table-column>
                <el-table-column prop="createdAt" label="创建时间" width="180" />
                <el-table-column label="操作" width="120" fixed="right">
                  <template #default="{ row }">
                    <el-button link type="primary" size="small" @click="downloadFile(row as ModelFile)">下载</el-button>
                    <el-button link type="danger" size="small" @click="handleDeleteFile(row.id)">删除</el-button>
                  </template>
                </el-table-column>
              </el-table>
              <el-empty v-if="files.length === 0" description="暂无文件" />
            </div>
            <el-empty v-else description="请先选择一个版本" />
          </el-tab-pane>
        </el-tabs>
      </div>
    </div>

    <!-- 创建版本弹窗 -->
    <el-dialog v-model="versionDialogVisible" title="创建版本" width="500px" class="custom-modal">
      <el-form :model="versionForm" label-width="100px">
        <el-form-item label="版本号" required>
          <el-input v-model="versionForm.version" placeholder="如: v1.0.0" />
        </el-form-item>
        <el-form-item label="版本描述">
          <el-input v-model="versionForm.description" type="textarea" :rows="3" placeholder="请输入版本描述" />
        </el-form-item>
        <el-form-item label="推理框架">
          <el-select v-model="versionForm.framework" style="width: 100%" clearable>
            <el-option label="vLLM" value="vLLM" />
            <el-option label="MindIE" value="MindIE" />
            <el-option label="自定义" value="custom" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="versionDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleCreateVersion" :loading="creatingVersion">创建</el-button>
      </template>
    </el-dialog>

    <!-- 添加文件弹窗 -->
    <el-dialog v-model="fileDialogVisible" title="添加文件" width="560px" class="custom-modal">
      <el-alert type="info" :closable="false" show-icon style="margin-bottom: 16px">
        <template #title>支持拖拽文件到此处或点击选择本地文件，可一次选择多个文件</template>
      </el-alert>
      <el-upload
        ref="fileUploadRef"
        drag
        multiple
        :auto-upload="false"
        :file-list="uploadFileList"
        :on-change="handleUploadChange"
        :on-remove="handleUploadRemove"
      >
        <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
        <div class="el-upload__text">将文件拖到此处，或<em>点击选择文件</em></div>
        <template #tip>
          <div class="el-upload__tip">支持 .safetensors / .bin / .json / .txt 等模型文件，可多选</div>
        </template>
      </el-upload>
      <el-progress v-if="addingFile" :percentage="uploadProgress" :stroke-width="6" style="margin-top: 16px" />
      <template #footer>
        <el-button @click="fileDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleAddFiles" :loading="addingFile" :disabled="uploadFileList.length === 0">
          开始上传
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Plus, UploadFilled } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { UploadFile, UploadInstance } from 'element-plus'
import { getModel, getModelVersions, createModelVersion, setDefaultVersion, deleteModelVersion, getModelFiles, deleteModelFile, uploadModelFiles, downloadModelFile } from '@/api/model'
import { ModelTypeMap, ModelSpecMap } from '@/types'
import type { Model, ModelVersion, ModelFile } from '@/types'

const route = useRoute()
const router = useRouter()
const modelId = computed(() => route.params.id as string)

const loading = ref(false)
const modelData = ref<Model | null>(null)
const versions = ref<ModelVersion[]>([])
const currentVersionId = ref('')
const files = ref<ModelFile[]>([])
const activeTab = ref('intro')

// 版本弹窗
const versionDialogVisible = ref(false)
const creatingVersion = ref(false)
const versionForm = ref({ version: '', description: '', framework: '' })

// 文件弹窗
const fileDialogVisible = ref(false)
const addingFile = ref(false)
const uploadProgress = ref(0)
const fileUploadRef = ref<UploadInstance>()
const uploadFileList = ref<UploadFile[]>([])

const currentVersion = computed(() => versions.value.find(v => v.id === currentVersionId.value))

const parsedTags = computed(() => {
  if (!modelData.value?.tags) return []
  const t = modelData.value.tags
  return typeof t === 'string' ? JSON.parse(t || '[]') : t
})

function formatSize(bytes: number) {
  if (!bytes || bytes === 0) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  const i = Math.floor(Math.log(bytes) / Math.log(1024))
  return `${(bytes / Math.pow(1024, i)).toFixed(1)} ${units[i]}`
}

function versionStatusType(status: string): 'success' | 'warning' | 'info' | 'danger' {
  const map: Record<string, 'success' | 'warning' | 'info' | 'danger'> = { ready: 'success', uploading: 'warning', failed: 'danger' }
  return map[status] || 'info'
}

function versionStatusText(status: string) {
  const map: Record<string, string> = { ready: '就绪', uploading: '上传中', failed: '失败' }
  return map[status] || status
}

async function fetchData() {
  if (!modelId.value) return
  loading.value = true
  try {
    const [model, vers] = await Promise.all([
      getModel(modelId.value),
      getModelVersions(modelId.value),
    ])
    modelData.value = model
    versions.value = vers
    // 默认选中默认版本或第一个
    const defaultVer = vers.find((v: ModelVersion) => v.isDefault)
    if (defaultVer) {
      currentVersionId.value = defaultVer.id
    } else if (vers.length > 0) {
      currentVersionId.value = vers[0].id
    }
  } catch (e: any) {
    ElMessage.error(e.message || '获取模型详情失败')
  } finally {
    loading.value = false
  }
}

async function selectVersion(v: ModelVersion) {
  currentVersionId.value = v.id
  if (activeTab.value === 'files') {
    await fetchFiles()
  }
}

async function fetchFiles() {
  if (!currentVersionId.value) return
  try {
    files.value = await getModelFiles(currentVersionId.value)
  } catch (e: any) {
    ElMessage.error(e.message || '获取文件列表失败')
  }
}

watch(activeTab, (val) => {
  if (val === 'files') fetchFiles()
})

function goBack() {
  router.push('/model/my-library')
}

function openCreateVersion() {
  versionForm.value = { version: '', description: '', framework: '' }
  versionDialogVisible.value = true
}

async function handleCreateVersion() {
  if (!versionForm.value.version) {
    ElMessage.warning('请输入版本号')
    return
  }
  creatingVersion.value = true
  try {
    await createModelVersion(modelId.value, versionForm.value)
    ElMessage.success('创建版本成功')
    versionDialogVisible.value = false
    const vers = await getModelVersions(modelId.value)
    versions.value = vers
  } catch (e: any) {
    ElMessage.error(e.message || '创建版本失败')
  } finally {
    creatingVersion.value = false
  }
}

async function setDefault(verId: string) {
  try {
    await setDefaultVersion(modelId.value, verId)
    ElMessage.success('设置成功')
    const vers = await getModelVersions(modelId.value)
    versions.value = vers
  } catch (e: any) {
    ElMessage.error(e.message || '设置失败')
  }
}

async function deleteVersion(verId: string) {
  try {
    await ElMessageBox.confirm('确定删除该版本？版本下的文件将一并删除。', '删除确认', { type: 'warning' })
    await deleteModelVersion(verId)
    ElMessage.success('删除成功')
    if (currentVersionId.value === verId) {
      currentVersionId.value = ''
    }
    const vers = await getModelVersions(modelId.value)
    versions.value = vers
    if (!currentVersionId.value && vers.length > 0) {
      currentVersionId.value = vers[0].id
    }
  } catch {
    // 用户取消
  }
}

function openAddFile() {
  uploadFileList.value = []
  uploadProgress.value = 0
  fileDialogVisible.value = true
}

function handleUploadChange(file: UploadFile, list: UploadFile[]) {
  uploadFileList.value = list
}

function handleUploadRemove(file: UploadFile, list: UploadFile[]) {
  uploadFileList.value = list
}

async function handleAddFiles() {
  const raws = uploadFileList.value
    .map((f) => f.raw)
    .filter((raw): raw is NonNullable<UploadFile['raw']> => Boolean(raw))
  if (raws.length === 0) {
    ElMessage.warning('请先选择要上传的文件')
    return
  }
  addingFile.value = true
  uploadProgress.value = 0
  try {
    const formData = new FormData()
    for (const raw of raws) {
      formData.append('files', raw)
    }
    const result = await uploadModelFiles(currentVersionId.value, formData, (percent) => {
      uploadProgress.value = percent
    })
    const failed = result.files.filter((x) => x.status !== 'success')
    const succeeded = result.files.length - failed.length
    if (failed.length > 0) {
      const msgs = failed.map((x) => `${x.fileName}: ${x.errorMessage || '上传失败'}`).join('；')
      ElMessage.error(`有 ${failed.length} 个文件上传失败：${msgs}`)
    }
    if (succeeded > 0) {
      ElMessage.success(`成功上传 ${succeeded} 个文件`)
      fileDialogVisible.value = false
      await fetchFiles()
    }
  } catch (e: any) {
    ElMessage.error(e.message || '添加文件失败')
  } finally {
    addingFile.value = false
  }
}

async function handleDeleteFile(fileId: string) {
  try {
    await ElMessageBox.confirm('确定删除该文件？', '删除确认', { type: 'warning' })
    await deleteModelFile(fileId)
    ElMessage.success('删除成功')
    await fetchFiles()
  } catch {
    // 用户取消
  }
}

async function downloadFile(row: ModelFile) {
  try {
    await downloadModelFile(currentVersionId.value, row.id, row.fileName)
  } catch (e: any) {
    ElMessage.error(e.message || '下载失败')
  }
}

onMounted(fetchData)
</script>

<style lang="scss" scoped>
.model-detail {
  .detail-header {
    margin-bottom: 16px;
    .model-name {
      font-size: 16px;
      font-weight: 600;
    }
  }

  .detail-body {
    display: flex;
    gap: 20px;
    min-height: 500px;
  }

  .version-sidebar {
    width: 260px;
    flex-shrink: 0;
    background: $bg-color-white;
    border: 1px solid $border-color-light;
    border-radius: $border-radius-large;
    padding: 16px;

    .sidebar-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 12px;
      .sidebar-title {
        font-size: 15px;
        font-weight: 600;
      }
    }

    .version-list {
      .version-item {
        padding: 12px;
        border: 1px solid $border-color-lighter;
        border-radius: $border-radius-base;
        margin-bottom: 8px;
        cursor: pointer;
        transition: $transition-base;

        &:hover, &.active {
          border-color: $color-primary;
          background: rgba($color-primary, 0.04);
        }

        .version-name {
          display: flex;
          align-items: center;
          gap: 6px;
          font-weight: 600;
          font-size: 14px;
          margin-bottom: 6px;
        }

        .version-meta {
          display: flex;
          gap: 8px;
          font-size: 12px;
          color: $text-secondary;
          margin-bottom: 6px;
        }

        .version-status {
          margin-bottom: 4px;
        }

        .version-actions {
          display: flex;
          gap: 8px;
          margin-top: 4px;
        }
      }
    }
  }

  .detail-content {
    flex: 1;
    min-width: 0;
    background: $bg-color-white;
    border: 1px solid $border-color-light;
    border-radius: $border-radius-large;
    padding: 16px 20px;

    .intro-section {
      .intro-tags {
        margin-top: 16px;
        display: flex;
        align-items: center;
        .tag-label {
          font-size: 14px;
          color: $text-secondary;
          margin-right: 8px;
        }
      }
    }

    .files-section {
      .files-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 16px;
        font-weight: 600;
      }
    }
  }
}
</style>
