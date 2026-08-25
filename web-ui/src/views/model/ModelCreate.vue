<template>
  <div class="model-create">
    <div class="create-header">
      <el-page-header @back="goBack">
        <template #content>
          <span class="create-title">创建模型</span>
        </template>
      </el-page-header>
    </div>

    <div class="create-body">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="120px" class="create-form">
        <div class="form-section">
          <div class="section-title">基本信息</div>
          <div class="section-body">
            <el-row :gutter="24">
              <el-col :span="12">
                <el-form-item label="模型名称" prop="name">
                  <el-input v-model="form.name" placeholder="请输入模型名称" maxlength="200" show-word-limit />
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="厂商/来源" prop="vendor">
                  <el-input v-model="form.vendor" placeholder="如 Qwen / DeepSeek / 自定义" />
                </el-form-item>
              </el-col>
            </el-row>
            <el-row :gutter="24">
              <el-col :span="12">
                <el-form-item label="模型类型" prop="type">
                  <el-select v-model="form.type" style="width: 100%" placeholder="请选择模型类型">
                    <el-option v-for="(label, key) in ModelTypeMap" :key="key" :label="label" :value="key" />
                  </el-select>
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="规格" prop="spec">
                  <el-select v-model="form.spec" style="width: 100%" placeholder="请选择模型规格">
                    <el-option v-for="(label, key) in ModelSpecMap" :key="key" :label="label" :value="key" />
                  </el-select>
                </el-form-item>
              </el-col>
            </el-row>
            <el-form-item label="标签">
              <el-select v-model="form.tags" multiple filterable allow-create default-first-option placeholder="输入标签回车添加" style="width: 100%">
                <el-option label="Safetensors" value="Safetensors" />
                <el-option label="PyTorch" value="PyTorch" />
                <el-option label="LoRA" value="LoRA" />
                <el-option label="GPTQ" value="GPTQ" />
                <el-option label="中文" value="中文" />
              </el-select>
            </el-form-item>
            <el-form-item label="描述">
              <el-input v-model="form.description" type="textarea" :rows="4" placeholder="请输入模型描述" maxlength="500" show-word-limit />
            </el-form-item>
          </div>
        </div>

        <div class="form-section">
          <div class="section-title">版本信息</div>
          <div class="section-body">
            <el-row :gutter="24">
              <el-col :span="12">
                <el-form-item label="初始版本号" prop="version">
                  <el-input v-model="form.version" placeholder="如: v1.0.0" />
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="推理框架">
                  <el-select v-model="form.framework" style="width: 100%" clearable placeholder="请选择推理框架">
                    <el-option label="vLLM" value="vLLM" />
                    <el-option label="MindIE" value="MindIE" />
                    <el-option label="自定义" value="custom" />
                  </el-select>
                </el-form-item>
              </el-col>
            </el-row>
            <el-form-item label="版本描述">
              <el-input v-model="form.versionDescription" type="textarea" :rows="3" placeholder="请输入版本描述" />
            </el-form-item>
          </div>
        </div>

        <div class="form-section">
          <div class="section-title">访问设置</div>
          <div class="section-body">
            <el-form-item label="是否公开">
              <el-switch v-model="form.isPublic" active-text="公开" inactive-text="私有" />
              <span class="form-tip">公开模型将显示在模型库广场中，其他用户可查看和导入</span>
            </el-form-item>
          </div>
        </div>
      </el-form>

      <div class="form-footer">
        <el-button @click="goBack">取消</el-button>
        <el-button type="primary" @click="handleSubmit" :loading="submitting">创建</el-button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'
import { createModel, createModelVersion } from '@/api/model'
import { ModelTypeMap, ModelSpecMap } from '@/types'

const router = useRouter()
const formRef = ref<FormInstance>()
const submitting = ref(false)

const form = reactive({
  name: '',
  type: 'dialogue',
  spec: 'below-10b',
  vendor: '',
  tags: [] as string[],
  description: '',
  version: 'v1.0.0',
  framework: '',
  versionDescription: '',
  isPublic: false,
})

const rules: FormRules = {
  name: [{ required: true, message: '请输入模型名称', trigger: 'blur' }],
  type: [{ required: true, message: '请选择模型类型', trigger: 'change' }],
  version: [{ required: true, message: '请输入版本号', trigger: 'blur' }],
}

function goBack() {
  router.push('/model/my-library')
}

async function handleSubmit() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return

  submitting.value = true
  try {
    const modelData = await createModel({
      name: form.name,
      type: form.type,
      spec: form.spec,
      vendor: form.vendor,
      description: form.description,
      tags: JSON.stringify(form.tags),
      isPublic: form.isPublic,
      version: form.version,
    })

    // 创建初始版本
    if (modelData?.id) {
      await createModelVersion(modelData.id, {
        version: form.version,
        description: form.versionDescription,
        framework: form.framework,
        isDefault: true,
      })
    }

    ElMessage.success('模型创建成功')
    router.push(`/model/detail/${modelData.id}`)
  } catch (e: any) {
    ElMessage.error(e.message || '创建失败')
  } finally {
    submitting.value = false
  }
}
</script>

<style lang="scss" scoped>
.model-create {
  .create-header {
    margin-bottom: 16px;
    .create-title {
      font-size: 16px;
      font-weight: 600;
    }
  }

  .create-body {
    background: $bg-color-white;
    border: 1px solid $border-color-light;
    border-radius: $border-radius-large;
    padding: 24px 32px;

    .form-section {
      margin-bottom: 24px;
      .section-title {
        font-size: 15px;
        font-weight: 600;
        color: $text-primary;
        margin-bottom: 16px;
        padding-left: 10px;
        border-left: 3px solid $color-primary;
      }
    }

    .form-tip {
      font-size: 12px;
      color: $text-secondary;
      margin-left: 12px;
    }

    .form-footer {
      display: flex;
      justify-content: flex-end;
      gap: 12px;
      padding-top: 24px;
      border-top: 1px solid $border-color-lighter;
    }
  }
}
</style>
