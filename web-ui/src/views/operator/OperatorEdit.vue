<template>
  <div class="operator-edit-page">
    <PageHeaderCard title="修改算子" />

    <div class="edit-card" v-loading="loading">
      <template v-if="detail">
        <el-form
          ref="formRef"
          :model="form"
          :rules="rules"
          label-position="top"
          class="edit-form"
        >
          <div class="form-section">
            <div class="section-title">基础信息</div>
            <div class="section-body">
              <el-row :gutter="20">
                <el-col :span="12">
                  <el-form-item label="算子类型" prop="category">
                    <el-select v-model="form.category" placeholder="请选择算子类型" style="width: 100%">
                      <el-option label="预训练" value="预训练" />
                      <el-option label="大模型微调" value="大模型微调" />
                      <el-option label="模型蒸馏" value="模型蒸馏" />
                      <el-option label="模型推理" value="模型推理" />
                      <el-option label="模型合并" value="模型合并" />
                      <el-option label="结果存储" value="结果存储" />
                      <el-option label="数据集导入" value="数据集导入" />
                    </el-select>
                  </el-form-item>
                </el-col>
                <el-col :span="12">
                  <el-form-item label="训练框架" prop="training_framework">
                    <el-select v-model="form.training_framework" placeholder="请选择训练框架" style="width: 100%">
                      <el-option label="ms-swift" value="ms-swift" />
                      <el-option label="LlamaFactory" value="llamafactory" />
                    </el-select>
                  </el-form-item>
                </el-col>
              </el-row>
              <el-row :gutter="20">
                <el-col :span="12">
                  <el-form-item label="训练方法" prop="training_method">
                    <el-select v-model="form.training_method" placeholder="请选择训练方法" style="width: 100%">
                      <el-option label="全量更新" value="full" />
                      <el-option label="冻结微调" value="freeze" />
                      <el-option label="LoRA微调" value="lora" />
                    </el-select>
                  </el-form-item>
                </el-col>
                <el-col :span="12">
                  <el-form-item label="算子名称" prop="name">
                    <el-input
                      v-model="form.name"
                      placeholder="请输入算子名称"
                      maxlength="50"
                      show-word-limit
                    />
                  </el-form-item>
                </el-col>
              </el-row>
              <el-row :gutter="20">
                <el-col :span="24">
                  <el-form-item label="描述" prop="description">
                    <el-input
                      v-model="form.description"
                      type="textarea"
                      :rows="4"
                      placeholder="请输入算子描述"
                      maxlength="200"
                      show-word-limit
                    />
                  </el-form-item>
                </el-col>
              </el-row>
            </div>
          </div>
        </el-form>
      </template>

      <el-empty v-else-if="!loading" description="未找到该算子" />
    </div>

    <!-- 底部按钮 -->
    <div class="footer-bar">
      <el-button @click="goBack">取消</el-button>
      <el-button type="primary" :loading="saving" @click="handleSave">保存</el-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import PageHeaderCard from '@/components/common/PageHeaderCard.vue'
import { fetchOperatorDetail, updateOperator } from '@/api/operator'
import type { OperatorWithVersions } from '@/types'

const route = useRoute()
const router = useRouter()

const loading = ref(false)
const saving = ref(false)
const formRef = ref<FormInstance>()
const detail = ref<OperatorWithVersions | null>(null)

const form = reactive({
  name: '',
  category: '',
  training_framework: '',
  training_method: '',
  description: '',
})

const rules: FormRules = {
  name: [
    { required: true, message: '请输入算子名称', trigger: 'blur' },
    { max: 50, message: '最多 50 个字符', trigger: 'blur' },
  ],
  category: [{ required: true, message: '请选择算子类型', trigger: 'change' }],
  training_framework: [{ required: true, message: '请选择训练框架', trigger: 'change' }],
  training_method: [{ required: true, message: '请选择训练方法', trigger: 'change' }],
  description: [{ max: 200, message: '最多 200 个字符', trigger: 'blur' }],
}

async function fetchData() {
  const id = route.params.id as string
  if (!id) return
  loading.value = true
  try {
    detail.value = await fetchOperatorDetail(id)
    form.name = detail.value.name
    form.category = detail.value.category
    form.training_framework = detail.value.training_framework || ''
    form.training_method = detail.value.training_method || ''
    form.description = detail.value.description || ''
  } catch {
    detail.value = null
  } finally {
    loading.value = false
  }
}

async function handleSave() {
  if (!formRef.value) return
  try {
    await formRef.value.validate()
  } catch {
    return
  }
  saving.value = true
  try {
    await updateOperator(route.params.id as string, {
      name: form.name,
      category: form.category,
      training_framework: form.training_framework,
      training_method: form.training_method,
      description: form.description,
    })
    ElMessage.success('保存成功')
    router.push({ name: 'OperatorManagement' })
  } catch (e: any) {
    ElMessage.error(e?.message || '保存失败')
  } finally {
    saving.value = false
  }
}

function goBack() {
  router.push({ name: 'OperatorManagement' })
}

onMounted(fetchData)
</script>

<style scoped lang="scss">
@use '@/assets/styles/variables' as *;

.operator-edit-page {
  padding: 0;
}

.edit-card {
  background: #fff;
  border-radius: 8px;
  padding: 24px;
  margin-top: 16px;
  min-height: 300px;
}

.edit-form {
  max-width: 900px;
}

.form-section {
  .section-title {
    font-size: 15px;
    font-weight: 600;
    color: $text-primary;
    margin-bottom: 16px;
    padding-bottom: 8px;
    border-bottom: 1px solid $border-color-light;
  }
}

.footer-bar {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  margin-top: 20px;
  padding: 16px 24px;
  background: #fff;
  border-radius: 8px;
}
</style>
