<template>
  <div class="app-layout" :class="{ 'sidebar-collapsed': isCollapsed }">
    <!-- 侧边栏 -->
    <AppSidebar v-model:collapsed="isCollapsed" />

    <!-- 主区域 -->
    <div class="app-main-wrap">
      <!-- 顶部栏 -->
      <AppHeader />

      <!-- 内容主体 -->
      <div class="app-main-content">
        <router-view v-slot="{ Component }">
          <transition name="fade" mode="out-in">
            <component :is="Component" />
          </transition>
        </router-view>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import AppSidebar from './AppSidebar.vue'
import AppHeader from './AppHeader.vue'
import { useUserStore, useMenuStore, useDictStore, useNotificationStore } from '@/stores'
import { useRouter } from 'vue-router'

const router = useRouter()
const userStore = useUserStore()
const menuStore = useMenuStore()
const dictStore = useDictStore()
const notificationStore = useNotificationStore()

const isCollapsed = ref(false)

onMounted(async () => {
  try {
    // 关键请求：用户信息 + 菜单
    await Promise.all([
      userStore.fetchUserInfo(),
      menuStore.fetchMenu(),
    ])
  } catch (e) {
    // Token 失效跳登录
    router.push('/login')
    return
  }

  // 非关键请求：字典 + 通知，失败不影响页面
  try {
    await dictStore.fetchDict()
  } catch { /* 忽略 */ }
  try {
    await notificationStore.fetchNotifications()
  } catch { /* 忽略 */ }
})
</script>

<style lang="scss" scoped>
.app-layout {
  height: 100vh;
  overflow: hidden;
}

.app-main-wrap {
  height: 100%;
  margin-left: $sidebar-width;
  transition: margin-left 0.3s;
  display: flex;
  flex-direction: column;
}

.app-main-content {
  margin-top: $header-height;
  flex: 1;
  overflow-y: auto;
  padding: $content-padding;
  background: $bg-color;
  min-width: 0;
}

.sidebar-collapsed .app-main-wrap {
  margin-left: $sidebar-collapsed-width;
}
</style>
