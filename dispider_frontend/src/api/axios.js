import axios from 'axios';
import { useAuthStore } from '@/stores/auth';
import { ElMessage } from 'element-plus';
import 'element-plus/es/components/message/style/css';

// Create an Axios instance
const apiClient = axios.create({
  baseURL: location.hostname === 'localhost' 
    ? 'http://localhost:8000/api' 
    : `${location.protocol}//${location.hostname}/api`,
  headers: {
    'Content-Type': 'application/json',
  }
});
// Add a request interceptor to include the token
apiClient.interceptors.request.use(
  (config) => {
    const authStore = useAuthStore();
    const token = authStore.token;
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// 响应拦截器：全局错误处理
apiClient.interceptors.response.use(
  (response) => {
    // 状态码在 2xx 范围内会触发该函数。
    // 如果响应成功，则直接返回响应。
    return response;
  },
  (error) => {
    // 超出 2xx 范围的状态码都会触发该函数。
    // 在这里统一处理错误。
    if (error.response && error.response.data && error.response.data.msg) {
      // 如果后端返回了包含 msg 字段的错误信息，则显示该信息。
      ElMessage({
        message: error.response.data.msg, // 显示后端提供的错误消息
        type: 'error',
        duration: 5 * 1000, // 消息显示 5 秒
      });
    } else {
      // 对于网络错误或其他没有特定 msg 的错误，显示通用的错误消息。
      ElMessage({
        message: error.message,
        type: 'error',
        duration: 5 * 1000,
      });
    }

    // 必须返回一个 rejected promise，以保证错误可以被业务代码中的 .catch() 块捕获，
    // 例如，用于停止加载状态的 spinning。
    return Promise.reject(error);
  }
);

export default apiClient; 