<template>
  <div class="fine-tune-create">
    <div class="back-row">
      <el-button text @click="goBack">
        <el-icon><ArrowLeft /></el-icon> 返回
      </el-button>
    </div>
    <PageHeaderCard :title="isEdit ? '编辑微调任务' : '创建微调任务'" desc="配置模型微调训练任务，通过步骤引导完成参数配置。" />

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
                    <el-radio value="freeze">冻结微调</el-radio>
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
                  <HierarchicalSelect v-model="form.operator" :data="operatorTree" placeholder="请选择" />
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
                  <el-input v-model="form.learningRate" placeholder="1e-5" />
                </el-form-item>
              </el-col>
              <el-col :span="8">
                <el-form-item label="训练轮数">
                  <el-input-number v-model="form.epochs" :min="1" :max="100" style="width: 100%" />
                </el-form-item>
              </el-col>
              <el-col :span="8">
                <el-form-item label="批次大小">
                  <el-input-number v-model="form.batchSize" :min="1" :max="256" style="width: 100%" />
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
                  <el-input-number v-model="form.gpuCount" :min="1" :max="16" style="width: 100%" />
                </el-form-item>
              </el-col>
            </el-row>
            <el-row :gutter="20">
              <el-col :span="12">
                <el-form-item label="CPU(核)">
                  <el-input-number v-model="form.cpu" :min="1" :max="128" style="width: 100%" />
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="内存(GB)">
                  <el-input-number v-model="form.memory" :min="4" :max="1024" :step="8" style="width: 100%" />
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
  { step: 2, title: '数据配置', desc: '选择训练数据集及版本' },
  { step: 3, title: '训练参数', desc: '配置训练框架、方法、模型、算子、参数' },
  { step: 4, title: '资源配置', desc: '选择资源池，配置 GPU/CPU/内存' },
]

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
  kvParams: [{ key: 'max_length', value: '1024' }],
  poolId: '',
  gpuCount: 1,
  cpu: 4,
  memory: 32,
})

const { datasetTree, modelTree, operatorTree, loadDatasetOptions, ensureDatasetById, loadModelOptions, loadOperatorOptions, findModelName, findDatasetName, buildCascaderValue } = useTrainOptions()

function goBack() {
  router.push('/train/fine-tune')
}

async function buildPayload(): Promise<Record<string, unknown>> {
  return {
    name: form.name,
    taskType: 'fine-tune',
    taskSubType: form.taskType,
    subType: form.method === 'lora' ? 'LoRA微调' : form.method === 'freeze' ? '冻结微调' : '全量更新',
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
      num_train_epochs: form.epochs,
      per_device_train_batch_size: form.batchSize,
      ...Object.fromEntries(
        form.kvParams.filter((k) => k.key).map((k) => [k.key, k.value]),
      ),
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
  const payload = await buildPayload()
  try {
    if (isEdit.value) {
      await updateTrainTask(taskId, payload)
      ElMessage.success('微调任务修改已保存')
    } else {
      await createTrainTask(payload)
      ElMessage.success('微调任务保存成功')
    }
  } catch {
    // 接口失败不阻断 UI
  }
  router.push('/train/fine-tune')
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
    form.method = task.subType === '全量更新' ? 'full' : task.subType === '冻结微调' ? 'freeze' : 'lora'
    const hp = task.hyperParams || {}
    form.learningRate = String(hp.learning_rate ?? form.learningRate)
    form.epochs = Number(hp.num_train_epochs ?? form.epochs)
    form.batchSize = Number(hp.per_device_train_batch_size ?? form.batchSize)
    const stdKeys = ['training_method', 'learning_rate', 'num_train_epochs', 'per_device_train_batch_size']
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
  await Promise.all([loadDatasetOptions('SFT'), loadModelOptions(), loadOperatorOptions(), loadResourcePools()])
  await loadTaskDetail()
  // 编辑回显：已选数据集不在 SFT 列表时，补齐全量以保留原选择
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
</style>
