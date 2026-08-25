<template>
  <div class="scene-train-create">
    <div class="back-row">
      <el-button text @click="goBack">
        <el-icon><ArrowLeft /></el-icon> 返回
      </el-button>
    </div>
    <PageHeaderCard :title="isEdit ? '编辑场景训练任务' : '创建场景训练任务'" desc="基于预置场景模板，按阶段快速完成大模型的多阶段训练流程。" />

    <StepCards :steps="steps" :current="currentStep" />

    <div class="content-card">
      <!-- Step 1: 基本信息 -->
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
                @click="form.sceneType = scene.value"
              >
                <div class="scene-icon">
                  <el-icon :size="32"><component :is="scene.icon" /></el-icon>
                </div>
                <div class="scene-name">{{ scene.label }}</div>
                <div class="scene-desc">{{ scene.desc }}</div>
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
                <el-form-item label="基础模型" required>
                  <HierarchicalSelect v-model="form.baseModel" :data="modelTree" placeholder="请选择基础模型" />
                </el-form-item>
              </el-col>
            </el-row>
            <el-form-item label="任务描述">
              <el-input v-model="form.description" type="textarea" :rows="3" placeholder="请输入任务描述" />
            </el-form-item>
          </div>
        </div>
      </div>

      <!-- Step 2: 多阶段训练流程 -->
      <div v-if="currentStep === 2">
        <div class="form-section">
          <div class="section-title">
            训练阶段
            <span class="section-hint-inline">系统预置 5 个阶段，不可手动添加或删除，点击阶段卡片切换配置</span>
          </div>
          <div class="section-body">
            <div class="stage-flow">
              <template v-for="(stage, idx) in form.stages" :key="stage.key">
                <div
                  class="stage-card"
                  :class="{ active: activeStageTab === idx }"
                  @click="activeStageTab = idx"
                >
                  <div class="stage-icon">
                    <el-icon :size="22"><component :is="stage.icon" /></el-icon>
                  </div>
                  <div class="stage-info">
                    <div class="stage-no">第 {{ idx + 1 }} 阶段</div>
                    <div class="stage-name">{{ stage.name }}</div>
                    <div class="stage-desc">{{ stage.desc }}</div>
                  </div>
                </div>
                <div v-if="idx < form.stages.length - 1" class="stage-arrow">
                  <el-icon :size="20"><ArrowRight /></el-icon>
                </div>
              </template>
            </div>
          </div>
        </div>

        <!-- 当前选中阶段的训练参数 -->
        <div v-if="activeStage" class="form-section">
          <div class="section-title">
            <el-icon style="color: #e63946; vertical-align: middle; margin-right: 4px"><Setting /></el-icon>
            {{ activeStage.name }} - 训练参数
          </div>
          <div class="section-body">
            <el-row :gutter="20">
              <el-col :span="8">
                <el-form-item label="训练方法">
                  <el-select v-model="activeStage.method" style="width: 100%">
                    <el-option label="全量更新" value="full" />
                    <el-option label="LoRA" value="lora" />
                    <el-option label="QLoRA" value="qlora" />
                    <el-option label="RLHF" value="rlhf" />
                    <el-option label="DPO" value="dpo" />
                  </el-select>
                </el-form-item>
              </el-col>
              <el-col :span="8">
                <el-form-item label="训练框架">
                  <el-select v-model="activeStage.framework" style="width: 100%" disabled>
                    <el-option label="ms-swift" value="ms-swift" />
                  </el-select>
                </el-form-item>
              </el-col>
              <el-col :span="8">
                <el-form-item label="学习率">
                  <el-input v-model="activeStage.learningRate" placeholder="5e-5" />
                </el-form-item>
              </el-col>
            </el-row>
            <el-row :gutter="20">
              <el-col :span="6">
                <el-form-item label="训练轮数">
                  <el-input-number v-model="activeStage.epochs" :min="1" :max="100" style="width: 100%" />
                </el-form-item>
              </el-col>
              <el-col :span="6">
                <el-form-item label="批次大小">
                  <el-input-number v-model="activeStage.batchSize" :min="1" :max="256" style="width: 100%" />
                </el-form-item>
              </el-col>
              <el-col :span="6">
                <el-form-item label="最大序列长度">
                  <el-input-number v-model="activeStage.maxLength" :min="128" :max="32768" :step="256" style="width: 100%" />
                </el-form-item>
              </el-col>
              <el-col :span="6">
                <el-form-item label="梯度累积步数">
                  <el-input-number v-model="activeStage.gradAccumSteps" :min="1" :max="64" style="width: 100%" />
                </el-form-item>
              </el-col>
            </el-row>
            <div class="kv-section">
              <KvEditor v-model="activeStage.kvParams" add-label="自定义参数" />
            </div>
          </div>
        </div>

        <!-- 当前选中阶段的环境变量 -->
        <div v-if="activeStage" class="form-section">
          <div class="section-title">
            <el-icon style="color: #e63946; vertical-align: middle; margin-right: 4px"><Operation /></el-icon>
            {{ activeStage.name }} - 环境变量
          </div>
          <div class="section-body">
            <KvEditor v-model="activeStage.envVars" add-label="添加环境变量" />
          </div>
        </div>

        <!-- 当前选中阶段的数据配置 -->
        <div v-if="activeStage" class="form-section">
          <div class="section-title">
            <el-icon style="color: #e63946; vertical-align: middle; margin-right: 4px"><Files /></el-icon>
            {{ activeStage.name }} - 数据配置
          </div>
          <div class="section-body">
            <el-row :gutter="20">
              <el-col :span="12">
                <el-form-item label="训练数据集" required>
                  <HierarchicalSelect v-model="activeStage.datasetId" :data="datasetTree" placeholder="请选择数据集" />
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="验证数据集">
                  <HierarchicalSelect v-model="activeStage.valDatasetId" :data="datasetTree" placeholder="请选择验证数据集（可选）" clearable />
                </el-form-item>
              </el-col>
            </el-row>
          </div>
        </div>

        <!-- 当前选中阶段的资源配置 -->
        <div v-if="activeStage" class="form-section">
          <div class="section-title">
            <el-icon style="color: #e63946; vertical-align: middle; margin-right: 4px"><Cpu /></el-icon>
            {{ activeStage.name }} - 资源配置
          </div>
          <div class="section-body">
            <el-row :gutter="20">
              <el-col :span="12">
                <el-form-item label="资源池" required>
                  <el-select v-model="activeStage.poolId" style="width: 100%" placeholder="请选择资源池">
                    <el-option v-for="p in poolOptions" :key="p.id" :label="poolLabel(p)" :value="p.id" />
                  </el-select>
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="GPU数量" required>
                  <el-input-number v-model="activeStage.gpuCount" :min="1" :max="16" style="width: 100%" />
                </el-form-item>
              </el-col>
            </el-row>
            <el-row :gutter="20">
              <el-col :span="12">
                <el-form-item label="CPU(核)">
                  <el-input-number v-model="activeStage.cpu" :min="1" :max="128" style="width: 100%" />
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="内存(GB)">
                  <el-input-number v-model="activeStage.memory" :min="4" :max="1024" :step="8" style="width: 100%" />
                </el-form-item>
              </el-col>
            </el-row>
          </div>
        </div>
      </div>

      <!-- Step 3: 公共参数 -->
      <div v-if="currentStep === 3">
        <div class="form-section">
          <div class="section-title">公共环境变量</div>
          <div class="section-body">
            <p class="section-hint">公共环境变量会下发到所有训练阶段；同名变量以阶段级配置为准。</p>
            <KvEditor v-model="form.globalEnvVars" add-label="添加公共环境变量" />
          </div>
        </div>
        <div class="form-section">
          <div class="section-title">通知配置</div>
          <div class="section-body">
            <el-form-item label="失败通知">
              <el-switch v-model="form.notifyOnFailure" />
              <span class="form-hint">训练失败时发送通知</span>
            </el-form-item>
            <el-form-item label="完成通知">
              <el-switch v-model="form.notifyOnSuccess" />
              <span class="form-hint">训练完成时发送通知</span>
            </el-form-item>
          </div>
        </div>
      </div>

      <!-- 底部按钮 -->
      <div class="step-actions">
        <el-button v-if="currentStep > 1" @click="currentStep--">上一步</el-button>
        <el-button v-if="currentStep < 3" type="primary" @click="goNext">下一步</el-button>
        <el-button v-if="currentStep === 3" type="primary" @click="handleSave">{{ isEdit ? '保存修改' : '保存' }}</el-button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  ArrowLeft, ArrowRight, Setting, Operation, Files, Cpu,
  VideoCamera, Picture, Reading, MagicStick, Trophy,
  Document, ChatDotRound,
} from '@element-plus/icons-vue'
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
const activeStageTab = ref(0)
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
  { step: 1, title: '基本信息', desc: '选择场景，配置任务名称与基础模型' },
  { step: 2, title: '多阶段训练流程', desc: '为每个预置阶段配置参数、数据集与资源' },
  { step: 3, title: '公共参数', desc: '配置公共环境变量与通知设置' },
]

// 5 个系统预置训练阶段（不可手动添加/删除）
const STAGE_PRESETS = [
  {
    key: 'vision_alignment',
    name: '视觉-语言对齐',
    desc: '建立视觉特征与文本语义的映射关系，提供文本感知基础。',
    icon: VideoCamera,
    method: 'lora',
  },
  {
    key: 'multimodal_pretrain',
    name: '多模态预训练',
    desc: '跨模态融合学习，提升对文档、表格、图表等结构化内容的深度理解与推理能力。',
    icon: Picture,
    method: 'lora',
  },
  {
    key: 'long_context_pretrain',
    name: '长上下文预训练',
    desc: '扩展模型上下文窗口，支持长文本解析和跨页分析。',
    icon: Reading,
    method: 'lora',
  },
  {
    key: 'app_sft',
    name: '应用导向SFT',
    desc: '让模型适配真实应用场景，遵循统一指令模板和输出格式，为强化学习铺路。',
    icon: MagicStick,
    method: 'lora',
  },
  {
    key: 'reinforcement_learning',
    name: '强化学习',
    desc: '让轻量级 OCR 模型的输出与可验证指标 / 人类偏好对齐。',
    icon: Trophy,
    method: 'rlhf',
  },
]

const sceneOptions = [
  { value: 'ocr', label: 'OCR场景', desc: '光学字符识别，适用于文档理解、票据识别等', icon: Document },
  { value: 'chat', label: '客服场景', desc: '智能客服对话，适用于售后、咨询等', icon: ChatDotRound },
  { value: 'vision', label: '视觉理解场景', desc: '多模态视觉理解，适用于图像描述、VQA等', icon: Picture },
  { value: 'code', label: '代码生成场景', desc: '代码生成与补全，适用于编程辅助等', icon: Cpu },
]

const { datasetTree, modelTree, loadDatasetOptions, loadModelOptions, findModelName, buildCascaderValue } = useTrainOptions()

interface StageConfig {
  key: string
  name: string
  desc: string
  icon: unknown
  method: string
  framework: string
  datasetId: string
  valDatasetId: string
  learningRate: string
  epochs: number
  batchSize: number
  maxLength: number
  gradAccumSteps: number
  warmupSteps: number
  kvParams: { key: string; value: string }[]
  envVars: { key: string; value: string }[]
  poolId: string
  gpuCount: number
  cpu: number
  memory: number
}

function createDefaultStage(preset: typeof STAGE_PRESETS[number]): StageConfig {
  return {
    key: preset.key,
    name: preset.name,
    desc: preset.desc,
    icon: preset.icon,
    method: preset.method,
    framework: 'ms-swift',
    datasetId: '',
    valDatasetId: '',
    learningRate: '1e-5',
    epochs: 1,
    batchSize: 1,
    maxLength: 1024,
    gradAccumSteps: 1,
    warmupSteps: 100,
    kvParams: [
      { key: 'train_type', value: preset.method === 'fuLl' ? 'full' : 'lora' },
      { key: 'torch_dtype', value: 'bfloat16' },
      { key: 'num_train_epochs', value: '3' },
      { key: 'per_device_train_batch_size', value: '1' },
      { key: 'per_device_eval_batch_size', value: '1' },
    ],
    envVars: [
      { key: 'RANK', value: '0' },
      { key: 'WORLD_SIZE', value: '1' },
      { key: 'MASTER_ADDR', value: 'localhost' },
      { key: 'MASTER_PORT', value: '5678' },
      { key: 'LOCAL_RANK', value: '0' },
    ],
    poolId: '',
    gpuCount: 1,
    cpu: 4,
    memory: 32,
  }
}

const form = reactive({
  name: '',
  sceneType: 'ocr',
  description: '',
  baseModel: '',
  stages: STAGE_PRESETS.map(createDefaultStage) as StageConfig[],
  globalEnvVars: [] as { key: string; value: string }[],
  notifyOnFailure: true,
  notifyOnSuccess: true,
})

const activeStage = computed(() => form.stages[activeStageTab.value] || null)

function goBack() {
  router.push('/train/scene')
}

function goNext() {
  // 进入下一步前先做一次基本校验
  if (currentStep.value === 2) {
    for (let i = 0; i < form.stages.length; i++) {
      const s = form.stages[i]
      if (!s.datasetId) {
        ElMessage.warning(`请为「${s.name}」选择训练数据集`)
        activeStageTab.value = i
        return
      }
      if (!s.poolId) {
        ElMessage.warning(`请为「${s.name}」选择资源池`)
        activeStageTab.value = i
        return
      }
    }
  }
  currentStep.value++
}

function buildPayload() {
  return {
    name: form.name,
    taskType: 'scene',
    taskSubType: 'text-generation',
    subType: sceneOptions.find(s => s.value === form.sceneType)?.label || '视觉理解场景',
    description: form.description,
    baseModelId: form.baseModel.split('/')[1] || form.baseModel,
    baseModelVersion: form.baseModel.split('/')[2] || '',
    baseModelName: findModelName(form.baseModel.split('/')[1] || form.baseModel),
    framework: 'ms-swift',
    hyperParams: {
      sceneType: form.sceneType,
      stages: form.stages.map(s => ({
        key: s.key,
        name: s.name,
        method: s.method,
        framework: s.framework,
        datasetId: s.datasetId.split('/')[1] || s.datasetId,
        datasetVersion: s.datasetId.split('/')[2] || '',
        valDatasetId: s.valDatasetId.split('/')[1] || s.valDatasetId,
        valDatasetVersion: s.valDatasetId.split('/')[2] || '',
        learning_rate: s.learningRate,
        epochs: s.epochs,
        batch_size: s.batchSize,
        max_length: s.maxLength,
        gradient_accumulation_steps: s.gradAccumSteps,
        warmup_steps: s.warmupSteps,
        ...Object.fromEntries(s.kvParams.filter(p => p.key).map(p => [p.key, p.value])),
        envVars: Object.fromEntries(s.envVars.filter(p => p.key).map(p => [p.key, p.value])),
        resourceConfig: {
          poolId: s.poolId,
          gpuCount: s.gpuCount,
          cpu: s.cpu,
          memory: s.memory,
        },
      })),
      globalEnvVars: Object.fromEntries(form.globalEnvVars.filter(p => p.key).map(p => [p.key, p.value])),
      notifyOnFailure: form.notifyOnFailure,
      notifyOnSuccess: form.notifyOnSuccess,
    },
  }
}

async function handleSave() {
  if (!form.name) { ElMessage.warning('请输入任务名称'); return }
  if (!form.baseModel) { ElMessage.warning('请选择基础模型'); return }
  for (let i = 0; i < form.stages.length; i++) {
    const s = form.stages[i]
    if (!s.datasetId) {
      ElMessage.warning(`请为「${s.name}」选择训练数据集`)
      activeStageTab.value = i
      currentStep.value = 2
      return
    }
    if (!s.poolId) {
      ElMessage.warning(`请为「${s.name}」选择资源池`)
      activeStageTab.value = i
      currentStep.value = 2
      return
    }
  }
  try {
    if (isEdit.value) {
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
    const scene = sceneOptions.find(s => s.label === task.subType)
    if (scene) form.sceneType = scene.value
    const hp = (task.hyperParams || {}) as Record<string, unknown>
    if (hp.sceneType && typeof hp.sceneType === 'string') {
      form.sceneType = hp.sceneType
    }
    const stages = hp.stages
    if (Array.isArray(stages) && stages.length > 0) {
      stages.forEach((raw, idx) => {
        if (idx >= form.stages.length) return
        const s = raw as Record<string, unknown>
        const target = form.stages[idx]
        target.method = String(s.method ?? target.method)
        target.datasetId = s.datasetId ? buildCascaderValue(String(s.datasetId), 'dataset', s.datasetVersion as string | undefined) : ''
        target.valDatasetId = s.valDatasetId ? buildCascaderValue(String(s.valDatasetId), 'dataset', s.valDatasetVersion as string | undefined) : ''
        target.learningRate = String(s.learning_rate ?? s.learningRate ?? target.learningRate)
        target.epochs = Number(s.epochs ?? target.epochs)
        target.batchSize = Number(s.batch_size ?? s.batchSize ?? target.batchSize)
        target.maxLength = Number(s.max_length ?? s.maxLength ?? target.maxLength)
        target.gradAccumSteps = Number(s.gradient_accumulation_steps ?? s.gradAccumSteps ?? target.gradAccumSteps)
        target.warmupSteps = Number(s.warmup_steps ?? s.warmupSteps ?? target.warmupSteps)
        // 反序列化自定义参数
        const stdKeys = new Set([
          'key', 'name', 'desc', 'icon', 'method', 'framework',
          'datasetId', 'datasetVersion', 'valDatasetId', 'valDatasetVersion',
          'learning_rate', 'epochs', 'batch_size', 'max_length', 'gradient_accumulation_steps', 'warmup_steps',
          'envVars', 'resourceConfig',
        ])
        target.kvParams = Object.entries(s)
          .filter(([k, v]) => !stdKeys.has(k) && v !== null && v !== undefined)
          .map(([key, value]) => ({ key, value: String(value) }))
        // 反序列化阶段级环境变量
        const ev = (s.envVars || {}) as Record<string, unknown>
        target.envVars = Object.entries(ev).map(([key, value]) => ({ key, value: String(value) }))
        // 反序列化资源配置
        const rc = (s.resourceConfig || {}) as Record<string, unknown>
        target.poolId = String(rc.poolId ?? '')
        target.gpuCount = Number(rc.gpuCount ?? rc.gpu ?? target.gpuCount)
        target.cpu = Number(rc.cpu ?? target.cpu)
        target.memory = Number(rc.memory ?? target.memory)
      })
    }
    const gev = (hp.globalEnvVars || {}) as Record<string, unknown>
    form.globalEnvVars = Object.entries(gev).map(([key, value]) => ({ key, value: String(value) }))
    form.notifyOnFailure = Boolean(hp.notifyOnFailure ?? form.notifyOnFailure)
    form.notifyOnSuccess = Boolean(hp.notifyOnSuccess ?? form.notifyOnSuccess)
  } catch { /* ignore */ }
}

onMounted(async () => {
  await Promise.all([loadDatasetOptions(), loadModelOptions(), loadResourcePools()])
  await loadTaskDetail()
})
</script>

<style lang="scss" scoped>
.back-row {
  margin-bottom: 16px;
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
.stage-flow {
  display: flex;
  align-items: stretch;
  gap: 8px;
  flex-wrap: nowrap;
  overflow-x: auto;
  padding: 4px 2px;
}
.stage-card {
  flex: 1;
  min-width: 170px;
  border: 2px solid $border-color-lighter;
  border-radius: 8px;
  padding: 12px;
  cursor: pointer;
  display: flex;
  flex-direction: column;
  gap: 6px;
  background: $bg-color-white;
  transition: all 0.2s;

  &:hover {
    border-color: $color-primary;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
  }

  &.active {
    border-color: $color-primary;
    background: rgba($color-primary, 0.04);
    box-shadow: 0 0 0 1px rgba($color-primary, 0.1);
  }
}
.stage-icon {
  color: $color-primary;
}
.stage-info {
  flex: 1;
  min-width: 0;
}
.stage-no {
  font-size: 12px;
  color: $text-secondary;
  margin-bottom: 2px;
}
.stage-name {
  font-weight: 600;
  font-size: 14px;
  margin-bottom: 4px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.stage-desc {
  font-size: 11px;
  color: $text-secondary;
  line-height: 1.4;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.stage-arrow {
  align-self: center;
  color: $border-color;
  flex-shrink: 0;
}
.section-hint {
  font-size: 12px;
  color: $text-secondary;
  margin: 0 0 12px;
}
.section-hint-inline {
  margin-left: 8px;
  font-size: 12px;
  color: $text-secondary;
  font-weight: normal;
}
.form-hint {
  margin-left: 8px;
  font-size: 12px;
  color: $text-secondary;
}
.kv-section {
  margin-top: 4px;
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
