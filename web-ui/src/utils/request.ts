import axios, { type AxiosInstance, type InternalAxiosRequestConfig, type AxiosResponse } from 'axios'
import { ElMessage, ElLoading } from 'element-plus'
import type { ApiResponse } from '@/types'

let loadingInstance: ReturnType<typeof ElLoading.service> | null = null
let requestCount = 0

// 创建 Axios 实例
const service: AxiosInstance = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL,
  timeout: 30000,
  headers: { 'Content-Type': 'application/json' },
})

// 显示 loading
function showLoading() {
  if (requestCount === 0 && !loadingInstance) {
    loadingInstance = ElLoading.service({
      lock: true,
      text: '加载中...',
      background: 'rgba(0, 0, 0, 0.1)',
    })
  }
  requestCount++
}

// 隐藏 loading
function hideLoading() {
  requestCount--
  if (requestCount <= 0) {
    requestCount = 0
    loadingInstance?.close()
    loadingInstance = null
  }
}

// 请求拦截器
service.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    // 是否需要 loading（可配置 noLoading）
    if (!config.headers?.noLoading) {
      showLoading()
    }

    // Token 注入
    const token = localStorage.getItem('access_token')
    if (token && config.headers) {
      config.headers.Authorization = `Bearer ${token}`
    }

    return config
  },
  (error) => {
    hideLoading()
    return Promise.reject(error)
  }
)

// 响应拦截器
service.interceptors.response.use(
  (response: AxiosResponse<ApiResponse>) => {
    hideLoading()
    const res = response.data

    // 文件下载等直接返回
    if (response.config.responseType === 'blob') {
      return response
    }

    if (res.code !== 0) {
      ElMessage.error(res.message || '请求失败')
      // 401 未授权 → 跳转登录
      if (res.code === 401) {
        localStorage.removeItem('access_token')
        localStorage.removeItem('refresh_token')
        window.location.href = '/#/login'
      }
      return Promise.reject(new Error(res.message || '请求失败'))
    }

    return response
  },
  (error) => {
    hideLoading()
    const msg = error.response?.data?.message || error.message || '网络异常'
    ElMessage.error(msg)

    if (error.response?.status === 401) {
      localStorage.removeItem('access_token')
      localStorage.removeItem('refresh_token')
      window.location.href = '/#/login'
    }

    return Promise.reject(error)
  }
)

/**
 * 封装请求方法
 */
export function get<T = unknown>(url: string, params?: Record<string, unknown>): Promise<T> {
  return service.get(url, { params }).then((res) => res.data.data)
}

export function post<T = unknown>(url: string, data?: Record<string, unknown>): Promise<T> {
  return service.post(url, data).then((res) => res.data.data)
}

export function put<T = unknown>(url: string, data?: Record<string, unknown>): Promise<T> {
  return service.put(url, data).then((res) => res.data.data)
}

export function del<T = unknown>(url: string, params?: Record<string, unknown>): Promise<T> {
  return service.delete(url, { params }).then((res) => res.data.data)
}

export function download<T = Blob>(
  url: string,
  params?: Record<string, unknown>,
  filename?: string,
): Promise<T> {
  return service
    .get(url, {
      params,
      responseType: 'blob',
      headers: { noLoading: true },
    })
    .then((res) => {
      // 错误响应也是 blob，尝试解析出后端错误信息
      const blob = res.data as Blob
      if (blob.type.includes('application/json')) {
        return blob.text().then((text) => {
          try {
            const parsed = JSON.parse(text)
            ElMessage.error(parsed.message || '下载失败')
          } catch {
            ElMessage.error('下载失败')
          }
          return Promise.reject(new Error('download failed'))
        }) as unknown as T
      }
      // 从响应头解析文件名
      const headerName = parseFilename(res.headers['content-disposition']) || filename
      if (headerName) {
        saveBlob(blob, headerName)
      } else {
        saveBlob(blob, 'download')
      }
      return blob as T
    })
}

function parseFilename(contentDisposition: string | undefined): string {
  if (!contentDisposition) return ''
  // 优先取 filename*=UTF-8''... 格式
  const encoded = /filename\*=UTF-8''([^;]+)/i.exec(contentDisposition)
  if (encoded) {
    try {
      return decodeURIComponent(encoded[1])
    } catch {
      return encoded[1]
    }
  }
  const plain = /filename="?([^";]+)"?/i.exec(contentDisposition)
  return plain ? plain[1] : ''
}

function saveBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(url)
}

export function upload<T = unknown>(
  url: string,
  formData: FormData,
  onProgress?: (percent: number) => void
): Promise<T> {
  return service
    .post(url, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 600000, // 上传超时 10 分钟
      onUploadProgress: (e) => {
        if (e.total && onProgress) {
          onProgress(Math.round((e.loaded * 100) / e.total))
        }
      },
    })
    .then((res) => res.data.data)
}

export default service
