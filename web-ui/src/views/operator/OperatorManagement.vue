<template>
  <div class="operator-management">
    <PageHeaderCard
      title="算子管理"
      desc="预置覆盖模型训练与推理全链路的标准化算子库，支持动态算子组合与适配优化，实现训练推理任务的高效加速与资源利用率提升"
    />

    <!-- 搜索筛选 -->
    <SearchFilter
      v-model:model-value="searchKeyword"
      placeholder="请输入算子名称"
      @search="fetchData"
      @reset="handleReset"
      @create="openCreateDialog"
    >
      <template #filters>
        <el-select
          v-model="filterCategory"
          placeholder="算子类型"
          clearable
          style="width: 180px"
          @change="fetchData"
        >
          <el-option label="全部" value="" />
          <el-option label="预训练" value="预训练" />
          <el-option label="大模型微调" value="大模型微调" />
          <el-option label="模型蒸馏" value="模型蒸馏" />
          <el-option label="模型推理" value="模型推理" />
          <el-option label="模型合并" value="模型合并" />
          <el-option label="结果存储" value="结果存储" />
          <el-option label="数据集导入" value="数据集导入" />
        </el-select>
      </template>
    </SearchFilter>

    <!-- 表格 -->
    <DataTable
      :data="tableData"
      :columns="columns"
      :loading="loading"
      :total="total"
      :action-width="140"
      v-model:page="pageIndex"
      v-model:page-size="pageSize"
      @page-change="fetchData"
      @size-change="fetchData"
      @expand-change="handleExpand"
    >
      <!-- 展开行：版本列表 -->
      <template #expand="{ row: rawRow }">
        <div class="version-panel" v-if="isOperator(rawRow)">
          <el-table
            :data="versionMap[rawRow.id] || []"
            :border="false"
            :show-header="true"
            size="small"
            class="version-table"
            v-loading="versionLoadingMap[rawRow.id]"
          >
            <el-table-column
              prop="name"
              label="版本名称"
              min-width="100"
              align="left"
            />
            <el-table-column
              prop="image_address"
              label="镜像地址"
              min-width="280"
              align="left"
              show-overflow-tooltip
            >
              <template #default="{ row: v }">
                <el-tooltip
                  :content="v.image_address || '-'"
                  placement="top"
                  :show-after="300"
                >
                  <span class="image-text">{{ v.image_address || '-' }}</span>
                </el-tooltip>
              </template>
            </el-table-column>
            <el-table-column
              prop="description"
              label="描述"
              min-width="120"
              align="left"
            >
              <template #default="{ row: v }">
                {{ v.description || '-' }}
              </template>
            </el-table-column>
            <el-table-column label="是否公开" width="100" align="center">
              <template #default="{ row: v }">
                <el-switch
                  v-model="v.is_public"
                  :active-color="primaryColor"
                  @change="(val: any) => handleTogglePublic(v as OperatorVersion, val as boolean)"
                />
              </template>
            </el-table-column>
            <el-table-column
              prop="created_at"
              label="创建时间"
              width="180"
              align="left"
            >
              <template #default="{ row: v }">
                {{ formatDate(v.created_at) }}
              </template>
            </el-table-column>
            <el-table-column
              prop="updated_at"
              label="更新时间"
              width="180"
              align="left"
            >
              <template #default="{ row: v }">
                {{ formatDate(v.updated_at) }}
              </template>
            </el-table-column>
            <el-table-column label="操作" width="100" align="left" class-name="action-column">
              <template #default="{ row: v }">
                <el-button type="primary" link size="small" @click="goVersionDetail(rawRow as Operator, v as OperatorVersion)">详情</el-button>
                <el-dropdown trigger="click" @command="(cmd: any) => handleVersionAction(cmd as string, rawRow as Operator, v as OperatorVersion)">
                  <el-button type="primary" link size="small">
                    更多 <el-icon><ArrowDown /></el-icon>
                  </el-button>
                  <template #dropdown>
                    <el-dropdown-menu>
                      <el-dropdown-item command="edit">修改</el-dropdown-item>
                      <el-dropdown-item command="delete">删除</el-dropdown-item>
                    </el-dropdown-menu>
                  </template>
                </el-dropdown>
              </template>
            </el-table-column>
            <template #empty>
              <div class="version-empty">暂无版本</div>
            </template>
          </el-table>
        </div>
      </template>

      <!-- 算子操作 -->
      <template #actions="{ row: rawRow }">
        <el-button type="primary" link size="small" @click="goDetail(rawRow as Operator)">详情</el-button>
        <el-dropdown trigger="click" @command="(cmd: any) => handleAction(cmd as string, rawRow as Operator)">
          <el-button type="primary" link size="small">
            更多 <el-icon><ArrowDown /></el-icon>
          </el-button>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="edit">修改</el-dropdown-item>
              <el-dropdown-item command="addVersion">新增版本</el-dropdown-item>
              <el-dropdown-item command="delete">删除</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </template>
    </DataTable>

    <!-- 新增算子弹窗 -->
    <el-dialog
      v-model="showCreateDialog"
      title="新增算子"
      width="560px"
      :close-on-click-modal="false"
      destroy-on-close
    >
      <el-form
        ref="createFormRef"
        :model="createForm"
        :rules="createRules"
        label-position="top"
      >
        <el-form-item label="算子类型" prop="category">
          <el-select
            v-model="createForm.category"
            placeholder="请选择算子类型"
            style="width: 100%"
          >
            <el-option label="预训练" value="预训练" />
            <el-option label="大模型微调" value="大模型微调" />
            <el-option label="模型蒸馏" value="模型蒸馏" />
            <el-option label="模型推理" value="模型推理" />
            <el-option label="模型合并" value="模型合并" />
            <el-option label="结果存储" value="结果存储" />
            <el-option label="数据集导入" value="数据集导入" />
          </el-select>
        </el-form-item>
        <el-form-item label="训练框架" prop="training_framework">
          <el-select
            v-model="createForm.training_framework"
            placeholder="请选择训练框架"
            style="width: 100%"
          >
            <el-option label="ms-swift" value="ms-swift" />
          </el-select>
        </el-form-item>
        <el-form-item label="训练方法" prop="training_method">
          <el-select
            v-model="createForm.training_method"
            placeholder="请选择训练方法"
            style="width: 100%"
          >
            <el-option label="全量更新" value="full" />
            <el-option label="冻结微调" value="freeze" />
            <el-option label="LoRA微调" value="lora" />
          </el-select>
        </el-form-item>
        <el-form-item label="算子名称" prop="name">
          <el-input
            v-model="createForm.name"
            placeholder="请输入算子名称"
            maxlength="50"
            show-word-limit
          />
        </el-form-item>
        <el-form-item label="描述" prop="description">
          <el-input
            v-model="createForm.description"
            type="textarea"
            :rows="4"
            placeholder="请输入算子描述"
            maxlength="200"
            show-word-limit
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreateDialog = false">取消</el-button>
        <el-button type="primary" :loading="creating" @click="handleCreateOperator">
          确定
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import { ArrowDown } from '@element-plus/icons-vue'
import PageHeaderCard from '@/components/common/PageHeaderCard.vue'
import SearchFilter from '@/components/common/SearchFilter.vue'
import DataTable, { type ColumnConfig } from '@/components/common/DataTable.vue'
import {
  fetchOperatorList,
  fetchOperatorVersions,
  updateOperatorVersion,
  deleteOperator,
  deleteOperatorVersion,
  createOperator,
} from '@/api/operator'
import type { Operator, OperatorVersion } from '@/types'

const router = useRouter()
const primaryColor = '#d43030'

function isOperator(row: any): row is Operator {
  return typeof row.id === 'string'
}

const searchKeyword = ref('')
const filterCategory = ref('')
const loading = ref(false)
const tableData = ref<Operator[]>([])
const total = ref(0)
const pageIndex = ref(1)
const pageSize = ref(20)

const versionMap = reactive<Record<string, OperatorVersion[]>>({})
const versionLoadingMap = reactive<Record<string, boolean>>({})

const columns: ColumnConfig[] = [
  { prop: 'name', label: '算子名称', minWidth: 160 },
  { prop: 'category', label: '算子类型', width: 140 },
  { prop: 'version_count', label: '版本数', width: 100, align: 'center' },
  {
    prop: 'description',
    label: '描述',
    minWidth: 140,
    showOverflowTooltip: true,
  },
  {
    prop: 'owner',
    label: '归属用户',
    width: 120,
    type: 'formatter',
    formatter: (value: unknown, row: Record<string, unknown>) =>
      (row.owner_name as string) || (value as string) || '-',
  },
  {
    prop: 'created_at',
    label: '创建时间',
    width: 180,
    type: 'datetime' as const,
  },
  {
    prop: 'updated_at',
    label: '更新时间',
    width: 180,
    type: 'datetime' as const,
  },
]

function formatDate(val: string | Date | undefined | null) {
  if (!val) return '-'
  const d = new Date(val)
  if (isNaN(d.getTime())) return String(val)
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
}

async function fetchData() {
  loading.value = true
  try {
    const res = await fetchOperatorList({
      pageIndex: pageIndex.value,
      pageSize: pageSize.value,
      keyword: searchKeyword.value || undefined,
      category: filterCategory.value || undefined,
    })
    tableData.value = (res.list as Operator[]).map((o) => ({
      ...o,
      version_count: o.version_count ?? 0,
    }))
    total.value = res.total
  } catch (e) {
    // 静默失败
    tableData.value = []
    total.value = 0
  } finally {
    loading.value = false
  }
}

async function loadVersions(operatorId: string) {
  if (versionMap[operatorId]) return
  versionLoadingMap[operatorId] = true
  try {
    const list = await fetchOperatorVersions(operatorId)
    versionMap[operatorId] = list
  } catch {
    versionMap[operatorId] = []
  } finally {
    versionLoadingMap[operatorId] = false
  }
}

function handleExpand(payload: { row: Record<string, unknown>; expanded: Record<string, unknown>[] }) {
  // 只在展开时请求一次
  const expandedRows = payload.expanded || []
  expandedRows.forEach((row) => {
    if (row && row.id && !versionMap[row.id as string]) {
      loadVersions(row.id as string)
    }
  })
}

function handleReset() {
  searchKeyword.value = ''
  filterCategory.value = ''
  fetchData()
}

// ============ 新增算子弹窗 ============
const showCreateDialog = ref(false)
const creating = ref(false)
const createFormRef = ref<FormInstance>()
const createForm = reactive({
  name: '',
  category: '',
  training_framework: '',
  training_method: '',
  description: '',
})
const createRules: FormRules = {
  name: [
    { required: true, message: '请输入算子名称', trigger: 'blur' },
    { max: 50, message: '最多 50 个字符', trigger: 'blur' },
  ],
  category: [{ required: true, message: '请选择算子类型', trigger: 'change' }],
  training_framework: [{ required: true, message: '请选择训练框架', trigger: 'change' }],
  training_method: [{ required: true, message: '请选择训练方法', trigger: 'change' }],
  description: [{ max: 200, message: '最多 200 个字符', trigger: 'blur' }],
}

function openCreateDialog() {
  createForm.name = ''
  createForm.category = ''
  createForm.training_framework = ''
  createForm.training_method = ''
  createForm.description = ''
  showCreateDialog.value = true
}

async function handleCreateOperator() {
  if (!createFormRef.value) return
  try {
    await createFormRef.value.validate()
  } catch {
    return
  }
  creating.value = true
  try {
    await createOperator({
      name: createForm.name,
      category: createForm.category,
      training_framework: createForm.training_framework,
      training_method: createForm.training_method,
      description: createForm.description,
      type: 'training',
      isPublic: false,
    })
    ElMessage.success('算子创建成功')
    showCreateDialog.value = false
    fetchData()
  } catch (e: any) {
    ElMessage.error(e?.message || '创建失败')
  } finally {
    creating.value = false
  }
}

// ============ 版本跳转 ============
function goCreateVersion(operatorId?: string) {
  router.push({
    name: 'OperatorVersionCreate',
    query: { operatorId: operatorId || '' },
  })
}

function goDetail(row: Operator) {
  router.push({
    name: 'OperatorDetail',
    params: { id: row.id },
  })
}

function handleAction(cmd: string, row: Operator) {
  if (cmd === 'delete') {
    ElMessageBox.confirm(`确定删除算子"${row.name}"吗？该操作会同时删除其下所有版本。`, '提示', {
      type: 'warning',
    })
      .then(async () => {
        try {
          await deleteOperator(row.id)
          ElMessage.success('删除成功')
          fetchData()
        } catch {
          // 忽略
        }
      })
      .catch(() => {})
  } else if (cmd === 'edit') {
    router.push({
      name: 'OperatorEdit',
      params: { id: row.id },
    })
  } else if (cmd === 'addVersion') {
    goCreateVersion(row.id)
  }
}

async function handleTogglePublic(v: OperatorVersion, val: boolean) {
  try {
    await updateOperatorVersion(v.operator_id, v.id, { is_public: val })
    ElMessage.success(val ? '已公开' : '已取消公开')
  } catch {
    v.is_public = !val
  }
}

function handleVersionAction(cmd: string, op: Operator, v: OperatorVersion) {
  if (cmd === 'delete') {
    ElMessageBox.confirm(`确定删除版本"${v.name}"吗？`, '提示', { type: 'warning' })
      .then(async () => {
        try {
          await deleteOperatorVersion(op.id, v.id)
          ElMessage.success('删除成功')
          versionMap[op.id] = (versionMap[op.id] || []).filter((x) => x.id !== v.id)
          op.version_count = versionMap[op.id].length
        } catch {
          // 忽略
        }
      })
      .catch(() => {})
  } else if (cmd === 'edit') {
    router.push({
      name: 'OperatorVersionEdit',
      params: { operatorId: op.id, versionId: v.id },
    })
  }
}

function goVersionDetail(op: Operator, v: OperatorVersion) {
  router.push({
    name: 'OperatorVersionDetail',
    params: { operatorId: op.id, versionId: v.id },
  })
}

onMounted(fetchData)
</script>

<style lang="scss" scoped>
.operator-management {
  display: flex;
  flex-direction: column;
}

.version-panel {
  padding: 0 16px 8px 16px;
  background: #fafbfc;
}

.version-table {
  background: transparent;

  :deep(.el-table__cell) {
    padding: 6px 0;
  }

  :deep(.el-table__header-wrapper th) {
    background-color: #f0f2f5;
  }
}

.version-empty {
  padding: 12px 0;
  text-align: center;
  color: #909399;
  font-size: 13px;
}

.image-text {
  display: inline-block;
  max-width: 100%;
  vertical-align: middle;
}
</style>
