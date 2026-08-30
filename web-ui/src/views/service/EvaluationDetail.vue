<template>
  <div class="evaluation-detail" v-loading="loading">
    <PageHeaderCard :title="detail?.name || '评测详情'" desc="">
      <template #actions>
        <el-button @click="router.back()">返回</el-button>
        <el-button v-if="detail?.status === 'pending'" type="primary" @click="startEval">启动评测</el-button>
        <el-button v-if="detail?.evalType === 'manual' && detail?.status === 'running'" type="primary" @click="goReview">开始评测</el-button>
      </template>
    </PageHeaderCard>

    <template v-if="detail">
      <div class="detail-card">
        <!-- 基本信息 -->
        <div class="form-section">
          <div class="section-title">基本信息</div>
          <div class="section-body">
            <el-descriptions :column="2" border size="small">
              <el-descriptions-item label="任务名称">{{ detail.name }}</el-descriptions-item>
              <el-descriptions-item label="状态">
                <el-tag :type="EvalStatusColorMap[detail.status as EvalStatus] || 'info'" size="small">
                  {{ EvalStatusMap[detail.status as EvalStatus] || detail.status }}
                </el-tag>
              </el-descriptions-item>
              <el-descriptions-item label="描述" :span="2">{{ detail.description || '-' }}</el-descriptions-item>
              <el-descriptions-item label="评测类型">{{ detail.evalType === 'auto' ? '自动评测' : '人工评测' }}</el-descriptions-item>
              <el-descriptions-item label="是否基准评测" v-if="detail.evalType === 'auto'">{{ detail.isBaseline ? '是' : '否' }}</el-descriptions-item>
            </el-descriptions>
          </div>
        </div>

        <!-- 评估对象配置 -->
        <div class="form-section">
          <div class="section-title">评估对象配置</div>
          <div class="section-body">
            <el-descriptions :column="2" border size="small">
              <el-descriptions-item label="数据集">{{ detail.datasetName || '-' }}</el-descriptions-item>
              <el-descriptions-item label="数据集版本">{{ detail.datasetVersion || '-' }}</el-descriptions-item>
              <el-descriptions-item label="模型服务">{{ detail.deploymentName || '-' }}</el-descriptions-item>
            </el-descriptions>
          </div>
        </div>

        <!-- 评估方法配置 -->
        <div class="form-section">
          <div class="section-title">评估方法配置</div>
          <div class="section-body">
            <el-descriptions :column="2" border size="small">
              <el-descriptions-item label="评测方式">{{ detail.evalType === 'auto' ? '自动评测' : '人工评测' }}</el-descriptions-item>
              <el-descriptions-item label="评估场景">
                <template v-if="detail.evalType === 'auto'">
                  <el-tag v-for="s in (detail.scenes || [])" :key="s" size="small" style="margin-right: 4px">
                    {{ EvalSceneMap[s as EvalScene] || s }}
                  </el-tag>
                </template>
                <template v-else>
                  <el-tag v-for="s in (detail.scenes || [])" :key="s" size="small" style="margin-right: 4px">
                    {{ ManualEvalSceneMap[s as ManualEvalScene] || s }}
                  </el-tag>
                </template>
              </el-descriptions-item>
              <el-descriptions-item label="评估指标" :span="2">
                <el-table v-if="detail.metrics && detail.metrics.length > 0" :data="detail.metrics" size="small" border>
                  <el-table-column type="index" label="序列" width="60" />
                  <el-table-column prop="name" label="评估指标" min-width="120" />
                  <el-table-column prop="description" label="指标说明" min-width="160" />
                </el-table>
                <span v-else class="text-muted">-</span>
              </el-descriptions-item>
              <el-descriptions-item v-if="detail.evalType === 'manual'" label="评分量级">{{ detail.ratingScale || 5 }}分</el-descriptions-item>
            </el-descriptions>
          </div>
        </div>

        <!-- 评估报告（自动评测） -->
        <div class="form-section" v-if="detail.evalType === 'auto'">
          <div class="section-title">评估报告</div>
          <div class="section-body">
            <div v-if="detail.status === 'completed' && report">
              <el-descriptions :column="1" border size="small">
                <el-descriptions-item label="综合评分">
                  <span class="score-value">{{ report.overallScore }}</span>
                </el-descriptions-item>
              </el-descriptions>
              <h4 class="sub-title">维度评分</h4>
              <el-table :data="report.dimensionScores" size="small" border>
                <el-table-column label="维度" min-width="120">
                  <template #default="{ row }">
                    {{ row.dimensionName || row.dimension }}
                  </template>
                </el-table-column>
                <el-table-column prop="score" label="评分" width="100" />
              </el-table>
            </div>
            <el-empty v-else description="评测尚未完成，暂无报告" />
          </div>
        </div>

        <!-- 评估详情（人工评测） -->
        <div class="form-section" v-if="detail.evalType === 'manual'">
          <div class="section-title">评估详情</div>
          <div class="section-body">
            <div class="progress-bar">
              <span>评测进度</span>
              <el-progress :percentage="detail.progress || 0" :stroke-width="10" style="width: 300px" />
            </div>
            <el-table :data="evalItems" size="small" border v-loading="itemsLoading">
              <el-table-column prop="prompt" label="Prompt" min-width="200" show-overflow-tooltip />
              <el-table-column prop="referenceResponse" label="Reference Response" min-width="200" show-overflow-tooltip />
              <el-table-column prop="modelResponse" label="Response" min-width="200" show-overflow-tooltip />
              <el-table-column prop="isEvaluated" label="评估效果" width="100" align="center">
                <template #default="{ row }">
                  <el-tag :type="row.isEvaluated ? 'success' : 'info'" size="small">
                    {{ row.isEvaluated ? `${row.score}分` : '未评估' }}
                  </el-tag>
                </template>
              </el-table-column>
            </el-table>
            <div class="pagination-wrap">
              <el-pagination background layout="total, prev, pager, next" :total="itemsTotal"
                v-model:current-page="itemsPageIndex" v-model:page-size="itemsPageSize"
                @current-change="fetchItems" />
            </div>
          </div>
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
  startEvaluation,
  getEvalReport,
  getEvalItems,
} from '@/api/service'
import type { EvalStatus, EvalScene, ManualEvalScene, EvalItem } from '@/types'
import { EvalStatusMap, EvalStatusColorMap, EvalSceneMap, ManualEvalSceneMap } from '@/types'

const router = useRouter()
const route = useRoute()
const loading = ref(false)
const detail = ref<any>(null)
const report = ref<any>(null)
const evalItems = ref<EvalItem[]>([])
const itemsLoading = ref(false)
const itemsTotal = ref(0)
const itemsPageIndex = ref(1)
const itemsPageSize = ref(20)

async function fetchData() {
  loading.value = true
  try {
    const res = await getEvaluationDetail(route.params.id as string)
    detail.value = res
    if (res.evalType === 'auto' && res.status === 'completed') {
      fetchReport()
    }
    if (res.evalType === 'manual') {
      fetchItems()
    }
  } catch {
    detail.value = null
  } finally {
    loading.value = false
  }
}

async function fetchReport() {
  try {
    const res = await getEvalReport(route.params.id as string)
    report.value = res
  } catch { report.value = null }
}

async function fetchItems() {
  itemsLoading.value = true
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
  } finally {
    itemsLoading.value = false
  }
}

async function startEval() {
  try {
    await startEvaluation(route.params.id as string)
    ElMessage.success('评测已启动')
    fetchData()
  } catch (e: any) {
    ElMessage.error(e.message || '启动失败')
  }
}

function goReview() {
  router.push(`/service/evaluation/review/${route.params.id}`)
}

onMounted(fetchData)
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

.text-muted {
  color: $text-secondary;
}

.sub-title {
  font-size: 14px;
  font-weight: 600;
  color: $text-primary;
  margin: 20px 0 12px;
}

.score-value {
  font-size: 24px;
  font-weight: 700;
  color: $color-primary;
}

.progress-bar {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 16px;
  span { font-weight: 600; white-space: nowrap; }
}

.pagination-wrap {
  display: flex;
  justify-content: flex-end;
  margin-top: 16px;
}
</style>
