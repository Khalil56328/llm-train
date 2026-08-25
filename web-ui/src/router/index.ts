import { createRouter, createWebHashHistory, type RouteRecordRaw } from 'vue-router'
import AppLayout from '@/components/layout/AppLayout.vue'
import LoginView from '@/views/LoginView.vue'

// 公共路由
const publicRoutes: RouteRecordRaw[] = [
  {
    path: '/login',
    name: 'Login',
    component: LoginView,
    meta: { title: '登录', hidden: true },
  },
]

// 布局路由
const layoutRoute: RouteRecordRaw = {
  path: '/',
  component: AppLayout,
  redirect: '/home',
  children: [
    {
      path: 'home',
      name: 'Home',
      component: () => import('@/views/home/HomePage.vue'),
      meta: { title: '首页', icon: 'HomeFilled' },
    },
  ],
}

// 动态路由（按模块注册，后续根据权限过滤）
export const asyncRoutes: RouteRecordRaw[] = [
  // ========= 算子中心 =========
  {
    path: '/operator',
    component: AppLayout,
    redirect: '/operator/management',
    meta: { title: '算子中心', icon: 'Monitor' },
    children: [
      {
        path: 'management',
        name: 'OperatorManagement',
        component: () => import('@/views/operator/OperatorManagement.vue'),
        meta: { title: '算子管理', icon: 'Monitor' },
      },
      {
        path: 'management/version-create',
        name: 'OperatorVersionCreate',
        component: () => import('@/views/operator/OperatorVersionCreate.vue'),
        meta: { title: '新增版本', hidden: true, activeMenu: '/operator/management', parent: { title: '算子管理', path: '/operator/management' } },
      },
      {
        path: 'management/detail/:id',
        name: 'OperatorDetail',
        component: () => import('@/views/operator/OperatorDetail.vue'),
        meta: { title: '算子详情', hidden: true, activeMenu: '/operator/management', parent: { title: '算子管理', path: '/operator/management' } },
      },
      {
        path: 'management/edit/:id',
        name: 'OperatorEdit',
        component: () => import('@/views/operator/OperatorEdit.vue'),
        meta: { title: '修改算子', hidden: true, activeMenu: '/operator/management', parent: { title: '算子管理', path: '/operator/management' } },
      },
      {
        path: 'management/version-detail/:operatorId/:versionId',
        name: 'OperatorVersionDetail',
        component: () => import('@/views/operator/VersionDetail.vue'),
        meta: { title: '版本详情', hidden: true, activeMenu: '/operator/management', parent: { title: '算子管理', path: '/operator/management' } },
      },
      {
        path: 'management/version-edit/:operatorId/:versionId',
        name: 'OperatorVersionEdit',
        component: () => import('@/views/operator/VersionEdit.vue'),
        meta: { title: '修改版本', hidden: true, activeMenu: '/operator/management', parent: { title: '算子管理', path: '/operator/management' } },
      },
      {
        path: 'plaza',
        name: 'OperatorPlaza',
        component: () => import('@/views/operator/OperatorPlaza.vue'),
        meta: { title: '算子广场', icon: 'Shop' },
      },
    ],
  },

  // ========= 数据中心 =========
  {
    path: '/data',
    component: AppLayout,
    redirect: '/data/training',
    meta: { title: '数据中心', icon: 'Folder' },
    children: [
      {
        path: 'training',
        name: 'TrainingDataset',
        component: () => import('@/views/data/TrainingDataset.vue'),
        meta: { title: '训练数据集', icon: 'Folder' },
      },
      {
        path: 'training/files/:id',
        name: 'data-training-files',
        component: () => import('@/views/data/TrainingDatasetFiles.vue'),
        meta: { title: '文件列表', hidden: true, activeMenu: '/data/training', parent: { title: '训练数据集', path: '/data/training' } },
      },
      {
        path: 'evaluation',
        name: 'EvaluationDataset',
        component: () => import('@/views/data/EvaluationDataset.vue'),
        meta: { title: '评测数据集', icon: 'FolderChecked' },
      },
      {
        path: 'evaluation/create',
        name: 'data-evaluation-create',
        component: () => import('@/views/data/EvaluationDatasetCreate.vue'),
        meta: { title: '创建评测数据集', hidden: true, activeMenu: '/data/evaluation', parent: { title: '评测数据集', path: '/data/evaluation' } },
      },
      {
        path: 'evaluation/files/:id',
        name: 'data-evaluation-files',
        component: () => import('@/views/data/EvaluationDatasetFiles.vue'),
        meta: { title: '文件列表', hidden: true, activeMenu: '/data/evaluation', parent: { title: '评测数据集', path: '/data/evaluation' } },
      },
      {
        path: 'plaza',
        name: 'DatasetPlaza',
        component: () => import('@/views/data/DatasetPlaza.vue'),
        meta: { title: '数据集广场', icon: 'Shop' },
      },
    ],
  },

  // ========= 模型训练 =========
  {
    path: '/train',
    component: AppLayout,
    redirect: '/train/fine-tune',
    meta: { title: '模型训练', icon: 'Cpu' },
    children: [
      {
        path: 'fine-tune',
        name: 'FineTune',
        component: () => import('@/views/training/FineTuneList.vue'),
        meta: { title: '模型微调', icon: 'Cpu' },
      },
      {
        path: 'fine-tune/create',
        name: 'FineTuneCreate',
        component: () => import('@/views/training/FineTuneCreate.vue'),
        meta: { title: '创建微调任务', hidden: true, activeMenu: '/train/fine-tune', parent: { title: '模型微调', path: '/train/fine-tune' } },
      },
      {
        path: 'alignment',
        name: 'Alignment',
        component: () => import('@/views/training/AlignmentList.vue'),
        meta: { title: '偏好对齐', icon: 'Connection' },
      },
      {
        path: 'alignment/create',
        name: 'AlignmentCreate',
        component: () => import('@/views/training/AlignmentCreate.vue'),
        meta: { title: '创建对齐训练任务', hidden: true, activeMenu: '/train/alignment', parent: { title: '偏好对齐', path: '/train/alignment' } },
      },
      {
        path: 'compression',
        name: 'Compression',
        component: () => import('@/views/training/CompressionList.vue'),
        meta: { title: '模型压缩', icon: 'Sort' },
      },
      {
        path: 'compression/create',
        name: 'CompressionCreate',
        component: () => import('@/views/training/CompressionCreate.vue'),
        meta: { title: '创建量化训练任务', hidden: true, activeMenu: '/train/compression', parent: { title: '模型压缩', path: '/train/compression' } },
      },
      {
        path: 'pretrain',
        name: 'PreTrain',
        component: () => import('@/views/training/PreTrainList.vue'),
        meta: { title: '预训练', icon: 'DataBoard' },
      },
      {
        path: 'pretrain/create',
        name: 'PreTrainCreate',
        component: () => import('@/views/training/PreTrainCreate.vue'),
        meta: { title: '创建预训练任务', hidden: true, activeMenu: '/train/pretrain', parent: { title: '预训练', path: '/train/pretrain' } },
      },
      {
        path: 'scene',
        name: 'SceneTrain',
        component: () => import('@/views/training/SceneTrainList.vue'),
        meta: { title: '场景训练', icon: 'TrendCharts' },
      },
      {
        path: 'scene/create',
        name: 'SceneTrainCreate',
        component: () => import('@/views/training/SceneTrainCreate.vue'),
        meta: { title: '创建场景训练任务', hidden: true, activeMenu: '/train/scene', parent: { title: '场景训练', path: '/train/scene' } },
      },
      {
        path: 'task/:id',
        name: 'TrainTaskDetail',
        component: () => import('@/views/training/TrainTaskDetail.vue'),
        meta: { title: '训练任务详情', hidden: true, activeMenu: '/train/fine-tune', parent: { title: '模型微调', path: '/train/fine-tune' } },
      },
    ],
  },

  // ========= 模型中心 =========
  {
    path: '/model',
    component: AppLayout,
    redirect: '/model/my-library',
    meta: { title: '模型中心', icon: 'Files' },
    children: [
      {
        path: 'my-library',
        name: 'MyModelLibrary',
        component: () => import('@/views/model/MyModelLibrary.vue'),
        meta: { title: '我的模型库', icon: 'Files' },
      },
      {
        path: 'plaza',
        name: 'ModelPlaza',
        component: () => import('@/views/model/ModelPlaza.vue'),
        meta: { title: '模型库广场', icon: 'Shop' },
      },
      {
        path: 'plaza-detail/:id',
        name: 'ModelPlazaDetail',
        component: () => import('@/views/model/ModelPlazaDetail.vue'),
        meta: { title: '模型详情', hidden: true, activeMenu: '/model/plaza', parent: { title: '模型库广场', path: '/model/plaza' } },
      },
      {
        path: 'detail/:id',
        name: 'ModelDetail',
        component: () => import('@/views/model/ModelDetail.vue'),
        meta: { title: '模型详情', hidden: true, activeMenu: '/model/my-library', parent: { title: '我的模型库', path: '/model/my-library' } },
      },
      {
        path: 'create',
        name: 'ModelCreate',
        component: () => import('@/views/model/ModelCreate.vue'),
        meta: { title: '创建模型', hidden: true, activeMenu: '/model/my-library', parent: { title: '我的模型库', path: '/model/my-library' } },
      },
      {
        path: 'upload/:id',
        name: 'ModelUpload',
        component: () => import('@/views/model/ModelUpload.vue'),
        meta: { title: '上传模型', hidden: true, activeMenu: '/model/my-library', parent: { title: '我的模型库', path: '/model/my-library' } },
      },
    ],
  },

  // ========= 模型服务 =========
  {
    path: '/service',
    component: AppLayout,
    redirect: '/service/deployment',
    meta: { title: '模型服务', icon: 'Platform' },
    children: [
      {
        path: 'deployment',
        name: 'Deployment',
        component: () => import('@/views/service/DeploymentList.vue'),
        meta: { title: '模型部署', icon: 'Platform' },
      },
      {
        path: 'deployment/create',
        name: 'DeploymentCreate',
        component: () => import('@/views/service/DeploymentCreate.vue'),
        meta: { title: '新增部署', hidden: true, activeMenu: '/service/deployment', parent: { title: '模型部署', path: '/service/deployment' } },
      },
      {
        path: 'deployment/detail/:id',
        name: 'DeploymentDetail',
        component: () => import('@/views/service/DeploymentDetail.vue'),
        meta: { title: '部署详情', hidden: true, activeMenu: '/service/deployment', parent: { title: '模型部署', path: '/service/deployment' } },
      },
      {
        path: 'evaluation',
        name: 'ModelEvaluation',
        component: () => import('@/views/service/EvaluationList.vue'),
        meta: { title: '模型评测', icon: 'Histogram' },
      },
      {
        path: 'evaluation/create',
        name: 'EvaluationCreate',
        component: () => import('@/views/service/EvaluationCreate.vue'),
        meta: { title: '新增评测', hidden: true, activeMenu: '/service/evaluation', parent: { title: '模型评测', path: '/service/evaluation' } },
      },
      {
        path: 'evaluation/detail/:id',
        name: 'EvaluationDetail',
        component: () => import('@/views/service/EvaluationDetail.vue'),
        meta: { title: '评测详情', hidden: true, activeMenu: '/service/evaluation', parent: { title: '模型评测', path: '/service/evaluation' } },
      },
      {
        path: 'evaluation/review/:id',
        name: 'EvalReview',
        component: () => import('@/views/service/EvalReview.vue'),
        meta: { title: '人工评测', hidden: true, activeMenu: '/service/evaluation', parent: { title: '模型评测', path: '/service/evaluation' } },
      },
      {
        path: 'evaluation/report/:id',
        name: 'EvalReport',
        component: () => import('@/views/service/EvalReport.vue'),
        meta: { title: '评测报告', hidden: true, activeMenu: '/service/evaluation', parent: { title: '模型评测', path: '/service/evaluation' } },
      },
    ],
  },

  // ========= 运维中心 =========
  {
    path: '/ops',
    component: AppLayout,
    redirect: '/ops/resource',
    meta: { title: '运维中心', icon: 'Setting' },
    children: [
      {
        path: 'resource',
        name: 'ResourcePool',
        component: () => import('@/views/ops/ResourcePool.vue'),
        meta: { title: '资源管理', icon: 'Setting' },
      },
      {
        path: 'images',
        name: 'ImageManagement',
        component: () => import('@/views/ops/ImageManagement.vue'),
        meta: { title: '镜像管理', icon: 'Box' },
      },
    ],
  },
]

const router = createRouter({
  history: createWebHashHistory(),
  routes: [...publicRoutes, layoutRoute, ...asyncRoutes],
})

// 路由守卫
router.beforeEach((to, _from, next) => {
  const token = localStorage.getItem('access_token')
  if (to.path === '/login') {
    if (token) {
      next('/')
    } else {
      next()
    }
  } else {
    if (!token) {
      next('/login')
    } else {
      next()
    }
  }
})

export default router
