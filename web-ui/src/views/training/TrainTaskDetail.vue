<template>
  <div class="train-detail">
    <div class="back-row">
      <el-button text @click="goBack">
        <el-icon><ArrowLeft /></el-icon> 返回
      </el-button>
    </div>
    <PageHeaderCard :title="`训练任务详情 - ${task.name || ''}`" desc="查看训练任务详细信息、实时日志、训练指标与产出。" />

    <!-- 状态 & 操作 -->
    <div class="content-card" style="margin-bottom: 16px">
      <div class="detail-status-bar">
        <div class="status-info">
          <span class="label">任务状态：</span>
          <el-tag :type="TaskStatusColorMap[task.status as keyof typeof TaskStatusColorMap]" size="large">
            {{ TaskStatusMap[task.status as keyof typeof TaskStatusMap] }}
          </el-tag>
          <el-progress
            v-if="['running','pending','paused'].includes(task.status)"
            :percentage="task.progress || 0"
            style="width: 200px; margin-left: 12px"
          />
          <span v-if="task.startedAt" class="detail-time">开始：{{ task.startedAt }}</span>
          <span v-if="task.finishedAt" class="detail-time">完成：{{ task.finishedAt }}</span>
        </div>
        <div class="status-actions">
          <el-button v-if="task.status === 'pending'" type="primary" :loading="acting" @click="handleSubmit">提交</el-button>
          <el-button v-if="task.status === 'running'" type="warning" :loading="acting" @click="handlePause">暂停</el-button>
          <el-button v-if="task.status === 'paused'" type="primary" :loading="acting" @click="handleResume">继续</el-button>
          <el-button v-if="['running','paused'].includes(task.status)" type="danger" :loading="acting" @click="handleStop">停止</el-button>
          <el-button v-if="['running','pending','paused'].includes(task.status)" :loading="acting" @click="handleCancel">取消</el-button>
          <el-button v-if="task.status === 'failed' || task.status === 'stopped'" type="primary" :loading="acting" @click="handleRetry">重试</el-button>
        </div>
      </div>
      <div v-if="task.errorMessage" class="error-message">错误信息：{{ task.errorMessage }}</div>
      <div v-if="task.engineCommand" class="engine-command">
        <span class="label">引擎命令：</span>
        <code>{{ task.engineCommand }}</code>
      </div>
    </div>

    <!-- 标签页 -->
    <div class="content-card">
      <el-tabs v-model="activeTab">
        <!-- 基本信息 -->
        <el-tab-pane label="基本信息" name="info">
          <div class="info-grid">
            <div class="info-item"><span class="info-label">任务名称：</span>{{ task.name }}</div>
            <div class="info-item"><span class="info-label">任务类型：</span>{{ task.taskType }}</div>
            <div class="info-item"><span class="info-label">模态：</span>{{ task.taskSubType || '-' }}</div>
            <div class="info-item"><span class="info-label">训练方法：</span>{{ task.subType || '-' }}</div>
            <div class="info-item"><span class="info-label">训练框架：</span>{{ task.framework || '-' }}</div>
            <div class="info-item"><span class="info-label">基础模型：</span>{{ task.baseModelName || '-' }}</div>
            <div class="info-item"><span class="info-label">基础模型版本：</span>{{ task.baseModelVersion || '-' }}</div>
            <div class="info-item"><span class="info-label">数据集：</span>{{ task.datasetName || task.datasetId || '-' }}</div>
            <div class="info-item"><span class="info-label">数据集版本：</span>{{ task.datasetVersion || '-' }}</div>
            <div class="info-item"><span class="info-label">验证数据集：</span>{{ task.valDatasetId || '-' }}</div>
            <div class="info-item"><span class="info-label">SFT模型：</span>{{ task.sftModelId || '-' }}</div>
            <div class="info-item"><span class="info-label">教师模型：</span>{{ task.teacherModelId || '-' }}</div>
            <div class="info-item"><span class="info-label">校准数据集：</span>{{ task.calibDatasetId || '-' }}</div>
            <div class="info-item"><span class="info-label">资源池：</span>{{ poolName }}</div>
            <div class="info-item"><span class="info-label">GPU数量：</span>{{ gpuCount }}</div>
            <div class="info-item"><span class="info-label">内存：</span>{{ memory }} GB</div>
            <div class="info-item"><span class="info-label">创建人：</span>{{ task.createdBy || '-' }}</div>
            <div class="info-item" style="grid-column: span 2">
              <span class="info-label">描述：</span>{{ task.description || '-' }}
            </div>
          </div>
        </el-tab-pane>

        <!-- 日志 -->
        <el-tab-pane label="训练日志" name="logs">
          <div class="log-controls">
            <el-button size="small" @click="autoScroll = !autoScroll" :type="autoScroll ? 'primary' : ''">
              {{ autoScroll ? '自动滚动' : '手动模式' }}
            </el-button>
            <el-button size="small" @click="loadLogs">刷新</el-button>
            <el-tag v-if="logs.length" size="small" type="info" effect="plain">共 {{ logs.length }} 条</el-tag>
          </div>
          <div ref="logContainer" class="log-viewer">
            <div v-for="(line, i) in logs" :key="i" class="log-line">{{ line }}</div>
            <div v-if="!logs.length" class="log-empty">暂无日志</div>
          </div>
        </el-tab-pane>

        <!-- 指标 -->
        <el-tab-pane label="训练指标" name="metrics">
          <div class="metrics-chart">
            <v-chart :option="lossChartOption" style="height: 300px" autoresize />
          </div>
          <div class="metrics-chart" style="margin-top: 20px">
            <v-chart :option="lrChartOption" style="height: 250px" autoresize />
          </div>
          <div v-if="!metrics.length" class="metrics-empty">暂无可视化指标数据</div>
        </el-tab-pane>

        <!-- 产物 -->
        <el-tab-pane label="训练产物" name="outputs">
          <DataTable :data="outputs" :columns="outputColumns" :show-pagination="false">
            <template #actions="{ row }">
              <el-button v-if="row.type === 'model'" type="primary" link size="small" @click="viewModel(row)">查看模型</el-button>
              <el-button v-if="row.type === 'model' && task.outputModelId" type="primary" link size="small" @click="deployModel(row)">创建部署</el-button>
            </template>
          </DataTable>
          <div v-if="!outputs.length" class="metrics-empty">训练完成后将在此展示产出模型</div>
        </el-tab-pane>
      </el-tabs>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { ArrowLeft } from '@element-plus/icons-vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import PageHeaderCard from '@/components/common/PageHeaderCard.vue'
import DataTable, { type ColumnConfig } from '@/components/common/DataTable.vue'
import { TaskStatusMap, TaskStatusColorMap } from '@/types'
import {
  getTaskDetail,
  getTaskLogs,
  getTaskMetrics,
  submitTask,
  pauseTask,
  resumeTask,
  cancelTask,
  stopTrainTask,
  retryTask,
} from '@/api/training'
import { fetchResourcePoolList } from '@/api/ops'
import type { ResourcePool } from '@/types'

use([LineChart, GridComponent, TooltipComponent, LegendComponent, CanvasRenderer])

const route = useRoute()
const router = useRouter()
const taskId = route.params.id as string

const activeTab = ref('info')
const autoScroll = ref(true)
const acting = ref(false)
const logContainer = ref<HTMLElement>()
let pollTimer: ReturnType<typeof setInterval> | null = null

const task = reactive({
  id: taskId,
  name: '',
  taskType: '',
  taskSubType: '',
  subType: '',
  baseModelName: '',
  baseModelVersion: '',
  datasetId: '',
  datasetName: '',
  datasetVersion: '',
  framework: '',
  valDatasetId: '',
  sftModelId: '',
  teacherModelId: '',
  calibDatasetId: '',
  status: 'pending' as string,
  progress: 0 as number | null,
  description: '',
  resourceConfig: {} as Record<string, unknown>,
  startedAt: '',
  finishedAt: '',
  errorMessage: '',
  engineCommand: '',
  outputModelId: '',
  outputModelName: '',
  createdBy: '',
})

const logs = ref<string[]>([])
const metrics = ref<{ step: number; loss: number | null; lr: number | null }[]>([])
// WebSocket 实时日志（方案8）：可用时用 WS 增量推送，否则回退 HTTP 轮询
let ws: WebSocket | null = null
let wsLastSeq = 0
let wsHealthy = false

const poolOptions = ref<ResourcePool[]>([])
async function loadResourcePools() {
  try {
    const res = await fetchResourcePoolList({ pageIndex: 1, pageSize: 100 })
    poolOptions.value = res.list || []
  } catch { /* 资源池加载失败不阻塞 */ }
}

const poolName = computed(() => {
  const id = String(task.resourceConfig?.poolId ?? '')
  if (!id) return '-'
  return poolOptions.value.find((p) => p.id === id)?.name || id
})
const gpuCount = computed(() => {
  const v = task.resourceConfig?.gpuCount ?? task.resourceConfig?.gpu
  return v ? String(v) : '-'
})
const memory = computed(() => {
  const v = task.resourceConfig?.memory
  return v ? String(v) : '-'
})

const outputs = computed(() => {
  const list: { name: string; type: string; path: string }[] = []
  if (task.outputModelName) {
    list.push({ name: task.outputModelName, type: 'model', path: task.outputModelId || task.id })
  }
  return list
})

const outputColumns: ColumnConfig[] = [
  { prop: 'name', label: '名称', minWidth: 200 },
  { prop: 'type', label: '类型', width: 120 },
  { prop: 'path', label: '产出ID', minWidth: 200 },
]

const lossChartOption = computed(() => ({
  title: { text: 'Loss 曲线' },
  tooltip: { trigger: 'axis' },
  grid: { left: 60, right: 30, top: 50, bottom: 40 },
  xAxis: { type: 'category', data: metrics.value.map((m) => String(m.step)) },
  yAxis: { type: 'value', name: 'Loss' },
  series: [{
    data: metrics.value.map((m) => m.loss),
    type: 'line', smooth: true, showSymbol: false, color: '#e63946',
    areaStyle: { opacity: 0.1 },
  }],
}))

const lrChartOption = computed(() => ({
  title: { text: 'Learning Rate' },
  tooltip: { trigger: 'axis' },
  grid: { left: 60, right: 30, top: 50, bottom: 40 },
  xAxis: { type: 'category', data: metrics.value.map((m) => String(m.step)) },
  yAxis: { type: 'value', name: 'LR' },
  series: [{
    data: metrics.value.map((m) => m.lr),
    type: 'line', smooth: true, showSymbol: false, color: '#409eff',
    areaStyle: { opacity: 0.1 },
  }],
}))

function goBack() { router.back() }

async function loadDetail() {
  try {
    const data = await getTaskDetail(taskId)
    Object.assign(task, {
      id: data.id,
      name: data.name || '',
      taskType: data.taskType || '',
      taskSubType: data.taskSubType || '',
      subType: data.subType || '',
      baseModelName: data.baseModelName || '',
      baseModelVersion: data.baseModelVersion || '',
      datasetId: data.datasetId || '',
      datasetName: data.datasetName || '',
      datasetVersion: data.datasetVersion || '',
      framework: data.framework || '',
      valDatasetId: data.valDatasetId || '',
      sftModelId: data.sftModelId || '',
      teacherModelId: data.teacherModelId || '',
      calibDatasetId: data.calibDatasetId || '',
      status: data.status || 'pending',
      progress: data.progress ?? 0,
      description: data.description || '',
      resourceConfig: data.resourceConfig || {},
      startedAt: data.startedAt || '',
      finishedAt: data.finishedAt || '',
      errorMessage: data.errorMessage || '',
      engineCommand: data.engineCommand || '',
      outputModelId: data.outputModelId || '',
      outputModelName: data.outputModelName || '',
      createdBy: data.createdBy || '',
    })
  } catch (e) {
    ElMessage.error('加载任务详情失败')
  }
}

async function loadLogs() {
  try {
    const data = await getTaskLogs(taskId, 300)
    const arr = data || []
    logs.value = arr.map((l) => `${l.time} [${l.level}] ${l.message}`)
    if (arr.length) wsLastSeq = Math.max(wsLastSeq, ...arr.map((l: any) => l.seq ?? 0))
    scrollToBottom()
  } catch (e) {
    /* 日志加载失败不阻塞 UI */
  }
}

function scrollToBottom() {
  if (!autoScroll.value) return
  nextTick().then(() => {
    const el = logContainer.value
    if (el) el.scrollTop = el.scrollHeight
  })
}

function connectLogWS() {
  const proto = window.location.protocol === 'https:' ? 'wss://' : 'ws://'
  const url = `${proto}${window.location.host}/api/ws/train/${taskId}`
  try {
    ws = new WebSocket(url)
  } catch (e) {
    return
  }
  ws.onopen = () => { wsHealthy = true }
  ws.onmessage = (ev) => {
    try {
      const m = JSON.parse(ev.data)
      if (m.seq > wsLastSeq) {
        logs.value.push(`${m.time || ''} [${m.level || 'INFO'}] ${m.message || ''}`)
        wsLastSeq = m.seq
        scrollToBottom()
      }
    } catch (e) { /* 忽略非法消息 */ }
  }
  ws.onclose = () => { wsHealthy = false }
  ws.onerror = () => { wsHealthy = false }
}

function disconnectLogWS() {
  if (ws) {
    try { ws.close() } catch (e) { /* ignore */ }
    ws = null
    wsHealthy = false
  }
}

async function loadMetrics() {
  try {
    const data = await getTaskMetrics(taskId)
    metrics.value = (data || []).map((m: any) => ({
      step: m.step ?? 0,
      loss: m.loss ?? null,
      lr: m.lr ?? null,
    }))
  } catch (e) {
    /* 指标加载失败不阻塞 UI */
  }
}

function startPolling() {
  stopPolling()
  pollTimer = setInterval(() => {
    if (!wsHealthy) loadLogs()
    loadMetrics()
    loadDetail()
  }, 3000)
}

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

async function runAction(action: () => Promise<unknown>, successMsg: string) {
  acting.value = true
  try {
    await action()
    ElMessage.success(successMsg)
    await loadDetail()
    startPolling()
  } catch (e) {
    ElMessage.error((e as Error)?.message || '操作失败')
  } finally {
    acting.value = false
  }
}

function handleSubmit() {
  runAction(() => submitTask(taskId), '任务已提交，开始执行')
}
function handlePause() {
  runAction(() => pauseTask(taskId), '暂停指令已下发')
}
function handleResume() {
  runAction(() => resumeTask(taskId), '恢复指令已下发')
}
function handleCancel() {
  runAction(() => cancelTask(taskId), '取消指令已下发')
}
function handleStop() {
  runAction(() => stopTrainTask(taskId), '停止指令已下发')
}
function handleRetry() {
  runAction(() => retryTask(taskId), '任务已重新提交')
}

function viewModel(row: any) {
  const modelId = row.path || task.outputModelId
  if (modelId) {
    router.push(`/model/detail/${modelId}`)
  } else {
    ElMessage.warning('产出模型尚未入库')
  }
}

function deployModel(_row: any) {
  if (!task.outputModelId) {
    ElMessage.warning('产出模型尚未入库')
    return
  }
  router.push({
    path: '/service/deployment/create',
    query: { modelId: task.outputModelId, modelName: task.outputModelName || '产出模型' },
  })
}

watch(activeTab, (tab) => {
  if (tab === 'logs') loadLogs()
  if (tab === 'metrics') loadMetrics()
})

onMounted(async () => {
  await loadResourcePools()
  await loadDetail()
  await loadLogs()
  await loadMetrics()
  connectLogWS()
  if (['running', 'paused', 'pending'].includes(task.status)) {
    startPolling()
  }
})

onUnmounted(() => {
  stopPolling()
  disconnectLogWS()
})
</script>

<style lang="scss" scoped>
.back-row {
  margin-bottom: 16px;
}
.detail-status-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px;
  .status-info { display: flex; align-items: center; gap: 12px; }
  .label { color: $text-secondary; }
  .detail-time { font-size: $font-size-mini; color: $text-secondary; }
}

.error-message {
  margin-top: 12px;
  padding: 8px 12px;
  background: #fef0f0;
  color: #f56c6c;
  border-radius: 6px;
  font-size: $font-size-mini;
}

.engine-command {
  margin-top: 12px;
  font-size: $font-size-mini;
  color: $text-secondary;
  code {
    background: #f5f5f5;
    padding: 4px 8px;
    border-radius: 4px;
    word-break: break-all;
  }
}

.info-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  .info-item { font-size: $font-size-base; color: $text-regular;
    .info-label { color: $text-secondary; }
  }
}

.log-controls {
  margin-bottom: 12px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.log-viewer {
  background: #1e1e1e;
  color: #d4d4d4;
  font-family: 'Consolas', 'Courier New', monospace;
  font-size: 13px;
  line-height: 1.6;
  padding: 16px;
  border-radius: 8px;
  height: 400px;
  overflow-y: auto;
  .log-empty { color: #666; }
}

.metrics-chart {
  padding: 16px;
  background: $bg-color-light;
  border-radius: $border-radius-large;
}

.metrics-empty {
  padding: 24px;
  text-align: center;
  color: $text-secondary;
}
</style>
