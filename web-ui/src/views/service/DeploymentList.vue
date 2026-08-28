<template>
  <div class="deployment-list">
    <PageHeaderCard title="模型部署" desc="部署模型推理服务，支持 vLLM、MindIE 及自定义镜像，部署后可通过 Endpoint 访问。" />
    <!-- 搜索筛选 -->
    <SearchFilter
      v-model:model-value="searchKeyword"
      placeholder="搜索服务名称"
      @search="fetchData"
      @reset="handleReset"
      @create="goCreate"
    >
      <template #filters>
        <el-select v-model="filterStatus" placeholder="状态" clearable style="width: 140px" @change="fetchData">
          <el-option v-for="(label, key) in DeployStatusMap" :key="key" :label="label" :value="key" />
        </el-select>
      </template>
    </SearchFilter>
    <!-- 表格 -->
    <DataTable
      :data="tableData"
      :columns="columns"
      :loading="loading"
      :total="total"
      :action-width="200"
      row-key="id"
      v-model:page="pageIndex"
      v-model:page-size="pageSize"
      @page-change="fetchData"
      @size-change="fetchData"
      @expand-change="handleExpandChange"
    >
      <!-- 展开行：POD 实例列表 -->
      <template #expand="{ row }">
        <div class="expand-pod">
          <el-table :data="row._instances || []" size="small" border>
            <el-table-column prop="podName" label="POD名称" min-width="200" />
            <el-table-column prop="status" label="状态" width="100">
              <template #default="{ row: pod }">
                <el-tag :type="pod.status === 'running' ? 'success' : pod.status === 'pending' ? 'warning' : 'danger'" size="small">
                  {{ pod.status === 'running' ? '运行中' : pod.status === 'pending' ? '等待中' : '异常' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="hostIp" label="主机IP" width="160" />
            <el-table-column prop="podIp" label="PodIP" width="160" />
<!--            <el-table-column label="操作" width="100" fixed="right">-->
<!--              <template #default="{ row: pod }">-->
<!--                <el-button type="primary" link size="small" @click="enterContainer(pod)">进入容器</el-button>-->
<!--              </template>-->
<!--            </el-table-column>-->
          </el-table>
        </div>
      </template>

      <!-- 模型名称(版本) -->
      <template #modelSlot="{ row }">
        {{ row.modelName || '-' }} <span v-if="row.modelVersion" class="text-muted">{{ row.modelVersion }}</span>
      </template>

      <!-- 操作 -->
      <template #actions="{ row }">
        <el-button type="primary" link size="small" @click="goDetail(row)">详情</el-button>
        <el-dropdown trigger="click">
          <el-button type="primary" link size="small">更多 <el-icon><ArrowDown /></el-icon></el-button>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item v-if="row.status !== 'running'" @click="toggleService(row)">部署</el-dropdown-item>
              <el-dropdown-item v-if="row.status === 'running'" @click="toggleService(row)">停止</el-dropdown-item>
              <el-dropdown-item @click="openTestDrawer(row)">测试</el-dropdown-item>
              <el-dropdown-item @click="goEdit(row)">修改</el-dropdown-item>
              <el-dropdown-item @click="deleteDeployment(row)">删除</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </template>
    </DataTable>

    <!-- 在线测试抽屉（右侧弹出，多轮对话） -->
    <el-drawer
      v-model="testVisible"
      direction="rtl"
      size="33%"
      class="chat-test-drawer"
      :close-on-click-modal="false"
      @close="handleTestDrawerClose"
    >
      <template #header>
        <div class="test-drawer-title">
          <span class="test-drawer-name">在线测试</span>
          <span v-if="testRow" class="test-drawer-service">
            {{ testRow.name }}
            <el-tag
              :type="DeployStatusColorMap[testRow.status as DeployStatus] || 'info'"
              size="small"
            >
              {{ DeployStatusMap[testRow.status as DeployStatus] || testRow.status }}
            </el-tag>
          </span>
        </div>
      </template>
      <div v-if="testRow" class="test-drawer-body">
        <template v-if="testRow.status === 'running'">
          <div ref="chatBox" class="chat-box">
            <div v-if="!chatMessages.length" class="chat-empty">
              开始与模型对话吧（流式输出，Enter 发送，Shift + Enter 换行）
            </div>
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
              resize="none"
              :disabled="testLoading"
              placeholder="请输入消息，Enter 发送，Shift + Enter 换行"
              @keydown.enter.exact.prevent="sendTest"
            />
            <div class="chat-actions">
              <el-button type="primary" :loading="testLoading" :disabled="!testPrompt.trim()" @click="sendTest">
                发送
              </el-button>
              <el-button v-if="chatMessages.length" @click="clearChat">清空</el-button>
            </div>
          </div>
        </template>
        <div v-else class="test-not-running">
          <el-empty description="服务未运行，无法进行在线测试，请先启动服务" />
        </div>
      </div>
    </el-drawer>

    <!-- 详情抽屉 -->
    <el-drawer v-model="detailVisible" title="部署详情" size="550px" direction="rtl">
      <template v-if="detailData">
        <el-descriptions :column="1" border size="small">
          <el-descriptions-item label="服务名称">{{ detailData.name }}</el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag :type="DeployStatusColorMap[detailData.status as DeployStatus] || 'info'" size="small">
              {{ DeployStatusMap[detailData.status as DeployStatus] || detailData.status }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="服务描述">{{ detailData.description || '-' }}</el-descriptions-item>
          <el-descriptions-item label="基础模型">{{ detailData.modelName || '-' }}</el-descriptions-item>
          <el-descriptions-item label="推理框架">{{ detailData.inferenceFramework }}</el-descriptions-item>
          <el-descriptions-item label="实例数">{{ detailData.instances || 1 }}</el-descriptions-item>
          <el-descriptions-item label="访问地址">{{ detailData.endpoint || '-' }}</el-descriptions-item>
          <el-descriptions-item label="创建时间">{{ detailData.createdAt }}</el-descriptions-item>
        </el-descriptions>
        <div class="drawer-actions">
          <el-button type="primary" v-if="detailData.status !== 'running'" @click="toggleService(detailData)">启动服务</el-button>
          <el-button type="danger" v-if="detailData.status === 'running'" @click="toggleService(detailData)">停止服务</el-button>
          <el-button type="primary" v-if="detailData.status === 'running'" @click="openTestDrawer(detailData)">在线测试</el-button>
        </div>
      </template>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, nextTick, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ArrowDown } from '@element-plus/icons-vue'
import PageHeaderCard from '@/components/common/PageHeaderCard.vue'
import SearchFilter from '@/components/common/SearchFilter.vue'
import DataTable, { type ColumnConfig } from '@/components/common/DataTable.vue'
import {
  getDeploymentList,
  startDeployment,
  stopDeployment,
  deleteDeployment as deleteDeploymentApi,
  getDeployInstances,
  chatCompletionsStream,
} from '@/api/service'
import type { Deployment, DeployStatus, DeployInstance } from '@/types'
import { DeployStatusMap, DeployStatusColorMap } from '@/types'

const router = useRouter()
const searchKeyword = ref('')
const filterStatus = ref('')
const loading = ref(false)
const tableData = ref<any[]>([])
const total = ref(0)
const pageIndex = ref(1)
const pageSize = ref(20)
const testVisible = ref(false)
const testRow = ref<any>(null)
const testPrompt = ref('')
const testLoading = ref(false)
const chatMessages = ref<{ role: string; content: string }[]>([])
const chatAbort = ref<AbortController | null>(null)
const chatBox = ref<HTMLElement | null>(null)
const detailVisible = ref(false)
const detailData = ref<Deployment | null>(null)

const columns: ColumnConfig[] = [
  { prop: 'name', label: '服务名称', minWidth: 180 },
  { prop: 'status', label: '状态', width: 100, type: 'status' as const, statusMap: DeployStatusMap, statusColorMap: DeployStatusColorMap },
  { prop: 'modelName', label: '模型名称(版本)', minWidth: 200, slot: 'modelSlot' },
  { prop: 'instances', label: '实例数', width: 80, align: 'center' },
  { prop: 'createdAt', label: '创建时间', width: 170, type: 'datetime' as const },
  { prop: 'createdBy', label: '所属用户', width: 100 },
]

async function fetchData() {
  loading.value = true
  try {
    const params: Record<string, unknown> = {
      pageIndex: pageIndex.value,
      pageSize: pageSize.value,
    }
    if (searchKeyword.value) params.keyword = searchKeyword.value
    if (filterStatus.value) params.status = filterStatus.value
    const res = await getDeploymentList(params)
    tableData.value = (res.list || []).map((d: any) => ({ ...d, _instances: [] }))
    total.value = res.total || 0
  } catch {
    tableData.value = []
    total.value = 0
  } finally {
    loading.value = false
  }
}

function enterContainer(pod: any) {
  // 容器终端需要 k8s/web-terminal 基础设施支持，当前为占位提示（方案9）
  ElMessage.info(`实例「${pod?.podName || ''}」容器终端需连接 k8s 环境，请在详情页查看实例信息。`)
}

async function loadInstances(row: any) {
  if (!row || !row.id) return
  try {
    const res = await getDeployInstances(row.id)
    row._instances = res || []
  } catch {
    row._instances = []
  }
}

async function handleExpandChange(payload: { row: Record<string, unknown>; expanded: Record<string, unknown>[] }) {
  // 展开时懒加载 POD 实例列表（只在首次展开时请求）
  const expandedRows = payload.expanded || []
  expandedRows.forEach((r) => {
    const row = tableData.value.find((d) => d.id === r.id)
    if (row && (!row._instances || row._instances.length === 0)) {
      loadInstances(row)
    }
  })
}

function handleReset() {
  searchKeyword.value = ''
  filterStatus.value = ''
  fetchData()
}

function goCreate() { router.push('/service/deployment/create') }
function goDetail(row: any) { router.push(`/service/deployment/detail/${row.id}`) }
function goEdit(row: any) { router.push(`/service/deployment/create?id=${row.id}`) }

function openTestDrawer(row: any) {
  // 切换到不同服务时重置会话
  if (!testRow.value || testRow.value.id !== row.id) {
    chatAbort.value?.abort()
    chatMessages.value = []
    testPrompt.value = ''
    testLoading.value = false
    testRow.value = row
  }
  detailVisible.value = false
  testVisible.value = true
}

function handleTestDrawerClose() {
  chatAbort.value?.abort()
  testLoading.value = false
}

function clearChat() {
  chatMessages.value = []
  testPrompt.value = ''
}

async function sendTest() {
  const prompt = testPrompt.value.trim()
  if (!prompt || testLoading.value || !testRow.value) return
  if (testRow.value.status !== 'running') {
    ElMessage.warning('服务未运行，无法进行在线测试')
    return
  }
  testLoading.value = true
  testPrompt.value = ''
  chatMessages.value.push({ role: 'user', content: prompt })
  const assistantIdx = chatMessages.value.push({ role: 'assistant', content: '' }) - 1
  const history = chatMessages.value.slice(0, -1).map((m) => ({ role: m.role, content: m.content }))
  chatAbort.value = new AbortController()
  try {
    await chatCompletionsStream(
      testRow.value.id,
      history,
      (delta) => {
        chatMessages.value[assistantIdx].content += delta
      },
      chatAbort.value.signal,
    )
  } catch (e: any) {
    chatMessages.value[assistantIdx].content += `\n[请求失败: ${e.message || '未知错误'}]`
  } finally {
    testLoading.value = false
    chatAbort.value = null
  }
}

// 对话内容变化时自动滚动到底部
watch(
  () => chatMessages.value[chatMessages.value.length - 1]?.content,
  async () => {
    await nextTick()
    const el = chatBox.value
    if (el) el.scrollTop = el.scrollHeight
  },
)

onUnmounted(() => {
  chatAbort.value?.abort()
})

async function toggleService(row: any) {
  try {
    if (row.status === 'running') {
      await stopDeployment(row.id)
      ElMessage.success('服务已停止')
    } else {
      await startDeployment(row.id)
      ElMessage.success('服务已启动')
    }
    fetchData()
  } catch (e: any) {
    ElMessage.error(e.message || '操作失败')
  }
}

function deleteDeployment(row: any) {
  ElMessageBox.confirm('确定删除该部署服务？', '提示', { type: 'warning' }).then(async () => {
    try {
      await deleteDeploymentApi(row.id)
      ElMessage.success('删除成功')
      fetchData()
    } catch (e: any) {
      ElMessage.error(e.message || '删除失败')
    }
  })
}

onMounted(fetchData)
</script>

<style lang="scss" scoped>
.deployment-list {
  display: flex;
  flex-direction: column;
}

.text-muted {
  color: $text-secondary;
  font-size: 12px;
  margin-left: 4px;
}

.expand-pod {
  padding: 12px 20px;
  .expand-title {
    font-weight: 600;
    color: $text-primary;
    margin-bottom: 10px;
    font-size: 14px;
  }
}

.drawer-actions {
  margin-top: 24px;
  display: flex;
  gap: 10px;
}

// ===== 在线测试抽屉 =====
.test-drawer-title {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;

  .test-drawer-name {
    font-size: 16px;
    font-weight: 600;
    color: $text-primary;
  }

  .test-drawer-service {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    font-size: 13px;
    color: $text-secondary;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
}

.test-drawer-body {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;

  .test-not-running {
    flex: 1;
    display: flex;
    align-items: center;
    justify-content: center;
  }
}

.chat-box {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  background: $bg-color-light;
  border-radius: $border-radius-large;
  padding: 16px 14px;

  .chat-empty {
    text-align: center;
    color: $text-placeholder;
    font-size: 13px;
    padding: 32px 0;
  }

  .chat-msg {
    display: flex;
    flex-direction: column;
    margin-bottom: 14px;

    .chat-role {
      font-size: 12px;
      color: $text-secondary;
      margin-bottom: 4px;
    }

    .chat-content {
      max-width: 86%;
      padding: 10px 12px;
      border-radius: $border-radius-large;
      font-size: 14px;
      line-height: 1.6;
      white-space: pre-wrap;
      word-break: break-word;
    }

    &.user {
      align-items: flex-end;

      .chat-content {
        background: $color-primary;
        color: #fff;
        border-top-right-radius: $border-radius-small;
      }
    }

    &.assistant {
      align-items: flex-start;

      .chat-content {
        background: $bg-color-white;
        color: $text-primary;
        border: 1px solid $border-color-lighter;
        border-top-left-radius: $border-radius-small;
      }
    }
  }
}

.chat-input-row {
  padding-top: 12px;

  .chat-actions {
    display: flex;
    justify-content: flex-end;
    gap: 0;
    margin-top: 10px;
  }
}
</style>

<style lang="scss">
// 让测试抽屉与列表内容区等高（从 header 下沿开始），宽度由 size=33% 控制
.chat-test-drawer {
  .el-drawer {
    top: $header-height;
    height: calc(100% - $header-height) !important;
  }

  .el-drawer__body {
    display: flex;
    flex-direction: column;
    padding: 0 16px 16px;
    overflow: hidden;
  }
}
</style>
