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
              <el-dropdown-item @click="goEdit(row)">修改</el-dropdown-item>
              <el-dropdown-item @click="deleteDeployment(row)">删除</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </template>
    </DataTable>

    <!-- 在线测试弹窗 -->
    <el-dialog v-model="testVisible" title="在线测试" width="700px" class="custom-modal">
      <div class="test-area">
        <el-input v-model="testPrompt" type="textarea" :rows="6" placeholder="请输入测试 Prompt..." />
        <div class="test-response" v-if="testResponse">
          <div class="test-response-header">模型响应</div>
          <div class="test-response-body">{{ testResponse }}</div>
        </div>
      </div>
      <template #footer>
        <el-button @click="testVisible = false">关闭</el-button>
        <el-button type="primary" :loading="testLoading" @click="sendTest">发送</el-button>
      </template>
    </el-dialog>

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
          <el-button @click="onlineTest(detailData)">在线测试</el-button>
        </div>
      </template>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
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
  testDeployment,
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
const testPrompt = ref('')
const testResponse = ref('')
const testLoading = ref(false)
const currentTestRow = ref<any>(null)
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

function onlineTest(row: any) {
  currentTestRow.value = row
  testPrompt.value = ''
  testResponse.value = ''
  testVisible.value = true
}

async function sendTest() {
  if (!currentTestRow.value) return
  testLoading.value = true
  try {
    const res = await testDeployment(currentTestRow.value.id, { prompt: testPrompt.value })
    testResponse.value = res.response || '无响应'
  } catch (e: any) {
    testResponse.value = '请求失败: ' + (e.message || '未知错误')
  } finally {
    testLoading.value = false
  }
}

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

.test-area {
  .test-response {
    margin-top: 16px;
    .test-response-header { font-weight: 600; color: $text-primary; margin-bottom: 8px; }
    .test-response-body { background: $bg-color-light; padding: 12px 16px; border-radius: 8px; line-height: 1.6; white-space: pre-wrap; }
  }
}

.drawer-actions {
  margin-top: 24px;
  display: flex;
  gap: 10px;
}
</style>
