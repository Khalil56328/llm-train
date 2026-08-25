import { get, post, put, del, download, upload } from '@/utils/request'
import type { PaginatedData, Model, ModelVersion, ModelFile, ModelCompareItem } from '@/types'

/** 批量上传结果中的单个文件结果（成功/失败） */
export interface UploadResult {
  id?: string
  fileName: string
  status: string
  size?: number
  errorMessage?: string
}

/** 批量上传返回结构 */
export interface UploadBatchResult {
  batchId: string
  source: string
  files: UploadResult[]
}

const BASE = '/models'

// ========== 模型库 ==========
export function getModelList(params: Record<string, unknown>) {
  return get<PaginatedData<Model>>(BASE, params)
}

export function getModel(id: string) {
  return get<Model>(`${BASE}/${id}`)
}

export function createModel(data: Record<string, unknown>) {
  return post<Model>(BASE, data)
}

export function updateModel(id: string, data: Record<string, unknown>) {
  return put<Model>(`${BASE}/${id}`, data)
}

export function deleteModel(id: string) {
  return del(`${BASE}/${id}`)
}

// ========== 广场 ==========
export function getPlazaModels(params: Record<string, unknown>) {
  return get<PaginatedData<Model>>(`${BASE}/plaza/search`, params)
}

// ========== 版本 ==========
export function getModelVersions(modelId: string) {
  return get<ModelVersion[]>(`${BASE}/${modelId}/versions`)
}

export function getModelVersion(versionId: string) {
  return get<ModelVersion>(`${BASE}/versions/${versionId}`)
}

export function createModelVersion(modelId: string, data: Record<string, unknown>) {
  return post<ModelVersion>(`${BASE}/${modelId}/versions`, data)
}

export function updateModelVersion(modelId: string, versionId: string, data: Record<string, unknown>) {
  return put<ModelVersion>(`${BASE}/${modelId}/versions/${versionId}`, data)
}

export function setDefaultVersion(modelId: string, versionId: string) {
  return put(`${BASE}/${modelId}/versions/${versionId}/default`)
}

export function deleteModelVersion(versionId: string) {
  return del(`${BASE}/versions/${versionId}`)
}

// ========== 模型文件 ==========
export function getModelFiles(versionId: string) {
  return get<ModelFile[]>(`${BASE}/versions/${versionId}/files`)
}

export function deleteModelFile(fileId: string) {
  return del(`${BASE}/files/${fileId}`)
}

export function uploadModelFile(versionId: string, formData: FormData, onProgress?: (percent: number) => void) {
  return upload<ModelFile & { url?: string }>(`${BASE}/versions/${versionId}/files/upload`, formData, onProgress)
}

export function uploadModelFiles(versionId: string, formData: FormData, onProgress?: (percent: number) => void) {
  return upload<UploadBatchResult>(`${BASE}/versions/${versionId}/files/upload-batch`, formData, onProgress)
}

// ========== 模型文件下载 ==========
export function downloadModelVersion(versionId: string, filename?: string) {
  return download(`${BASE}/versions/${versionId}/download`, undefined, filename)
}

export function downloadModelFile(versionId: string, fileId: string, filename?: string) {
  return download(`${BASE}/versions/${versionId}/files/${fileId}/download`, undefined, filename)
}

// ========== 模型对比 ==========
export function compareModels(modelIds: string[]) {
  return post<ModelCompareItem[]>(`${BASE}/compare`, { modelIds })
}

// ========== 统计 ==========
export function getModelStats() {
  return get<{ total: number; publicCount: number }>(`${BASE}/stats/summary`)
}
