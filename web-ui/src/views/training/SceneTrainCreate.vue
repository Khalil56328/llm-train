<template>
  <div class="scene-train-create">
    <div class="back-row">
      <el-button text @click="goBack">
        <el-icon><ArrowLeft /></el-icon> 返回
      </el-button>
    </div>
    <PageHeaderCard title="创建场景训练任务" desc="选择预置场景模板，按单阶段 SFT 完成配置后一键启动训练（演示版：多阶段流程已简化为单阶段 SFT）。" />

    <StepCards :steps="steps" :current="currentStep" />

    <div class="content-card">
      <!-- Step 1: 场景与基本信息 -->
      <div v-if="currentStep === 1">
        <div class="form-section">
          <div class="section-title">场景选择</div>
          <div class="section-body">
            <div class="scene-cards">
              <div
                v-for="scene in sceneOptions"
                :key="scene.value"
                class="scene-card"
                :class="{ active: form.sceneType === scene.value }"
                @click="selectScene(scene.value)"
              >
                <div class="scene-icon">
                  <el-icon :size="32"><component :is="scene.icon" /></el-icon>
                </div>
                <div class="scene-name">{{ scene.label }}</div>
                <div class="scene-desc">{{ scene.desc }}</div>
                <div v-if="scene.tip" class="scene-tip">{{ scene.tip }}</div>
              </div>
            </div>
          </div>
        </div>

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
                <el-form-item label="任务类型">
                  <el-input model-value="文本生成" disabled />
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
            <el-alert class="dataset-tip" type="info" :closable="false" show-icon :title="datasetTip" />
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
            <el-alert
              class="preset-alert"
              type="info"
              :closable="false"
              show-icon
              :title="`已应用「${currentScene?.label || ''}」基础参数模板`"
            >
              <div class="preset-alert-body">
                <span>{{ currentScene?.tip }}</span>
                <el-button link type="primary" @click="restoreScenePreset">恢复模板参数</el-button>
              </div>
            </el-alert>
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
            <el-row :gutter="20">
              <el-col :span="8">
                <el-form-item label="最大序列长度">
                  <el-input-number v-model="form.maxLength" :min="128" :max="32768" :step="256" style="width: 100%" />
                </el-form-item>
              </el-col>
              <el-col :span="8">
                <el-form-item label="梯度累积步数">
                  <el-input-number v-model="form.gradAccumSteps" :min="1" :max="64" style="width: 100%" />
                </el-form-item>
              </el-col>
            </el-row>
            <KvEditor v-model="form.kvParams" add-label="自定义参数" />
          </div>
        </div>
      </div>

      <!-- Step 4: 资源配置（演示版仅展示，实际执行按宿主机真实资源） -->
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
        <el-button v-if="currentStep < 4" type="primary" @click="goNext">下一步</el-button>
        <el-button v-if="currentStep === 4" type="primary" @click="handleSave">保存</el-button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import type { Component } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { ArrowLeft, Document, ChatDotRound, Picture, Cpu } from '@element-plus/icons-vue'
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
  { step: 1, title: '基本信息', desc: '选择场景，配置任务名称与描述' },
  { step: 2, title: '数据配置', desc: '选择训练数据集' },
  { step: 3, title: '训练参数', desc: '配置训练方法、模型、算子、超参' },
  { step: 4, title: '资源配置', desc: '资源参数仅展示，按宿主机真实资源执行' },
]

interface SceneOption {
  value: string
  label: string
  desc: string
  icon: Component
  tip: string
  template: {
    learningRate: string
    epochs: number
    batchSize: number
    maxLength: number
    gradAccumSteps: number
    kvParams: { key: string; value: string }[]
  }
}

// 场景基础参数模板：选择场景时自动预置一套行业主流的训练超参（基于 MS-Swift 多模态/纯文本 SFT 推荐配置），
// 用户可在步骤三基于模板微调，也可一键恢复模板参数。
const sceneOptions: SceneOption[] = [
  {
    value: 'ocr',
    label: 'OCR场景',
    desc: '光学字符识别，适用于文档理解、票据识别、版面分析等',
    icon: Document,
    tip: '高分辨率输入（max_pixels 1003520）+ 冻结视觉编码器 + all-linear LoRA，适配文档/票据等密集文本识别',
    template: {
      learningRate: '1e-4',
      epochs: 3,
      batchSize: 1,
      maxLength: 8192,
      gradAccumSteps: 16,
      kvParams: [
        { key: 'lora_rank', value: '8' },
        { key: 'lora_alpha', value: '16' },
        { key: 'target_modules', value: 'all-linear' },
        { key: 'max_pixels', value: '1003520' },
        { key: 'freeze_vit', value: 'true' },
        { key: 'eval_strategy', value: 'no' },
        { key: 'save_steps', value: '500' },
      ],
    },
  },
  {
    value: 'chat',
    label: '客服场景',
    desc: '智能客服对话，适用于售后、咨询、订单物流等',
    icon: ChatDotRound,
    tip: '纯文本 SFT 基线：all-linear LoRA + 2048 上下文，适合快速验证对话效果',
    template: {
      learningRate: '1e-4',
      epochs: 3,
      batchSize: 2,
      maxLength: 2048,
      gradAccumSteps: 8,
      kvParams: [
        { key: 'lora_rank', value: '8' },
        { key: 'lora_alpha', value: '16' },
        { key: 'target_modules', value: 'all-linear' },
        { key: 'eval_strategy', value: 'no' },
        { key: 'save_steps', value: '500' },
      ],
    },
  },
  {
    value: 'vision',
    label: '视觉理解场景',
    desc: '多模态视觉理解，适用于图像描述、视觉问答 VQA、通用视觉理解等',
    icon: Picture,
    tip: 'General Vision 通用视觉基线：冻结视觉编码器 + all-linear LoRA，适配图像描述 / VQA 等视觉任务',
    template: {
      learningRate: '1e-4',
      epochs: 3,
      batchSize: 2,
      maxLength: 8192,
      gradAccumSteps: 8,
      kvParams: [
        { key: 'lora_rank', value: '8' },
        { key: 'lora_alpha', value: '16' },
        { key: 'target_modules', value: 'all-linear' },
        { key: 'max_pixels', value: '1003520' },
        { key: 'freeze_vit', value: 'true' },
        { key: 'eval_strategy', value: 'no' },
        { key: 'save_steps', value: '500' },
      ],
    },
  },
  {
    value: 'code',
    label: '代码生成场景',
    desc: '代码生成与补全，适用于编程辅助、单元测试生成等',
    icon: Cpu,
    tip: '代码场景建议更长上下文：max_length 4096 + lora_rank 16，兼顾生成质量与显存',
    template: {
      learningRate: '2e-4',
      epochs: 3,
      batchSize: 2,
      maxLength: 4096,
      gradAccumSteps: 8,
      kvParams: [
        { key: 'lora_rank', value: '16' },
        { key: 'lora_alpha', value: '32' },
        { key: 'target_modules', value: 'all-linear' },
        { key: 'eval_strategy', value: 'no' },
        { key: 'save_steps', value: '500' },
      ],
    },
  },
]

const { datasetTree, modelTree, operatorTree, loadDatasetOptions, ensureDatasetById, loadModelOptions, loadOperatorOptions, findModelName, findDatasetName, buildCascaderValue } = useTrainOptions()

const form = reactive({
  name: '',
  sceneType: 'ocr',
  description: '',
  datasetId: '',
  framework: 'ms-swift',
  method: 'lora',
  baseModel: '',
  operator: '',
  learningRate: sceneOptions[0].template.learningRate,
  epochs: sceneOptions[0].template.epochs,
  batchSize: sceneOptions[0].template.batchSize,
  maxLength: sceneOptions[0].template.maxLength,
  gradAccumSteps: sceneOptions[0].template.gradAccumSteps,
  kvParams: sceneOptions[0].template.kvParams.map(p => ({ ...p })) as { key: string; value: string }[],
  poolId: '',
  gpuCount: 1,
  cpu: 4,
  memory: 32,
})

function applyScenePreset(value: string) {
  const preset = sceneOptions.find(s => s.value === value)
  if (!preset) return
  const t = preset.template
  form.learningRate = t.learningRate
  form.epochs = t.epochs
  form.batchSize = t.batchSize
  form.maxLength = t.maxLength
  form.gradAccumSteps = t.gradAccumSteps
  // 合并模板自定义参数：同名 key（lora_rank/max_pixels 等）以模板为准，用户额外项保留
  const templateKeys = new Set(t.kvParams.map(p => p.key))
  const kept = form.kvParams.filter(p => p.key && !templateKeys.has(p.key))
  form.kvParams = [...t.kvParams.map(p => ({ ...p })), ...kept]
}

function selectScene(value: string) {
  const preset = sceneOptions.find(s => s.value === value)
  form.sceneType = value
  if (preset) {
    applyScenePreset(value)
    ElMessage.info(`已应用「${preset.label}」基础参数模板，可在步骤三调整或一键恢复`)
  }
}

function restoreScenePreset() {
  const preset = sceneOptions.find(s => s.value === form.sceneType)
  if (preset) {
    applyScenePreset(form.sceneType)
    ElMessage.success(`已恢复「${preset.label}」基础参数模板`)
  }
}

const currentScene = computed(() => sceneOptions.find(s => s.value === form.sceneType))

// 步骤二：按场景给出数据集类型提示，与各场景基础参数模板形成完整闭环
const datasetTips: Record<string, string> = {
  ocr: 'OCR 场景为多模态图文任务，请选择包含图像字段（messages + images）的多模态 SFT 数据集，如内置演示数据集 scene_ocr_demo（票据/单据/文档识别问答）。',
  vision: '视觉理解（General Vision）为多模态图文任务，请选择包含图像字段（messages + images）的多模态 SFT 数据集，如内置演示数据集 scene_vision_demo（图像描述 / VQA 问答）。',
  chat: '客服场景为纯文本对话任务，请选择对话式 SFT 数据集，如内置演示数据集 sft_self_cognition 或 scene_customer_service（电商客服多轮对话）。',
  code: '代码生成场景为纯文本任务，请选择代码相关的文本 SFT 数据集，或自行导入代码问答数据。',
}
const datasetTip = computed(() => datasetTips[form.sceneType] || '请选择与当前场景匹配的 SFT 训练数据集。')

function goBack() {
  router.push('/train/scene')
}

function goNext() {
  if (currentStep.value === 1) {
    if (!form.name) { ElMessage.warning('请输入任务名称'); return }
  } else if (currentStep.value === 2) {
    if (!form.datasetId) { ElMessage.warning('请选择训练数据集'); return }
  } else if (currentStep.value === 3) {
    if (!form.baseModel) { ElMessage.warning('请选择基础模型'); return }
    if (!form.operator) { ElMessage.warning('请选择算子'); return }
  }
  currentStep.value++
}

function buildPayload() {
  return {
    name: form.name,
    taskType: 'scene',
    taskSubType: 'text-generation',
    subType: sceneOptions.find(s => s.value === form.sceneType)?.label || 'OCR场景',
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
      ...Object.fromEntries(form.kvParams.filter(p => p.key).map(p => [p.key, p.value])),
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
    if (taskId) {
      await updateTrainTask(taskId, buildPayload())
      ElMessage.success('场景训练任务修改已保存')
    } else {
      await createTrainTask(buildPayload())
      ElMessage.success('场景训练任务保存成功')
    }
  } catch (e: any) {
    ElMessage.error(e?.message || '保存失败，请稍后重试')
    return
  }
  router.push('/train/scene')
}

async function loadTaskDetail() {
  if (!taskId) return
  try {
    const task = await getTrainTaskDetail(taskId)
    form.name = task.name || ''
    form.description = task.description || ''
    form.baseModel = task.baseModelId ? buildCascaderValue(task.baseModelId, 'model', task.baseModelVersion) : ''
    form.operator = task.operatorId ? buildCascaderValue(task.operatorId, 'operator', task.operatorVersion) : ''
    form.framework = String(task.framework ?? '') || 'ms-swift'
    form.datasetId = task.datasetId ? buildCascaderValue(task.datasetId, 'dataset', task.datasetVersion) : ''
    const scene = sceneOptions.find(s => s.label === task.subType)
    if (scene) form.sceneType = scene.value
    const hp = (task.hyperParams || {}) as Record<string, unknown>
    if (typeof hp.sceneType === 'string') form.sceneType = hp.sceneType
    // 兼容旧版多阶段任务：无扁平超参时取第 1 阶段的参数回显
    const legacy = Array.isArray(hp.stages) ? (hp.stages[0] as Record<string, unknown> | undefined) : undefined
    form.method = String(hp.training_method ?? (legacy?.method as string) ?? form.method)
    form.learningRate = String(hp.learning_rate ?? (legacy?.learning_rate as string) ?? form.learningRate)
    form.epochs = Number(hp.epochs ?? legacy?.epochs ?? form.epochs)
    form.batchSize = Number(hp.batch_size ?? legacy?.batch_size ?? form.batchSize)
    form.maxLength = Number(hp.max_length ?? legacy?.max_length ?? form.maxLength)
    form.gradAccumSteps = Number(hp.gradient_accumulation_steps ?? legacy?.gradient_accumulation_steps ?? form.gradAccumSteps)
    const stdKeys = new Set(['training_method', 'learning_rate', 'epochs', 'batch_size', 'max_length', 'gradient_accumulation_steps'])
    form.kvParams = Object.entries(hp)
      .filter(([k, v]) => !stdKeys.has(k) && k !== 'sceneType' && k !== 'stages' && v !== null && v !== undefined)
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
.dataset-tip {
  margin-top: 4px;
  margin-bottom: 8px;
}
.scene-cards {
  display: flex;
  gap: 16px;
  flex-wrap: wrap;
}
.scene-card {
  width: 200px;
  padding: 20px 16px;
  border: 2px solid $border-color-lighter;
  border-radius: 8px;
  text-align: center;
  cursor: pointer;
  transition: all 0.2s;
  &:hover {
    border-color: $color-primary;
    box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
  }
  &.active {
    border-color: $color-primary;
    background: rgba($color-primary, 0.04);
  }
}
.scene-icon {
  margin-bottom: 8px;
  color: $color-primary;
}
.scene-name {
  font-weight: 600;
  font-size: 14px;
  margin-bottom: 4px;
}
.scene-desc {
  font-size: 12px;
  color: $text-secondary;
  line-height: 1.4;
}
.scene-tip {
  margin-top: 8px;
  font-size: 11px;
  color: $color-primary;
  background: rgba($color-primary, 0.06);
  border-radius: 4px;
  padding: 4px 6px;
  line-height: 1.4;
  text-align: left;
}
.preset-alert {
  margin-bottom: 16px;
}
.preset-alert-body {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
</style>
