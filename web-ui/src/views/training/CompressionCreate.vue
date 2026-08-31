<template>
  <div class="compression-create">
    <div class="back-row">
      <el-button text @click="goBack">
        <el-icon><ArrowLeft /></el-icon> 返回
      </el-button>
    </div>
    <PageHeaderCard title="创建压缩训练任务" desc="通过量化压缩模型体积、降低推理延迟，提升部署效率。" />

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
                <el-form-item label="压缩类型" required>
                  <el-select v-model="form.compressionType" style="width: 100%">
                    <el-option label="量化 (Quantization)" value="quantization" />
                    <el-option label="剪枝 (Pruning)" value="pruning" />
                    <el-option label="蒸馏 (Distillation)" value="distillation" />
                    <el-option label="量化+蒸馏" value="quant_distill" />
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

      <!-- Step 2: 模型与压缩配置 -->
      <div v-if="currentStep === 2">
        <div class="form-section">
          <div class="section-title">模型配置</div>
          <div class="section-body">
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

        <div v-if="isQuant" class="form-section">
          <div class="section-title">量化参数</div>
          <div class="section-body">
            <el-row :gutter="20">
              <el-col :span="8">
                <el-form-item label="量化位数" required>
                  <el-select v-model="form.quantBits" style="width: 100%">
                    <el-option label="4-bit (INT4)" value="4" />
                    <el-option label="8-bit (INT8)" value="8" />
                  </el-select>
                </el-form-item>
              </el-col>
              <el-col :span="8">
                <el-form-item label="量化方法" required>
                  <el-select v-model="form.quantMethod" style="width: 100%">
                    <el-option label="BitsAndBytes（无需校准数据）" value="bnb" />
                    <el-option label="GPTQ（需校准数据集）" value="gptq" />
                    <el-option label="AWQ（需校准数据集）" value="awq" />
                    <el-option label="GGUF" value="gguf" />
                  </el-select>
                </el-form-item>
              </el-col>
              <el-col :span="8">
                <el-form-item label="校准数据集" :required="needCalib">
                  <HierarchicalSelect v-model="form.calibDataset" :data="datasetTree" placeholder="请选择校准数据集" clearable />
                </el-form-item>
              </el-col>
            </el-row>
            <el-row :gutter="20">
              <el-col :span="8">
                <el-form-item label="校准样本数">
                  <el-input-number v-model="form.calibSamples" :min="32" :max="4096" :step="32" style="width: 100%" />
                </el-form-item>
              </el-col>
              <el-col :span="8">
                <el-form-item label="分组大小">
                  <el-input-number v-model="form.groupSize" :min="32" :max="512" :step="32" style="width: 100%" />
                </el-form-item>
              </el-col>
            </el-row>
            <div v-if="needCalib" class="form-tip">GPTQ / AWQ 量化需要校准数据集。</div>
            <KvEditor v-model="form.kvParams" add-label="自定义参数" />
          </div>
        </div>

        <div v-if="form.compressionType === 'pruning'" class="form-section">
          <div class="section-title">剪枝参数</div>
          <div class="section-body">
            <el-row :gutter="20">
              <el-col :span="12">
                <el-form-item label="剪枝方法" required>
                  <el-select v-model="form.pruningMethod" style="width: 100%">
                    <el-option label="幅度剪枝（Magnitude）" value="magnitude" />
                    <el-option label="结构化剪枝（Structured）" value="structured" />
                  </el-select>
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="剪枝率" required>
                  <el-input-number v-model="form.pruningRatio" :min="0.1" :max="0.9" :step="0.05" style="width: 100%" />
                </el-form-item>
              </el-col>
            </el-row>
          </div>
        </div>

        <div v-if="isDistill" class="form-section">
          <div class="section-title">蒸馏参数</div>
          <div class="section-body">
            <el-row :gutter="20">
              <el-col :span="12">
                <el-form-item label="教师模型">
                  <HierarchicalSelect v-model="form.teacherModel" :data="modelTree" placeholder="请选择教师模型（可选）" clearable />
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="蒸馏轮数">
                  <el-input-number v-model="form.distillEpochs" :min="1" :max="64" style="width: 100%" />
                </el-form-item>
              </el-col>
            </el-row>
            <el-row :gutter="20">
              <el-col :span="12">
                <el-form-item label="蒸馏温度">
                  <el-input-number v-model="form.distillTemp" :min="1" :max="10" :step="0.5" style="width: 100%" />
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="蒸馏损失权重">
                  <el-input-number v-model="form.distillAlpha" :min="0.1" :max="0.9" :step="0.1" style="width: 100%" />
                </el-form-item>
              </el-col>
            </el-row>
          </div>
        </div>
      </div>

      <!-- Step 3: 资源配置 -->
      <div v-if="currentStep === 3">
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
        <el-button v-if="currentStep < 3" type="primary" @click="goNext">下一步</el-button>
        <el-button v-if="currentStep === 3" type="primary" @click="handleSave">保存</el-button>
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
  { step: 1, title: '基本信息', desc: '配置任务名称、压缩类型、描述' },
  { step: 2, title: '压缩配置', desc: '选择模型、算子、量化参数' },
  { step: 3, title: '资源配置', desc: '选择资源池，配置资源规格' },
]

const form = reactive({
  name: '',
  compressionType: 'quantization',
  description: '',
  baseModel: '',
  operator: '',
  quantBits: '4',
  quantMethod: 'bnb',
  calibDataset: '',
  calibSamples: 128,
  groupSize: 128,
  pruningMethod: 'magnitude',
  pruningRatio: 0.5,
  teacherModel: '',
  distillTemp: 2,
  distillAlpha: 0.5,
  distillEpochs: 3,
  kvParams: [] as { key: string; value: string }[],
  poolId: '',
  gpuCount: 1,
  cpu: 4,
  memory: 32,
})

const isQuant = computed(() => ['quantization', 'quant_distill'].includes(form.compressionType))
const isDistill = computed(() => ['distillation', 'quant_distill'].includes(form.compressionType))
const needCalib = computed(() => isQuant.value && (form.quantMethod === 'gptq' || form.quantMethod === 'awq'))

function goBack() {
  router.push('/train/compression')
}

function goNext() {
  if (currentStep.value === 1) {
    if (!form.name) { ElMessage.warning('请输入任务名称'); return }
  } else if (currentStep.value === 2) {
    if (!form.baseModel) { ElMessage.warning('请选择基础模型'); return }
    if (!form.operator) { ElMessage.warning('请选择算子'); return }
    if (needCalib.value && !form.calibDataset) {
      ElMessage.warning('量化方法 GPTQ/AWQ 需要选择校准数据集')
      return
    }
    if (form.compressionType === 'pruning' && !form.pruningRatio) {
      ElMessage.warning('请配置剪枝率')
      return
    }
  }
  currentStep.value++
}

const COMPRESSION_SUBTYPE: Record<string, string> = {
  quantization: '量化',
  pruning: '剪枝',
  distillation: '蒸馏',
  quant_distill: '量化+蒸馏',
}

function buildPayload() {
  const hyperParams: Record<string, unknown> = {}
  if (isQuant.value) {
    hyperParams.quant_bits = form.quantBits
    hyperParams.quant_method = form.quantMethod
    hyperParams.calib_dataset = form.calibDataset
    hyperParams.calib_samples = form.calibSamples
    hyperParams.group_size = form.groupSize
  }
  if (form.compressionType === 'pruning') {
    hyperParams.pruning_method = form.pruningMethod
    hyperParams.pruning_ratio = form.pruningRatio
  }
  if (isDistill.value) {
    hyperParams.teacher_model = form.teacherModel
    hyperParams.distill_temp = form.distillTemp
    hyperParams.distill_alpha = form.distillAlpha
    hyperParams.distill_epochs = form.distillEpochs
  }
  Object.assign(hyperParams, Object.fromEntries(form.kvParams.filter(p => p.key).map(p => [p.key, p.value])))
  return {
    name: form.name,
    taskType: 'compression',
    subType: COMPRESSION_SUBTYPE[form.compressionType] || '量化',
    description: form.description,
    baseModelId: form.baseModel.split('/')[1] || form.baseModel,
    baseModelVersion: form.baseModel.split('/')[2] || '',
    baseModelName: findModelName(form.baseModel.split('/')[1] || form.baseModel),
    operatorId: form.operator.split('/')[1] || form.operator,
    operatorVersion: form.operator.split('/')[2] || '',
    calibDatasetId: form.calibDataset.split('/')[1] || form.calibDataset,
    calibDatasetVersion: form.calibDataset.split('/')[2] || '',
    hyperParams,
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
  if (!form.baseModel) { ElMessage.warning('请选择基础模型'); return }
  if (!form.operator) { ElMessage.warning('请选择算子'); return }
  if (needCalib.value && !form.calibDataset) {
    ElMessage.warning('量化方法 GPTQ/AWQ 需要选择校准数据集')
    return
  }
  if (form.compressionType === 'pruning' && !form.pruningRatio) {
    ElMessage.warning('请配置剪枝率')
    return
  }
  try {
    if (taskId) {
      await updateTrainTask(taskId, buildPayload())
      ElMessage.success('压缩训练任务修改已保存')
    } else {
      await createTrainTask(buildPayload())
      ElMessage.success('压缩训练任务保存成功')
    }
  } catch (e: any) {
    ElMessage.error(e?.message || '保存失败，请稍后重试')
    return
  }
  router.push('/train/compression')
}

async function loadTaskDetail() {
  if (!taskId) return
  try {
    const task = await getTrainTaskDetail(taskId)
    form.name = task.name || ''
    form.description = task.description || ''
    form.baseModel = task.baseModelId ? buildCascaderValue(task.baseModelId, 'model', task.baseModelVersion) : ''
    form.operator = task.operatorId ? buildCascaderValue(task.operatorId, 'operator', task.operatorVersion) : ''
    form.calibDataset = task.calibDatasetId ? buildCascaderValue(task.calibDatasetId, 'dataset', task.calibDatasetVersion) : ''
    const hp = task.hyperParams || {}
    // 压缩类型回显：按 subType 精确映射（量化/剪枝/蒸馏/量化+蒸馏）
    const typeByLabel: Record<string, string> = {
      '量化': 'quantization',
      '剪枝': 'pruning',
      '蒸馏': 'distillation',
      '量化+蒸馏': 'quant_distill',
    }
    form.compressionType = typeByLabel[String(task.subType || '')] || 'quantization'
    form.quantBits = String(hp.quant_bits ?? form.quantBits)
    form.quantMethod = String(hp.quant_method ?? form.quantMethod)
    form.calibSamples = Number(hp.calib_samples ?? form.calibSamples)
    form.groupSize = Number(hp.group_size ?? form.groupSize)
    form.pruningMethod = String(hp.pruning_method ?? form.pruningMethod)
    form.pruningRatio = Number(hp.pruning_ratio ?? form.pruningRatio)
    form.teacherModel = String(hp.teacher_model ?? form.teacherModel)
    form.distillTemp = Number(hp.distill_temp ?? form.distillTemp)
    form.distillAlpha = Number(hp.distill_alpha ?? form.distillAlpha)
    form.distillEpochs = Number(hp.distill_epochs ?? form.distillEpochs)
    const stdKeys = new Set([
      'quant_bits', 'quant_method', 'calib_dataset', 'calib_samples', 'group_size',
      'pruning_method', 'pruning_ratio', 'teacher_model', 'distill_temp', 'distill_alpha', 'distill_epochs',
    ])
    form.kvParams = Object.entries(hp)
      .filter(([k, v]) => !stdKeys.has(k) && v !== null && v !== undefined)
      .map(([key, value]) => ({ key, value: String(value) }))
    const rc = (task.resourceConfig || {}) as unknown as Record<string, unknown>
    form.poolId = String(rc.poolId ?? form.poolId)
    form.gpuCount = Number(rc.gpuCount ?? rc.gpu ?? form.gpuCount)
    form.cpu = Number(rc.cpu ?? form.cpu)
    form.memory = Number(rc.memory ?? form.memory)
  } catch { /* ignore */ }
}

const { datasetTree, modelTree, operatorTree, loadDatasetOptions, ensureDatasetById, loadModelOptions, loadOperatorOptions, findModelName, buildCascaderValue } = useTrainOptions()

onMounted(async () => {
  await Promise.all([loadDatasetOptions('general'), loadModelOptions(), loadOperatorOptions(), loadResourcePools()])
  await loadTaskDetail()
  await ensureDatasetById(form.calibDataset.split('/')[1] || form.calibDataset)
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
  margin-top: 4px;
}
</style>
