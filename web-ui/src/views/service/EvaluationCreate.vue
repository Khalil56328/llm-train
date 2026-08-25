<template>
  <div class="evaluation-create">
    <PageHeaderCard :title="evalType === 'auto' ? '新增自动评测' : '新增人工评测'" desc="配置评测任务的参数" />

    <div class="content-card">
      <el-form ref="formRef" :model="form" :rules="rules" label-position="top" class="evaluation-form">
        <!-- 基础信息 -->
        <div class="form-section">
          <div class="section-title">基础信息</div>
          <div class="section-body">
            <el-form-item label="评测名称" prop="name">
              <el-input v-model="form.name" placeholder="请输入评测名称" maxlength="200" />
            </el-form-item>
            <el-form-item label="描述" prop="description" class="no-asterisk">
              <el-input v-model="form.description" type="textarea" :rows="3" placeholder="请输入描述" maxlength="500" />
            </el-form-item>
            <el-form-item v-if="evalType === 'auto'" label="是否基准评测" label-position="left" class="no-asterisk">
              <el-switch v-model="form.isBaseline" />
            </el-form-item>
          </div>
        </div>

        <!-- 评估对象配置 -->
        <div class="form-section">
          <div class="section-title">评估对象配置</div>
          <div class="section-body">
            <el-form-item label="数据集" prop="datasetId">
              <el-select v-model="form.datasetId" placeholder="请选择数据集" filterable style="width: 100%"
                @change="onDatasetChange">
                <el-option v-for="ds in datasetList" :key="ds.id" :label="ds.name" :value="ds.id" />
              </el-select>
            </el-form-item>
            <el-form-item label="模型服务" prop="deploymentId">
              <el-select v-model="form.deploymentId" placeholder="请选择模型服务" filterable style="width: 100%"
                @change="onDeploymentChange">
                <el-option v-for="dp in deploymentList" :key="dp.id" :label="dp.name" :value="dp.id" />
              </el-select>
            </el-form-item>
          </div>
        </div>

        <!-- 评估方法配置 -->
        <div class="form-section">
          <div class="section-title">评估方法配置</div>
          <div class="section-body">
            <!-- 自动评测场景选择 -->
            <template v-if="evalType === 'auto'">
              <el-form-item label="评估场景" prop="scenes">
                <div class="scene-cards">
                  <div v-for="(label, key) in EvalSceneMap" :key="key"
                    :class="['scene-card', { active: form.scenes.includes(key as string) }]"
                    @click="toggleScene(key as string)">
                    <el-icon :size="28"><component :is="EvalSceneIconMap[key as EvalScene]" /></el-icon>
                    <span>{{ label }}</span>
                  </div>
                </div>
              </el-form-item>

              <el-form-item label="评估指标" class="no-asterisk">
                <el-table :data="form.metrics" size="small" border style="width: 100%">
                  <el-table-column type="index" label="序列" width="60" />
                  <el-table-column prop="name" label="评估指标" min-width="120">
                    <template #default="{ row }">
                      <el-input v-model="row.name" placeholder="指标名称" size="small" />
                    </template>
                  </el-table-column>
                  <el-table-column prop="description" label="指标说明" min-width="160">
                    <template #default="{ row }">
                      <el-input v-model="row.description" placeholder="指标说明" size="small" />
                    </template>
                  </el-table-column>
                  <el-table-column label="操作" width="60">
                    <template #default="{ $index }">
                      <el-button type="danger" link size="small" @click="form.metrics.splice($index, 1)">
                        <el-icon><Delete /></el-icon>
                      </el-button>
                    </template>
                  </el-table-column>
                </el-table>
                <el-button type="primary" link size="small" @click="form.metrics.push({ name: '', description: '' })" style="margin-top: 8px">
                  <el-icon><Plus /></el-icon> 添加指标
                </el-button>
              </el-form-item>
            </template>

            <!-- 人工评测场景选择 -->
            <template v-if="evalType === 'manual'">
              <el-form-item label="评估量级" prop="ratingScale">
                <div class="rating-scale">
                  <el-slider v-model="form.ratingScale" :min="1" :max="10" :step="1" show-stops
                    :marks="{ 1: '1', 5: '5', 10: '10' }" />
                  <span class="rating-value">{{ form.ratingScale }}分</span>
                </div>
              </el-form-item>

              <el-form-item label="评估场景" prop="scenes">
                <div class="scene-cards">
                  <div v-for="(label, key) in ManualEvalSceneMap" :key="key"
                    :class="['scene-card', { active: form.scenes.includes(key as string) }]"
                    @click="toggleScene(key as string)">
                    <el-icon :size="28"><component :is="ManualEvalSceneIconMap[key as ManualEvalScene]" /></el-icon>
                    <span>{{ label }}</span>
                  </div>
                </div>
              </el-form-item>

              <el-form-item label="评估指标">
                <el-table :data="form.metrics" size="small" border style="width: 100%">
                  <el-table-column type="index" label="序列" width="60" />
                  <el-table-column prop="name" label="评估指标" min-width="120">
                    <template #default="{ row }">
                      <el-input v-model="row.name" placeholder="指标名称" size="small" />
                    </template>
                  </el-table-column>
                  <el-table-column prop="description" label="指标说明" min-width="160">
                    <template #default="{ row }">
                      <el-input v-model="row.description" placeholder="指标说明" size="small" />
                    </template>
                  </el-table-column>
                  <el-table-column label="操作" width="60">
                    <template #default="{ $index }">
                      <el-button type="danger" link size="small" @click="form.metrics.splice($index, 1)">
                        <el-icon><Delete /></el-icon>
                      </el-button>
                    </template>
                  </el-table-column>
                </el-table>
                <el-button type="primary" link size="small" @click="form.metrics.push({ name: '', description: '' })" style="margin-top: 8px">
                  <el-icon><Plus /></el-icon> 添加指标
                </el-button>
              </el-form-item>
            </template>
          </div>
        </div>
      </el-form>

      <!-- 底部按钮：与表单同一卡片内自然衔接 -->
      <div class="form-footer">
        <el-button @click="router.back()">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleSubmit">保存</el-button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Plus, Delete } from '@element-plus/icons-vue'
import PageHeaderCard from '@/components/common/PageHeaderCard.vue'
import { createEvaluation } from '@/api/service'
import { getDatasetList } from '@/api/dataset'
import { getDeploymentList } from '@/api/service'
import type { EvalScene, ManualEvalScene } from '@/types'
import { EvalSceneMap, EvalSceneIconMap, ManualEvalSceneMap, ManualEvalSceneIconMap } from '@/types'

const router = useRouter()
const route = useRoute()
const evalType = computed(() => (route.query.type as string) || 'auto')
const submitting = ref(false)

const form = ref({
  name: '',
  description: '',
  evalType: evalType.value,
  isBaseline: false,
  datasetId: '',
  datasetName: '',
  deploymentId: '',
  deploymentName: '',
  scenes: [] as string[],
  metrics: [] as { name: string; description: string }[],
  ratingScale: 5,
})

const rules = {
  name: [{ required: true, message: '请输入评测名称', trigger: 'blur' }],
  datasetId: [{ required: true, message: '请选择数据集', trigger: 'change' }],
  deploymentId: [{ required: true, message: '请选择模型服务', trigger: 'change' }],
  scenes: [{ required: true, type: 'array' as const, min: 1, message: '请选择评估场景', trigger: 'change' }],
}

const formRef = ref()
const datasetList = ref<any[]>([])
const deploymentList = ref<any[]>([])

function toggleScene(key: string) {
  const idx = form.value.scenes.indexOf(key)
  if (idx >= 0) form.value.scenes.splice(idx, 1)
  else form.value.scenes.push(key)
}

function onDatasetChange(val: string) {
  const ds = datasetList.value.find((d: any) => d.id === val)
  if (ds) form.value.datasetName = ds.name
}

function onDeploymentChange(val: string) {
  const dp = deploymentList.value.find((d: any) => d.id === val)
  if (dp) form.value.deploymentName = dp.name
}

async function handleSubmit() {
  if (formRef.value) {
    try { await formRef.value.validate() } catch { return }
  }
  submitting.value = true
  try {
    await createEvaluation({
      ...form.value,
      evalType: evalType.value,
    })
    ElMessage.success('创建成功')
    router.push('/service/evaluation')
  } catch (e: any) {
    ElMessage.error(e.message || '创建失败')
  } finally {
    submitting.value = false
  }
}

async function loadDatasets() {
  try {
    const res = await getDatasetList({ pageIndex: 1, pageSize: 200, type: 'evaluation' })
    datasetList.value = res.list || []
  } catch { datasetList.value = [] }
}

async function loadDeployments() {
  try {
    const res = await getDeploymentList({ pageIndex: 1, pageSize: 200, status: 'running' })
    deploymentList.value = res.list || []
  } catch { deploymentList.value = [] }
}

onMounted(() => {
  loadDatasets()
  loadDeployments()
})
</script>

<style lang="scss" scoped>
.evaluation-create {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.evaluation-form {
  max-width: 900px;
  :deep(.el-form-item.no-asterisk) > .el-form-item__label::before {
    content: none !important;
  }
}

.scene-cards {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}
.scene-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 16px 20px;
  border: 2px solid $border-color-light;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s;
  min-width: 100px;
  span {
    font-size: 13px;
    color: $text-secondary;
  }
  &:hover {
    border-color: $color-primary;
  }
  &.active {
    border-color: $color-primary;
    background: rgba($color-primary, 0.06);
    span { color: $color-primary; font-weight: 600; }
    .el-icon { color: $color-primary; }
  }
}

.rating-scale {
  display: flex;
  align-items: center;
  gap: 16px;
  width: 100%;
  max-width: 500px;

  .el-slider {
    flex: 1;
  }

  .rating-value {
    font-size: 14px;
    font-weight: 600;
    color: $color-primary;
    min-width: 48px;
  }
}

.form-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  margin-top: 8px;
  padding-top: 20px;
  border-top: 1px solid $border-color-lighter;
}
</style>
