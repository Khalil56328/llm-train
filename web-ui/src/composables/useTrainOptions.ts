import { ref, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { useUserStore } from '@/stores'
import { getModelList, getModelVersions } from '@/api/model'
import { getDatasetList, getDatasetVersions } from '@/api/dataset'
import { fetchOperatorList, fetchOperatorVersions } from '@/api/operator'
import type { HierarchicalItem } from '@/components/common/HierarchicalSelect.vue'
import type { Dataset, DatasetVersion, Operator, OperatorVersion, Model, ModelVersion } from '@/types'

export type ScopeType = 'public' | 'mine'

export interface DatasetOptionItem {
  id: string
  name: string
  scope?: ScopeType
}

export interface ModelOptionItem {
  id: string
  name: string
  scope?: ScopeType
  versions?: { id: string; name: string }[]
}

export interface OperatorOptionItem {
  id: string
  name: string
  scope?: ScopeType
  versions?: { id: string; name: string }[]
}

/** 版本节点（携带分组信息，供级联选择器按分组过滤） */
export interface VersionOption {
  id: string
  name: string
  scope: ScopeType[]
}

export function useTrainOptions() {
  const userStore = useUserStore()
  const currentUserId = computed(() => userStore.userInfo?.id)

  const datasetList = ref<Dataset[]>([])
  const modelList = ref<Model[]>([])
  const operatorList = ref<Operator[]>([])
  const datasetVersionMap = ref<Record<string, VersionOption[]>>({})
  const modelVersionMap = ref<Record<string, VersionOption[]>>({})
  const operatorVersionMap = ref<Record<string, VersionOption[]>>({})

  function resolveScopes(item: {
    isPublic?: boolean
    is_public?: boolean
    ownerId?: string | number | null
    owner_id?: string | number | null
    owner?: string | number | null
  }): ScopeType[] {
    const scopes: ScopeType[] = []
    const isPublic = !!(item.isPublic ?? item.is_public)
    const ownerId = item.ownerId ?? item.owner_id ?? item.owner
    if (isPublic) {
      scopes.push('public')
    }
    if (ownerId !== undefined && ownerId !== null && String(ownerId) === String(currentUserId.value)) {
      scopes.push('mine')
    }
    return scopes
  }

  /** 计算版本的分组：公开版本进「公开」，属于当前用户的版本进「我的」 */
  function resolveVersionScopes(
    version: {
      isPublic?: boolean
      is_public?: boolean
      creator?: string | number | null
      createdBy?: string | number | null
      ownerId?: string | number | null
      owner_id?: string | number | null
    },
    parent: { isPublic?: boolean; is_public?: boolean; ownerId?: string | number | null; owner_id?: string | number | null; owner?: string | number | null }
  ): ScopeType[] {
    const scopes: ScopeType[] = []
    const versionIsPublic = version.isPublic ?? version.is_public
    if (versionIsPublic === undefined) {
      // 后端未提供版本级公开状态时，跟随父级公开状态（兼容旧数据）
      if (resolveScopes(parent).includes('public')) scopes.push('public')
    } else if (versionIsPublic) {
      scopes.push('public')
    }
    if (resolveScopes(parent).includes('mine')) {
      scopes.push('mine')
    }
    const versionOwner = version.creator ?? version.createdBy ?? version.ownerId ?? version.owner_id
    if (
      versionOwner !== undefined &&
      versionOwner !== null &&
      String(versionOwner) === String(currentUserId.value) &&
      !scopes.includes('mine')
    ) {
      scopes.push('mine')
    }
    return scopes
  }

  async function loadDatasetOptions(dataType?: string) {
    try {
      const res = await getDatasetList({
        pageIndex: 1,
        pageSize: 9999,
        // 仅保留训练数据集（后端按 type 过滤）
        dataset_type: 'training',
        // 按训练方式对应的数据类型过滤（如 SFT/DPO/CPT），限定可选数据集与任务匹配
        ...(dataType ? { data_type: dataType } : {}),
      })
      datasetList.value = (res.list || []).filter((d: Dataset) => d.type === 'training')
      await loadDatasetVersions(datasetList.value)
    } catch (error) {
      ElMessage.error('加载数据集列表失败')
    }
  }

  async function loadDatasetVersions(items: Dataset[]) {
    const map: Record<string, VersionOption[]> = {}
    await Promise.all(
      items.map(async (item) => {
        try {
          const versions = await getDatasetVersions(item.id)
          map[item.id] =
            versions.map((v: DatasetVersion) => ({
              id: v.id || v.version,
              name: v.version,
              // 数据集版本无公开/私有标识，默认两个分组都展示
              scope: ['public', 'mine'],
            })) || []
        } catch {
          map[item.id] = []
        }
      })
    )
    datasetVersionMap.value = map
  }

  async function loadModelOptions() {
    try {
      const res = await getModelList({ pageIndex: 1, pageSize: 9999 })
      modelList.value = res.list || []
      await loadModelVersions(modelList.value)
    } catch (error) {
      ElMessage.error('加载模型列表失败')
    }
  }

  async function loadModelVersions(items: Model[]) {
    const map: Record<string, VersionOption[]> = {}
    await Promise.all(
      items.map(async (item) => {
        try {
          const versions = await getModelVersions(item.id)
          map[item.id] =
            versions.map((v: ModelVersion) => ({
              id: v.id || v.version,
              name: v.version,
              scope: resolveVersionScopes(v, item),
            })) || []
        } catch {
          map[item.id] = []
        }
      })
    )
    modelVersionMap.value = map
  }

  async function loadOperatorOptions() {
    try {
      const res = await fetchOperatorList({ pageIndex: 1, pageSize: 9999 })
      operatorList.value = res.list || []
      await loadOperatorVersions(operatorList.value)
    } catch (error) {
      ElMessage.error('加载算子列表失败')
    }
  }

  async function loadOperatorVersions(items: Operator[]) {
    const map: Record<string, VersionOption[]> = {}
    await Promise.all(
      items.map(async (item) => {
        try {
          const versions = await fetchOperatorVersions(item.id)
          map[item.id] =
            versions.map((v: OperatorVersion) => ({
              id: v.id || v.name,
              name: v.name,
              scope: resolveVersionScopes(v, item),
            })) || []
        } catch {
          map[item.id] = []
        }
      })
    )
    operatorVersionMap.value = map
  }

  const datasetOptions = computed<DatasetOptionItem[]>(() =>
    datasetList.value.map((d: Dataset) => ({
      id: d.id,
      name: d.name,
      scope: resolveScopes(d)[0],
    }))
  )

  const modelOptions = computed<ModelOptionItem[]>(() =>
    modelList.value.map((m: Model) => ({
      id: m.id,
      name: m.name,
      scope: resolveScopes(m)[0],
      versions: modelVersionMap.value[m.id],
    }))
  )

  const operatorOptions = computed<OperatorOptionItem[]>(() =>
    operatorList.value.map((o: Operator) => ({
      id: o.id,
      name: o.name,
      scope: resolveScopes(o)[0],
      versions: operatorVersionMap.value[o.id],
    }))
  )

  const datasetTree = computed<HierarchicalItem[]>(() =>
    datasetList.value.map((d: Dataset) => {
      const scopes = resolveScopes(d)
      const versions = datasetVersionMap.value[d.id] || []
      return {
        id: d.id,
        name: `${d.name}${d.sampleCount ? ` (${d.sampleCount}条)` : ''}`,
        scope: scopes,
        children: versions.length
          ? versions.map((v) => ({ id: v.id, name: v.name, scope: v.scope }))
          : undefined,
      }
    })
  )

  const modelTree = computed<HierarchicalItem[]>(() =>
    modelList.value.map((m: Model) => {
      const scopes = resolveScopes(m)
      const versions = modelVersionMap.value[m.id] || []
      return {
        id: m.id,
        name: m.name,
        scope: scopes,
        children: versions.length
          ? versions.map((v) => ({ id: v.id, name: v.name, scope: v.scope }))
          : undefined,
      }
    })
  )

  const operatorTree = computed<HierarchicalItem[]>(() =>
    operatorList.value.map((o: Operator) => {
      const scopes = resolveScopes(o)
      const versions = operatorVersionMap.value[o.id] || []
      // 算子级公开性：与算子广场可见性规则一致（后端 is_public=true 筛选同样按
      // “存在至少一个公开版本即视为公开”计算），算子自身公开或存在公开版本，
      // 都应出现在「公开」分组下，与“基础模型”字段的展示保持一致。
      if (
        !scopes.includes('public') &&
        versions.some((v) => v.scope.includes('public'))
      ) {
        scopes.push('public')
      }
      return {
        id: o.id,
        name: o.name,
        scope: scopes,
        children: versions.length
          ? versions.map((v) => ({ id: v.id, name: v.name, scope: v.scope }))
          : undefined,
      }
    })
  )

  /** 编辑回显兜底：若给定数据集已不在当前列表（可能被 data_type 过滤掉），补拉全量并合并 */
  async function ensureDatasetById(id?: string) {
    if (!id || datasetList.value.some((d) => d.id === id)) return
    try {
      const res = await getDatasetList({ pageIndex: 1, pageSize: 9999, dataset_type: 'training' })
      const all = (res.list || []).filter((d: Dataset) => d.type === 'training')
      const knownIds = new Set(datasetList.value.map((d) => d.id))
      const extra = all.filter((d) => !knownIds.has(d.id))
      if (!extra.length) return
      datasetList.value = [...datasetList.value, ...extra]
      await loadDatasetVersions(extra)
    } catch {
      /* 兜底失败不阻塞页面 */
    }
  }

  function findDatasetName(id: string) {
    const item = datasetList.value.find((d) => d.id === id)
    return item ? `${item.name}${item.sampleCount ? ` (${item.sampleCount}条)` : ''}` : id
  }

  function findModelName(id: string) {
    const item = modelList.value.find((m) => m.id === id)
    return item ? item.name : id
  }

  function findOperatorName(id: string) {
    const item = operatorList.value.find((o) => o.id === id)
    return item ? item.name : id
  }

  function findDatasetVersionName(id: string, version: string) {
    return datasetVersionMap.value[id]?.find((v) => v.id === version)?.name || version
  }

  function findModelVersionName(id: string, version: string) {
    return modelVersionMap.value[id]?.find((v) => v.id === version)?.name || version
  }

  function findOperatorVersionName(id: string, version: string) {
    return operatorVersionMap.value[id]?.find((v) => v.id === version)?.name || version
  }

  function findItemName(id: string, type: 'dataset' | 'model' | 'operator') {
    if (type === 'dataset') return findDatasetName(id)
    if (type === 'model') return findModelName(id)
    return findOperatorName(id)
  }

  function buildCascaderValue(
    id: string,
    type: 'dataset' | 'model' | 'operator',
    version?: string
  ): string {
    const list: (Dataset | Model | Operator)[] =
      type === 'dataset'
        ? datasetList.value
        : type === 'model'
          ? modelList.value
          : operatorList.value
    const item = list.find((it) => it.id === id)
    const scopes = item ? resolveScopes(item as { isPublic: boolean; ownerId?: string | number | null }) : []
    const scope = scopes.includes('mine') ? 'mine' : scopes[0] || 'public'
    return version ? `${scope}/${id}/${version}` : `${scope}/${id}`
  }

  return {
    datasetList,
    modelList,
    operatorList,
    datasetOptions,
    modelOptions,
    operatorOptions,
    datasetTree,
    modelTree,
    operatorTree,
    loadDatasetOptions,
    ensureDatasetById,
    loadModelOptions,
    loadOperatorOptions,
    findDatasetName,
    findModelName,
    findOperatorName,
    findDatasetVersionName,
    findModelVersionName,
    findOperatorVersionName,
    findItemName,
    buildCascaderValue,
  }
}
