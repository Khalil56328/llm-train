<template>
  <div class="eval-report-page">
    <page-header-card title="评测报告" description="模型评测结果详情，支持自动评测与人工评测两种报告" />

    <el-card shadow="never" class="main-card" v-loading="loading">
      <template #header>
        <div class="card-header">
          <span class="title">{{ report.taskName || '评测任务' }}</span>
          <div>
            <el-tag :type="report.evalType === 'manual' ? 'warning' : 'primary'" effect="light" style="margin-right: 8px">
              {{ report.evalType === 'manual' ? '人工评测' : '自动评测' }}
            </el-tag>
            <el-tag v-if="report.status" :type="(EvalStatusColorMap as any)[report.status] || 'info'" effect="light">
              {{ (EvalStatusMap as any)[report.status] || report.status }}
            </el-tag>
          </div>
        </div>
      </template>

      <template v-if="!loading && isEmpty">
        <el-empty description="暂无评测报告，请等待评测任务完成后查看" />
      </template>

      <template v-else-if="!loading">
        <!-- 概览统计 -->
        <div class="score-overview">
          <div class="score-main">
            <div class="score-value">{{ formatScore(report.overallScore) }}</div>
            <div class="score-label">
              综合得分（{{ report.evalType === 'manual' ? `满分 ${report.ratingScale || 5} 分制折算百分制` : '四维加权' }}）
            </div>
          </div>
          <div class="stat-items">
            <div class="stat-item">
              <div class="stat-value">{{ report.totalSamples ?? sampleList.length }}</div>
              <div class="stat-label">评测样本</div>
            </div>
            <div v-if="report.evalType !== 'manual'" class="stat-item">
              <div class="stat-value">{{ report.passedCount ?? passedCount }}</div>
              <div class="stat-label">通过样本（≥60分）</div>
            </div>
            <div v-if="report.evalType === 'manual'" class="stat-item">
              <div class="stat-value">{{ report.reviewers?.length ?? 0 }}</div>
              <div class="stat-label">参与评审员</div>
            </div>
            <div class="stat-item">
              <div class="stat-value">{{ report.generatedAt || '-' }}</div>
              <div class="stat-label">报告生成时间</div>
            </div>
          </div>
        </div>

        <el-alert v-if="report.summary" :title="report.summary" type="info" :closable="false" show-icon style="margin: 16px 0" />

        <!-- 维度得分 -->
        <h4 class="section-title">维度得分</h4>
        <el-table :data="report.dimensionScores || []" border size="default" style="width: 100%">
          <el-table-column label="评测维度" min-width="140">
            <template #default="{ row }">
              <span>{{ row.dimensionName || (EvalSceneMap as any)[row.dimension] || row.dimension }}</span>
            </template>
          </el-table-column>
          <el-table-column label="得分" width="120" align="center">
            <template #default="{ row }">
              <span :style="{ color: scoreColor(row.score), fontWeight: 700 }">{{ formatScore(row.score) }}</span>
            </template>
          </el-table-column>
          <el-table-column v-if="report.evalType !== 'manual'" label="权重" width="100" align="center">
            <template #default="{ row }">
              {{ row.weight != null ? `${Math.round(row.weight * 100)}%` : '-' }}
            </template>
          </el-table-column>
          <el-table-column label="样本数" width="100" align="center">
            <template #default="{ row }">{{ row.sampleCount ?? '-' }}</template>
          </el-table-column>
          <el-table-column label="说明" min-width="200" show-overflow-tooltip>
            <template #default="{ row }">{{ row.desc || '-' }}</template>
          </el-table-column>
        </el-table>

        <!-- 维度雷达图 -->
        <div v-if="radarDims.length >= 3" class="radar-wrap">
          <v-chart class="radar-chart" :option="radarOption" autoresize />
        </div>

        <!-- 样本明细 -->
        <el-divider content-position="left">评测样本明细</el-divider>

        <el-table :data="pagedSamples" border size="small" style="width: 100%">
          <el-table-column type="expand">
            <template #default="{ row }">
              <div class="sample-detail">
                <div class="detail-block">
                  <div class="detail-label">问题（Prompt）</div>
                  <div class="detail-content">{{ row.prompt }}</div>
                </div>
                <div v-if="row.referenceResponse" class="detail-block">
                  <div class="detail-label">参考答案</div>
                  <div class="detail-content">{{ row.referenceResponse }}</div>
                </div>
                <div class="detail-block">
                  <div class="detail-label">模型回复</div>
                  <div class="detail-content" :class="{ 'err-text': !row.modelResponse }">
                    {{ row.modelResponse || '（推理失败，无模型回复）' }}
                  </div>
                </div>
                <div v-if="row.notes && Object.keys(row.notes).length" class="detail-block">
                  <div class="detail-label">评分说明</div>
                  <div class="detail-content">
                    <div v-for="(note, dim) in row.notes" :key="dim" class="note-line">
                      <el-tag size="small" effect="plain">{{ (EvalSceneMap as any)[dim] || dim }}</el-tag>
                      <span>{{ note }}</span>
                    </div>
                  </div>
                </div>
              </div>
            </template>
          </el-table-column>
          <el-table-column type="index" label="#" width="50" />
          <el-table-column prop="prompt" label="问题" min-width="220" show-overflow-tooltip />
          <el-table-column prop="referenceResponse" label="参考答案" min-width="180" show-overflow-tooltip>
            <template #default="{ row }">
              {{ row.referenceResponse || '—' }}
            </template>
          </el-table-column>
          <el-table-column prop="modelResponse" label="模型回复" min-width="220" show-overflow-tooltip>
            <template #default="{ row }">
              <span :class="{ 'err-text': !row.modelResponse }">{{ row.modelResponse || '推理失败' }}</span>
            </template>
          </el-table-column>

          <!-- 自动评测：四维度分 -->
          <template v-if="report.evalType !== 'manual'">
            <el-table-column v-for="dim in EVAL_DIM_KEYS" :key="dim" :label="EvalSceneMap[dim]" width="90" align="center">
              <template #default="{ row }">
                <span v-if="row.scores && row.scores[dim] != null" :style="{ color: scoreColor(row.scores[dim]!) }">
                  {{ row.scores[dim] }}
                </span>
                <span v-else class="dim-na">—</span>
              </template>
            </el-table-column>
            <el-table-column label="综合分" width="90" align="center">
              <template #default="{ row }">
                <span :style="{ color: scoreColor(row.score || 0), fontWeight: 700 }">{{ row.score ?? '-' }}</span>
              </template>
            </el-table-column>
            <el-table-column label="结果" width="80" align="center">
              <template #default="{ row }">
                <el-tag :type="row.passed ? 'success' : 'danger'" size="small" effect="light">
                  {{ row.passed ? '通过' : '未通过' }}
                </el-tag>
              </template>
            </el-table-column>
          </template>

          <!-- 人工评测：人工评分列 -->
          <template v-else>
            <el-table-column label="人工评分" width="100" align="center">
              <template #default="{ row }">
                <span :style="{ color: scoreColor(row.humanScore ?? 0), fontWeight: 700 }">
                  {{ row.score != null ? `${row.score} / ${report.ratingScale || 5}` : '未评分' }}
                </span>
              </template>
            </el-table-column>
            <el-table-column label="百分制" width="90" align="center">
              <template #default="{ row }">
                <span :style="{ color: scoreColor(row.humanScore ?? 0) }">{{ row.humanScore ?? '-' }}</span>
              </template>
            </el-table-column>
            <el-table-column label="评审人" width="110" align="center" show-overflow-tooltip>
              <template #default="{ row }">{{ row.evaluatedBy || '-' }}</template>
            </el-table-column>
          </template>
        </el-table>

        <div class="pager-wrap" v-if="sampleList.length > pageSize">
          <el-pagination background layout="prev, pager, next, total" :total="sampleList.length"
            :page-size="pageSize" v-model:current-page="currentPage" />
        </div>
      </template>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { RadarChart } from 'echarts/charts'
import { CanvasRenderer } from 'echarts/renderers'
import { getEvalReport } from '@/api/service'
import { EvalSceneMap, EvalStatusMap, EvalStatusColorMap, type EvalReport, type EvalSample } from '@/types'

use([CanvasRenderer, RadarChart])

const EVAL_DIM_KEYS = ['accuracy', 'instruction', 'fluency', 'safety'] as const

const route = useRoute()
const loading = ref(false)
const report = ref<Partial<EvalReport>>({})

const currentPage = ref(1)
const pageSize = 20

const sampleList = computed<EvalSample[]>(() => report.value.details || report.value.samples || [])
const isEmpty = computed(() => !report.value.dimensionScores?.length && !sampleList.value.length)
const passedCount = computed(() => sampleList.value.filter((s) => s.passed).length)
const pagedSamples = computed(() =>
  sampleList.value.slice((currentPage.value - 1) * pageSize, currentPage.value * pageSize)
)
const radarDims = computed(() => (report.value.dimensionScores || []).filter((d) => d.score != null))

const radarOption = computed(() => ({
  radar: {
    indicator: radarDims.value.map((d) => ({
      name: `${d.dimensionName || (EvalSceneMap as any)[d.dimension] || d.dimension} ${d.score}`,
      max: 100,
    })),
    radius: '62%',
    axisName: { color: '#909399', fontSize: 12 },
    splitArea: { areaStyle: { color: ['#fff', '#fdf2f3'] } },
    axisLine: { lineStyle: { color: '#e4e7ed' } },
  },
  series: [
    {
      type: 'radar',
      symbolSize: 5,
      data: [
        {
          value: radarDims.value.map((d) => d.score),
          name: '维度得分',
          itemStyle: { color: '#e63946' },
          areaStyle: { color: 'rgba(230, 57, 70, 0.18)' },
        },
      ],
    },
  ],
}))

const formatScore = (score?: number | null) => (score == null ? '-' : Number(score).toFixed(1))
const scoreColor = (score: number) => (score >= 80 ? '#67c23a' : score >= 60 ? '#e6a23c' : '#f56c6c')

async function loadReport() {
  const id = route.query.id as string
  if (!id) return
  loading.value = true
  try {
    const res: any = await getEvalReport(id)
    report.value = res ?? {}
  } finally {
    loading.value = false
  }
}

onMounted(loadReport)
</script>

<style scoped lang="scss">
.eval-report-page {
  padding: 16px;
}

.main-card {
  border-radius: 8px;

  .card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;

    .title {
      font-size: 15px;
      font-weight: 600;
    }
  }
}

.score-overview {
  display: flex;
  align-items: center;
  gap: 40px;
  padding: 20px;
  background: linear-gradient(135deg, rgba($color-primary, 0.06), transparent);
  border-radius: 8px;
  flex-wrap: wrap;

  .score-main {
    text-align: center;
    min-width: 140px;

    .score-value {
      font-size: 42px;
      font-weight: 700;
      color: $color-primary;
      line-height: 1.1;
    }

    .score-label {
      margin-top: 6px;
      font-size: 12px;
      color: $text-secondary;
    }
  }

  .stat-items {
    display: flex;
    gap: 40px;
    flex-wrap: wrap;

    .stat-item {
      text-align: center;

      .stat-value {
        font-size: 20px;
        font-weight: 600;
        color: $text-primary;
      }

      .stat-label {
        margin-top: 4px;
        font-size: 12px;
        color: $text-secondary;
      }
    }
  }
}

.section-title {
  margin: 20px 0 12px;
  font-size: 14px;
  font-weight: 600;
}

.radar-wrap {
  display: flex;
  justify-content: center;
  margin-top: 16px;

  .radar-chart {
    width: 380px;
    height: 300px;
  }
}

.dim-na {
  color: #c0c4cc;
}

.err-text {
  color: $color-danger;
}

.pager-wrap {
  display: flex;
  justify-content: flex-end;
  margin-top: 12px;
}

.sample-detail {
  padding: 8px 16px;

  .detail-block {
    margin-bottom: 12px;

    .detail-label {
      font-size: 12px;
      font-weight: 600;
      color: $text-secondary;
      margin-bottom: 4px;
    }

    .detail-content {
      font-size: 13px;
      line-height: 1.7;
      white-space: pre-wrap;
      word-break: break-all;
    }
  }

  .note-line {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 4px;
    font-size: 12px;
    color: $text-secondary;
  }
}
</style>
