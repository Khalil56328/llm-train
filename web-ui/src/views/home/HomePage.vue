<template>
  <div class="home-page">
    <!-- 欢迎卡片 -->
    <div class="page-header-card">
      <div class="header-title">欢迎使用大模型训推平台</div>
      <div class="header-desc">
        平台提供从数据处理、模型训练到部署评测的一站式大模型训推服务，支持模型微调、偏好对齐、模型压缩、预训练等能力。
      </div>
    </div>

    <!-- 统计卡片（数据来自后端统计接口） -->
    <div class="stats-row">
      <div class="stat-card" v-for="s in statCards" :key="s.key">
        <div class="stat-icon" :style="{ background: s.bg }">
          <el-icon :size="22">
            <component :is="s.icon" />
          </el-icon>
        </div>
        <div class="stat-info">
          <div class="stat-value">{{ statValues[s.key] ?? 0 }}</div>
          <div class="stat-label">{{ s.label }}</div>
        </div>
      </div>
    </div>

    <!-- 快捷入口 -->
    <div class="content-card" style="margin-bottom: 20px">
      <div class="card-header">快捷入口</div>
      <div class="quick-actions">
        <div
          v-for="action in quickActions"
          :key="action.path"
          class="quick-action-card"
          @click="$router.push(action.path)"
        >
          <el-icon :size="28" :color="action.color">
            <component :is="action.icon" />
          </el-icon>
          <span class="action-name">{{ action.name }}</span>
          <span class="action-desc">{{ action.desc }}</span>
        </div>
      </div>
    </div>

    <!-- 最新任务 -->
    <div class="content-card">
      <div class="card-header">
        <span>我的训练任务</span>
        <el-button type="primary" link @click="$router.push('/train/fine-tune')">
          查看全部 <el-icon><ArrowRight /></el-icon>
        </el-button>
      </div>
      <DataTable
        :data="recentTasks"
        :columns="taskColumns"
        :show-pagination="false"
      >
        <template #actions="{ row }">
          <el-button type="primary" link size="small" @click="viewDetail(row)">详情</el-button>
        </template>
      </DataTable>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { Document, Cpu, Connection, DataAnalysis, CircleCheck, TrendCharts, ArrowRight } from '@element-plus/icons-vue'
import { TaskStatusMap, TaskStatusColorMap, TrainTaskTypeMenuMap } from '@/types'
import DataTable from '@/components/common/DataTable.vue'
import { getTrainTaskList, getTaskStats } from '@/api/training'
import { getModelStats } from '@/api/model'
import { getDeploymentStats, getEvalStats } from '@/api/service'

const router = useRouter()

// 统计卡片 UI 配置（数据值从后端统计接口获取）
const statCards = [
  { key: 'tasks', label: '训练任务', icon: 'Cpu', bg: 'linear-gradient(135deg, #e63946, #f56c6c)' },
  { key: 'models', label: '我的模型', icon: 'Document', bg: 'linear-gradient(135deg, #409eff, #79bbff)' },
  { key: 'deploys', label: '部署服务', icon: 'Connection', bg: 'linear-gradient(135deg, #67c23a, #95d475)' },
  { key: 'evals', label: '评测任务', icon: 'DataAnalysis', bg: 'linear-gradient(135deg, #e6a23c, #eebe77)' },
]
const statValues = ref<Record<string, number>>({ tasks: 0, models: 0, deploys: 0, evals: 0 })

const quickActions = [
  { name: '模型微调', desc: '监督微调训练', icon: 'Cpu', color: '#e63946', path: '/train/fine-tune' },
  { name: '偏好对齐', desc: 'DPO/KTO/ORPO/SimPO', icon: 'TrendCharts', color: '#e6a23c', path: '/train/alignment' },
  { name: '模型压缩', desc: '模型量化', icon: 'CircleCheck', color: '#409eff', path: '/train/compression' },
  { name: '预训练', desc: '持续预训练', icon: 'DataAnalysis', color: '#67c23a', path: '/train/pretrain' },
  { name: '场景训练', desc: 'OCR/客服/代码', icon: 'Document', color: '#8b5cf6', path: '/train/scene' },
  { name: '模型部署', desc: '推理服务部署', icon: 'Connection', color: '#06b6d4', path: '/service/deployment' },
]

const taskColumns = [
  { prop: 'name', label: '任务名称', minWidth: 160 },
  { prop: 'taskType', label: '任务类型', width: 100 },
  {
    prop: 'status',
    label: '状态',
    width: 100,
    type: 'status' as const,
    statusMap: TaskStatusMap,
    statusColorMap: TaskStatusColorMap,
  },
  { prop: 'createdAt', label: '创建时间', width: 170, type: 'datetime' as const },
]

const recentTasks = ref<any[]>([])

async function loadStats() {
  // 并行加载四个统计接口，单个失败不影响其余卡片
  const [taskStats, modelStats, deployStats, evalStats] = await Promise.allSettled([
    getTaskStats(),
    getModelStats(),
    getDeploymentStats(),
    getEvalStats(),
  ])
  if (taskStats.status === 'fulfilled') {
    statValues.value.tasks = Number(taskStats.value?.total ?? 0)
  }
  if (modelStats.status === 'fulfilled') {
    statValues.value.models = Number(modelStats.value?.total ?? 0)
  }
  if (deployStats.status === 'fulfilled') {
    statValues.value.deploys = Number(deployStats.value?.total ?? 0)
  }
  if (evalStats.status === 'fulfilled') {
    statValues.value.evals = Number(evalStats.value?.total ?? 0)
  }
}

async function loadRecentTasks() {
  try {
    const res = await getTrainTaskList({ pageIndex: 1, pageSize: 3 })
    recentTasks.value = res.list || []
  } catch {
    recentTasks.value = []
  }
}

onMounted(() => {
  loadStats()
  loadRecentTasks()
})

function viewDetail(row: any) {
  const menu = TrainTaskTypeMenuMap[row?.taskType as keyof typeof TrainTaskTypeMenuMap]
  router.push({ path: `/train/task/${row.id}`, query: { from: menu?.path || '/train/fine-tune' } })
}
</script>

<style lang="scss" scoped>
.home-page {
  .stats-row {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 16px;
    margin-bottom: 20px;
  }

  .stat-card {
    background: $bg-color-white;
    border: 1px solid $border-color-light;
    border-radius: $border-radius-large;
    padding: 20px;
    display: flex;
    align-items: center;
    gap: 16px;
    transition: $transition-base;

    &:hover {
      box-shadow: $box-shadow-base;
      transform: translateY(-2px);
    }

    .stat-icon {
      width: 52px;
      height: 52px;
      border-radius: 12px;
      display: flex;
      align-items: center;
      justify-content: center;
      color: #fff;
      flex-shrink: 0;
    }

    .stat-info {
      .stat-value {
        font-size: 26px;
        font-weight: 700;
        color: $text-primary;
        line-height: 1.2;
      }

      .stat-label {
        font-size: $font-size-mini;
        color: $text-secondary;
        margin-top: 2px;
      }
    }
  }

  .quick-actions {
    display: grid;
    grid-template-columns: repeat(6, 1fr);
    gap: 14px;
  }

  .quick-action-card {
    text-align: center;
    padding: 20px 12px;
    border: 1px solid $border-color-light;
    border-radius: $border-radius-large;
    cursor: pointer;
    transition: $transition-base;

    &:hover {
      border-color: $color-primary;
      background: $color-primary-opacity;
      transform: translateY(-2px);
    }

    .action-name {
      display: block;
      font-size: 14px;
      font-weight: 500;
      color: $text-primary;
      margin-top: 10px;
    }

    .action-desc {
      display: block;
      font-size: 11px;
      color: $text-secondary;
      margin-top: 4px;
    }
  }

  .card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-size: 16px;
    font-weight: 600;
    color: $text-primary;
    margin-bottom: 16px;
    padding-bottom: 12px;
    border-bottom: 1px solid $border-color-lighter;
  }
}
</style>
