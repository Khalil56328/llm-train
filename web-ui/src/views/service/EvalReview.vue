<template>
  <div class="eval-review">
    <PageHeaderCard :title="`人工评测 - ${evalDetail?.name || ''}`" desc="对模型回答进行人工评分">
      <template #actions>
        <el-button @click="router.back()">返回</el-button>
      </template>
    </PageHeaderCard>

    <div class="progress-section">
      <span>评测进度</span>
      <el-progress :percentage="evalDetail?.progress || 0" :stroke-width="12" style="width: 400px" />
      <span>{{ evalDetail?.progress || 0 }}%</span>
    </div>

    <div class="filter-tabs">
      <el-radio-group v-model="filterEvaluated" @change="fetchItems">
        <el-radio-button :value="undefined">全部</el-radio-button>
        <el-radio-button :value="false">未评估</el-radio-button>
        <el-radio-button :value="true">已评估</el-radio-button>
      </el-radio-group>
    </div>

    <el-table :data="evalItems" size="small" border v-loading="itemsLoading">
      <el-table-column prop="prompt" label="Prompt" min-width="200" show-overflow-tooltip />
      <el-table-column prop="referenceResponse" label="Reference Response" min-width="200" show-overflow-tooltip />
      <el-table-column prop="modelResponse" label="模型回答" min-width="200" show-overflow-tooltip />
      <el-table-column label="评估效果" width="280" align="center">
        <template #default="{ row }">
          <div v-if="row.isEvaluated" class="scored">
            <el-tag type="success" size="small">{{ row.score }}分</el-tag>
          </div>
          <div v-else class="score-buttons">
            <el-button v-for="s in scoreRange" :key="s" :class="['score-btn', { active: row._tempScore === s }]"
              size="small" @click="row._tempScore = s">
              {{ s }}
            </el-button>
            <el-button type="primary" size="small" @click="submitScore(row)" :disabled="row._tempScore == null">确认</el-button>
          </div>
        </template>
      </el-table-column>
    </el-table>

    <div class="pagination-wrap">
      <el-pagination background layout="total, prev, pager, next" :total="itemsTotal"
        v-model:current-page="itemsPageIndex" v-model:page-size="itemsPageSize"
        @current-change="fetchItems" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import PageHeaderCard from '@/components/common/PageHeaderCard.vue'
import {
  getEvaluationDetail,
  getEvalItems,
  scoreEvalItem,
} from '@/api/service'
import type { EvalItem } from '@/types'

const router = useRouter()
const route = useRoute()
const evalDetail = ref<any>(null)
const evalItems = ref<any[]>([])
const itemsLoading = ref(false)
const itemsTotal = ref(0)
const itemsPageIndex = ref(1)
const itemsPageSize = ref(20)
const filterEvaluated = ref<boolean | undefined>(undefined)

const scoreRange = computed(() => {
  const scale = evalDetail.value?.ratingScale || 5
  return Array.from({ length: scale }, (_, i) => i + 1)
})

async function fetchDetail() {
  try {
    const res = await getEvaluationDetail(route.params.id as string)
    evalDetail.value = res
  } catch { evalDetail.value = null }
}

async function fetchItems() {
  itemsLoading.value = true
  try {
    const params: Record<string, unknown> = {
      pageIndex: itemsPageIndex.value,
      pageSize: itemsPageSize.value,
    }
    if (filterEvaluated.value !== undefined) {
      params.isEvaluated = filterEvaluated.value
    }
    const res = await getEvalItems(route.params.id as string, params)
    evalItems.value = (res.list || []).map((item: any) => ({ ...item, _tempScore: null }))
    itemsTotal.value = res.total || 0
  } catch {
    evalItems.value = []
    itemsTotal.value = 0
  } finally {
    itemsLoading.value = false
  }
}

async function submitScore(row: any) {
  if (row._tempScore == null) return
  try {
    await scoreEvalItem(route.params.id as string, row.id, { score: row._tempScore })
    ElMessage.success('评分成功')
    row.isEvaluated = true
    row.score = row._tempScore
    row._tempScore = null
    // 刷新进度
    fetchDetail()
  } catch (e: any) {
    ElMessage.error(e.message || '评分失败')
  }
}

onMounted(() => {
  fetchDetail()
  fetchItems()
})
</script>

<style lang="scss" scoped>
.progress-section {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 20px;
  padding: 16px 20px;
  background: $bg-color-light;
  border-radius: 8px;
  span { font-weight: 600; white-space: nowrap; }
}
.filter-tabs {
  margin-bottom: 16px;
}
.score-buttons {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-wrap: wrap;
  .score-btn {
    width: 32px;
    height: 28px;
    padding: 0;
    font-size: 12px;
    &.active {
      background: $color-primary;
      color: #fff;
      border-color: $color-primary;
    }
  }
}
.scored {
  display: flex;
  justify-content: center;
}
.pagination-wrap {
  display: flex;
  justify-content: flex-end;
  margin-top: 16px;
}
</style>
