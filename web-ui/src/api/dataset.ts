import { get, post, put, del, upload, download } from '@/utils/request'
import type { PaginatedData, Dataset, DatasetFile, CollectTask } from '@/types'

const BASE = '/datasets'

export function getDatasetList(params: Record<string, unknown>) {
  return get<PaginatedData<Dataset>>(BASE, params)
}

export function createDataset(data: Record<string, unknown>) {
  return post<Dataset>(BASE, data)
}

export function updateDataset(id: string, data: Record<string, unknown>) {
  return put<Dataset>(`${BASE}/${id}`, data)
}

export function deleteDataset(id: string) {
  return del(`${BASE}/${id}`)
}

export function getDatasetDetail(id: string) {
  return get<Dataset>(`${BASE}/${id}`)
}

export function getDatasetVersions(id: string) {
  return get<{ version: string; storagePath: string }[]>(`${BASE}/${id}/versions`)
}

export function previewDataset(id: string, version: string) {
  return get<Record<string, unknown>[]>(`${BASE}/${id}/preview`, { version })
}

// ========== 文件 ==========
export function getDatasetFiles(id: string, params: Record<string, unknown>) {
  return get<PaginatedData<DatasetFile>>(`${BASE}/${id}/files`, params)
}

export function getDatasetFileStats(id: string) {
  return get<{ fileCount: number; success: number; failed: number; processing: number; totalSize: number }>(
    `${BASE}/${id}/files/stats`,
  )
}

export function uploadDatasetFile(id: string, formData: FormData, onProgress?: (percent: number) => void) {
  return upload<DatasetFile>(`${BASE}/${id}/files/upload`, formData, onProgress)
}

export function uploadDatasetFiles(id: string, formData: FormData, onProgress?: (percent: number) => void) {
  return upload<{ batchId: string; source: string; files: DatasetFile[] }>(
    `${BASE}/${id}/files/upload-batch`,
    formData,
    onProgress,
  )
}

export function deleteDatasetFile(fileId: string) {
  return del(`${BASE}/files/${fileId}`)
}

export function getCollectTasks(id: string) {
  return get<CollectTask[]>(`${BASE}/${id}/files/collect-tasks`)
}

export function downloadDatasetFile(id: string, fileId: string, fallbackName?: string) {
  return download<Blob>(`${BASE}/${id}/files/${fileId}/download`, undefined, fallbackName)
}

export function downloadTemplate(name: string) {
  return download<Blob>(`${BASE}/templates/${name}`, undefined, `example_${name}.jsonl`)
}

// ========== ModelScope 下载 ==========
export function importFromModelscope(
  id: string,
  formData: FormData,
  onProgress?: (percent: number) => void,
) {
  return upload<{ repoId: string; batchId: string; source: string; files: DatasetFile[] }>(
    `${BASE}/${id}/files/modelscope`,
    formData,
    onProgress,
  )
}

// ========== 广场 ==========
export function getPlazaDatasets(params: Record<string, unknown>) {
  return get<PaginatedData<Dataset>>(`${BASE}/plaza/search`, params)
}

export function importDataset(id: string) {
  return post(`${BASE}/${id}/import`)
}

export function downloadDataset(id: string, fallbackName?: string) {
  return download<Blob>(`${BASE}/${id}/download`, undefined, fallbackName)
}

export function importFromHuggingFace(data: { url: string; name: string }) {
  return post(`${BASE}/import-hf`, data)
}
