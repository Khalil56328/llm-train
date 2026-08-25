<template>
  <div class="page-header-card">
    <div class="header-content">
      <div class="header-left">
        <div class="header-title">{{ title }}</div>
        <div v-if="desc || $slots.desc" class="header-desc">
          <slot name="desc">{{ desc }}</slot>
        </div>
      </div>
      <div class="header-right">
        <slot name="extra">
          <svg class="deco-icon" viewBox="0 0 80 80" width="80" height="80">
            <circle cx="40" cy="40" r="36" fill="rgba(212,48,48,0.08)" />
            <circle cx="40" cy="40" r="24" fill="rgba(212,48,48,0.06)" />
            <circle cx="40" cy="40" r="12" fill="rgba(212,48,48,0.04)" />
          </svg>
        </slot>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  title: string
  desc?: string
}>()
</script>

<style lang="scss" scoped>
.page-header-card {
  background: linear-gradient(135deg, $color-primary-opacity 0%, $bg-color-white 100%);
  border: 1px solid $border-color-light;
  border-radius: $border-radius-large;
  padding: 20px 24px;
  margin-bottom: 16px;
  position: relative;
  overflow: hidden;

  .header-content {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
  }

  .header-left {
    flex: 1;
    min-width: 0;
  }

  .header-title {
    font-size: 18px;
    font-weight: 600;
    color: $color-primary;
    display: flex;
    align-items: center;

    &::before {
      content: '';
      display: inline-block;
      width: 4px;
      height: 20px;
      background: $color-primary;
      border-radius: 2px;
      margin-right: 10px;
    }
  }

  .header-desc {
    margin-top: 8px;
    font-size: $font-size-small;
    color: $text-secondary;
    line-height: 1.6;
    padding-left: 14px;
  }

  .header-right {
    flex-shrink: 0;
    margin-left: 16px;

    .deco-icon {
      opacity: 0.6;
    }
  }
}
</style>
