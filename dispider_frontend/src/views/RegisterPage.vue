<template>
  <el-card class="register-card">
    <template #header>
      <div class="card-header">
        <h1>注册</h1>
      </div>
    </template>
    <el-form ref="registerFormRef" :model="registerForm" :rules="registerRules" label-width="100px" @submit.prevent="handleRegister">
      <el-form-item label="用户名" prop="username">
        <el-input v-model="registerForm.username" placeholder="请输入用户名"></el-input>
      </el-form-item>
      <el-form-item label="邮箱" prop="email">
        <el-input v-model="registerForm.email" placeholder="请输入邮箱"></el-input>
      </el-form-item>
      <el-form-item label="密码" prop="password">
        <el-input v-model="registerForm.password" type="password" placeholder="请输入密码" show-password></el-input>
      </el-form-item>
      <el-form-item label="确认密码" prop="confirmPassword">
        <el-input v-model="registerForm.confirmPassword" type="password" placeholder="请再次输入密码" show-password></el-input>
      </el-form-item>
      <el-form-item label="PushMe" prop="pushme_key">
        <el-input v-model="registerForm.pushme_key" placeholder="请输入PushMe Key"></el-input>
      </el-form-item>
      <el-form-item>
        <el-button type="primary" :loading="loading" @click="handleRegister" >注册</el-button>
        <el-button plain @click="goToLogin" >返回登录</el-button>
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
const registerFormRef = ref(null);
const loading = ref(false);

const goToLogin = () => {
  router.push('/auth/login');
};

const registerForm = reactive({
  username: '',
  email: '',
  password: '',
  confirmPassword: '',
  pushme_key: '',
});

const validatePass = (rule, value, callback) => {
  if (value === '') {
    callback(new Error('请再次输入密码'));
  } else if (value !== registerForm.password) {
    callback(new Error("两次输入的密码不一致!"));
  } else {
    callback();
  }
};

const registerRules = reactive({
  username: [
      { required: true, message: '请输入用户名', trigger: 'blur' }
  ],
  email: [
    { required: true, message: '请输入邮箱地址', trigger: 'blur' },
    { type: 'email', message: '请输入有效的邮箱地址', trigger: ['blur', 'change'] },
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
  ],
  confirmPassword: [
    { required: true, validator: validatePass, trigger: 'blur' }
  ],
  pushme_key: [
    { required: true, message: '请输入PushMe Key', trigger: 'blur' }
  ]
});

/**
 * Handles the form submission for user registration.
 * Validates the form and sends registration data to the server.
 */
const handleRegister = async () => {
  if (!registerFormRef.value) return;
  await registerFormRef.value.validate(async (valid) => {
    if (valid) {
        loading.value = true;
        try {
            await authStore.register({
                username: registerForm.username,
                email: registerForm.email,
                password: registerForm.password,
                pushme_key: registerForm.pushme_key,
            });
            router.push('/auth/login');
            ElNotification({
                title: '成功',
                message: '注册成功，请登录。',
                type: 'success',
            });
        } catch (error) {
            console.error('注册失败:', error);
            ElNotification({
                title: '错误',
                message: error.response?.data?.detail || '注册失败，请稍后重试。',
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
.register-card {
  width: 500px;
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