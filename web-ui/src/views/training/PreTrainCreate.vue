<template>
  <div class="pretrain-create">
    <div class="back-row">
      <el-button text @click="goBack">
        <el-icon><ArrowLeft /></el-icon> 返回
      </el-button>
    </div>
    <PageHeaderCard :title="isEdit ? '编辑预训练任务' : '创建预训练任务'" desc="对大模型进行持续预训练（Continual Pre-training），提升模型在特定领域的知识储备。" />

    <StepCards :steps="steps" :current="currentStep" />

    <div class="content-card">
      <!-- Step 1: 基本信息 -->
      <div v-if="currentStep === 1">
        <div class="form-section">
          <div class="section-title">基本信息</div>
          <div class="section-body">
            <el-row :gutter="20">
              <el-col :span="12">
                <el-form-item label="任务名称" required>
                  <el-input v-model="form.name" placeholder="请输入任务名称" />
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="任务类型" required>
                  <el-select v-model="form.taskType" style="width: 100%">
                    <el-option label="文本生成" value="text-generation" />
                    <el-option label="图像生成" value="image-generation" />
                    <el-option label="图像理解" value="image-understanding" />
                  </el-select>
                </el-form-item>
              </el-col>
            </el-row>
            <el-form-item label="任务描述">
              <el-input v-model="form.description" type="textarea" :rows="3" placeholder="请输入任务描述" />
            </el-form-item>
          </div>
        </div>
      </div>

      <!-- Step 2: 数据配置 -->
      <div v-if="currentStep === 2">
        <div class="form-section">
          <div class="section-title">数据配置</div>
          <div class="section-body">
            <el-form-item label="训练数据集" required>
              <HierarchicalSelect v-model="form.datasetId" :data="datasetTree" placeholder="请选择数据集" />
            </el-form-item>
            <div class="form-tip">预训练数据集需为纯文本格式（JSONL 每行 {"text": "..."}，可用演示数据集 pretrain_demo）；对话格式数据会解析失败。</div>
          </div>
        </div>
      </div>

      <!-- Step 3: 训练参数 -->
      <div v-if="currentStep === 3">
        <div class="form-section">
          <div class="section-title">训练参数</div>
          <div class="section-body">
            <el-row :gutter="20">
              <el-col :span="12">
                <el-form-item label="训练框架" required>
                  <el-select v-model="form.framework" style="width: 100%">
                    <el-option label="ms-swift" value="ms-swift" />
                    <el-option label="LlamaFactory" value="llamafactory" />
                  </el-select>
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="训练方法" required>
                  <el-radio-group v-model="form.method">
                    <el-radio value="lora">LoRA微调</el-radio>
                    <el-radio value="full">全量更新</el-radio>
                  </el-radio-group>
                </el-form-item>
              </el-col>
            </el-row>
            <el-row :gutter="20">
              <el-col :span="12">
                <el-form-item label="基础模型" required>
                  <HierarchicalSelect v-model="form.baseModel" :data="modelTree" placeholder="请选择基础模型" />
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="算子" required>
                  <HierarchicalSelect v-model="form.operator" :data="operatorTree" placeholder="请选择算子" />
                </el-form-item>
              </el-col>
            </el-row>
          </div>
        </div>

        <div class="form-section">
          <div class="section-title">参数配置</div>
          <div class="section-body">
            <el-row :gutter="20">
              <el-col :span="8">
                <el-form-item label="学习率">
                  <el-input v-model="form.learningRate" />
                </el-form-item>
              </el-col>
              <el-col :span="8">
                <el-form-item label="训练轮数">
                  <el-input :model-value="String(form.epochs)" />
                </el-form-item>
              </el-col>
              <el-col :span="8">
                <el-form-item label="批次大小">
                  <el-input :model-value="String(form.batchSize)" />
                </el-form-item>
              </el-col>
            </el-row>
            <el-row :gutter="20">
              <el-col :span="8">
                <el-form-item label="最大序列长度">
                  <el-input :model-value="String(form.maxLength)" />
                </el-form-item>
              </el-col>
              <el-col :span="8">
                <el-form-item label="梯度累积步数">
                  <el-input :model-value="String(form.gradAccumSteps)" />
                </el-form-item>
              </el-col>
              <el-col :span="8">
                <el-form-item label="预热步数">
                  <el-input :model-value="String(form.warmupSteps)" />
                </el-form-item>
              </el-col>
            </el-row>
            <KvEditor v-model="form.kvParams" add-label="自定义参数" />
          </div>
        </div>
      </div>

      <!-- Step 4: 资源配置 -->
      <div v-if="currentStep === 4">
        <div class="form-section">
          <div class="section-title">资源配置</div>
          <div class="section-body">
            <el-row :gutter="20">
              <el-col :span="12">
                <el-form-item label="资源池" required>
                  <el-select v-model="form.poolId" style="width: 100%" placeholder="请选择资源池">
                    <el-option v-for="p in poolOptions" :key="p.id" :label="poolLabel(p)" :value="p.id" />
                  </el-select>
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="GPU数量" required>
                  <el-input :model-value="String(form.gpuCount)" />
                </el-form-item>
              </el-col>
            </el-row>
            <el-row :gutter="20">
              <el-col :span="12">
                <el-form-item label="CPU(核)">
                  <el-input :model-value="String(form.cpu)" />
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="内存(GB)">
                  <el-input :model-value="String(form.memory)" />
                </el-form-item>
              </el-col>
            </el-row>
          </div>
        </div>
      </div>

      <!-- 底部按钮 -->
      <div class="step-actions">
        <el-button v-if="currentStep > 1" @click="currentStep--">上一步</el-button>
        <el-button v-if="currentStep < 4" type="primary" @click="currentStep++">下一步</el-button>
        <el-button v-if="currentStep === 4" type="primary" @click="handleSave">{{ isEdit ? '保存修改' : '保存' }}</el-button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { ArrowLeft } from '@element-plus/icons-vue'
import PageHeaderCard from '@/components/common/PageHeaderCard.vue'
import StepCards from '@/components/common/StepCards.vue'
import KvEditor from '@/components/common/KvEditor.vue'
import HierarchicalSelect from '@/components/common/HierarchicalSelect.vue'
import { createTrainTask, updateTrainTask, getTrainTaskDetail } from '@/api/training'
import { fetchResourcePoolList } from '@/api/ops'
import { useTrainOptions } from '@/composables/useTrainOptions'
import type { ResourcePool } from '@/types'

const router = useRouter()
const route = useRoute()
const currentStep = ref(1)
const taskId = (route.query.id as string) || ''
const isEdit = computed(() => !!taskId)

const poolOptions = ref<ResourcePool[]>([])
function poolLabel(p: ResourcePool) {
  return p.name + (p.gpu_type ? `（${p.gpu_type}）` : '')
}
async function loadResourcePools() {
  try {
    const res = await fetchResourcePoolList({ pageIndex: 1, pageSize: 100 })
    poolOptions.value = res.list || []
  } catch { /* 资源池加载失败不阻塞 */ }
}

const steps = [
  { step: 1, title: '基本信息', desc: '配置任务名称、任务类型、描述' },
  { step: 2, title: '数据配置', desc: '选择训练数据集' },
  { step: 3, title: '训练参数', desc: '配置训练框架、方法、模型、算子、参数' },
  { step: 4, title: '资源配置', desc: '选择资源池（单卡最低标准已锁定）' },
]

const { datasetTree, modelTree, operatorTree, loadDatasetOptions, ensureDatasetById, loadModelOptions, loadOperatorOptions, findDatasetName, findModelName, buildCascaderValue } = useTrainOptions()

const form = reactive({
  name: '',
  taskType: 'text-generation',
  description: '',
  datasetId: '',
  framework: 'ms-swift',
  method: 'lora',
  baseModel: '',
  operator: '',
  learningRate: '1e-5',
  epochs: 1,
  batchSize: 1,
  maxLength: 1024,
  gradAccumSteps: 1,
  warmupSteps: 0,
  kvParams: [] as { key: string; value: string }[],
  poolId: '',
  gpuCount: 1,
  cpu: 4,
  memory: 32,
})

function goBack() {
  router.push('/train/pretrain')
}

function buildPayload() {
  return {
    name: form.name,
    taskType: 'pretrain',
    taskSubType: form.taskType,
    subType: form.method === 'full' ? '全量更新' : 'LoRA微调',
    description: form.description,
    baseModelId: form.baseModel.split('/')[1] || form.baseModel,
    baseModelVersion: form.baseModel.split('/')[2] || '',
    baseModelName: findModelName(form.baseModel.split('/')[1] || form.baseModel),
    operatorId: form.operator.split('/')[1] || form.operator,
    operatorVersion: form.operator.split('/')[2] || '',
    datasetId: form.datasetId.split('/')[1] || form.datasetId,
    datasetName: findDatasetName(form.datasetId.split('/')[1] || form.datasetId),
    datasetVersion: form.datasetId.split('/')[2] || '',
    framework: form.framework,
    hyperParams: {
      training_method: form.method,
      learning_rate: form.learningRate,
      epochs: form.epochs,
      batch_size: form.batchSize,
      max_length: form.maxLength,
      gradient_accumulation_steps: form.gradAccumSteps,
      warmup_steps: form.warmupSteps,
      ...Object.fromEntries(form.kvParams.map(p => [p.key, p.value])),
    },
    resourceConfig: {
      poolId: form.poolId,
      gpuCount: form.gpuCount,
      cpu: form.cpu,
      memory: form.memory,
    },
  }
}

async function handleSave() {
  if (!form.name) { ElMessage.warning('请输入任务名称'); return }
  if (!form.datasetId) { ElMessage.warning('请选择训练数据集'); return }
  if (!form.baseModel) { ElMessage.warning('请选择基础模型'); return }
  if (!form.operator) { ElMessage.warning('请选择算子'); return }
  try {
    if (isEdit.value) {
      await updateTrainTask(taskId, buildPayload())
      ElMessage.success('预训练任务修改已保存')
    } else {
      await createTrainTask(buildPayload())
      ElMessage.success('预训练任务保存成功')
    }
  } catch (e: any) {
    ElMessage.error(e?.message || '保存失败，请稍后重试')
    return
  }
  router.push('/train/pretrain')
}

async function loadTaskDetail() {
  if (!taskId) return
  try {
    const task = await getTrainTaskDetail(taskId)
    form.name = task.name || ''
    form.description = task.description || ''
    form.taskType = (task.taskSubType as string) || form.taskType
    form.datasetId = task.datasetId ? buildCascaderValue(task.datasetId, 'dataset', task.datasetVersion) : ''
    form.baseModel = task.baseModelId ? buildCascaderValue(task.baseModelId, 'model', task.baseModelVersion) : ''
    form.operator = task.operatorId ? buildCascaderValue(task.operatorId, 'operator', task.operatorVersion) : ''
    form.framework = String(task.framework ?? '') || 'ms-swift'
    form.method = task.subType === '全量更新' ? 'full' : 'lora'
    const hp = task.hyperParams || {}
    form.learningRate = String(hp.learning_rate ?? form.learningRate)
    form.epochs = Number(hp.epochs ?? form.epochs)
    form.batchSize = Number(hp.batch_size ?? form.batchSize)
    form.maxLength = Number(hp.max_length ?? form.maxLength)
    form.gradAccumSteps = Number(hp.gradient_accumulation_steps ?? form.gradAccumSteps)
    form.warmupSteps = Number(hp.warmup_steps ?? form.warmupSteps)
    const stdKeys = ['training_method', 'learning_rate', 'epochs', 'batch_size', 'max_length', 'gradient_accumulation_steps', 'warmup_steps']
    form.kvParams = Object.entries(hp)
      .filter(([k]) => !stdKeys.includes(k))
      .map(([key, value]) => ({ key, value: String(value) }))
    const rc = (task.resourceConfig || {}) as unknown as Record<string, unknown>
    form.poolId = String(rc.poolId ?? form.poolId)
    form.gpuCount = Number(rc.gpuCount ?? rc.gpu ?? form.gpuCount)
    form.cpu = Number(rc.cpu ?? form.cpu)
    form.memory = Number(rc.memory ?? form.memory)
  } catch { /* ignore */ }
}

onMounted(async () => {
  await Promise.all([loadDatasetOptions('CPT'), loadModelOptions(), loadOperatorOptions(), loadResourcePools()])
  await loadTaskDetail()
  await ensureDatasetById(form.datasetId.split('/')[1] || form.datasetId)
})
</script>

<style lang="scss" scoped>
.back-row {
  margin-bottom: 16px;
}
.step-actions {
  display: flex;
  justify-content: center;
  gap: 12px;
  margin-top: 32px;
  padding-top: 20px;
  border-top: 1px solid $border-color-lighter;
}
.form-tip {
  font-size: 12px;
  color: $text-secondary;
}
</style>
