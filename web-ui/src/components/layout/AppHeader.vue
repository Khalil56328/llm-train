<template>
  <div class="app-header">
    <!-- 面包屑 -->
    <div class="header-left">
      <el-breadcrumb separator="/">
        <el-breadcrumb-item :to="{ path: '/' }">
          <el-icon><HomeFilled /></el-icon>
        </el-breadcrumb-item>
        <el-breadcrumb-item
          v-for="(crumb, idx) in breadcrumbs"
          :key="idx"
          :to="idx < breadcrumbs.length - 1 ? crumb.path : undefined"
        >
          {{ crumb.title }}
        </el-breadcrumb-item>
      </el-breadcrumb>
    </div>

    <!-- 右侧操作区 -->
    <div class="header-right">
      <!-- 消息通知 -->
      <el-badge :value="notificationStore.unreadCount" :hidden="notificationStore.unreadCount === 0" :max="99">
        <el-popover placement="bottom" :width="320" trigger="click">
          <template #reference>
            <div class="header-icon-btn">
              <el-icon :size="18"><Bell /></el-icon>
            </div>
          </template>
          <div class="notification-popover">
            <div class="notif-header">
              <span>消息通知</span>
              <el-button type="primary" link @click="notificationStore.markAllRead()">全部已读</el-button>
            </div>
            <div class="notif-list">
              <div
                v-for="n in (notificationStore.notifications || []).slice(0, 5)"
                :key="n.id"
                class="notif-item"
                :class="{ unread: !n.read }"
                @click="notificationStore.markRead(n.id)"
              >
                <div class="notif-title">{{ n.title }}</div>
                <div class="notif-content">{{ n.content }}</div>
                <div class="notif-time">{{ n.createdAt }}</div>
              </div>
              <el-empty v-if="!(notificationStore.notifications || []).length" description="暂无消息" :image-size="48" />
            </div>
          </div>
        </el-popover>
      </el-badge>

      <!-- 用户信息 -->
      <el-dropdown trigger="click" @command="handleUserCommand">
        <div class="header-user">
          <el-avatar :size="32" :icon="UserFilled" />
          <span class="user-name">{{ userStore.userInfo?.nickname || '用户' }}</span>
          <el-icon class="user-arrow"><ArrowDown /></el-icon>
        </div>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item command="profile">
              <el-icon><User /></el-icon> 个人中心
            </el-dropdown-item>
            <el-dropdown-item divided command="logout">
              <el-icon><SwitchButton /></el-icon> 退出登录
            </el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { HomeFilled, Bell, UserFilled, ArrowDown, User, SwitchButton } from '@element-plus/icons-vue'
import { useUserStore, useNotificationStore } from '@/stores'
import { TrainTaskTypeMenuMap } from '@/types'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()
const notificationStore = useNotificationStore()

// 面包屑
// 设计为通用方案：通过路由 meta.parent 定义默认父级，通过 query.from 传递来源上下文，
// 在不同来源下自动替换为对应的面包屑层级链，无需在 AppHeader 中硬编码具体页面名称。
const breadcrumbs = computed(() => {
  const matched = route.matched.filter((r) => r.meta?.title)
  const result = matched.map((r) => ({
    title: r.meta?.title as string,
    path: r.path,
  }))
  // 如果当前路由定义了 parent breadcrumb，插入到最后一项之前
  const currentRoute = matched[matched.length - 1]
  if (currentRoute?.meta?.parent) {
    const parent = currentRoute.meta.parent as { title: string; path: string }

    // 训练任务详情共用路由 /train/task/:id：根据来源 query.from（对应训练子菜单列表路径）展示对应父级面包屑
    if (route.name === 'TrainTaskDetail') {
      const from = route.query.from as string | undefined
      const trainMenu = from && Object.values(TrainTaskTypeMenuMap).find((m) => m.path === from)
      const parentCrumb = trainMenu || parent
      result.splice(result.length - 1, 0, { title: parentCrumb.title, path: parentCrumb.path })
      return result
    }

    // 来源上下文映射：当 query.from 值对应的 parent 存在时，替换父级面包屑
    const fromSource = route.query.from as string | undefined
    const plazaParentTitleMap: Record<string, string> = {
      '算子管理': '算子广场',
      '训练数据集': '数据集广场',
      '评测数据集': '数据集广场',
      '我的模型库': '模型库广场',
    }
    const plazaParentPathMap: Record<string, string> = {
      '算子管理': '/operator/plaza',
      '训练数据集': '/data/plaza',
      '评测数据集': '/data/plaza',
      '我的模型库': '/model/plaza',
    }

    if (fromSource === 'plaza' && plazaParentTitleMap[parent.title]) {
      result.splice(result.length - 1, 0, {
        title: plazaParentTitleMap[parent.title],
        path: plazaParentPathMap[parent.title],
      })
      // 当路由存在 operatorId/datasetId/modelId 参数时，说明当前处于更深层级（如版本详情/编辑），
      // 需额外插入对应模块的详情面包屑以保持层级链完整
      if (route.params.operatorId) {
        result.splice(result.length - 1, 0, {
          title: '算子详情',
          path: `/operator/management/detail/${route.params.operatorId}`,
        })
      } else if (route.params.datasetId) {
        result.splice(result.length - 1, 0, {
          title: '数据集详情',
          path: `/data/training`,
        })
      } else if (route.params.modelId) {
        result.splice(result.length - 1, 0, {
          title: '模型详情',
          path: `/model/my-library`,
        })
      }
    } else {
      result.splice(result.length - 1, 0, { title: parent.title, path: parent.path })
    }
  }
  return result
})

// 用户菜单操作
function handleUserCommand(cmd: string) {
  if (cmd === 'logout') {
    userStore.logout()
    router.push('/login')
  } else if (cmd === 'profile') {
    router.push('/profile')
  }
}
</script>

<style lang="scss" scoped>
.app-header {
  position: fixed;
  top: 0;
  right: 0;
  height: $header-height;
  background: $bg-color-white;
  border-bottom: 1px solid $border-color-light;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 20px;
  z-index: 99;
  transition: left 0.3s;
  left: $sidebar-width;

  // 面包屑
  .header-left {
    .el-breadcrumb {
      font-size: 14px;
    }
  }

  // 右侧操作区
  .header-right {
    display: flex;
    align-items: center;
    gap: 4px;
  }

  .header-icon-btn {
    width: 36px;
    height: 36px;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: 8px;
    cursor: pointer;
    color: $text-secondary;
    transition: all 0.2s;

    &:hover {
      background: $color-primary-opacity;
      color: $color-primary;
    }
  }

  // 用户信息
  .header-user {
    display: flex;
    align-items: center;
    padding: 4px 12px;
    border-radius: 8px;
    cursor: pointer;
    transition: background 0.2s;

    &:hover {
      background: $color-primary-opacity;
    }

    :deep(.el-avatar) {
      border: 2px solid $color-primary;
    }

    .user-name {
      margin-left: 8px;
      font-size: 14px;
      color: $text-primary;
      max-width: 100px;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    .user-arrow {
      margin-left: 4px;
      font-size: 12px;
      color: $text-secondary;
    }
  }
}

// 通知弹窗
.notification-popover {
  .notif-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding-bottom: 10px;
    margin-bottom: 6px;
    border-bottom: 1px solid $border-color-lighter;
    font-weight: 600;
    font-size: 14px;
  }

  .notif-list {
    max-height: 300px;
    overflow-y: auto;
  }

  .notif-item {
    padding: 10px 8px;
    border-radius: 6px;
    cursor: pointer;
    transition: background 0.2s;

    &:hover {
      background: $color-primary-opacity;
    }

    &.unread::before {
      content: '';
      display: inline-block;
      width: 6px;
      height: 6px;
      border-radius: 50%;
      background: $color-primary;
      margin-right: 6px;
      vertical-align: middle;
    }

    .notif-title {
      font-size: 13px;
      color: $text-primary;
      font-weight: 500;
    }

    .notif-content {
      font-size: 12px;
      color: $text-secondary;
      margin-top: 4px;
    }

    .notif-time {
      font-size: 11px;
      color: $text-placeholder;
      margin-top: 6px;
    }
  }
}

// 侧边栏收起时
.sidebar-collapsed .app-header {
  left: $sidebar-collapsed-width;
}
</style>
