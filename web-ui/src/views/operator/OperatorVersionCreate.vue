<template>
  <div class="operator-version-create">
    <PageHeaderCard
      title="新增版本"
      desc="为已存在的算子创建新的版本，可调整镜像、启动参数等配置。"
    />

    <div class="form-card">
      <el-form
        ref="basicFormRef"
        :model="form"
        :rules="basicRules"
        label-position="top"
        class="version-form"
      >
        <!-- 基础信息 -->
        <div class="form-section">
          <div class="section-title">基础信息</div>
          <div class="section-body">
            <el-row :gutter="20">
              <el-col :span="12">
                <el-form-item label="版本名称" prop="name">
                  <el-input
                    v-model="form.name"
                    placeholder="请输入版本名称"
                    maxlength="50"
                    show-word-limit
                  />
                  <div class="field-tip">支持英文+50字符，数字、中横线、下划线及汉字等，不允许使用大写字母、点、竖线等特殊符号</div>
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="版本描述" prop="description">
                  <el-input
                    v-model="form.description"
                    placeholder="请输入版本描述"
                    maxlength="500"
                    show-word-limit
                  />
                  <div class="field-tip">模板的描述可重复编辑在 pipeline 编排界面</div>
                </el-form-item>
              </el-col>
            </el-row>
            <el-row :gutter="20">
              <el-col :span="12">
                <el-form-item label="资源类型" prop="resource_type">
                  <el-select v-model="form.resource_type" placeholder="请选择资源类型" style="width: 100%">
                    <el-option label="CPU" value="CPU" />
                    <el-option label="GPU" value="GPU" />
                  </el-select>
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="所属算子">
                  <el-input
                    :model-value="operatorName"
                    readonly
                    placeholder="从算子管理跳转后自动关联"
                    style="width: 100%"
                  />
                </el-form-item>
              </el-col>
            </el-row>
          </div>
        </div>

        <!-- 镜像配置 -->
        <div class="form-section">
          <div class="section-title">镜像配置</div>
          <div class="section-body">
            <el-row :gutter="20">
              <el-col :span="24">
                <el-form-item label="基础镜像" prop="base_image">
                  <div class="image-picker">
                    <el-input
                      v-model="form.base_image"
                      placeholder="请选择镜像地址"
                      readonly
                      class="image-input"
                    />
                    <el-button type="primary" @click="imageDialogVisible = true">选择镜像</el-button>
                  </div>
                  <div class="field-tip">该字段为声明/展示用：任务在宿主机直接执行（TRAIN_CONTAINER_RUNTIME=local），实际运行环境为宿主机镜像，如 ModelScope Notebook 的 ubuntu22.04-cuda12.8.1-py312-torch2.10.0-1.39.0</div>
                </el-form-item>
              </el-col>
            </el-row>
            <el-row :gutter="20">
              <el-col :span="12">
                <el-form-item label="工作目录">
                  <el-input v-model="form.work_dir" placeholder="请输入工作目录" />
                  <div class="field-tip">工作目录，不填可使用镜像默认的工作目录</div>
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="启动命令">
                  <el-input v-model="form.start_cmd" placeholder="请输入启动命令" />
                  <div class="field-tip">启动命令；训练任务中作为命令模板，支持占位符 {subcommand} {task_type} {sub_type} {model} {dataset} {output_dir}，留空则由平台按任务类型自动生成</div>
                </el-form-item>
              </el-col>
            </el-row>
            <el-row :gutter="20">
              <el-col :span="24">
                <el-form-item label="挂载目录">
                  <el-input
                    v-model="form.mount_dir"
                    type="textarea"
                    :rows="3"
                    placeholder="请输入挂载目录"
                  />
                  <div class="field-tip">
                    格式示例：pvc:/container_path1,pvc:/container_path2。注意 pvc 中的挂载路径必须为非空的 /.&lt;username&gt; 目录
                  </div>
                </el-form-item>
              </el-col>
            </el-row>
          </div>
        </div>

        <!-- 参数配置 -->
        <div class="form-section">
          <div class="section-title">参数配置</div>
          <div class="section-body">
            <el-form-item label="启动参数" :rules="[{ required: true, validator: validateStartParams, trigger: 'blur' }]">
              <el-input
                v-model="startParamsJson"
                type="textarea"
                :rows="12"
                placeholder='请输入 JSON 格式的参数契约（任务提交时回填默认值并校验），例如：&#10;{&#10;  "learning_rate": { "default": 0.0001, "required": true, "choices": [1e-5, 5e-05, 0.0001, 0.0005] },&#10;  "epochs": 3&#10;}'
              />
              <div class="field-tip">参数为 JSON 对象，键为分组名，值为参数数组</div>
            </el-form-item>

            <!-- 环境变量（可选） -->
            <el-form-item label="环境变量">
              <div class="env-vars-container">
                <div
                  v-for="(item, idx) in envVars"
                  :key="idx"
                  class="env-var-row"
                >
                  <el-input
                    v-model="item.key"
                    placeholder="变量名"
                    class="env-key"
                    maxlength="64"
                  />
                  <span class="env-eq">=</span>
                  <el-input
                    v-model="item.value"
                    placeholder="变量值"
                    class="env-value"
                    maxlength="256"
                  />
                  <el-button
                    type="danger"
                    link
                    :disabled="envVars.length <= 1"
                    @click="removeEnvVar(idx)"
                  >
                    <el-icon><Delete /></el-icon>
                  </el-button>
                </div>
                <el-button link type="primary" @click="addEnvVar">
                  + 添加环境变量
                </el-button>
                <div class="field-tip">支持 key=value 格式的环境变量，运行时会注入到容器中</div>
              </div>
            </el-form-item>
          </div>
        </div>
      </el-form>
    </div>

    <!-- 底部按钮 -->
    <div class="footer-bar">
      <el-button @click="goBack">返回</el-button>
      <el-button type="primary" :loading="submitting" @click="handleSubmit">保存</el-button>
    </div>

    <!-- 镜像选择弹框 -->
    <el-dialog
      v-model="imageDialogVisible"
      title="镜像选择"
      width="780px"
      :close-on-click-modal="false"
      class="image-dialog"
    >
      <div class="image-search">
        <el-input
          v-model="imageKeyword"
          placeholder="请输入镜像名称"
          clearable
          style="width: 240px"
          @keyup.enter="onImageSearch"
          @clear="fetchImages"
        >
          <template #suffix>
            <el-icon><Search /></el-icon>
          </template>
        </el-input>
        <el-button type="primary" :icon="Search" @click="onImageSearch" />
      </div>

      <el-table
        :data="imageList"
        v-loading="imageLoading"
        height="380"
        class="image-table"
      >
        <el-table-column prop="name" label="名称" min-width="200" align="left" />
        <el-table-column prop="resource_type" label="类型" width="80" align="left">
          <template #default="{ row }">
            <el-tag :type="row.resource_type === 'GPU' ? 'danger' : 'info'" size="small">
              {{ row.resource_type || 'CPU' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="address" label="镜像地址" min-width="380" align="left" show-overflow-tooltip>
          <template #default="{ row }">
            <el-tooltip :content="row.address" placement="top" :show-after="300">
              <span>{{ row.address }}</span>
            </el-tooltip>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="80" align="left" class-name="action-column">
          <template #default="{ row }">
            <el-button type="primary" link size="small" @click="handlePickImage(row as DockerImage)">选择</el-button>
          </template>
        </el-table-column>
        <template #empty>
          <el-empty description="暂无镜像数据" :image-size="80" />
        </template>
      </el-table>

      <div class="image-pagination">
        <el-pagination
          v-model:current-page="imagePageIndex"
          v-model:page-size="imagePageSize"
          :page-sizes="[10, 20, 50, 100]"
          :total="imageTotal"
          layout="total, sizes, prev, pager, next, jumper"
          background
          @size-change="fetchImages"
          @current-change="fetchImages"
        />
      </div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import { Search, Delete } from '@element-plus/icons-vue'
import PageHeaderCard from '@/components/common/PageHeaderCard.vue'
import { createOperatorVersion, fetchOperatorDetail } from '@/api/operator'
import { fetchImageList } from '@/api/ops'
import type { DockerImage } from '@/types'

const route = useRoute()
const router = useRouter()

// 表单数据
const form = reactive({
  name: '',
  description: '',
  resource_type: 'CPU' as 'CPU' | 'GPU',
  base_image: '',
  work_dir: '',
  start_cmd: '',
  mount_dir: '',
  is_public: false,
  operator_id: '',
})

// 启动参数用 JSON 文本编辑（参数契约：任务提交时回填默认值并校验）
const startParamsJson = ref(JSON.stringify(
  {
    learning_rate: { default: 0.0001, required: true, choices: [1e-5, 5e-05, 0.0001, 0.0005] },
    epochs: 3,
  },
  null,
  2,
))

const basicFormRef = ref<FormInstance>()
const submitting = ref(false)

const basicRules: FormRules = {
  name: [
    { required: true, message: '请输入版本名称', trigger: 'blur' },
    { max: 50, message: '最多 50 个字符', trigger: 'blur' },
  ],
  description: [{ max: 500, message: '最多 500 个字符', trigger: 'blur' }],
  resource_type: [{ required: true, message: '请选择资源类型', trigger: 'change' }],
  base_image: [{ required: true, message: '请选择基础镜像', trigger: 'change' }],
}

// 所属算子名称（只读，从路由 query 自动带入）
const operatorName = ref('')
async function loadOperatorName() {
  const opId = route.query.operatorId as string | undefined
  if (!opId) return
  form.operator_id = opId
  try {
    const detail = await fetchOperatorDetail(opId)
    operatorName.value = detail.name || ''
  } catch {
    operatorName.value = ''
  }
}

// 启动参数自定义校验
function validateStartParams(_rule: any, _value: any, callback: any) {
  const raw = (startParamsJson.value || '').trim()
  if (!raw) {
    callback(new Error('请输入启动参数'))
    return
  }
  try {
    const parsed = JSON.parse(raw)
    if (typeof parsed !== 'object' || parsed === null || Array.isArray(parsed)) {
      callback(new Error('启动参数必须为有效的 JSON 对象'))
      return
    }
    callback()
  } catch {
    callback(new Error('启动参数 JSON 格式不合法'))
  }
}

// 环境变量动态 KV
interface EnvVarItem {
  key: string
  value: string
}
const envVars = ref<EnvVarItem[]>([{ key: '', value: '' }])
function addEnvVar() {
  envVars.value.push({ key: '', value: '' })
}
function removeEnvVar(idx: number) {
  if (envVars.value.length <= 1) return
  envVars.value.splice(idx, 1)
}

// 镜像选择
const imageDialogVisible = ref(false)
const imageKeyword = ref('')
const imageLoading = ref(false)
const imageList = ref<DockerImage[]>([])
const imageTotal = ref(0)
const imagePageIndex = ref(1)
const imagePageSize = ref(10)

async function fetchImages() {
  imageLoading.value = true
  try {
    const res = await fetchImageList({
      pageIndex: imagePageIndex.value,
      pageSize: imagePageSize.value,
      keyword: imageKeyword.value || undefined,
      resource_type: form.resource_type || undefined,
    })
    imageList.value = res.list
    imageTotal.value = res.total
  } catch {
    imageList.value = []
    imageTotal.value = 0
  } finally {
    imageLoading.value = false
  }
}

function onImageSearch() {
  imagePageIndex.value = 1
  fetchImages()
}

function handlePickImage(img: DockerImage) {
  form.base_image = img.address
  imageDialogVisible.value = false
}

watch(imageDialogVisible, (val) => {
  if (val) {
    imageKeyword.value = ''
    imagePageIndex.value = 1
    fetchImages()
  }
})

async function handleSubmit() {
  if (!basicFormRef.value) return
  try {
    await basicFormRef.value.validate()
  } catch {
    return
  }
  // 校验启动参数
  let startParams: Record<string, unknown> = {}
  const raw = startParamsJson.value.trim()
  if (!raw) {
    ElMessage.error('请输入启动参数')
    return
  }
  try {
    startParams = JSON.parse(raw)
    if (typeof startParams !== 'object' || startParams === null || Array.isArray(startParams)) {
      ElMessage.error('启动参数必须为有效的 JSON 对象')
      return
    }
  } catch {
    ElMessage.error('启动参数 JSON 格式不合法')
    return
  }
  submitting.value = true
  try {
    // 过滤空的环境变量
    const envVarsPayload = envVars.value
      .filter((e) => e.key.trim() !== '')
      .reduce(
        (acc, e) => {
          acc[e.key.trim()] = e.value
          return acc
        },
        {} as Record<string, string>,
      )

    await createOperatorVersion(form.operator_id, {
      name: form.name,
      description: form.description,
      resource_type: form.resource_type,
      base_image: form.base_image,
      work_dir: form.work_dir,
      start_cmd: form.start_cmd,
      mount_dir: form.mount_dir,
      start_params: startParams,
      env_vars: envVarsPayload,
      is_public: form.is_public,
    })
    ElMessage.success('保存成功')
    router.push({ name: 'OperatorManagement' })
  } catch (e: any) {
    ElMessage.error(e?.message || '保存失败')
  } finally {
    submitting.value = false
  }
}

function goBack() {
  router.push({ name: 'OperatorManagement' })
}

onMounted(() => {
  loadOperatorName()
})
</script>

<style lang="scss" scoped>
.operator-version-create {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding-bottom: 80px;
}

.form-card {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.form-section {
  margin-bottom: 4px;

  .section-title {
    font-size: 15px;
    font-weight: 600;
    color: $text-primary;
    margin-bottom: 18px;
    display: flex;
    align-items: center;

    &::before {
      content: '';
      display: inline-block;
      width: 3px;
      height: 16px;
      background: $color-primary;
      border-radius: 2px;
      margin-right: 8px;
    }
  }

  .section-body {
    padding-left: 11px;
  }
}

.version-form {
  .field-tip {
    margin-top: 4px;
    color: $text-secondary;
    font-size: 12px;
    line-height: 1.5;
  }
}

.env-vars-container {
  .env-var-row {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 10px;

    .env-key {
      width: 200px;
      flex-shrink: 0;
    }

    .env-eq {
      color: $text-secondary;
      font-size: 14px;
      flex-shrink: 0;
    }

    .env-value {
      flex: 1;
    }
  }
}

.image-picker {
  display: flex;
  align-items: center;
  gap: 12px;
  width: 100%;

  .image-input {
    flex: 1;
  }
}

.footer-bar {
  position: fixed;
  right: 24px;
  bottom: 24px;
  display: flex;
  gap: 12px;
  padding: 12px 20px;
  background: $bg-color-white;
  border: 1px solid $border-color-light;
  border-radius: $border-radius-large;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.08);
  z-index: 50;
}

.image-search {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
}

.image-pagination {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}
</style>
