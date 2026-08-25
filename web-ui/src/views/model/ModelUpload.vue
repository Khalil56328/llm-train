<template>
  <div class="model-upload">
    <div class="upload-header">
      <el-page-header @back="goBack">
        <template #content>
          <span class="upload-title">上传模型 - {{ modelName }}</span>
        </template>
      </el-page-header>
    </div>

    <div class="upload-body">
      <div class="upload-section">
        <el-alert type="info" :closable="false" show-icon style="margin-bottom: 20px">
          <template #title>上传说明</template>
          <p>支持上传 .safetensors, .bin, .json, .txt 等格式的模型文件。单文件大小不超过 10GB。</p>
        </el-alert>

        <el-form :model="localForm" label-width="100px">
          <el-form-item label="目标版本">
            <el-select v-model="localForm.versionId" style="width: 100%" placeholder="请选择要上传到的版本">
              <el-option v-for="v in versions" :key="v.id" :label="v.version" :value="v.id" />
            </el-select>
          </el-form-item>
          <el-form-item label="文件">
            <el-upload
              ref="uploadRef"
              :auto-upload="false"
              :file-list="fileList"
              :on-change="handleFileChange"
              :on-remove="handleFileRemove"
              multiple
              drag
            >
              <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
              <div class="el-upload__text">拖拽文件到此处，或<em>点击上传</em></div>
              <template #tip>
                <div class="el-upload__tip">支持 .safetensors / .bin / .json / .txt 格式</div>
              </template>
            </el-upload>
          </el-form-item>
        </el-form>

        <el-progress
          v-if="uploading"
          :percentage="uploadProgress"
          :stroke-width="6"
          style="margin: 16px 0 8px"
        />

        <div class="upload-actions">
          <el-button @click="goBack">取消</el-button>
          <el-button type="primary" @click="handleLocalUpload" :loading="uploading" :disabled="fileList.length === 0">
            开始上传
          </el-button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { UploadFilled } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import type { UploadFile, UploadInstance } from 'element-plus'
import { getModel, getModelVersions, uploadModelFiles } from '@/api/model'
import type { ModelVersion } from '@/types'

const route = useRoute()
const router = useRouter()
const modelId = computed(() => route.params.id as string)

const modelName = ref('')
const versions = ref<ModelVersion[]>([])
const uploading = ref(false)
const uploadProgress = ref(0)
const uploadRef = ref<UploadInstance>()
const fileList = ref<UploadFile[]>([])

const localForm = ref({ versionId: '' })

async function fetchData() {
  if (!modelId.value) return
  try {
    const [model, vers] = await Promise.all([
      getModel(modelId.value),
      getModelVersions(modelId.value),
    ])
    modelName.value = model.name
    versions.value = vers
    if (vers.length > 0) {
      const defaultVer = vers.find((v: ModelVersion) => v.isDefault) || vers[0]
      localForm.value.versionId = defaultVer.id
    }
  } catch (e: any) {
    ElMessage.error(e.message || '获取模型信息失败')
  }
}

function goBack() {
  router.push(`/model/detail/${modelId.value}`)
}

function handleFileChange(file: UploadFile, list: UploadFile[]) {
  fileList.value = list
}

function handleFileRemove(file: UploadFile, list: UploadFile[]) {
  fileList.value = list
}

async function handleLocalUpload() {
  if (!localForm.value.versionId) {
    ElMessage.warning('请选择目标版本')
    return
  }
  const raws = fileList.value
    .map((f) => f.raw)
    .filter((raw): raw is NonNullable<UploadFile['raw']> => Boolean(raw))
  if (raws.length === 0) {
    ElMessage.warning('请选择要上传的文件')
    return
  }

  uploading.value = true
  uploadProgress.value = 0
  try {
    const formData = new FormData()
    for (const raw of raws) {
      formData.append('files', raw)
    }
    const result = await uploadModelFiles(localForm.value.versionId, formData, (percent) => {
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
      router.push(`/model/detail/${modelId.value}`)
    }
  } catch (e: any) {
    ElMessage.error(e.message || '上传失败')
  } finally {
    uploading.value = false
  }
}

onMounted(fetchData)
</script>

<style lang="scss" scoped>
.model-upload {
  .upload-header {
    margin-bottom: 16px;
    .upload-title {
      font-size: 16px;
      font-weight: 600;
    }
  }

  .upload-body {
    background: $bg-color-white;
    border: 1px solid $border-color-light;
    border-radius: $border-radius-large;
    padding: 24px 32px;
  }

  .upload-section {
    padding: 16px 0;
  }

  .upload-actions {
    display: flex;
    justify-content: flex-end;
    gap: 12px;
    margin-top: 24px;
    padding-top: 16px;
    border-top: 1px solid $border-color-lighter;
  }
}
</style>
