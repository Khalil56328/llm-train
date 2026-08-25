<template>
  <div class="search-filter">
    <!-- 左侧：搜索输入框 + 筛选条件 -->
    <div class="filter-left">
      <el-input
        v-model="keyword"
        :placeholder="placeholder"
        clearable
        class="filter-input"
        @clear="$emit('search')"
        @keyup.enter="$emit('search')"
      >
        <template #prefix>
          <el-icon><Search /></el-icon>
        </template>
      </el-input>
      <slot name="filters" />
    </div>

    <!-- 右侧：操作按钮 -->
    <div class="filter-right">
      <slot name="actions">
        <el-button type="primary" @click="$emit('search')">
          <el-icon><Search /></el-icon>
          <span>查询</span>
        </el-button>
        <el-button @click="handleReset">
          <el-icon><Refresh /></el-icon>
          <span>重置</span>
        </el-button>
        <el-button v-if="showCreate" type="primary" @click="$emit('create')">
          <el-icon><Plus /></el-icon>
          <span>新增</span>
        </el-button>
      </slot>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { Search, Refresh, Plus } from '@element-plus/icons-vue'

const props = withDefaults(
  defineProps<{
    modelValue?: string
    showCreate?: boolean
    placeholder?: string
  }>(),
  { showCreate: true, placeholder: '请输入关键词搜索' }
)

const emit = defineEmits<{
  search: []
  reset: []
  create: []
  'update:modelValue': [value: string]
}>()

const keyword = ref(props.modelValue || '')

watch(
  () => props.modelValue,
  (val) => {
    keyword.value = val || ''
  }
)

watch(keyword, (val) => {
  emit('update:modelValue', val)
})

function handleReset() {
  keyword.value = ''
  emit('reset')
}
</script>

<style lang="scss" scoped>
.search-filter {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 14px 20px;
  background: $bg-color-white;
  border: 1px solid $border-color-light;
  border-radius: $border-radius-large;
  margin-bottom: 16px;

  // 左侧筛选区
  .filter-left {
    display: flex;
    align-items: center;
    gap: 12px;
    flex: 1;
    min-width: 0;
    flex-wrap: nowrap;

    .filter-input {
      width: 240px;
      flex-shrink: 0;
    }

    // 统一控件高度
    :deep(.el-input__wrapper) {
      height: 32px;
    }

    :deep(.el-select) {
      flex-shrink: 0;
    }

    :deep(.el-select__wrapper) {
      height: 32px;
    }
  }

  // 右侧按钮区
  .filter-right {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-shrink: 0;

    :deep(.el-button) {
      height: 32px;
      padding: 0 16px;
      font-size: 13px;
      display: inline-flex;
      align-items: center;
      gap: 4px;
    }
  }
}
</style>