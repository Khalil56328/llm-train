<template>
  <div class="step-cards">
    <div
      v-for="(item, idx) in steps"
      :key="item.step ?? idx + 1"
      class="step-card"
      :class="{ active: (item.step ?? idx + 1) === current, completed: (item.step ?? idx + 1) < current }"
    >
      <div class="step-header">
        <div class="step-number">
          <el-icon v-if="(item.step ?? idx + 1) < current" :size="16"><Check /></el-icon>
          <span v-else>{{ item.step ?? idx + 1 }}</span>
        </div>
        <div class="step-title">{{ item.title }}</div>
      </div>
      <div class="step-desc">{{ item.desc }}</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { Check } from '@element-plus/icons-vue'
import type { StepItem } from './types'

const props = withDefaults(
  defineProps<{
    steps: StepItem[]
    current?: number
  }>(),
  { current: 1 }
)
</script>

<style lang="scss" scoped>
.step-cards {
  display: flex;
  gap: 16px;
  margin-bottom: 24px;
  flex-wrap: nowrap;

  .step-card {
    flex: 1;
    background: $bg-color-white;
    border: 1px solid $border-color-light;
    border-radius: $border-radius-large;
    padding: 20px;
    position: relative;
    transition: all 0.3s;

    // 步骤间箭头
    &:not(:last-child)::after {
      content: '';
      position: absolute;
      right: -18px;
      top: 50%;
      transform: translateY(-50%);
      width: 20px;
      height: 2px;
      background: $border-color;
    }

    &.active {
      border-color: $color-primary;
      background: $color-primary-opacity;
      box-shadow: 0 0 0 1px rgba($color-primary, 0.1);

      .step-number {
        background: $color-primary;
        border-color: $color-primary;
        color: #fff;
      }

      .step-title {
        color: $color-primary;
      }

      &:not(:last-child)::after {
        background: $color-primary-light;
      }
    }

    &.completed {
      border-color: $color-primary-light;

      .step-number {
        background: $color-success;
        border-color: $color-success;
        color: #fff;
      }

      .step-title {
        color: $color-success;
      }
    }

    .step-header {
      display: flex;
      align-items: center;
      margin-bottom: 10px;

      .step-number {
        width: 32px;
        height: 32px;
        border-radius: 50%;
        border: 2px solid $border-color;
        background: #fff;
        display: flex;
        align-items: center;
        justify-content: center;
        font-weight: 700;
        font-size: 14px;
        color: $text-secondary;
        margin-right: 12px;
        flex-shrink: 0;
        transition: all 0.3s;
      }

      .step-title {
        font-size: 15px;
        font-weight: 600;
        color: $text-primary;
        transition: color 0.3s;
      }
    }

    .step-desc {
      font-size: $font-size-mini;
      color: $text-secondary;
      line-height: 1.5;
      padding-left: 44px;
    }
  }
}
</style>