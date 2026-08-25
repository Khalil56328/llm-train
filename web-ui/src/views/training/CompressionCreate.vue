<template>
  <div class="compression-create">
    <div class="back-row">
      <el-button text @click="goBack">
        <el-icon><ArrowLeft /></el-icon> 返回
      </el-button>
    </div>
    <PageHeaderCard :title="isEdit ? '编辑压缩训练任务' : '创建压缩训练任务'" desc="通过量化、剪枝、蒸馏等压缩技术，降低模型体积和推理延迟，提升部署效率。" />

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

      <!-- Step 2: 压缩配置 -->
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
            <el-form-item label="教师模型" v-if="form.compressionType === 'distillation' || form.compressionType === 'quant_distill'">
              <HierarchicalSelect v-model="form.teacherModel" :data="modelTree" placeholder="请选择教师模型" clearable />
              <div class="form-tip">知识蒸馏需要选择一个更大的教师模型来指导学生模型训练</div>
            </el-form-item>
          </div>
        </div>

        <div class="form-section">
          <div class="section-title">压缩参数</div>
          <div class="section-body">
            <template v-if="form.compressionType === 'quantization' || form.compressionType === 'quant_distill'">
              <el-row :gutter="20">
                <el-col :span="8">
                  <el-form-item label="量化位数" required>
                    <el-select v-model="form.quantBits" style="width: 100%">
                      <el-option label="4-bit (INT4)" value="4" />
                      <el-option label="8-bit (INT8)" value="8" />
                      <el-option label="GPTQ-4bit" value="gptq4" />
                      <el-option label="AWQ-4bit" value="awq4" />
                      <el-option label="GGUF-Q4_K_M" value="gguf-q4km" />
                    </el-select>
                  </el-form-item>
                </el-col>
                <el-col :span="8">
                  <el-form-item label="量化方法">
                    <el-select v-model="form.quantMethod" style="width: 100%">
                      <el-option label="GPTQ" value="gptq" />
                      <el-option label="AWQ" value="awq" />
                      <el-option label="BitsAndBytes" value="bnb" />
                      <el-option label="GGUF" value="gguf" />
                    </el-select>
                  </el-form-item>
                </el-col>
                <el-col :span="8">
                  <el-form-item label="校准数据集">
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
            </template>
            <template v-if="form.compressionType === 'pruning'">
              <el-row :gutter="20">
                <el-col :span="8">
                  <el-form-item label="剪枝方法">
                    <el-select v-model="form.pruningMethod" style="width: 100%">
                      <el-option label="结构化剪枝" value="structured" />
                      <el-option label="非结构化剪枝" value="unstructured" />
                    </el-select>
                  </el-form-item>
                </el-col>
                <el-col :span="8">
                  <el-form-item label="剪枝比例">
                    <el-slider v-model="form.pruningRatio" :min="0" :max="90" :step="5" show-input />
                  </el-form-item>
                </el-col>
              </el-row>
            </template>
            <template v-if="form.compressionType === 'distillation' || form.compressionType === 'quant_distill'">
              <el-row :gutter="20">
                <el-col :span="8">
                  <el-form-item label="蒸馏温度">
                    <el-input v-model="form.distillTemp" placeholder="2.0" />
                  </el-form-item>
                </el-col>
                <el-col :span="8">
                  <el-form-item label="蒸馏损失权重">
                    <el-input v-model="form.distillAlpha" placeholder="0.5" />
                  </el-form-item>
                </el-col>
                <el-col :span="8">
                  <el-form-item label="训练轮数">
                    <el-input-number v-model="form.epochs" :min="1" :max="100" style="width: 100%" />
                  </el-form-item>
                </el-col>
              </el-row>
            </template>
            <KvEditor v-model="form.kvParams" add-label="自定义参数" />
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
        <el-button v-if="currentStep < 3" type="primary" @click="currentStep++">下一步</el-button>
        <el-button v-if="currentStep === 3" type="primary" @click="handleSave">{{ isEdit ? '保存修改' : '保存' }}</el-button>
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
  { step: 1, title: '基本信息', desc: '配置任务名称、压缩类型、描述' },
  { step: 2, title: '压缩配置', desc: '选择模型、算子、压缩参数' },
  { step: 3, title: '资源配置', desc: '选择资源池，配置 GPU/CPU/内存' },
]

const form = reactive({
  name: '',
  compressionType: 'quantization',
  description: '',
  baseModel: '',
  operator: '',
  teacherModel: '',
  // 量化参数
  quantBits: '4',
  quantMethod: 'gptq',
  calibDataset: 'general-zh',
  calibSamples: 128,
  groupSize: 128,
  // 剪枝参数
  pruningMethod: 'structured',
  pruningRatio: 50,
  // 蒸馏参数
  distillTemp: '2.0',
  distillAlpha: '0.5',
  epochs: 1,
  kvParams: [] as { key: string; value: string }[],
  // 资源配置
  poolId: '',
  gpuCount: 2,
  cpu: 16,
  memory: 64,
})

function goBack() {
  router.push('/train/compression')
}

function buildPayload() {
  return {
    name: form.name,
    taskType: 'compression',
    subType: form.compressionType === 'quantization' ? '量化' : form.compressionType === 'pruning' ? '剪枝' : form.compressionType === 'distillation' ? '蒸馏' : '量化+蒸馏',
    description: form.description,
    baseModelId: form.baseModel.split('/')[1] || form.baseModel,
    baseModelVersion: form.baseModel.split('/')[2] || '',
    baseModelName: findModelName(form.baseModel.split('/')[1] || form.baseModel),
    operatorId: form.operator.split('/')[1] || form.operator,
    operatorVersion: form.operator.split('/')[2] || '',
    teacherModelId: form.teacherModel.split('/')[1] || form.teacherModel,
    teacherModelVersion: form.teacherModel.split('/')[2] || '',
    calibDatasetId: form.calibDataset.split('/')[1] || form.calibDataset,
    calibDatasetVersion: form.calibDataset.split('/')[2] || '',
    hyperParams: {
      quant_bits: form.quantBits,
      quant_method: form.quantMethod,
      calib_dataset: form.calibDataset,
      calib_samples: form.calibSamples,
      group_size: form.groupSize,
      pruning_method: form.pruningMethod,
      pruning_ratio: form.pruningRatio,
      distill_temp: form.distillTemp,
      distill_alpha: form.distillAlpha,
      epochs: form.epochs,
      teacher_model: form.teacherModel,
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
  try {
    if (isEdit.value) {
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
    form.teacherModel = task.teacherModelId ? buildCascaderValue(task.teacherModelId, 'model', task.teacherModelVersion) : ''
    form.calibDataset = task.calibDatasetId ? buildCascaderValue(task.calibDatasetId, 'dataset', task.calibDatasetVersion) : ''
    const hp = task.hyperParams || {}
    const compressionTypeBySubType: Record<string, string> = {
      量化: 'quantization',
      剪枝: 'pruning',
      蒸馏: 'distillation',
      '量化+蒸馏': 'quant_distill',
    }
    form.compressionType = compressionTypeBySubType[String(task.subType || '')] ?? String(hp.compressionType ?? form.compressionType)
    form.quantBits = String(hp.quant_bits ?? form.quantBits)
    form.quantMethod = String(hp.quant_method ?? form.quantMethod)
    form.calibDataset = String(hp.calib_dataset ?? form.calibDataset)
    form.calibSamples = Number(hp.calib_samples ?? form.calibSamples)
    form.groupSize = Number(hp.group_size ?? form.groupSize)
    form.pruningMethod = String(hp.pruning_method ?? form.pruningMethod)
    form.pruningRatio = Number(hp.pruning_ratio ?? form.pruningRatio)
    form.distillTemp = String(hp.distill_temp ?? form.distillTemp)
    form.distillAlpha = String(hp.distill_alpha ?? form.distillAlpha)
    form.epochs = Number(hp.epochs ?? form.epochs)
    form.teacherModel = String(hp.teacher_model ?? form.teacherModel)
    const stdKeys = ['quant_bits', 'quant_method', 'calib_dataset', 'calib_samples', 'group_size', 'pruning_method', 'pruning_ratio', 'distill_temp', 'distill_alpha', 'epochs', 'teacher_model']
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

const { datasetTree, modelTree, operatorTree, loadDatasetOptions, loadModelOptions, loadOperatorOptions, findModelName, findDatasetName, buildCascaderValue } = useTrainOptions()

onMounted(async () => {
  await Promise.all([loadDatasetOptions(), loadModelOptions(), loadOperatorOptions(), loadResourcePools()])
  await loadTaskDetail()
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
