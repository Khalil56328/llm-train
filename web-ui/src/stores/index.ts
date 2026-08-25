import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { UserInfo, MenuItem, DictMap, Notification } from '@/types'
import { get, post } from '@/utils/request'

// ====================================
// 用户状态
// ====================================
export const useUserStore = defineStore(
  'user',
  () => {
    const token = ref<string>('')
    const refreshToken = ref<string>('')
    const userInfo = ref<UserInfo | null>(null)
    const permissions = ref<string[]>([])

    async function login(username: string, password: string) {
      const res = await post<{ accessToken: string; refreshToken?: string; user: UserInfo }>(
        '/auth/login',
        { username, password }
      )
      token.value = res.accessToken
      refreshToken.value = res.refreshToken || ''
      userInfo.value = res.user
      permissions.value = res.user?.permissions || []
      localStorage.setItem('access_token', res.accessToken)
      localStorage.setItem('permissions', JSON.stringify(permissions.value))
      if (res.refreshToken) {
        localStorage.setItem('refresh_token', res.refreshToken)
      } else {
        localStorage.removeItem('refresh_token')
      }
    }

    async function fetchUserInfo() {
      userInfo.value = await get<UserInfo>('/auth/me')
      permissions.value = userInfo.value?.permissions || []
      localStorage.setItem('permissions', JSON.stringify(permissions.value))
    }

    function logout() {
      token.value = ''
      refreshToken.value = ''
      userInfo.value = null
      permissions.value = []
      localStorage.removeItem('access_token')
      localStorage.removeItem('refresh_token')
      localStorage.removeItem('permissions')
    }

    return { token, refreshToken, userInfo, permissions, login, fetchUserInfo, logout }
  },
  { persist: { paths: ['token', 'refreshToken'] } }
)

// ====================================
// 菜单状态
// ====================================
export const useMenuStore = defineStore('menu', () => {
  const menuList = ref<MenuItem[]>([])

  async function fetchMenu() {
    menuList.value = await get<MenuItem[]>('/auth/menu')
  }

  return { menuList, fetchMenu }
})

// ====================================
// 字典状态
// ====================================
export const useDictStore = defineStore('dict', () => {
  const dictMap = ref<DictMap>({})

  async function fetchDict() {
    dictMap.value = await get<DictMap>('/dict/all')
  }

  function getDict(code: string) {
    return dictMap.value[code] || []
  }

  function getDictLabel(code: string, value: string): string {
    const item = dictMap.value[code]?.find((d) => d.value === value)
    return item?.name || value
  }

  return { dictMap, fetchDict, getDict, getDictLabel }
})

// ====================================
// 通知状态
// ====================================
export const useNotificationStore = defineStore('notification', () => {
  const notifications = ref<Notification[]>([])
  const unreadCount = ref(0)

  async function fetchNotifications() {
    // 后端返回分页结构 { list, total, ... }，这里统一提取 list；若直接返回数组也兼容
    const res = await get<{ list: Notification[] }>('/notifications')
    notifications.value = Array.isArray(res) ? res : res?.list || []
    unreadCount.value = notifications.value.filter((n) => !n.read).length
  }

  async function markRead(id: string) {
    // await put(`/notifications/${id}/read`)
    const n = notifications.value.find((n) => n.id === id)
    if (n) n.read = true
    unreadCount.value = notifications.value.filter((n) => !n.read).length
  }

  async function markAllRead() {
    // await put('/notifications/read-all')
    notifications.value.forEach((n) => (n.read = true))
    unreadCount.value = 0
  }

  return { notifications, unreadCount, fetchNotifications, markRead, markAllRead }
})
