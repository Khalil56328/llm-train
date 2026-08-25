<template>
  <div class="deployment-detail" v-loading="loading">
    <PageHeaderCard :title="detail?.name || '部署详情'" desc="">
      <template #actions>
        <el-button @click="router.back()">返回</el-button>
        <el-button type="primary" v-if="detail?.status !== 'running'" @click="toggleService('start')">启动服务</el-button>
        <el-button type="danger" v-if="detail?.status === 'running'" @click="toggleService('stop')">停止服务</el-button>
      </template>
    </PageHeaderCard>

    <template v-if="detail">
      <div class="detail-card">
        <!-- 基本信息 -->
        <div class="form-section">
          <div class="section-title">基本信息</div>
          <div class="section-body">
            <el-descriptions :column="2" border size="small">
              <el-descriptions-item label="服务名称">{{ detail.name }}</el-descriptions-item>
              <el-descriptions-item label="状态">
                <el-tag :type="DeployStatusColorMap[detail.status as DeployStatus] || 'info'" size="small">
                  {{ DeployStatusMap[detail.status as DeployStatus] || detail.status }}
                </el-tag>
              </el-descriptions-item>
              <el-descriptions-item label="服务描述" :span="2">{{ detail.description || '-' }}</el-descriptions-item>
            </el-descriptions>
          </div>
        </div>

        <!-- 推理配置 -->
        <div class="form-section">
          <div class="section-title">推理配置</div>
          <div class="section-body">
            <el-descriptions :column="2" border size="small">
              <el-descriptions-item label="基础模型">{{ detail.modelName || '-' }}</el-descriptions-item>
              <el-descriptions-item label="推理框架">{{ detail.inferenceFramework }}</el-descriptions-item>
              <el-descriptions-item label="算子">{{ detail.operatorId || '-' }}</el-descriptions-item>
              <el-descriptions-item label="实例数">{{ detail.instances || 1 }}</el-descriptions-item>
              <el-descriptions-item label="参数配置" :span="2">
                <pre class="json-pre">{{ JSON.stringify(detail.params || {}, null, 2) }}</pre>
              </el-descriptions-item>
              <el-descriptions-item label="环境变量" :span="2">
                <pre class="json-pre">{{ JSON.stringify(detail.envVars || {}, null, 2) }}</pre>
              </el-descriptions-item>
            </el-descriptions>
          </div>
        </div>

        <!-- 访问地址 -->
        <div class="form-section">
          <div class="section-title">访问地址</div>
          <div class="section-body">
            <el-descriptions :column="1" border size="small">
              <el-descriptions-item label="服务端点">
                <span v-if="detail.endpoint">{{ detail.endpoint }}</span>
                <span v-else class="text-muted">服务未运行，暂无访问地址</span>
              </el-descriptions-item>
              <el-descriptions-item label="容器端口">{{ detail.containerPort || 8000 }}</el-descriptions-item>
              <el-descriptions-item label="访问端口">{{ detail.accessPort || '-' }}</el-descriptions-item>
            </el-descriptions>
            <div class="test-section" v-if="detail.status === 'running'">
              <h4>在线测试（多轮对话）</h4>
              <div class="chat-box">
                <div v-if="!chatMessages.length" class="chat-empty">开始一段对话吧（流式输出）</div>
                <div v-for="(msg, i) in chatMessages" :key="i" class="chat-msg" :class="msg.role">
                  <div class="chat-role">{{ msg.role === 'user' ? '我' : '模型' }}</div>
                  <div class="chat-content">{{ msg.content }}</div>
                </div>
              </div>
              <div class="chat-input-row">
                <el-input
                  v-model="testPrompt"
                  type="textarea"
                  :rows="3"
                  placeholder="请输入消息，Enter 发送，Shift+Enter 换行"
                  @keydown.enter.exact.prevent="sendTest"
                  :disabled="testLoading"
                />
                <div class="chat-actions">
                  <el-button :disabled="!testPrompt && !testLoading" :loading="testLoading" type="primary" @click="sendTest">发送</el-button>
                  <el-button v-if="chatMessages.length" @click="clearChat">清空</el-button>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- 实例 -->
        <div class="form-section">
          <div class="section-title">实例列表</div>
          <div class="section-body">
            <el-table :data="instances" size="small" border>
              <el-table-column prop="podName" label="POD名称" min-width="200" />
              <el-table-column prop="status" label="状态" width="100">
                <template #default="{ row }">
                  <el-tag :type="row.status === 'running' ? 'success' : row.status === 'pending' ? 'warning' : 'danger'" size="small">
                    {{ row.status === 'running' ? '运行中' : row.status === 'pending' ? '等待中' : '异常' }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="hostIp" label="主机IP" width="160" />
              <el-table-column prop="podIp" label="PodIP" width="160" />
              <el-table-column prop="createdAt" label="创建时间" width="170" />
            </el-table>
          </div>
        </div>

        <!-- 日志 -->
        <div class="form-section">
          <div class="section-title">日志</div>
          <div class="section-body">
            <div class="deploy-log-header">
              <el-button size="small" @click="loadLogs">刷新</el-button>
              <el-tag v-if="deployLogs.length" size="small" type="info" effect="plain">共 {{ deployLogs.length }} 条</el-tag>
            </div>
            <div ref="deployLogBox" class="deploy-log-viewer">
              <div v-for="(line, i) in deployLogs" :key="i" class="deploy-log-line">{{ line }}</div>
              <div v-if="!deployLogs.length" class="log-placeholder">
                <el-empty description="暂无日志信息" />
              </div>
            </div>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, nextTick } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import PageHeaderCard from '@/components/common/PageHeaderCard.vue'
import {
  getDeploymentDetail,
  startDeployment,
  stopDeployment,
  getDeployInstances,
  getDeploymentLogs,
  chatCompletionsStream,
} from '@/api/service'
import type { Deployment, DeployStatus, DeployInstance } from '@/types'
import { DeployStatusMap, DeployStatusColorMap } from '@/types'

const router = useRouter()
const route = useRoute()
const loading = ref(false)
const detail = ref<Deployment | null>(null)
const instances = ref<DeployInstance[]>([])
const testPrompt = ref('')
const testLoading = ref(false)
const chatMessages = ref<{ role: string; content: string }[]>([])
const chatAbort = ref<AbortController | null>(null)
const deployLogs = ref<string[]>([])
const deployLogBox = ref<HTMLElement>()

async function fetchData() {
  loading.value = true
  try {
    const res = await getDeploymentDetail(route.params.id as string)
    detail.value = res
  } catch {
    detail.value = null
  } finally {
    loading.value = false
  }
}

async function fetchInstances() {
  try {
    const res = await getDeployInstances(route.params.id as string)
    instances.value = res || []
  } catch { instances.value = [] }
}

async function toggleService(action: 'start' | 'stop') {
  try {
    if (action === 'start') {
      await startDeployment(route.params.id as string)
      ElMessage.success('服务已启动')
    } else {
      await stopDeployment(route.params.id as string)
      ElMessage.success('服务已停止')
    }
    fetchData()
    loadLogs()
  } catch (e: any) {
    ElMessage.error(e.message || '操作失败')
  }
}

onUnmounted(() => {
  chatAbort.value?.abort()
})

async function sendTest() {
  if (!detail.value) return
  const text = testPrompt.value.trim()
  if (!text || testLoading.value) return
  chatMessages.value.push({ role: 'user', content: text })
  chatMessages.value.push({ role: 'assistant', content: '' })
  testPrompt.value = ''
  testLoading.value = true
  chatAbort.value = new AbortController()
  const assistantIdx = chatMessages.value.length - 1
  const history = chatMessages.value.slice(0, -1).map((m) => ({ role: m.role, content: m.content }))
  try {
    await chatCompletionsStream(
      detail.value.id,
      history,
      (delta) => {
        chatMessages.value[assistantIdx].content += delta
      },
      chatAbort.value.signal,
    )
  } catch (e: any) {
    if (e?.name !== 'AbortError') {
      chatMessages.value[assistantIdx].content = '（请求失败: ' + (e?.message || '未知错误') + '）'
    }
  } finally {
    testLoading.value = false
  }
}

function clearChat() {
  chatMessages.value = []
  testPrompt.value = ''
}

async function loadLogs() {
  try {
    const data = await getDeploymentLogs(route.params.id as string, 300)
    deployLogs.value = data || []
    await nextTick()
    const el = deployLogBox.value
    if (el) el.scrollTop = el.scrollHeight
  } catch (e) {
    deployLogs.value = []
  }
}

onMounted(() => {
  fetchData()
  fetchInstances()
  loadLogs()
})
</script>

<style lang="scss" scoped>
.detail-card {
  background: $bg-color-white;
  border-radius: $border-radius-large;
  padding: 24px;
  margin-top: 16px;
  min-height: 300px;
}

.form-section {
  margin-bottom: 32px;

  &:last-child {
    margin-bottom: 0;
  }
}

.section-title {
  font-size: 15px;
  font-weight: 600;
  color: $text-primary;
  margin-bottom: 16px;
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

.json-pre {
  font-size: 12px;
  max-height: 200px;
  overflow: auto;
  margin: 0;
  white-space: pre-wrap;
}

.text-muted {
  color: $text-secondary;
}

.test-section {
  margin-top: 24px;
  h4 { margin-bottom: 12px; }
  .chat-box {
    background: $bg-color-light;
    border-radius: 8px;
    padding: 16px;
    max-height: 360px;
    overflow-y: auto;
    margin-bottom: 12px;
    .chat-empty { color: $text-secondary; text-align: center; padding: 20px 0; }
    .chat-msg {
      margin-bottom: 12px;
      display: flex;
      gap: 8px;
      &.user { flex-direction: row-reverse; }
      .chat-role {
        flex-shrink: 0;
        width: 40px;
        height: 28px;
        line-height: 28px;
        text-align: center;
        border-radius: 6px;
        font-size: 12px;
        color: #fff;
        background: $color-primary;
      }
      &.assistant .chat-role { background: $text-secondary; }
      .chat-content {
        background: #fff;
        padding: 8px 12px;
        border-radius: 8px;
        line-height: 1.6;
        white-space: pre-wrap;
        word-break: break-word;
        max-width: 75%;
        font-size: $font-size-base;
      }
    }
  }
  .chat-input-row {
    display: flex;
    flex-direction: column;
    gap: 10px;
    .chat-actions { display: flex; gap: 8px; }
  }
}

.deploy-log-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
}
.deploy-log-viewer {
  background: #1e1e1e;
  color: #d4d4d4;
  font-family: 'Consolas', 'Courier New', monospace;
  font-size: 13px;
  line-height: 1.6;
  padding: 16px;
  border-radius: 8px;
  height: 300px;
  overflow-y: auto;
  .deploy-log-line { white-space: pre-wrap; word-break: break-all; }
}

.log-placeholder {
  padding: 40px 0;
}
</style>
