// ============================================
// 算子中心 API
// ============================================
import { get, post, put, del } from '@/utils/request'
import type {
  Operator,
  OperatorVersion,
  OperatorWithVersions,
  PaginatedData,
} from '@/types'

/** 分页查询参数 */
export interface OperatorListQuery {
  pageIndex: number
  pageSize: number
  keyword?: string
  category?: string
  [key: string]: unknown
}

/** 新增算子版本请求体 */
export interface OperatorVersionCreatePayload {
  name: string
  description?: string
  resource_type: 'CPU' | 'GPU'
  base_image?: string
  work_dir?: string
  start_cmd?: string
  mount_dir?: string
  start_params?: Record<string, unknown>
  env_vars?: Record<string, string>
  is_public: boolean
  operator_id: string
}

// ============ 算子 ============
/** 算子列表 */
export const fetchOperatorList = (params: OperatorListQuery) =>
  get<PaginatedData<Operator>>('/operators', params)

/** 算子详情（含版本列表） */
export const fetchOperatorDetail = (id: string) =>
  get<OperatorWithVersions>(`/operators/${id}`)

/** 新增算子 */
export const createOperator = (payload: Partial<Operator>) =>
  post<Operator>('/operators', payload)

/** 更新算子 */
export const updateOperator = (id: string, payload: Partial<Operator>) =>
  put<Operator>(`/operators/${id}`, payload)

/** 删除算子 */
export const deleteOperator = (id: string) => del<{ id: string }>(`/operators/${id}`)

// ============ 算子版本 ============
/** 获取算子的版本列表 */
export const fetchOperatorVersions = (operatorId: string) =>
  get<OperatorVersion[]>(`/operators/${operatorId}/versions`)

/** 获取单个算子版本详情（通过算子下版本列表过滤） */
export const fetchOperatorVersionDetail = async (operatorId: string, versionId: string): Promise<OperatorVersion> => {
  const versions = await fetchOperatorVersions(operatorId)
  const found = versions.find((v) => v.id === versionId)
  if (!found) throw new Error('版本不存在')
  return found
}

/** 新增算子版本 */
export const createOperatorVersion = (
  operatorId: string,
  payload: Omit<OperatorVersionCreatePayload, 'operator_id'>,
) =>
  post<OperatorVersion>(`/operators/${operatorId}/versions`, {
    ...payload,
    operator_id: operatorId,
  })

/** 更新算子版本 */
export const updateOperatorVersion = (
  operatorId: string,
  versionId: string,
  payload: Partial<OperatorVersionCreatePayload>,
) =>
  put<OperatorVersion>(
    `/operators/${operatorId}/versions/${versionId}`,
    payload,
  )

/** 删除算子版本 */
export const deleteOperatorVersion = (operatorId: string, versionId: string) =>
  del<{ id: string }>(`/operators/${operatorId}/versions/${versionId}`)

// ============ 算子广场 ============
/** 算子广场搜索（仅公开算子） */
export const getPlazaOperators = (params: {
  pageIndex: number
  pageSize: number
  keyword?: string
  category?: string
}) => get<PaginatedData<Operator>>('/operators/plaza/search', params)
