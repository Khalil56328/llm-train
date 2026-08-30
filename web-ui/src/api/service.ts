import { get, post, put, del } from '@/utils/request'
import type { PaginatedData, Deployment, EvaluationTask, EvalItem, EvalReport } from '@/types'

const DP_BASE = '/deployments'
const EV_BASE = '/evaluations'

// ========== 部署服务 ==========
export function getDeploymentList(params: Record<string, unknown>) {
  return get<PaginatedData<Deployment>>(DP_BASE, params)
}

export function getDeploymentDetail(id: string) {
  return get<Deployment>(`${DP_BASE}/${id}`)
}

export function createDeployment(data: Record<string, unknown>) {
  return post<Deployment>(DP_BASE, data)
}

export function updateDeployment(id: string, data: Record<string, unknown>) {
  return put<Deployment>(`${DP_BASE}/${id}`, data)
}

export function deleteDeployment(id: string) {
  return del(`${DP_BASE}/${id}`)
}

export function startDeployment(id: string) {
  return post(`${DP_BASE}/${id}/start`)
}

export function stopDeployment(id: string) {
  return post(`${DP_BASE}/${id}/stop`)
}

export function testDeployment(id: string, data: { prompt: string }) {
  return post<{ response: string }>(`${DP_BASE}/${id}/test`, data)
}

export function getDeploymentLogs(id: string, tail = 200) {
  return get<string[]>(`${DP_BASE}/${id}/logs`, { tail })
}

// 流式在线推理（OpenAI 兼容，SSE）。用原生 fetch 读取 event-stream，逐块回调。
export async function chatCompletionsStream(
  deployId: string,
  messages: { role: string; content: string }[],
  onDelta: (text: string) => void,
  signal?: AbortSignal,
): Promise<string> {
  // 与 axios 实例（request.ts baseURL = VITE_API_BASE_URL）保持同一推导：
  // VITE_API_BASE_URL 已含 /api 前缀，未设置时兜底 /api，避免拼出 /api/api/ 双前缀
  const base = (import.meta.env.VITE_API_BASE_URL || '/api').replace(/\/+$/, '')
  const token = localStorage.getItem('access_token') || ''
  const resp = await fetch(`${base}/inference/chat/completions`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ deployId, payload: { messages, stream: true } }),
    signal,
  })
  if (!resp.ok || !resp.body) {
    const text = await resp.text().catch(() => '')
    throw new Error(`推理请求失败: HTTP ${resp.status} ${text}`)
  }
  const reader = resp.body.getReader()
  const decoder = new TextDecoder()
  let full = ''
  let buffer = ''
  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    // 按 SSE 事件块切分（以 \n\n 分隔）
    const parts = buffer.split('\n\n')
    buffer = parts.pop() || ''
    for (const part of parts) {
      const line = part.split('\n').find((l) => l.startsWith('data:'))
      if (!line) continue
      const data = line.slice(5).trim()
      if (data === '[DONE]') continue
      try {
        const obj = JSON.parse(data)
        if (obj?.error) {
          throw new Error(obj.error?.message || '推理服务错误')
        }
        const delta = obj?.choices?.[0]?.delta?.content || obj?.choices?.[0]?.message?.content || ''
        if (delta) {
          full += delta
          onDelta(delta)
        }
      } catch (e) {
        // 仅忽略 JSON 解析失败（上游偶发非 JSON 片段），其余错误（如上游 error 事件）向上抛出
        if (!(e instanceof SyntaxError)) throw e
      }
    }
  }
  return full
}

export function getDeploymentStats() {
  return get<Record<string, number>>(`${DP_BASE}/stats`)
}

export function getDeployInstances(deployId: string) {
  return get<DeployInstance[]>(`${DP_BASE}/${deployId}/instances`)
}

export function getDeployInstance(deployId: string, instanceId: string) {
  return get<DeployInstance>(`${DP_BASE}/${deployId}/instances/${instanceId}`)
}

// ========== 模型评测 ==========
export function getEvaluationList(params: Record<string, unknown>) {
  return get<PaginatedData<EvaluationTask>>(EV_BASE, params)
}

export function getEvaluationDetail(id: string) {
  return get<EvaluationTask>(`${EV_BASE}/${id}`)
}

export function createEvaluation(data: Record<string, unknown>) {
  return post<EvaluationTask>(EV_BASE, data)
}

export function updateEvaluation(id: string, data: Record<string, unknown>) {
  return put<EvaluationTask>(`${EV_BASE}/${id}`, data)
}

export function deleteEvaluation(id: string) {
  return del(`${EV_BASE}/${id}`)
}

export function startEvaluation(id: string) {
  return post(`${EV_BASE}/${id}/start`)
}

export function cancelEvaluation(id: string) {
  return post(`${EV_BASE}/${id}/cancel`)
}

export function getEvalStats(params?: Record<string, unknown>) {
  return get<Record<string, unknown>>(`${EV_BASE}/stats`, params)
}

export function getEvalReport(id: string) {
  return get<Partial<EvalReport>>(`${EV_BASE}/${id}/report`)
}

// 人工评测项
export function getEvalItems(evalId: string, params?: Record<string, unknown>) {
  return get<PaginatedData<EvalItem>>(`${EV_BASE}/${evalId}/items`, params)
}

export function getEvalItem(evalId: string, itemId: string) {
  return get<EvalItem>(`${EV_BASE}/${evalId}/items/${itemId}`)
}

export function scoreEvalItem(evalId: string, itemId: string, data: { score: number }) {
  return post<EvalItem>(`${EV_BASE}/${evalId}/items/${itemId}/score`, data)
}

// ========== 类型定义 ==========
export interface DeployInstance {
  id: string
  deployId: string
  podName: string
  status: string
  hostIp: string
  podIp: string
  createdAt: string
  updatedAt: string
}
