<template>
  <div class="model-plaza">
    <PageHeaderCard title="模型库广场" desc="浏览和查找公开模型。" />

    <SearchFilter v-model:model-value="searchKeyword" :show-create="false" @search="fetchData" @reset="handleReset">
      <template #filters>
        <el-select v-model="filterType" placeholder="模型类型" clearable style="width: 180px" @change="fetchData">
          <el-option v-for="(label, key) in ModelTypeMap" :key="key" :label="label" :value="key" />
        </el-select>
        <el-select v-model="filterSpec" placeholder="规格" clearable style="width: 180px" @change="fetchData">
          <el-option v-for="(label, key) in ModelSpecMap" :key="key" :label="label" :value="key" />
        </el-select>
        <el-select v-model="filterVendor" placeholder="厂商" clearable style="width: 180px" @change="fetchData">
          <el-option label="DeepSeek" value="DeepSeek" />
          <el-option label="Qwen" value="Qwen" />
          <el-option label="BAAI/BGE" value="BAAI" />
          <el-option label="Meta" value="Meta" />
          <el-option label="智谱" value="智谱" />
          <el-option label="OpenAI" value="OpenAI" />
        </el-select>
      </template>
      <template #actions>
        <el-button type="primary" @click="fetchData">
          <el-icon><Search /></el-icon>
          <span>查询</span>
        </el-button>
        <el-button @click="handleReset">
          <el-icon><Refresh /></el-icon>
          <span>重置</span>
        </el-button>
        <el-button type="warning" :disabled="selectedModels.length < 2" @click="openCompare">
          <el-icon><DataLine /></el-icon>
          <span>对比 ({{ selectedModels.length }})</span>
        </el-button>
      </template>
    </SearchFilter>

    <div v-loading="loading" class="card-grid-wrapper">
      <CardGrid :items="cardItems" icon-bg="#409eff" @select="(id) => goDetail(id)">
        <template #actions="{ item }: { item: any }">
          <el-tooltip content="选择对比">
            <el-checkbox
              :model-value="isModelSelected(item.id)"
              size="small"
              @change="(val: string | number | boolean) => toggleSelect(item.id, !!val)"
              @click.stop
            />
          </el-tooltip>
        </template>
      </CardGrid>
      <el-empty v-if="!loading && cardItems.length === 0" description="暂无公开模型" />
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

    <!-- 模型对比弹窗 -->
    <ModelCompare v-model:visible="compareVisible" :model-ids="selectedModels" />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { Search, Refresh, DataLine } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import PageHeaderCard from '@/components/common/PageHeaderCard.vue'
import SearchFilter from '@/components/common/SearchFilter.vue'
import CardGrid from '@/components/common/CardGrid.vue'
import ModelCompare from './ModelCompare.vue'
import { getPlazaModels } from '@/api/model'
import { ModelTypeMap, ModelSpecMap } from '@/types'
import type { Model } from '@/types'

const router = useRouter()
const searchKeyword = ref('')
const filterType = ref('')
const filterSpec = ref('')
const filterVendor = ref('')
const cardItems = ref<any[]>([])
const total = ref(0)
const pageIndex = ref(1)
const pageSize = ref(12)
const loading = ref(false)
const selectedModels = ref<string[]>([])
const compareVisible = ref(false)

function modelToCardItem(m: Model) {
  const tags = typeof m.tags === 'string' ? JSON.parse(m.tags || '[]') : (m.tags || [])
  return {
    id: m.id,
    name: m.name,
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
    if (filterVendor.value) params.vendor = filterVendor.value

    const res = await getPlazaModels(params)
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
  filterVendor.value = ''
  pageIndex.value = 1
  fetchData()
}

function goDetail(id: string) {
  router.push(`/model/plaza-detail/${id}`)
}

function isModelSelected(id: string) {
  return selectedModels.value.includes(id)
}

function toggleSelect(id: string, val: boolean) {
  if (val) {
    if (selectedModels.value.length >= 4) {
      ElMessage.warning('最多选择4个模型进行对比')
      return
    }
    selectedModels.value.push(id)
  } else {
    selectedModels.value = selectedModels.value.filter(i => i !== id)
  }
}

function openCompare() {
  if (selectedModels.value.length < 2) {
    ElMessage.warning('请至少选择2个模型进行对比')
    return
  }
  compareVisible.value = true
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
