<template>
  <div class="card-grid">
    <div
      v-for="item in items"
      :key="item.id"
      class="model-card"
      @click="$emit('select', item.id)"
    >
      <!-- 图标 -->
      <div class="card-icon" :style="{ background: item.iconBg || iconBg }">
        <el-icon :size="24" v-if="item.icon">
          <component :is="item.icon" />
        </el-icon>
        <span v-else class="card-icon-text">{{ item.name.charAt(0) }}</span>
      </div>

      <!-- 名称 -->
      <div class="card-name">{{ item.name }}</div>

      <!-- 标签 -->
      <div class="card-tags" v-if="item.tags?.length">
        <el-tag
          v-for="tag in item.tags"
          :key="tag"
          size="small"
          type="info"
        >
          {{ tag }}
        </el-tag>
      </div>

      <!-- 描述 -->
      <div class="card-desc" v-if="item.description">
        {{ item.description }}
      </div>

      <!-- 底部信息 -->
      <div class="card-footer">
        <span v-if="item.ownerLabel">{{ item.ownerLabel }}: {{ item.ownerValue }}</span>
        <span v-if="item.footerLabel">{{ item.footerLabel }}: {{ item.footerValue }}</span>
        <span v-else>{{ item.ownerValue }}</span>
      </div>

      <!-- 操作 -->
      <div class="card-actions" v-if="$slots.actions">
        <slot name="actions" :item="item" />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { CardItem } from './types'

withDefaults(
  defineProps<{
    items: CardItem[]
    iconBg?: string
  }>(),
  { iconBg: '#e63946' }
)

defineEmits<{
  select: [id: string]
}>()
</script>

<style lang="scss" scoped>
.card-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 16px;
}

.model-card {
  background: $bg-color-white;
  border: 1px solid $border-color-light;
  border-radius: $border-radius-large;
  padding: 20px;
  cursor: pointer;
  transition: $transition-base;
  position: relative;

  &:hover {
    border-color: $color-primary;
    box-shadow: $box-shadow-base;
    transform: translateY(-2px);
  }

  .card-icon {
    width: 48px;
    height: 48px;
    border-radius: 12px;
    display: flex;
    align-items: center;
    justify-content: center;
    margin-bottom: 14px;
    color: #fff;

    .card-icon-text {
      font-size: 20px;
      font-weight: 700;
    }
  }

  .card-name {
    font-size: 15px;
    font-weight: 600;
    color: $text-primary;
    margin-bottom: 6px;
  }

  .card-tags {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    margin-bottom: 8px;
  }

  .card-desc {
    font-size: $font-size-mini;
    color: $text-secondary;
    line-height: 1.5;
    margin-bottom: 12px;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }

  .card-footer {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding-top: 12px;
    border-top: 1px solid $border-color-lighter;
    font-size: $font-size-mini;
    color: $text-secondary;
  }

  .card-actions {
    position: absolute;
    top: 16px;
    right: 16px;
  }
}
</style>
