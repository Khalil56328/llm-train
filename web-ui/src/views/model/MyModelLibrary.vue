<template>
  <div class="my-model-library">
    <PageHeaderCard title="我的模型库" desc="管理和维护个人训练产出或导入的模型，支持版本管理和文件查看。" />

    <SearchFilter v-model:model-value="searchKeyword" @search="fetchData" @reset="handleReset" @create="goCreate">
      <template #filters>
        <el-select v-model="filterType" placeholder="模型类型" clearable style="width: 180px" @change="fetchData">
          <el-option v-for="(label, key) in ModelTypeMap" :key="key" :label="label" :value="key" />
        </el-select>
        <el-select v-model="filterSpec" placeholder="规格" clearable style="width: 180px" @change="fetchData">
          <el-option v-for="(label, key) in ModelSpecMap" :key="key" :label="label" :value="key" />
        </el-select>
      </template>
    </SearchFilter>

    <div v-loading="loading" class="card-grid-wrapper">
      <CardGrid :items="cardItems" icon-bg="#e63946" @select="(id) => viewDetail(id)">
        <template #actions="{ item }: { item: any }">
          <el-dropdown trigger="click">
            <el-button type="primary" link size="small" circle @click.stop>
              <el-icon><MoreFilled /></el-icon>
            </el-button>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item @click="viewDetail(item.id)">查看详情</el-dropdown-item>
                <el-dropdown-item @click="goUpload(item.id)">上传模型</el-dropdown-item>
                <el-dropdown-item @click="handleTogglePublic(item)">
                  {{ item.isPublic ? '取消公开' : '公开' }}
                </el-dropdown-item>
                <el-dropdown-item @click="handleDelete(item.id, item.name)">删除</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </template>
      </CardGrid>
      <el-empty v-if="!loading && cardItems.length === 0" description="暂无模型" />
    </div>

    <div class="plaza-pagination" v-if="total > 0">
      <el-pagination
        v-model:current-page="pageIndex"
        :page-size="pageSize"
        :total="total"
        layout="prev, pager, next"
        @current-change="fetchData"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { MoreFilled } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import PageHeaderCard from '@/components/common/PageHeaderCard.vue'
import SearchFilter from '@/components/common/SearchFilter.vue'
import CardGrid from '@/components/common/CardGrid.vue'
import { getModelList, updateModel, deleteModel } from '@/api/model'
import { ModelTypeMap, ModelSpecMap } from '@/types'
import type { Model } from '@/types'

const router = useRouter()
const searchKeyword = ref('')
const filterType = ref('')
const filterSpec = ref('')
const cardItems = ref<any[]>([])
const total = ref(0)
const pageIndex = ref(1)
const pageSize = ref(12)
const loading = ref(false)

function modelToCardItem(m: Model) {
  const tags = typeof m.tags === 'string' ? JSON.parse(m.tags || '[]') : (m.tags || [])
  return {
    id: m.id,
    name: m.name,
    isPublic: m.isPublic,
    tags,
    description: m.description,
    ownerLabel: '规格',
    ownerValue: ModelSpecMap[m.spec as keyof typeof ModelSpecMap] || m.spec,
    footerLabel: '厂商',
    footerValue: m.vendor,
  }
}

async function fetchData() {
  loading.value = true
  try {
    const params: Record<string, unknown> = {
      pageIndex: pageIndex.value,
      pageSize: pageSize.value,
    }
    if (searchKeyword.value) params.keyword = searchKeyword.value
    if (filterType.value) params.type = filterType.value
    if (filterSpec.value) params.spec = filterSpec.value

    const res = await getModelList(params)
    cardItems.value = (res.list || []).map(modelToCardItem)
    total.value = res.total || 0
  } catch (e: any) {
    ElMessage.error(e.message || '获取模型列表失败')
  } finally {
    loading.value = false
  }
}

function handleReset() {
  searchKeyword.value = ''
  filterType.value = ''
  filterSpec.value = ''
  pageIndex.value = 1
  fetchData()
}

function goCreate() {
  router.push('/model/create')
}

function viewDetail(id: string) {
  router.push(`/model/detail/${id}`)
}

function goUpload(id: string) {
  router.push(`/model/upload/${id}`)
}

async function handleTogglePublic(item: { id: string; name: string; isPublic?: boolean }) {
  const action = item.isPublic ? '取消公开' : '公开'
  try {
    await ElMessageBox.confirm(`确定要${action}模型「${item.name}」？`, `${action}确认`, { type: 'warning' })
    await updateModel(item.id, { isPublic: !item.isPublic })
    ElMessage.success(`${action}成功`)
    fetchData()
  } catch {
    // 用户取消
  }
}

async function handleDelete(id: string, name: string) {
  try {
    await ElMessageBox.confirm(`确定删除模型「${name}」？删除后不可恢复。`, '删除确认', { type: 'warning' })
    await deleteModel(id)
    ElMessage.success('删除成功')
    fetchData()
  } catch {
    // 用户取消
  }
}

onMounted(fetchData)
</script>

<style lang="scss" scoped>
.card-grid-wrapper {
  min-height: 200px;
}
.plaza-pagination {
  display: flex;
  justify-content: center;
  margin-top: 24px;
}
</style>
