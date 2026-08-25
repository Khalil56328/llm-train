<template>
  <div class="login-page">
    <div class="login-bg">
      <div class="login-decor">
        <div class="decor-circle decor-1" />
        <div class="decor-circle decor-2" />
        <div class="decor-circle decor-3" />
      </div>
    </div>

    <div class="login-card">
      <div class="login-header">
        <div class="login-logo">
          <svg viewBox="0 0 40 40" width="44" height="44">
            <rect width="40" height="40" rx="8" fill="#e63946" />
            <text x="20" y="28" text-anchor="middle" fill="white" font-size="22" font-weight="bold">AI</text>
          </svg>
        </div>
        <h1 class="login-title">大模型训推平台</h1>
        <p class="login-subtitle">一站式模型训练与推理服务</p>
      </div>

      <el-form
        ref="formRef"
        :model="loginForm"
        :rules="rules"
        class="login-form"
        @keyup.enter="handleLogin"
      >
        <el-form-item prop="username">
          <el-input
            v-model="loginForm.username"
            placeholder="请输入用户名"
            :prefix-icon="User"
            size="large"
          />
        </el-form-item>
        <el-form-item prop="password">
          <el-input
            v-model="loginForm.password"
            type="password"
            placeholder="请输入密码"
            :prefix-icon="Lock"
            size="large"
            show-password
          />
        </el-form-item>
        <el-form-item>
          <el-button
            type="primary"
            size="large"
            :loading="loading"
            class="login-btn"
            @click="handleLogin"
          >
            {{ loading ? '登录中...' : '登 录' }}
          </el-button>
        </el-form-item>
      </el-form>

      <div class="login-footer">
        <span>&copy; 2026 大模型训推平台</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { User, Lock } from '@element-plus/icons-vue'
import type { FormInstance, FormRules } from 'element-plus'
import { useUserStore } from '@/stores'

const router = useRouter()
const userStore = useUserStore()
const formRef = ref<FormInstance>()
const loading = ref(false)

const loginForm = reactive({
  username: '',
  password: '',
})

const rules: FormRules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
}

async function handleLogin() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return

  loading.value = true
  try {
    await userStore.login(loginForm.username, loginForm.password)
    await userStore.fetchUserInfo()
    ElMessage.success('登录成功')
    router.push('/')
  } catch {
    // 错误已在拦截器提示
  } finally {
    loading.value = false
  }
}
</script>

<style lang="scss" scoped>
.login-page {
  height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  position: relative;
  background: #f0f2f5;

  .login-bg {
    position: absolute;
    inset: 0;
    overflow: hidden;

    .login-decor {
      .decor-circle {
        position: absolute;
        border-radius: 50%;
        opacity: 0.06;
      }
      .decor-1 {
        width: 600px;
        height: 600px;
        background: $color-primary;
        top: -200px;
        right: -100px;
      }
      .decor-2 {
        width: 400px;
        height: 400px;
        background: $color-primary;
        bottom: -100px;
        left: -100px;
      }
      .decor-3 {
        width: 300px;
        height: 300px;
        background: $color-primary-light;
        top: 50%;
        left: 50%;
        transform: translate(-50%, -50%);
      }
    }
  }

  .login-card {
    position: relative;
    width: 420px;
    background: $bg-color-white;
    border-radius: 12px;
    box-shadow: 0 8px 40px rgba(0, 0, 0, 0.08);
    padding: 48px 40px 36px;
    z-index: 1;

    .login-header {
      text-align: center;
      margin-bottom: 36px;

      .login-logo {
        margin-bottom: 16px;
      }

      .login-title {
        font-size: 22px;
        font-weight: 700;
        color: $text-primary;
        margin-bottom: 6px;
      }

      .login-subtitle {
        font-size: 13px;
        color: $text-secondary;
      }
    }

    .login-form {
      .login-btn {
        width: 100%;
        height: 44px;
        font-size: 15px;
        letter-spacing: 4px;
      }
    }

    .login-footer {
      margin-top: 24px;
      text-align: center;
      font-size: 12px;
      color: $text-placeholder;
    }
  }
}
</style>
