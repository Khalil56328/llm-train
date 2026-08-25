<template>
  <div class="kv-editor">
    <div v-for="(item, idx) in list" :key="idx" class="kv-item">
      <el-input
        :model-value="item.key"
        placeholder="参数名"
        style="width: 180px"
        @update:model-value="updateItem(idx, 'key', $event)"
      />
      <el-input
        :model-value="item.value"
        placeholder="参数值"
        style="flex: 1"
        @update:model-value="updateItem(idx, 'value', $event)"
      />
      <el-button
        type="danger"
        :icon="Delete"
        circle
        size="small"
        @click="removeItem(idx)"
      />
    </div>
    <el-button type="primary" link :icon="Plus" @click="addItem">
      添加{{ addLabel }}
    </el-button>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Delete, Plus } from '@element-plus/icons-vue'
import type { KvItem } from './types'

const props = withDefaults(
  defineProps<{
    modelValue: KvItem[]
    addLabel?: string
  }>(),
  { addLabel: '参数' }
)

const emit = defineEmits<{
  'update:modelValue': [value: KvItem[]]
}>()

const list = computed({
  get: () => props.modelValue,
  set: (val) => emit('update:modelValue', val),
})

function updateItem(idx: number, field: 'key' | 'value', value: string) {
  const newList = [...list.value]
  newList[idx] = { ...newList[idx], [field]: value }
  emit('update:modelValue', newList)
}

function addItem() {
  emit('update:modelValue', [...list.value, { key: '', value: '' }])
}

function removeItem(idx: number) {
  const newList = list.value.filter((_, i) => i !== idx)
  emit('update:modelValue', newList)
}
</script>

<style lang="scss" scoped>
.kv-editor {
  .kv-item {
    display: flex;
    gap: 8px;
    align-items: center;
    margin-bottom: 8px;
  }
}
</style>
