<template>
  <div class="eval-report" v-loading="loading">
    <PageHeaderCard :title="`评测报告 - ${report?.taskName || ''}`" desc="">
      <template #actions>
        <el-button @click="router.back()">返回</el-button>
      </template>
    </PageHeaderCard>

    <template v-if="report">
      <!-- 自动评测报告 -->
      <div v-if="evalType === 'auto'" class="report-content">
        <div class="score-section">
          <div class="score-card">
            <div class="score-label">综合评分</div>
            <div class="score-number">{{ report.overallScore || '-' }}</div>
          </div>
        </div>

        <h4 class="section-title">维度评分</h4>
        <el-table :data="report.dimensionScores" size="small" border>
          <el-table-column prop="dimension" label="维度" min-width="120" />
          <el-table-column prop="score" label="评分" width="100" />
        </el-table>

        <h4 class="section-title">评测场景</h4>
        <div class="scenes-tags">
          <el-tag v-for="s in (report.scenes || [])" :key="s" size="large" style="margin-right: 8px">
            {{ EvalSceneMap[s as EvalScene] || s }}
          </el-tag>
        </div>
      </div>

      <!-- 人工评测报告 -->
      <div v-if="evalType === 'manual'" class="report-content">
        <div class="score-section">
          <div class="score-card">
            <div class="score-label">综合评分</div>
            <div class="score-number">{{ report.overallScore || '-' }}</div>
          </div>
        </div>

        <h4 class="section-title">评测详情</h4>
        <el-table :data="evalItems" size="small" border>
          <el-table-column prop="prompt" label="Prompt" min-width="180" show-overflow-tooltip />
          <el-table-column prop="referenceResponse" label="Reference Response" min-width="180" show-overflow-tooltip />
          <el-table-column prop="modelResponse" label="模型回答" min-width="180" show-overflow-tooltip />
          <el-table-column prop="score" label="正确性" width="80" align="center">
            <template #default="{ row }">
              <span v-if="row.score != null">{{ row.score }}</span>
              <span v-else class="text-muted">-</span>
            </template>
          </el-table-column>
          <el-table-column prop="evaluatedBy" label="满意度" width="80" align="center">
            <template #default="{ row }">
              <span v-if="row.score != null && row.score >= 4">满意</span>
              <span v-else-if="row.score != null && row.score >= 2">一般</span>
              <span v-else-if="row.score != null">不满意</span>
              <span v-else class="text-muted">-</span>
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
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import PageHeaderCard from '@/components/common/PageHeaderCard.vue'
import {
  getEvaluationDetail,
  getEvalReport,
  getEvalItems,
} from '@/api/service'
import type { EvalScene } from '@/types'
import { EvalSceneMap } from '@/types'

const router = useRouter()
const route = useRoute()
const loading = ref(false)
const report = ref<any>(null)
const evalType = ref<'auto' | 'manual'>('auto')
const evalItems = ref<any[]>([])
const itemsTotal = ref(0)
const itemsPageIndex = ref(1)
const itemsPageSize = ref(20)

async function fetchData() {
  loading.value = true
  try {
    const evalRes = await getEvaluationDetail(route.params.id as string)
    evalType.value = evalRes.evalType || 'auto'

    const reportRes = await getEvalReport(route.params.id as string)
    report.value = reportRes

    if (evalType.value === 'manual') {
      fetchItems()
    }
  } catch {
    report.value = null
  } finally {
    loading.value = false
  }
}

async function fetchItems() {
  try {
    const res = await getEvalItems(route.params.id as string, {
      pageIndex: itemsPageIndex.value,
      pageSize: itemsPageSize.value,
    })
    evalItems.value = res.list || []
    itemsTotal.value = res.total || 0
  } catch {
    evalItems.value = []
    itemsTotal.value = 0
  }
}

onMounted(fetchData)
</script>

<style lang="scss" scoped>
.score-section {
  display: flex;
  justify-content: center;
  margin-bottom: 32px;
}
.score-card {
  text-align: center;
  padding: 32px 64px;
  background: linear-gradient(135deg, rgba($color-primary, 0.08), rgba($color-primary, 0.02));
  border-radius: 12px;
  border: 1px solid rgba($color-primary, 0.15);
  .score-label {
    font-size: 14px;
    color: $text-secondary;
    margin-bottom: 8px;
  }
  .score-number {
    font-size: 48px;
    font-weight: 700;
    color: $color-primary;
  }
}
.section-title {
  margin: 24px 0 12px;
  font-size: 15px;
  color: $text-primary;
}
.scenes-tags {
  display: flex;
  flex-wrap: wrap;
}
.text-muted {
  color: $text-secondary;
}
.pagination-wrap {
  display: flex;
  justify-content: flex-end;
  margin-top: 16px;
}
</style>
