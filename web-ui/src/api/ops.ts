import { get, post, put, del } from '@/utils/request'
import type { DockerImage, ResourcePool, PaginatedData } from '@/types'

const BASE = '/images'

/** 分页查询镜像 */
export const fetchImageList = (params: {
  pageIndex: number
  pageSize: number
  keyword?: string
  resource_type?: string
}) => get<PaginatedData<DockerImage>>(BASE, params)

/** 查询镜像详情 */
export const fetchImageDetail = (id: string) => get<DockerImage>(`${BASE}/${id}`)

/** 新增镜像 */
export const createImage = (payload: Partial<DockerImage>) =>
  post<DockerImage>(BASE, payload)

/** 更新镜像 */
export const updateImage = (id: string, payload: Partial<DockerImage>) =>
  put<DockerImage>(`${BASE}/${id}`, payload)

/** 删除镜像 */
export const deleteImage = (id: string) =>
  del<{ id: string; message: string }>(`${BASE}/${id}`)

const POOL_BASE = '/resource-pools'

/** 分页查询资源池 */
export const fetchResourcePoolList = (params: {
  pageIndex: number
  pageSize: number
  keyword?: string
  status?: string
}) => get<PaginatedData<ResourcePool>>(POOL_BASE, params)

/** 查询资源池详情 */
export const fetchResourcePoolDetail = (id: string) => get<ResourcePool>(`${POOL_BASE}/${id}`)

/** 新增资源池 */
export const createResourcePool = (payload: Partial<ResourcePool>) =>
  post<ResourcePool>(POOL_BASE, payload)

/** 更新资源池 */
export const updateResourcePool = (id: string, payload: Partial<ResourcePool>) =>
  put<ResourcePool>(`${POOL_BASE}/${id}`, payload)

/** 删除资源池 */
export const deleteResourcePool = (id: string) =>
  del<{ id: string; message: string }>(`${POOL_BASE}/${id}`)
