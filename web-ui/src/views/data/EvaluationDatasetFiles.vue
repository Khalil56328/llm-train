<template>
  <DatasetFilePanel :datasetId="datasetId" />
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import DatasetFilePanel from '@/components/dataset/DatasetFilePanel.vue'

const route = useRoute()
const datasetId = computed(() => route.params.id as string)
</script>
