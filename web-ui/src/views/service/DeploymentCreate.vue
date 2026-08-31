<template>
  <div class="deployment-create">
    <PageHeaderCard :title="isEdit ? '编辑部署' : '新增部署'" desc="配置模型推理服务的部署参数" />

    <div class="content-card">
      <el-form ref="formRef" :model="form" :rules="rules" label-position="top" class="deployment-form">
        <!-- 基础信息 -->
        <div class="form-section">
          <div class="section-title">基础信息</div>
          <div class="section-body">
            <el-form-item label="服务名称" prop="name">
              <el-input v-model="form.name" placeholder="请输入服务名称" maxlength="200" />
            </el-form-item>
            <el-form-item label="服务描述" prop="description">
              <el-input v-model="form.description" type="textarea" :rows="4" placeholder="请输入服务描述" maxlength="500" />
            </el-form-item>
          </div>
        </div>

        <!-- 服务配置 -->
        <div class="form-section">
          <div class="section-title">服务配置</div>
          <div class="section-body">
            <el-form-item label="推理框架" prop="inferenceFramework" label-position="left" label-width="80px">
              <el-radio-group v-model="form.inferenceFramework">
                <el-radio value="vLLM">vLLM</el-radio>
                <el-radio value="MindIE">MindIE</el-radio>
                <el-radio value="custom">业务镜像</el-radio>
              </el-radio-group>
            </el-form-item>
            <el-form-item label="基础模型" prop="modelId">
              <el-select v-model="form.modelId" placeholder="请选择基础模型" filterable style="width: 100%"
                @change="onModelChange">
                <el-option v-for="m in modelList" :key="m.id" :label="m.name" :value="m.id" />
              </el-select>
            </el-form-item>
            <el-form-item label="算子选择" prop="operatorId">
              <el-select v-model="form.operatorId" placeholder="请选择算子(可选)" clearable filterable style="width: 100%">
                <el-option v-for="op in operatorList" :key="op.id" :label="op.name" :value="op.id" />
              </el-select>
            </el-form-item>
            <el-form-item label="参数配置">
              <KvEditor v-model="form.params" />
              <div class="field-tip">模型启动参数，如 max_model_len、tensor-parallel-size 等</div>
            </el-form-item>
            <el-form-item label="环境变量">
              <KvEditor v-model="form.envVars" />
              <div class="field-tip">容器运行环境变量，格式为 key=value</div>
            </el-form-item>
          </div>
        </div>

        <!-- 资源配置 -->
        <div class="form-section">
          <div class="section-title">资源配置</div>
          <div class="section-body">
            <el-form-item label="CPU(核)" prop="cpu">
              <el-input-number v-model="form.cpu" :min="1" :max="256" />
            </el-form-item>
            <el-form-item label="内存(GB)" prop="memory">
              <el-input-number v-model="form.memory" :min="1" :max="1024" />
            </el-form-item>
            <el-form-item label="存储(GB)" prop="storage">
              <el-input-number v-model="form.storage" :min="10" :max="10240" />
            </el-form-item>
            <el-form-item label="GPU" prop="gpu">
              <el-input-number v-model="form.gpu" :min="0" :max="16" />
            </el-form-item>
            <el-form-item label="实例数" prop="instances">
              <el-input-number v-model="form.instances" :min="1" :max="10" />
            </el-form-item>
            <el-form-item label="容器端口" prop="containerPort">
              <el-input-number v-model="form.containerPort" :min="1" :max="65535" />
            </el-form-item>
            <el-form-item label="访问端口">
              <el-input-number v-model="form.accessPort" :min="1" :max="65535" />
            </el-form-item>
          </div>
        </div>
      </el-form>

      <!-- 底部按钮：与表单同一卡片内自然衔接 -->
      <div class="form-footer">
        <el-button @click="router.back()">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleSubmit">保存</el-button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import PageHeaderCard from '@/components/common/PageHeaderCard.vue'
import KvEditor from '@/components/common/KvEditor.vue'
import { createDeployment, updateDeployment, getDeploymentDetail } from '@/api/service'
import { getModelList } from '@/api/model'
import { fetchOperatorList } from '@/api/operator'
import type { KvItem } from '@/components/common/types'

const router = useRouter()
const route = useRoute()
const isEdit = computed(() => !!route.query.id)
const submitting = ref(false)

function recordToKvItems(obj: Record<string, any>): KvItem[] {
  return Object.entries(obj || {}).map(([key, value]) => ({ key, value: String(value) }))
}

function kvItemsToRecord(items: KvItem[]): Record<string, string> {
  const result: Record<string, string> = {}
  for (const item of items) {
    if (item.key) result[item.key] = item.value
  }
  return result
}

const form = ref({
  name: '',
  description: '',
  inferenceFramework: 'vLLM',
  modelId: '',
  modelName: '',
  modelVersion: '',
  operatorId: '',
  operatorVersion: '',
  params: [] as KvItem[],
  envVars: [] as KvItem[],
  cpu: 4,
  memory: 16,
  storage: 100,
  gpu: 1,
  instances: 1,
  containerPort: 8000,
  accessPort: undefined as number | undefined,
})

const modelList = ref<any[]>([])
const operatorList = ref<any[]>([])

const rules = {
  name: [{ required: true, message: '请输入服务名称', trigger: 'blur' }],
  inferenceFramework: [{ required: true, message: '请选择推理框架', trigger: 'change' }],
  modelId: [{ required: true, message: '请选择基础模型', trigger: 'change' }],
  operatorId: [{ required: true, message: '请选择算子', trigger: 'change' }],
  cpu: [{ required: true, message: '请输入CPU', trigger: 'blur' }],
  memory: [{ required: true, message: '请输入内存', trigger: 'blur' }],
}

const formRef = ref()

function onModelChange(val: string) {
  const m = modelList.value.find((m: any) => m.id === val)
  if (m) {
    form.value.modelName = m.name
    form.value.modelVersion = m.version || '1'
  }
}

async function handleSubmit() {
  if (formRef.value) {
    try { await formRef.value.validate() } catch { return }
  }
  submitting.value = true
  try {
    const data = {
      name: form.value.name,
      description: form.value.description,
      inferenceFramework: form.value.inferenceFramework,
      modelId: form.value.modelId,
      modelName: form.value.modelName,
      modelVersion: form.value.modelVersion,
      operatorId: form.value.operatorId,
      operatorVersion: form.value.operatorVersion,
      params: kvItemsToRecord(form.value.params),
      envVars: kvItemsToRecord(form.value.envVars),
      instances: form.value.instances,
      containerPort: form.value.containerPort,
      accessPort: form.value.accessPort,
      resourceConfig: {
        poolId: '',
        gpuCount: form.value.gpu,
        cpu: form.value.cpu,
        memory: form.value.memory,
        storage: form.value.storage,
        gpu: form.value.gpu,
      },
    }
    if (isEdit.value) {
      await updateDeployment(route.query.id as string, data)
      ElMessage.success('更新成功')
    } else {
      await createDeployment(data)
      ElMessage.success('创建成功')
    }
    router.push('/service/deployment')
  } catch (e: any) {
    ElMessage.error(e.message || '操作失败')
  } finally {
    submitting.value = false
  }
}

async function loadModels() {
  try {
    const res = await getModelList({ pageIndex: 1, pageSize: 200 })
    modelList.value = res.list || []
  } catch { modelList.value = [] }
}

async function loadOperators() {
  try {
    const res = await fetchOperatorList({ pageIndex: 1, pageSize: 200 })
    operatorList.value = res.list || []
  } catch { operatorList.value = [] }
}

async function loadDetail() {
  if (!isEdit.value) return
  try {
    const res = await getDeploymentDetail(route.query.id as string)
    Object.assign(form.value, {
      name: res.name,
      description: res.description || '',
      inferenceFramework: res.inferenceFramework,
      modelId: res.modelId,
      modelName: res.modelName || '',
      modelVersion: res.modelVersion || '',
      operatorId: res.operatorId || '',
      operatorVersion: res.operatorVersion || '',
      params: recordToKvItems(res.params || {}),
      envVars: recordToKvItems(res.envVars || {}),
      instances: res.instances || 1,
      containerPort: res.containerPort || 8000,
      accessPort: res.accessPort,
      cpu: (res.resourceConfig as any)?.cpu || 4,
      memory: (res.resourceConfig as any)?.memory || 16,
      storage: (res.resourceConfig as any)?.storage || 100,
      gpu: (res.resourceConfig as any)?.gpu || 1,
    })
  } catch { /* ignore */ }
}

onMounted(async () => {
  await loadModels()
  loadOperators()
  await loadDetail()
  // 从《我的模型库》跳转过来时预选模型
  const preset = route.query.modelId as string
  if (preset && !isEdit.value && modelList.value.some((m: any) => m.id === preset)) {
    form.value.modelId = preset
    onModelChange(preset)
  }
})
</script>

<style lang="scss" scoped>
.deployment-create {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.deployment-form {
  max-width: 900px;

  // 一列一行布局：数字输入框限制宽度，避免撑满整行
  .el-input-number {
    width: 320px;
  }

  .field-tip {
    margin-top: 4px;
    color: $text-secondary;
    font-size: 12px;
    line-height: 1.5;
  }
}

.form-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  margin-top: 8px;
  padding-top: 20px;
  border-top: 1px solid $border-color-lighter;
}
</style>
