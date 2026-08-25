<template>
  <div class="evaluation-create">
    <div class="create-card">
      <el-form :model="formData" label-width="110px" label-position="left">
        <!-- 数据集名称 -->
        <el-form-item label="数据集名称" required>
          <el-input v-model="formData.name" placeholder="请输入数据集名称" />
        </el-form-item>

        <!-- 评测数据集类型（切换平台/自定义） -->
        <el-form-item label="评测数据集类型" required>
          <el-select v-model="formData.category" placeholder="请选择" style="width: 100%">
            <el-option label="平台数据集" value="平台数据集" />
            <el-option label="自定义数据集" value="自定义数据集" />
          </el-select>
        </el-form-item>

        <!-- 数据类型 -->
        <el-form-item label="数据类型" required>
          <el-select v-model="formData.dataType" placeholder="请选择" style="width: 100%">
            <el-option
              v-for="opt in availableDataTypes"
              :key="opt.value"
              :label="opt.label"
              :value="opt.value"
            />
          </el-select>
        </el-form-item>

        <!-- 评估场景：仅平台数据集展示 -->
        <template v-if="formData.category === '平台数据集'">
          <el-form-item label="评估场景" required>
            <div class="scene-cards">
              <div
                v-for="s in scenes"
                :key="s.value"
                class="scene-card"
                :class="{ active: selectedScenes.includes(s.value) }"
                @click="toggleScene(s.value)"
              >
                <div class="scene-title">{{ s.label }}</div>
                <div class="scene-desc">{{ s.desc }}</div>
              </div>
            </div>
          </el-form-item>

          <el-form-item label="评估指标" required>
            <div class="metric-hint">定义评估指标和相关说明，评估人员将依据模型表现进行打分。</div>
            <el-table
              :data="metricRows"
              :show-header="true"
              :border="true"
              class="metric-table"
            >
              <el-table-column label="序号" type="index" width="60" align="center" />
              <el-table-column prop="scene" label="场景" width="120" align="center" />
              <el-table-column label="评估指标">
                <template #default="{ row }">
                  <el-input v-model="row.metric" placeholder="请输入评估指标" />
                </template>
              </el-table-column>
              <el-table-column label="指标说明" width="280">
                <template #default="{ row }">
                  <el-input v-model="row.desc" placeholder="请输入指标说明" />
                </template>
              </el-table-column>
              <el-table-column label="操作" width="80" align="center">
                <template #default="{ $index }">
                  <el-button link type="danger" size="small" @click="metricRows.splice($index, 1)">删除</el-button>
                </template>
              </el-table-column>
            </el-table>
            <div class="metric-add-row">
              <el-button type="primary" plain size="small" @click="addMetricRow">
                <el-icon><Plus /></el-icon><span>新增指标</span>
              </el-button>
            </div>
          </el-form-item>
        </template>

        <!-- 数据集描述 -->
        <el-form-item label="数据集描述">
          <el-input v-model="formData.description" type="textarea" :rows="3" placeholder="请输入描述" />
        </el-form-item>
      </el-form>

      <div class="form-actions">
        <el-button @click="cancel">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submit">提交</el-button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, watch, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import { createDataset } from '@/api/dataset'

const router = useRouter()

interface MetricRow {
  scene: string
  metric: string
  desc: string
}

const formData = reactive({
  name: '',
  category: '平台数据集',
  dataType: 'OpenCompass',
  description: '',
})

const submitting = ref(false)

const platformDataTypes = [
  { label: 'OpenCompass', value: 'OpenCompass' },
]

const customDataTypes = [
  { label: '问答题', value: '问答题' },
  { label: '选择题', value: '选择题' },
]

const availableDataTypes = computed(() =>
  formData.category === '自定义数据集' ? customDataTypes : platformDataTypes
)

watch(
  () => formData.category,
  (v) => {
    // 切换类型时重置数据类型，避免非法值
    if (v === '自定义数据集') {
      formData.dataType = '问答题'
    } else {
      formData.dataType = 'OpenCompass'
    }
  }
)

const scenes = [
  { value: '代码', label: '代码', desc: '对模型的代码能力进行多方面的评估，包括基础编程、算法逻辑和js。' },
  { value: '对齐', label: '对齐', desc: '全面评测大模型在中文领域与人类意图的对齐度，通过模型打分评测。' },
  { value: '智能体', label: '智能体', desc: '在多个环境下，测试大模型作为智能体的能力。' },
  { value: '安全', label: '安全', desc: '评估大模型的安全性、隐私保护和向善性等。' },
  { value: '逻辑推理', label: '逻辑推理', desc: '全面衡量大模型在数学以及逻辑推理方向的能力。' },
]

const selectedScenes = ref<string[]>([])
const metricRows = ref<MetricRow[]>([])

function toggleScene(v: string) {
  const i = selectedScenes.value.indexOf(v)
  if (i >= 0) selectedScenes.value.splice(i, 1)
  else selectedScenes.value.push(v)
  // 同步指标行
  metricRows.value = metricRows.value.filter((m) => selectedScenes.value.includes(m.scene))
}

function addMetricRow() {
  if (!selectedScenes.value.length) {
    ElMessage.warning('请先选择评估场景')
    return
  }
  metricRows.value.push({ scene: selectedScenes.value[0], metric: '', desc: '' })
}

function cancel() {
  router.push({ name: 'EvaluationDataset' })
}

async function submit() {
  if (!formData.name) return ElMessage.warning('请输入数据集名称')
  if (!formData.category) return ElMessage.warning('请选择评测数据集类型')
  if (!formData.dataType) return ElMessage.warning('请选择数据类型')
  if (formData.category === '平台数据集' && !selectedScenes.value.length) {
    return ElMessage.warning('请选择评估场景')
  }

  submitting.value = true
  try {
    const payload: Record<string, unknown> = {
      name: formData.name,
      category: formData.category,
      data_type: formData.dataType,
      description: formData.description,
      type: 'evaluation',
      source: formData.category === '自定义数据集' ? 'custom' : 'platform',
      is_public: false,
    }
    if (formData.category === '平台数据集') {
      payload.eval_dimensions = JSON.stringify({
        scenes: selectedScenes.value,
        metrics: metricRows.value,
      })
    }
    await createDataset(payload)
    ElMessage.success('创建成功')
    router.push({ name: 'EvaluationDataset' })
  } finally {
    submitting.value = false
  }
}

onMounted(() => {
  // 默认添加一个空指标行，避免空表过于突兀
})
</script>

<style lang="scss" scoped>
.evaluation-create {
  .create-card {
    background: $bg-color-white;
    border: 1px solid $border-color-light;
    border-radius: $border-radius-large;
    padding: 24px 32px;

    .scene-cards {
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 12px;
      width: 100%;

      .scene-card {
        border: 1px solid $border-color;
        border-radius: 4px;
        padding: 14px 16px;
        cursor: pointer;
        transition: all 0.2s;
        background: $bg-color-white;

        .scene-title {
          color: $color-primary;
          font-weight: 600;
          margin-bottom: 6px;
        }
        .scene-desc {
          color: $text-secondary;
          font-size: 12px;
          line-height: 1.6;
        }
        &:hover {
          border-color: $color-primary-light;
        }
        &.active {
          border-color: $color-primary;
          background: rgba(230, 57, 70, 0.04);
        }
      }
    }

    .metric-hint {
      color: $color-primary;
      font-size: 12px;
      margin-bottom: 8px;
    }
    .metric-table {
      width: 100%;
      :deep(th) {
        background: $bg-card-header;
      }
    }
    .metric-add-row {
      margin-top: 8px;
    }
  }
  .form-actions {
    display: flex;
    justify-content: flex-end;
    gap: 8px;
    margin-top: 16px;
  }
}
</style>