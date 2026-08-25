<template>
  <div class="app-sidebar" :class="{ collapsed: isCollapsed }">
    <!-- Logo 区域 -->
    <div class="sidebar-logo" @click="$router.push('/')">
      <div class="logo-icon">
        <svg viewBox="0 0 36 36" width="30" height="30">
          <rect width="36" height="36" rx="8" fill="#d43030" />
          <text x="18" y="25" text-anchor="middle" fill="white" font-size="14" font-weight="bold" font-family="sans-serif">AI</text>
        </svg>
      </div>
      <span v-show="!isCollapsed" class="logo-text">训推平台</span>
    </div>

    <!-- 菜单区域 -->
    <div class="sidebar-menu-wrap">
      <el-menu
        :default-active="activeMenu"
        :collapse="isCollapsed"
        :unique-opened="true"
        background-color="transparent"
        text-color="#a0aec0"
        active-text-color="#ffffff"
        @select="handleSelect"
      >
        <template v-for="item in menuList" :key="item.id">
          <!-- 无子菜单 -->
          <el-menu-item v-if="!item.children?.length" :index="item.path">
            <el-icon v-if="item.icon"><component :is="item.icon" /></el-icon>
            <template #title>{{ item.name }}</template>
          </el-menu-item>
          <!-- 有子菜单 -->
          <el-sub-menu v-else :index="item.id">
            <template #title>
              <el-icon v-if="item.icon"><component :is="item.icon" /></el-icon>
              <span>{{ item.name }}</span>
            </template>
            <el-menu-item
              v-for="child in item.children"
              :key="child.id"
              :index="child.path"
            >
              <span class="sub-dot" />
              <span>{{ child.name }}</span>
            </el-menu-item>
          </el-sub-menu>
        </template>
      </el-menu>
    </div>

    <!-- 收起按钮 -->
    <div class="sidebar-toggle" @click="toggleCollapse">
      <el-icon :size="16">
        <DArrowLeft v-if="!isCollapsed" />
        <DArrowRight v-else />
      </el-icon>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { DArrowLeft, DArrowRight } from '@element-plus/icons-vue'
import { useMenuStore } from '@/stores'

const route = useRoute()
const router = useRouter()
const menuStore = useMenuStore()

const isCollapsed = defineModel<boolean>('collapsed', { default: false })
const menuList = computed(() => menuStore.menuList)

// 当前激活菜单
const activeMenu = computed(() => {
  return route.path
})

// 菜单选择
function handleSelect(path: string) {
  router.push(path)
}

// 收起 / 展开
function toggleCollapse() {
  isCollapsed.value = !isCollapsed.value
}
</script>

<style lang="scss" scoped>
.app-sidebar {
  position: fixed;
  left: 0;
  top: 0;
  bottom: 0;
  width: $sidebar-width;
  background: $bg-sidebar;
  display: flex;
  flex-direction: column;
  z-index: 100;
  transition: width 0.3s;
  box-shadow: 2px 0 8px rgba(0, 0, 0, 0.15);

  &.collapsed {
    width: $sidebar-collapsed-width;
  }

  // Logo
  .sidebar-logo {
    height: $header-height;
    display: flex;
    align-items: center;
    padding: 0 16px;
    cursor: pointer;
    flex-shrink: 0;
    transition: padding 0.3s;
    border-bottom: 1px solid rgba(255, 255, 255, 0.06);

    .logo-icon {
      flex-shrink: 0;
    }

    .logo-text {
      margin-left: 10px;
      font-size: 18px;
      font-weight: 700;
      color: #ffffff;
      white-space: nowrap;
      overflow: hidden;
      letter-spacing: 2px;
    }

    .collapsed & {
      padding: 0 17px;
      justify-content: center;
    }
  }

  // 菜单
  .sidebar-menu-wrap {
    flex: 1;
    overflow-y: auto;
    overflow-x: hidden;

    &::-webkit-scrollbar {
      width: 0;
    }

    .el-menu {
      border-right: none;

      .el-menu-item {
        height: 44px;
        line-height: 44px;
        font-size: $font-size-base;
        margin: 2px 8px;
        border-radius: 6px;
        padding-left: 20px !important;

        &.is-active {
          background-color: $sidebar-active-bg;
          color: $sidebar-active-text;
          position: relative;

          &::before {
            content: '';
            position: absolute;
            left: -8px;
            top: 50%;
            transform: translateY(-50%);
            width: 3px;
            height: 20px;
            background: $color-primary;
            border-radius: 0 2px 2px 0;
          }
        }

        &:hover {
          color: #ffffff;
          background-color: rgba(255, 255, 255, 0.06);
        }
      }

      .el-sub-menu {
        .el-sub-menu__title {
          height: 44px;
          line-height: 44px;
          font-size: $font-size-base;
          margin: 2px 8px;
          border-radius: 6px;
          padding-left: 20px !important;

          &:hover {
            color: #ffffff;
            background-color: rgba(255, 255, 255, 0.06);
          }

          .el-sub-menu__icon-arrow {
            color: $sidebar-text;
          }
        }

        &.is-active .el-sub-menu__title {
          color: #ffffff;
          font-weight: 600;
        }

        // 子菜单项 - 右缩进
        :deep(.el-menu) {
          background-color: transparent !important;

          .el-menu-item {
            height: 40px;
            line-height: 40px;
            font-size: 13px;
            padding-left: 50px !important;
            min-width: auto;

            .sub-dot {
              display: inline-block;
              width: 6px;
              height: 6px;
              border-radius: 50%;
              background: $sidebar-text;
              margin-right: 8px;
              flex-shrink: 0;
              transition: background 0.2s;
            }

            &.is-active {
              color: $sidebar-active-text;
              background-color: $sidebar-active-bg;

              .sub-dot {
                background: $color-primary;
              }

              &::before {
                display: none;
              }
            }

            &:hover {
              color: #ffffff;
              background-color: rgba(255, 255, 255, 0.06);

              .sub-dot {
                background: #ffffff;
              }
            }
          }
        }
      }
    }
  }

  // 收起 / 展开
  .sidebar-toggle {
    height: 40px;
    display: flex;
    align-items: center;
    justify-content: center;
    border-top: 1px solid rgba(255, 255, 255, 0.06);
    cursor: pointer;
    color: $sidebar-text;
    flex-shrink: 0;
    transition: all 0.2s;

    &:hover {
      background: rgba(255, 255, 255, 0.06);
      color: #ffffff;
    }
  }
}
</style>
