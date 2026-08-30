// ============================================
// 大模型训推平台 - 类型定义
// ============================================

// === 通用接口返回 ===
export interface ApiResponse<T = unknown> {
  code: number
  message: string
  data: T
}

export interface PaginatedData<T> {
  list: T[]
  total: number
  pageIndex: number
  pageSize: number
}

export interface PageQuery {
  pageIndex: number
  pageSize: number
  keyword?: string
}

// === 任务状态 ===
export type TaskStatus =
  | 'pending'
  | 'running'
  | 'succeeded'
  | 'failed'
  | 'paused'
  | 'stopped'
  | 'cancelled'
  | 'cleaned'

export const TaskStatusMap: Record<TaskStatus, string> = {
  pending: '待执行',
  running: '执行中',
  succeeded: '执行成功',
  failed: '执行失败',
  paused: '已暂停',
  stopped: '已停止',
  cancelled: '已取消',
  cleaned: '清理成功',
}

export const TaskStatusColorMap: Record<TaskStatus, 'primary' | 'success' | 'warning' | 'info' | 'danger'> = {
  pending: 'info',
  running: 'warning',
  succeeded: 'success',
  failed: 'danger',
  paused: 'info',
  stopped: 'info',
  cancelled: 'info',
  cleaned: 'success',
}

// === 用户 ===
export interface UserInfo {
  id: string
  username: string
  nickname: string
  avatar?: string
  role: string
  department: string
  permissions: string[]
}

// === 菜单 / 路由 ===
export interface MenuItem {
  id: string
  name: string
  path: string
  icon?: string
  children?: MenuItem[]
  hidden?: boolean
  order: number
}

// === 资源配置 ===
export interface ResourceConfig {
  poolId: string
  poolName?: string
  gpuType?: string
  gpuCount: number
  cpu: number
  memory: number
  nodeCount?: number
}

// === 训练任务 ===
export interface TrainTask {
  id: string
  name: string
  taskType: 'fine-tune' | 'alignment' | 'compression' | 'pretrain' | 'scene'
  taskSubType?: string
  subType?: string
  status: TaskStatus
  baseModelId: string
  baseModelName: string
  baseModelVersion?: string
  operatorId?: string
  operatorVersion?: string
  datasetId?: string
  datasetName?: string
  datasetVersion?: string
  framework?: string
  valDatasetId?: string
  valDatasetVersion?: string
  sftModelId?: string
  sftModelVersion?: string
  teacherModelId?: string
  teacherModelVersion?: string
  calibDatasetId?: string
  calibDatasetVersion?: string
  hyperParams: Record<string, unknown>
  envVars: Record<string, string>
  resourceConfig: ResourceConfig
  outputModelId?: string
  outputModelName?: string
  engineCommand?: string
  errorMessage?: string
  progress?: number
  description?: string
  createdBy: string
  createdAt: string
  startedAt?: string
  finishedAt?: string
}

// === 模型 ===
export type ModelType =
  | 'dialogue'
  | 'vision'
  | 'video'
  | 'image-generation'
  | 'audio'
  | 'embedding'
  | 'rerank'

export type ModelSpec = 'below-10b' | '10b-50b' | '50b-100b' | 'above-100b'

export const ModelTypeMap: Record<ModelType, string> = {
  dialogue: '对话',
  vision: '视觉',
  video: '视频',
  'image-generation': '图像生成',
  audio: '音频',
  embedding: 'Embedding',
  rerank: 'Rerank',
}

export const ModelSpecMap: Record<ModelSpec, string> = {
  'below-10b': '10B以下',
  '10b-50b': '10-50B',
  '50b-100b': '50-100B',
  'above-100b': '100B以上',
}

export interface Model {
  id: string
  name: string
  type: ModelType
  spec: ModelSpec
  vendor: string
  frameworks?: string[]
  frameworkLabel?: string
  version: string
  description?: string
  tags: string[]
  iconUrl?: string
  isPublic: boolean
  ownerId?: string
  ownerName?: string
  status: 'active' | 'inactive'
  createdAt: string
}

export type ModelVersionStatus = 'uploading' | 'ready' | 'failed'

export interface ModelVersion {
  id: string
  modelId: string
  version: string
  description?: string
  storagePath?: string
  framework?: InferenceFramework
  size?: number
  fileCount?: number
  status: ModelVersionStatus
  isDefault: boolean
  /** 版本公开状态（后端可能返回 camelCase 或 snake_case） */
  isPublic?: boolean
  is_public?: boolean
  createdAt: string
  updatedAt?: string
}

export interface ModelFile {
  id: string
  versionId: string
  fileName: string
  filePath?: string
  fileSize: number
  fileType: 'safetensors' | 'bin' | 'json' | 'txt' | 'other'
  status: 'uploading' | 'ready' | 'failed'
  createdAt: string
}

export interface ModelCompareItem {
  id: string
  name: string
  type: ModelType
  spec: ModelSpec
  vendor: string
  description?: string
  tags: string[]
  isPublic: boolean
  versions: ModelVersion[]
}

export interface ModelWithVersions extends Model {
  versions: ModelVersion[]
}

// === 算子 ===
// 算子细分类目（前端展示用）
export type OperatorCategory =
  | '预训练'
  | '大模型微调'
  | '模型蒸馏'
  | '模型推理'
  | '模型合并'
  | '结果存储'
  | '数据集导入'

export const OperatorCategoryMap: Record<OperatorCategory, string> = {
  '预训练': '预训练',
  '大模型微调': '大模型微调',
  '模型蒸馏': '模型蒸馏',
  '模型推理': '模型推理',
  '模型合并': '模型合并',
  '结果存储': '结果存储',
  '数据集导入': '数据集导入',
}

export type ResourceType = 'CPU' | 'GPU'

export type TrainingFramework = 'ms-swift' | 'llamafactory'

export const TrainingFrameworkMap: Record<TrainingFramework, string> = {
  'ms-swift': 'ms-swift',
  'llamafactory': 'LlamaFactory',
}

export type TrainingMethod = 'full' | 'freeze' | 'lora'

export const TrainingMethodMap: Record<TrainingMethod, string> = {
  full: '全量更新',
  freeze: '冻结微调',
  lora: 'LoRA微调',
}

export interface Operator {
  id: string
  name: string
  /** 算子类型（细分类目名称） */
  category: string
  /** 算子大类：training / inference / data / other */
  type: 'training' | 'inference' | 'data' | 'other'
  description?: string
  /** 该算子下的版本数量 */
  version_count?: number
  isPublic: boolean
  owner?: string
  owner_name?: string
  ownerId?: string
  createdAt: string
  updatedAt: string
  /** 后端实际返回的时间字段（snake_case） */
  created_at?: string
  updated_at?: string
  /** 训练框架 */
  training_framework?: string
  /** 训练方法 */
  training_method?: string
}

/** 算子版本（一个算子下可以有多个版本） */
export interface OperatorVersion {
  id: string
  operator_id: string
  name: string
  description?: string
  resource_type: ResourceType
  base_image?: string
  /** 显示用的镜像地址（同 base_image） */
  image_address?: string
  image_name?: string
  work_dir?: string
  start_cmd?: string
  mount_dir?: string
  /** 启动参数（JSON 对象，KV 形式） */
  start_params?: Record<string, StartParamItem[]>
  is_public: boolean
  creator?: string
  created_at: string
  updated_at: string
}

/** 启动参数单项 */
export interface StartParamItem {
  attr1: number
  type: string
  label: string
  default: string
  describe: string
}

export interface OperatorWithVersions extends Operator {
  versions: OperatorVersion[]
}

/** 镜像（运维中心资源 + 选择弹框） */
export interface DockerImage {
  id: string
  name: string
  address: string
  resource_type?: 'CPU' | 'GPU'
  description?: string
  createdAt?: string
  updatedAt?: string
  created_at?: string
  updated_at?: string
}

export interface ParameterDef {
  name: string
  type: 'string' | 'number' | 'boolean' | 'select' | 'json'
  required: boolean
  defaultValue?: unknown
  options?: { label: string; value: unknown }[]
  description?: string
}

// === 数据集 ===
export type DatasetDataType =
  | 'SFT'
  | 'KTO'
  | 'DPO'
  | 'GRPO(VerL)'
  | 'GRPO(swift)'
  | 'GSPO(swift)'
  | 'CPT'
  | 'general'
  | '问答题'
  | '选择题'
  | 'OpenCompass'

export interface Dataset {
  id: string
  name: string
  category: string
  type: 'training' | 'evaluation'
  dataType?: DatasetDataType
  evalDimensions?: string // JSON string stored by backend
  description?: string
  source: 'upload' | 'huggingface' | 'oss' | 'import' | 'platform' | 'custom'
  storagePath?: string
  size?: number
  sampleCount?: number
  isPublic: boolean
  ownerId: string
  ownerName?: string
  status: 'uploading' | 'processing' | 'ready' | 'failed'
  createdAt: string
  updatedAt?: string
  fileCount?: number
  versionCount?: number
  defaultVersion?: string
  fileStats?: { fileCount: number; success: number; failed: number; processing: number; totalSize: number }
}

// 数据集版本
export interface DatasetVersion {
  id: string
  datasetId: string
  version: string
  description?: string
  storagePath?: string
  fileCount: number
  size: number
  sampleCount: number
  isDefault: boolean
  createdBy?: string
  createdAt: string
  updatedAt?: string
}

export type DatasetFileStatus = 'processing' | 'success' | 'failed'

// 数据集文件来源（采集方式）统一枚举
export type DatasetFileSource = 'local_upload' | 'platform' | 'modelscope'

export interface DatasetFile {
  id: string
  datasetId: string
  versionId?: string
  fileName: string
  source: DatasetFileSource
  status: DatasetFileStatus
  size: number
  storagePath?: string
  batchId?: string
  sampleCount?: number
  errorMessage?: string
  createdAt: string
  updatedAt?: string
}

// 采集任务（按用户上传批次聚合）
export interface CollectTask {
  batchId: string
  taskName: string
  source: DatasetFileSource
  status: DatasetFileStatus
  fileCount: number
  successCount: number
  failedCount: number
}

// === 部署服务 ===
export type InferenceFramework = 'vLLM' | 'MindIE' | 'custom'
export type DeployStatus = 'creating' | 'running' | 'stopped' | 'failed' | 'deleting'

export const DeployStatusMap: Record<DeployStatus, string> = {
  creating: '创建中',
  running: '运行中',
  stopped: '已停止',
  failed: '异常',
  deleting: '删除中',
}

export const DeployStatusColorMap: Record<DeployStatus, 'primary' | 'success' | 'warning' | 'info' | 'danger'> = {
  creating: 'primary',
  running: 'success',
  stopped: 'info',
  failed: 'danger',
  deleting: 'warning',
}

export interface Deployment {
  id: string
  name: string
  description?: string
  modelId: string
  modelName?: string
  modelVersion?: string
  inferenceFramework: InferenceFramework
  operatorId?: string
  operatorVersion?: string
  params: Record<string, unknown>
  envVars: Record<string, string>
  resourceConfig: ResourceConfig
  instances?: number
  containerPort?: number
  accessPort?: number
  endpoint?: string
  status: DeployStatus
  progress?: number
  errorMessage?: string
  createdBy: string
  createdAt: string
  updatedAt?: string
}

// === 部署实例(POD) ===
export interface DeployInstance {
  id: string
  deployId: string
  podName: string
  status: string
  hostIp: string
  podIp: string
  createdAt: string
  updatedAt?: string
}

// === 评测任务 ===
export type EvalType = 'auto' | 'manual'
export type EvalStatus = 'pending' | 'running' | 'completed' | 'failed'

export const EvalTypeMap: Record<EvalType, string> = {
  auto: '自动评测',
  manual: '人工评测',
}

export const EvalStatusMap: Record<EvalStatus, string> = {
  pending: '待执行',
  running: '执行中',
  completed: '已完成',
  failed: '执行失败',
}

export const EvalStatusColorMap: Record<EvalStatus, 'primary' | 'success' | 'warning' | 'info' | 'danger'> = {
  pending: 'info',
  running: 'primary',
  completed: 'success',
  failed: 'danger',
}

export interface EvalMetric {
  name: string
  description: string
}

export interface EvaluationTask {
  id: string
  name: string
  description?: string
  evalType: EvalType
  isBaseline: boolean
  datasetId: string
  datasetName?: string
  datasetVersion?: string
  deploymentId: string
  deploymentName?: string
  scenes: string[]
  metrics?: EvalMetric[]
  ratingScale?: number
  status: EvalStatus
  progress?: number
  errorMessage?: string
  score?: number
  reportUrl?: string
  createdBy: string
  createdAt: string
  finishedAt?: string
}

// === 人工评测项 ===
export interface EvalItem {
  id: string
  evalId: string
  prompt: string
  referenceResponse: string
  modelResponse: string
  score?: number
  isEvaluated: boolean
  evaluatedBy?: string
  evaluatedAt?: string
  createdAt: string
}

// === 评测场景 ===
export type EvalScene = 'code' | 'alignment' | 'agent' | 'safety' | 'reasoning'
export type ManualEvalScene = 'text-classification' | 'text-summary' | 'text-generation' | 'qa' | 'custom'

export const EvalSceneMap: Record<EvalScene, string> = {
  code: '代码',
  alignment: '对齐',
  agent: '智能体',
  safety: '安全',
  reasoning: '逻辑推理',
}

export const EvalSceneIconMap: Record<EvalScene, string> = {
  code: 'Monitor',
  alignment: 'Aim',
  agent: 'Cpu',
  safety: 'Lock',
  reasoning: 'DataAnalysis',
}

export const ManualEvalSceneMap: Record<ManualEvalScene, string> = {
  'text-classification': '文本分类',
  'text-summary': '文本摘要',
  'text-generation': '文本生成',
  'qa': '问题问答',
  'custom': '自定义场景',
}

export const ManualEvalSceneIconMap: Record<ManualEvalScene, string> = {
  'text-classification': 'Document',
  'text-summary': 'Notebook',
  'text-generation': 'EditPen',
  'qa': 'ChatDotRound',
  'custom': 'Setting',
}

// === 评测报告 ===
export interface EvalReport {
  taskId: string
  taskName: string
  overallScore: number
  dimensionScores: { dimension: string; score: number }[]
  detailUrl?: string
}

// === 资源池 ===
export interface ResourcePool {
  id: string
  name: string
  gpu_type: string
  node_count: number
  total_gpu: number
  available_gpu: number
  status: 'active' | 'inactive'
  description?: string
  created_at?: string
  updated_at?: string
}

// === 通知 ===
export interface Notification {
  id: string
  title: string
  content: string
  type: 'info' | 'success' | 'warning' | 'error'
  read: boolean
  createdAt: string
}

// === 字典项 ===
export interface DictItem {
  id: string
  code: string
  name: string
  value: string
  sort: number
}

export type DictMap = Record<string, DictItem[]>
