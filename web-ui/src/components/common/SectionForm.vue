<template>
  <div class="section-form">
    <template v-for="(section, idx) in sections" :key="idx">
      <div class="form-section">
        <div class="section-title">{{ section.title }}</div>
        <div class="section-body">
          <el-row :gutter="20">
            <el-col
              v-for="field in section.fields"
              :key="field.prop"
              :span="field.colSpan || colSpan"
            >
              <el-form-item :label="field.label" :prop="field.prop" :required="field.required">
                <!-- 文本输入 -->
                <el-input
                  v-if="field.type === 'input'"
                  v-model="formData[field.prop]"
                  :placeholder="field.placeholder || `请输入${field.label}`"
                  :disabled="field.disabled"
                  :type="field.inputType || 'text'"
                />

                <!-- 数字输入 -->
                <el-input-number
                  v-else-if="field.type === 'number'"
                  v-model="formData[field.prop]"
                  :min="field.min"
                  :max="field.max"
                  :step="field.step || 1"
                  :placeholder="field.placeholder"
                  style="width: 100%"
                />

                <!-- 下拉选择 -->
                <el-select
                  v-else-if="field.type === 'select'"
                  v-model="formData[field.prop]"
                  :placeholder="field.placeholder || `请选择${field.label}`"
                  :disabled="field.disabled"
                  :multiple="field.multiple"
                  :filterable="field.filterable"
                  style="width: 100%"
                >
                  <el-option
                    v-for="opt in field.options"
                    :key="String(opt.value)"
                    :label="opt.label"
                    :value="opt.value"
                  />
                </el-select>

                <!-- 文本域 -->
                <el-input
                  v-else-if="field.type === 'textarea'"
                  v-model="formData[field.prop]"
                  type="textarea"
                  :rows="field.rows || 3"
                  :placeholder="field.placeholder || `请输入${field.label}`"
                />

                <!-- 开关 -->
                <el-switch
                  v-else-if="field.type === 'switch'"
                  v-model="formData[field.prop]"
                  :active-value="field.activeValue ?? true"
                  :inactive-value="field.inactiveValue ?? false"
                />

                <!-- 单选 -->
                <el-radio-group
                  v-else-if="field.type === 'radio'"
                  v-model="formData[field.prop]"
                >
                  <el-radio
                    v-for="opt in field.options"
                    :key="String(opt.value)"
                    :value="opt.value"
                  >
                    {{ opt.label }}
                  </el-radio>
                </el-radio-group>

                <!-- 自定义插槽 -->
                <slot v-else-if="field.type === 'slot'" :name="field.prop" :field="field" />

                <!-- 默认文本 -->
                <el-input v-else v-model="formData[field.prop]" :placeholder="`请输入${field.label}`" />
              </el-form-item>
            </el-col>
          </el-row>
          <!-- section 插槽 -->
          <slot :name="`section-${idx}`" />
        </div>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import type { FormField, FormSection } from './types'

defineProps<{
  sections: FormSection[]
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  formData: Record<string, any>
  colSpan?: number
}>()
</script>

<style lang="scss" scoped>
.form-section {
  margin-bottom: 24px;

  .section-title {
    font-size: 15px;
    font-weight: 600;
    color: $text-primary;
    margin-bottom: 18px;
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
}
</style>
