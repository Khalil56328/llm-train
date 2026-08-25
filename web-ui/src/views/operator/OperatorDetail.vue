<template>
  <div class="operator-detail-page">
    <PageHeaderCard title="算子详情" />

    <div class="detail-card" v-loading="loading">
      <template v-if="detail">
        <!-- 基础信息 -->
        <div class="form-section">
          <div class="section-header">
            <div class="section-title">基础信息</div>
            <el-button type="primary" link @click="goBack">
              <el-icon><ArrowLeft /></el-icon> 返回
            </el-button>
          </div>
          <div class="section-body">
            <el-descriptions :column="2" border>
              <el-descriptions-item label="算子名称">{{ detail.name }}</el-descriptions-item>
              <el-descriptions-item label="算子类型">{{ detail.category }}</el-descriptions-item>
              <el-descriptions-item label="训练框架">{{ detail.training_framework || '-' }}</el-descriptions-item>
              <el-descriptions-item label="训练方法">{{ trainingMethodLabel(detail.training_method) }}</el-descriptions-item>
              <el-descriptions-item label="所有者">{{ detail.owner_name || detail.owner || '-' }}</el-descriptions-item>
              <el-descriptions-item label="创建时间">{{ formatDate(detail.created_at) }}</el-descriptions-item>
              <el-descriptions-item label="描述" :span="2">
                {{ detail.description || '-' }}
              </el-descriptions-item>
            </el-descriptions>
          </div>
        </div>

        <!-- 版本列表 -->
        <div class="form-section">
          <div class="section-title">
            版本列表
            <span class="version-count">（{{ versions.length }}）</span>
          </div>
          <div class="section-body">
            <el-table :data="versions" border stripe>
              <el-table-column prop="name" label="版本名称" min-width="160" />
              <el-table-column prop="resource_type" label="资源类型" width="100" align="center">
                <template #default="{ row }">
                  <el-tag :type="row.resource_type === 'GPU' ? 'warning' : 'info'" size="small">
                    {{ row.resource_type }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="base_image" label="基础镜像" min-width="200" show-overflow-tooltip />
              <el-table-column prop="work_dir" label="工作目录" min-width="140" show-overflow-tooltip />
              <el-table-column v-if="!isFromPlaza" prop="is_public" label="是否公开" width="100" align="center">
                <template #default="{ row }">
                  <el-tag :type="row.is_public ? 'success' : 'info'" size="small">
                    {{ row.is_public ? '公开' : '私有' }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column label="创建时间" width="170" align="center">
                <template #default="{ row }">
                  {{ formatDate(row.created_at) }}
                </template>
              </el-table-column>
              <el-table-column label="操作" width="120" align="left">
                <template #default="{ row }">
                  <el-button type="primary" link size="small" @click="goVersionDetail(row as OperatorVersion)">详情</el-button>
                </template>
              </el-table-column>
            </el-table>
          </div>
        </div>
      </template>

      <el-empty v-else-if="!loading" description="未找到该算子" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowLeft } from '@element-plus/icons-vue'
import PageHeaderCard from '@/components/common/PageHeaderCard.vue'
import { fetchOperatorDetail } from '@/api/operator'
import type { OperatorWithVersions, OperatorVersion } from '@/types'
import { TrainingMethodMap } from '@/types'

const route = useRoute()
const router = useRouter()

const loading = ref(false)
const detail = ref<OperatorWithVersions | null>(null)

const isFromPlaza = computed(() => route.query.from === 'plaza')

const versions = computed<OperatorVersion[]>(() => {
  const allVersions = detail.value?.versions ?? []
  if (isFromPlaza.value) {
    return allVersions.filter(v => v.is_public)
  }
  return allVersions
})

function trainingMethodLabel(val: string | undefined) {
  return (TrainingMethodMap as Record<string, string>)[val || ''] || val || '-'
}

function goBack() {
  router.back()
}

async function fetchData() {
  const id = route.params.id as string
  if (!id) return
  loading.value = true
  try {
    detail.value = await fetchOperatorDetail(id)
  } catch {
    detail.value = null
  } finally {
    loading.value = false
  }
}

function goVersionDetail(v: OperatorVersion) {
  const query: Record<string, string> = {}
  if (isFromPlaza.value) {
    query.from = 'plaza'
  }
  router.push({
    name: 'OperatorVersionDetail',
    params: { operatorId: v.operator_id, versionId: v.id },
    query,
  })
}

function formatDate(val: string | Date | undefined | null) {
  if (!val) return '-'
  const d = new Date(val)
  if (isNaN(d.getTime())) return String(val)
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
}

onMounted(fetchData)
</script>

<style scoped lang="scss">
@use '@/assets/styles/variables' as *;

.operator-detail-page {
  padding: 0;
}

.detail-card {
  background: #fff;
  border-radius: 8px;
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

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
  padding-bottom: 8px;
  border-bottom: 1px solid $border-color-light;
}

.section-title {
  font-size: 15px;
  font-weight: 600;
  color: $text-primary;
}

.version-count {
  font-weight: 400;
  font-size: 13px;
  color: $text-secondary;
  margin-left: 4px;
}
</style>
