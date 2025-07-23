<template>
  <el-card class="login-card">
    <template #header>
      <div class="card-header">
        <h1>登录</h1>
      </div>
    </template>
    <el-form ref="loginFormRef" :model="loginForm" :rules="loginRules" label-width="80px" @submit.prevent="handleLogin">
      <el-form-item label="邮箱" prop="email">
        <el-input v-model="loginForm.email" placeholder="请输入邮箱"></el-input>
      </el-form-item>
      <el-form-item label="密码" prop="password">
        <el-input v-model="loginForm.password" type="password" placeholder="请输入密码" show-password></el-input>
      </el-form-item>
      <el-form-item>
        <el-button type="primary" :loading="loading" @click="handleLogin">登录</el-button>
        <el-button plain @click="goToRegister">注册</el-button>
      </el-form-item>
    </el-form>
  </el-card>
</template>

<script setup>
import { ref, reactive } from 'vue';
import { useRouter } from 'vue-router';
import { useAuthStore } from '@/stores/auth';
import { ElNotification } from 'element-plus';

const router = useRouter();
const authStore = useAuthStore();
const loginFormRef = ref(null);
const loading = ref(false);

const goToRegister = () => {
  router.push('/auth/register');
};

const loginForm = reactive({
  email: '',
  password: '',
});

const loginRules = reactive({
  email: [
    { required: true, message: '请输入邮箱地址', trigger: 'blur' },
    { type: 'email', message: '请输入有效的邮箱地址', trigger: ['blur', 'change'] },
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
  ],
});

/**
 * Handles the form submission for user login.
 * Validates the form, calls the login action, and handles success or error cases.
 */
const handleLogin = async () => {
  if (!loginFormRef.value) return;
  await loginFormRef.value.validate(async (valid) => {
    if (valid) {
      loading.value = true;
      try {
        await authStore.login(loginForm.email, loginForm.password);
        router.push('/');
        ElNotification({
          title: '成功',
          message: '登录成功，欢迎回来！',
          type: 'success',
        });
      } catch (error) {
        console.error('登录失败:', error);
        ElNotification({
          title: '错误',
          message: error.response?.data?.detail || '登录失败，请检查您的凭据。',
          type: 'error',
        });
      } finally {
        loading.value = false;
      }
    } else {
      console.log('表单校验失败！');
      return false;
    }
  });
};
</script>

<style scoped>
.login-card {
  width: 450px;
  border-radius: var(--border-radius-main);
  box-shadow: var(--box-shadow-main);
}
.card-header {
  text-align: center;
}
.card-header h1 {
    margin: 0;
    font-size: 24px;
}
</style> 