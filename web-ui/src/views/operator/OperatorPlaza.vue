<template>
  <div class="operator-plaza">
    <PageHeaderCard title="算子广场" desc="一站式标准化算子资源库，预置多种通用算子，支持动态组合与智能优化，赋能模型高效开发与性能加速" />

    <SearchFilter v-model:model-value="searchKeyword" :show-create="false" @search="fetchData" @reset="handleReset" />

    <div v-loading="loading" class="plaza-grid-wrapper">
      <CardGrid
        :items="cardItems"
        icon-bg="#e63946"
        @select="(id) => goDetail(id)"
      >
      </CardGrid>
      <el-empty v-if="!loading && cardItems.length === 0" description="暂无算子" />
    </div>

    <div class="plaza-pagination" v-if="total > 0">
      <el-pagination
        v-model:current-page="pageIndex"
        :page-size="pageSize"
        :total="total"
        layout="prev, pager, next"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import PageHeaderCard from '@/components/common/PageHeaderCard.vue'
import SearchFilter from '@/components/common/SearchFilter.vue'
import CardGrid from '@/components/common/CardGrid.vue'
import { getPlazaOperators } from '@/api/operator'
import type { Operator } from '@/types'

const router = useRouter()

const searchKeyword = ref('')
const cardItems = ref<any[]>([])
const total = ref(0)
const pageIndex = ref(1)
const pageSize = ref(12)
const loading = ref(false)

const colorPool = ['#e63946', '#409eff', '#67c23a', '#e6a23c', '#909399', '#9b59b6']
async function fetchData() {
  loading.value = true
  try {
    const res = await getPlazaOperators({
      pageIndex: pageIndex.value,
      pageSize: pageSize.value,
      keyword: searchKeyword.value || undefined,
    })
    total.value = res.total
    cardItems.value = (res.list as Operator[]).map((op, idx) => ({
      id: op.id,
      name: op.name,
      icon: 'Cpu',
      iconBg: colorPool[idx % colorPool.length],
      tags: [op.category, op.type || 'training'],
      description: op.description || '暂无描述',
      ownerLabel: '归属用户',
      ownerValue: op.owner_name || op.owner || '-',
      footerValue: `版本数：${op.version_count ?? 0}`,
    }))
  } catch (e) {
    cardItems.value = []
    total.value = 0
  } finally {
    loading.value = false
  }
}

function handleReset() { searchKeyword.value = ''; fetchData() }

function goDetail(id: string) {
  router.push({ name: 'OperatorDetail', params: { id }, query: { from: 'plaza' } })
}

onMounted(fetchData)
</script>

<style lang="scss" scoped>
.plaza-grid-wrapper {
  min-height: 200px;
}
.plaza-pagination {
  display: flex;
  justify-content: center;
  margin-top: 24px;
}
</style>
