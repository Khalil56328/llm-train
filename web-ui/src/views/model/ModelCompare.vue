<template>
  <el-dialog
    :model-value="visible"
    @update:model-value="$emit('update:visible', $event)"
    title="模型对比"
    width="80%"
    top="5vh"
    class="compare-dialog"
    destroy-on-close
  >
    <div class="compare-content" v-loading="loading">
      <div class="compare-header">
        <el-alert v-if="compareData.length < 2" type="info" :closable="false" show-icon>
          <template #title>请选择至少2个模型进行对比</template>
        </el-alert>
      </div>

      <div class="compare-table" v-if="compareData.length >= 2">
        <table class="compare-grid">
          <thead>
            <tr>
              <th class="field-col">对比项</th>
              <th v-for="m in compareData" :key="m.id">{{ m.name }}</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td class="field-col">模型类型</td>
              <td v-for="m in compareData" :key="m.id">{{ ModelTypeMap[m.type as keyof typeof ModelTypeMap] || m.type }}</td>
            </tr>
            <tr>
              <td class="field-col">规格</td>
              <td v-for="m in compareData" :key="m.id">{{ ModelSpecMap[m.spec as keyof typeof ModelSpecMap] || m.spec }}</td>
            </tr>
            <tr>
              <td class="field-col">厂商</td>
              <td v-for="m in compareData" :key="m.id">{{ m.vendor }}</td>
            </tr>
            <tr>
              <td class="field-col">版本数</td>
              <td v-for="m in compareData" :key="m.id">{{ m.versions?.length || 0 }}</td>
            </tr>
            <tr>
              <td class="field-col">最新版本</td>
              <td v-for="m in compareData" :key="m.id">
                {{ m.versions?.[0]?.version || '-' }}
                <el-tag v-if="m.versions?.[0]?.framework" size="small" type="info" style="margin-left: 4px">{{ m.versions[0].framework }}</el-tag>
              </td>
            </tr>
            <tr>
              <td class="field-col">文件大小</td>
              <td v-for="m in compareData" :key="m.id">{{ formatSize(m.versions?.[0]?.size || 0) }}</td>
            </tr>
            <tr>
              <td class="field-col">文件数</td>
              <td v-for="m in compareData" :key="m.id">{{ m.versions?.[0]?.fileCount || 0 }}</td>
            </tr>
            <tr>
              <td class="field-col">标签</td>
              <td v-for="m in compareData" :key="m.id">
                <template v-if="parseTags(m.tags).length">
                  <el-tag v-for="tag in parseTags(m.tags)" :key="tag" size="small" type="info" style="margin: 2px">{{ tag }}</el-tag>
                </template>
                <span v-else>-</span>
              </td>
            </tr>
            <tr>
              <td class="field-col">描述</td>
              <td v-for="m in compareData" :key="m.id" class="desc-cell">{{ m.description || '-' }}</td>
            </tr>
            <tr>
              <td class="field-col">是否公开</td>
              <td v-for="m in compareData" :key="m.id">
                <el-tag :type="m.isPublic ? 'success' : 'info'" size="small">{{ m.isPublic ? '公开' : '私有' }}</el-tag>
              </td>
            </tr>
            <tr>
              <td class="field-col">版本列表</td>
              <td v-for="m in compareData" :key="m.id">
                <div v-for="v in m.versions" :key="v.id" class="version-chip">
                  <span>{{ v.version }}</span>
                  <el-tag v-if="v.isDefault" size="small" type="success">默认</el-tag>
                  <el-tag :type="v.status === 'ready' ? 'success' : 'warning'" size="small">{{ v.status === 'ready' ? '就绪' : v.status }}</el-tag>
                </div>
                <span v-if="!m.versions?.length">-</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <template #footer>
      <el-button @click="$emit('update:visible', false)">关闭</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { compareModels } from '@/api/model'
import { ModelTypeMap, ModelSpecMap } from '@/types'
import type { ModelCompareItem } from '@/types'

const props = defineProps<{
  visible: boolean
  modelIds: string[]
}>()

defineEmits<{
  'update:visible': [val: boolean]
}>()

const loading = ref(false)
const compareData = ref<ModelCompareItem[]>([])

function formatSize(bytes: number) {
  if (!bytes || bytes === 0) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  const i = Math.floor(Math.log(bytes) / Math.log(1024))
  return `${(bytes / Math.pow(1024, i)).toFixed(1)} ${units[i]}`
}

function parseTags(tags: string | string[] | undefined): string[] {
  if (!tags) return []
  if (typeof tags === 'string') {
    try { return JSON.parse(tags || '[]') } catch { return [] }
  }
  return tags
}

async function fetchCompareData() {
  if (!props.visible || props.modelIds.length < 2) {
    compareData.value = []
    return
  }
  loading.value = true
  try {
    compareData.value = await compareModels(props.modelIds)
  } catch (e: any) {
    ElMessage.error(e.message || '获取对比数据失败')
    compareData.value = []
  } finally {
    loading.value = false
  }
}

watch(() => props.visible, (val) => {
  if (val) fetchCompareData()
})
</script>

<style lang="scss" scoped>
.compare-content {
  min-height: 200px;
}

.compare-grid {
  width: 100%;
  border-collapse: collapse;
  font-size: 14px;

  th, td {
    padding: 12px 16px;
    border: 1px solid $border-color-lighter;
    text-align: left;
    vertical-align: top;
  }

  th {
    background: $bg-color;
    font-weight: 600;
    min-width: 150px;
  }

  .field-col {
    width: 120px;
    font-weight: 600;
    background: $bg-color;
    white-space: nowrap;
  }

  .desc-cell {
    max-width: 300px;
    word-break: break-all;
  }
}

.version-chip {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 4px;
  font-size: 13px;
}
</style>
