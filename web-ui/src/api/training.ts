import { get, post, put, del } from '@/utils/request'
import type { PaginatedData, TrainTask } from '@/types'

const BASE = '/train-tasks'

export function getTaskList(params: Record<string, unknown>) {
  return get<PaginatedData<TrainTask>>(BASE, params)
}

export interface TaskStats {
  pending: number
  running: number
  succeeded: number
  failed: number
  stopped: number
  total: number
}

export function getTaskStats() {
  return get<TaskStats>(`${BASE}/stats`)
}

export function getTaskDetail(id: string) {
  return get<TrainTask>(`${BASE}/${id}`)
}

export function createTask(data: Record<string, unknown>) {
  return post<TrainTask>(BASE, data)
}

export function updateTask(id: string, data: Record<string, unknown>) {
  return put<TrainTask>(`${BASE}/${id}`, data)
}

export function submitTask(id: string) {
  return post(`${BASE}/${id}/submit`)
}

export function pauseTask(id: string) {
  return post(`${BASE}/${id}/pause`)
}

export function resumeTask(id: string) {
  return post(`${BASE}/${id}/resume`)
}

export function cancelTask(id: string) {
  return post(`${BASE}/${id}/cancel`)
}

export function retryTask(id: string) {
  return post(`${BASE}/${id}/retry`)
}

export interface TaskLogItem {
  time: string
  level: string
  message: string
}

export function getTaskLogs(id: string, tail?: number) {
  return get<TaskLogItem[]>(`${BASE}/${id}/logs`, { tail })
}

export interface TaskMetricItem {
  step: number
  loss: number | null
  lr: number | null
}

export function getTaskMetrics(id: string) {
  return get<TaskMetricItem[]>(`${BASE}/${id}/metrics`)
}

// Aliases used by training sub-menu pages
export const getTrainTaskList = getTaskList
export const getTrainTaskDetail = getTaskDetail
export const createTrainTask = createTask
export const updateTrainTask = updateTask
export const submitTrainTask = submitTask
export const stopTrainTask = (id: string) => post(`${BASE}/${id}/stop`)
export const deleteTrainTask = (id: string) => del(`${BASE}/${id}`)
export const getTrainTaskLogs = getTaskLogs
export const getTrainTaskMetrics = getTaskMetrics
