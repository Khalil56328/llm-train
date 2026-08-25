<template>
  <el-cascader
    v-model="selected"
    :options="cascaderOptions"
    :props="cascaderProps"
    :placeholder="placeholder"
    :clearable="clearable"
    :disabled="disabled"
    :filterable="filterable"
    separator="/"
    @change="handleChange"
  />
</template>

<script setup lang="ts">
import { computed } from 'vue'

export type HierarchicalScope = 'public' | 'mine'

export type HierarchicalItem = {
  id: string
  name: string
  scope?: HierarchicalScope | HierarchicalScope[]
  children?: HierarchicalItem[]
}

type HierarchicalNode = {
  value: string
  label: string
  level: number
  scope?: HierarchicalScope
  leaf?: boolean
  disabled?: boolean
  children?: HierarchicalNode[]
}

const props = withDefaults(
  defineProps<{
    modelValue: string
    data: HierarchicalItem[]
    placeholder?: string
    clearable?: boolean
    disabled?: boolean
    filterable?: boolean
  }>(),
  {
    placeholder: '请选择',
    clearable: true,
    disabled: false,
    filterable: true,
  }
)

const emit = defineEmits<{
  (e: 'update:modelValue', value: string): void
  (e: 'change', value: string, path: HierarchicalItem[]): void
}>()

const cascaderProps = {
  expandTrigger: 'hover' as const,
  checkStrictly: false,
  emitPath: true,
  value: 'value',
  label: 'label',
  children: 'children',
  leaf: 'leaf',
  disabled: 'disabled',
}

function getItemScopes(item: HierarchicalItem): HierarchicalScope[] {
  if (!item.scope) return []
  return Array.isArray(item.scope) ? item.scope : [item.scope]
}

const cascaderOptions = computed<HierarchicalNode[]>(() => {
  const publicItems = props.data.filter((d) => getItemScopes(d).includes('public'))
  const mineItems = props.data.filter((d) => getItemScopes(d).includes('mine'))
  const scopes: HierarchicalNode[] = []

  if (publicItems.length) {
    scopes.push({
      value: 'public',
      label: '公开',
      level: 0,
      scope: 'public',
      leaf: false,
      disabled: false,
      children: buildOptions(publicItems, 1, 'public'),
    })
  }

  if (mineItems.length) {
    scopes.push({
      value: 'mine',
      label: '我的',
      level: 0,
      scope: 'mine',
      leaf: false,
      disabled: false,
      children: buildOptions(mineItems, 1, 'mine'),
    })
  }

  return scopes
})

/**
 * 构建节点树。
 * 当传入 scope 时，只保留属于该分组的子节点（例如「公开」分组下只展示公开版本），
 * 若过滤后无子节点则退化为叶子节点。
 */
function buildOptions(items: HierarchicalItem[], level: number, scope?: HierarchicalScope): HierarchicalNode[] {
  return items.map((item) => {
    const rawChildren = Array.isArray(item.children) ? (item.children as HierarchicalItem[]) : []
    const children = scope ? rawChildren.filter((c) => getItemScopes(c).includes(scope)) : rawChildren
    const node: HierarchicalNode = {
      value: item.id,
      label: item.name,
      level,
      scope: Array.isArray(item.scope) ? item.scope[0] : item.scope,
      leaf: children.length === 0,
      disabled: false,
    }
    if (children.length) {
      node.children = buildOptions(children, level + 1, scope)
    }
    return node
  })
}

function findNodeByValue(
  options: HierarchicalNode[],
  value: string
): HierarchicalNode | undefined {
  for (const option of options) {
    if (option.value === value) return option
    if (option.children) {
      const found = findNodeByValue(option.children, value)
      if (found) return found
    }
  }
  return undefined
}

function pathToItems(
  options: HierarchicalNode[],
  pathValues: string[]
): HierarchicalItem[] {
  const result: HierarchicalItem[] = []
  let currentOptions = options
  for (const value of pathValues) {
    const node = findNodeByValue(currentOptions, value)
    if (!node) break
    result.push({
      id: node.value,
      name: node.label,
      scope: node.scope,
    })
    currentOptions = node.children || []
  }
  return result
}

const selected = computed({
  get: () => (props.modelValue ? props.modelValue.split('/') : []),
  set: (val) => {
    const arr = Array.isArray(val) ? (val as string[]) : []
    emit('update:modelValue', arr.length ? arr.join('/') : '')
  },
})

function handleChange(val: unknown) {
  const arr = Array.isArray(val) ? (val as string[]) : []
  if (!arr.length) {
    selected.value = []
    emit('change', '', [])
    return
  }
  selected.value = arr
  const pathItems = pathToItems(cascaderOptions.value, arr)
  emit('change', arr.join('/'), pathItems)
}
</script>
