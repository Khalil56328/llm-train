import type { App } from 'vue'

// 权限指令 v-permission（支持 "*" 通配与多权限"任一匹配"）
function permissionDirective(el: HTMLElement, binding: { value: string | string[] }) {
  const permissions: string[] = JSON.parse(localStorage.getItem('permissions') || '[]')
  if (permissions.includes('*')) return

  const required = Array.isArray(binding.value) ? binding.value : [binding.value]
  const hasPermission = required.some((p) => permissions.includes(p))

  if (!hasPermission) {
    el.parentNode?.removeChild(el)
  }
}

// 点击外部指令 v-click-outside
function clickOutsideDirective(el: HTMLElement, binding: { value: () => void }) {
  const handler = (e: MouseEvent) => {
    if (!el.contains(e.target as Node)) {
      binding.value()
    }
  }
  document.addEventListener('click', handler)
  ;(el as unknown as Record<string, unknown>)._clickOutside = handler
}

export function setupDirectives(app: App) {
  app.directive('permission', {
    mounted: permissionDirective,
  })

  app.directive('click-outside', {
    mounted: clickOutsideDirective,
    unmounted(el: HTMLElement) {
      const handler = (el as unknown as Record<string, unknown>)._clickOutside as () => void
      if (handler) {
        document.removeEventListener('click', handler)
      }
    },
  })
}
