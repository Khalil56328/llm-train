<template>
  <div class="version-detail-page">
    <PageHeaderCard title="版本详情" />

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
              <el-descriptions-item label="版本名称">{{ detail.name }}</el-descriptions-item>
              <el-descriptions-item label="所属算子">{{ operatorName }}</el-descriptions-item>
              <el-descriptions-item label="资源类型">
                <el-tag :type="detail.resource_type === 'GPU' ? 'warning' : 'info'" size="small">
                  {{ detail.resource_type }}
                </el-tag>
              </el-descriptions-item>
              <el-descriptions-item label="是否公开">
                <el-tag :type="detail.is_public ? 'success' : 'info'" size="small">
                  {{ detail.is_public ? '公开' : '私有' }}
                </el-tag>
              </el-descriptions-item>
              <el-descriptions-item label="创建者">{{ detail.creator || '-' }}</el-descriptions-item>
              <el-descriptions-item label="创建时间">{{ formatDate(detail.created_at) }}</el-descriptions-item>
              <el-descriptions-item label="更新时间">{{ formatDate(detail.updated_at) }}</el-descriptions-item>
              <el-descriptions-item label="版本描述" :span="2">
                {{ detail.description || '-' }}
              </el-descriptions-item>
            </el-descriptions>
          </div>
        </div>

        <!-- 镜像配置 -->
        <div class="form-section">
          <div class="section-title">镜像配置</div>
          <div class="section-body">
            <el-descriptions :column="2" border>
              <el-descriptions-item label="基础镜像" :span="2">
                {{ detail.base_image || '-' }}
              </el-descriptions-item>
              <el-descriptions-item label="工作目录">
                {{ detail.work_dir || '-' }}
              </el-descriptions-item>
              <el-descriptions-item label="启动命令">
                {{ detail.start_cmd || '-' }}
              </el-descriptions-item>
              <el-descriptions-item label="挂载目录" :span="2">
                {{ detail.mount_dir || '-' }}
              </el-descriptions-item>
            </el-descriptions>
          </div>
        </div>

        <!-- 参数配置 -->
        <div class="form-section">
          <div class="section-title">参数配置</div>
          <div class="section-body">
            <el-descriptions :column="1" border>
              <el-descriptions-item label="启动参数">
                <pre class="json-block" v-if="startParamsRaw">{{ startParamsFormatted }}</pre>
                <span v-else>-</span>
              </el-descriptions-item>
            </el-descriptions>
          </div>
        </div>
      </template>

      <el-empty v-else-if="!loading" description="未找到该版本" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowLeft } from '@element-plus/icons-vue'
import PageHeaderCard from '@/components/common/PageHeaderCard.vue'
import { fetchOperatorVersionDetail, fetchOperatorDetail } from '@/api/operator'
import type { OperatorVersion } from '@/types'

const route = useRoute()
const router = useRouter()

const loading = ref(false)
const detail = ref<OperatorVersion | null>(null)
const operatorName = ref('')

const startParamsRaw = computed(() => detail.value?.start_params)
const startParamsFormatted = computed(() => {
  const raw = startParamsRaw.value
  if (!raw) return ''
  try {
    return JSON.stringify(raw, null, 2)
  } catch {
    return String(raw)
  }
})

async function fetchData() {
  const operatorId = route.params.operatorId as string
  const versionId = route.params.versionId as string
  if (!operatorId || !versionId) return
  loading.value = true
  try {
    const [version, operator] = await Promise.all([
      fetchOperatorVersionDetail(operatorId, versionId),
      fetchOperatorDetail(operatorId),
    ])
    detail.value = version
    operatorName.value = operator.name || ''
  } catch {
    detail.value = null
  } finally {
    loading.value = false
  }
}

function formatDate(val: string | Date | undefined | null) {
  if (!val) return '-'
  const d = new Date(val)
  if (isNaN(d.getTime())) return String(val)
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
}

function goBack() {
  router.back()
}

onMounted(fetchData)
</script>

<style scoped lang="scss">
@use '@/assets/styles/variables' as *;

.version-detail-page {
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

.json-block {
  margin: 0;
  padding: 12px;
  background: $bg-color-light;
  border-radius: 4px;
  font-size: 13px;
  line-height: 1.6;
  max-height: 400px;
  overflow: auto;
  white-space: pre-wrap;
  word-break: break-all;
}
</style>
