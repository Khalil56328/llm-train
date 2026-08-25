import { createApp } from 'vue'
import { createPinia } from 'pinia'
import piniaPluginPersistedstate from 'pinia-plugin-persistedstate'
import ElementPlus from 'element-plus'
import zhCn from 'element-plus/es/locale/lang/zh-cn'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'
import App from './App.vue'
import router from './router'
import { setupDirectives } from './directives'
import 'element-plus/dist/index.css'
import './assets/styles/global.scss'

// ---------------------------------------------------------------------------
// 过滤浏览器级良性告警
// "ResizeObserver loop completed with undelivered notifications" 由 Element Plus
// 的 el-table / el-select 等组件在嵌入式 WebView 中进行尺寸自动测量时触发，
// 属浏览器已知良性提示，不影响功能。浏览器会将其作为 window error 事件派发，
// 若不拦截会被 IDE WebView / 全局错误统计误报为页面异常。
// ---------------------------------------------------------------------------
const BENIGN_ERROR_MESSAGES = [
  'ResizeObserver loop completed with undelivered notifications',
  'ResizeObserver loop limit exceeded',
]

function isBenignError(message: string) {
  return BENIGN_ERROR_MESSAGES.some((s) => message.includes(s))
}

window.addEventListener('error', (event) => {
  if (isBenignError(event.message || '')) {
    event.preventDefault()
  }
})

window.addEventListener('unhandledrejection', (event) => {
  const reason = event.reason instanceof Error ? event.reason.message : String(event.reason ?? '')
  if (isBenignError(reason)) {
    event.preventDefault()
  }
})

const app = createApp(App)

// Element Plus 中文语言包
app.use(ElementPlus, { locale: zhCn })

// 全局注册 Element Plus 图标（用于侧边栏动态渲染）
for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
  app.component(key, component)
}

// Pinia 状态管理 (含持久化插件)
const pinia = createPinia()
pinia.use(piniaPluginPersistedstate)
app.use(pinia)

// 路由
app.use(router)

// 自定义指令
setupDirectives(app)

app.mount('#app')
