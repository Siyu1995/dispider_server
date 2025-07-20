<template>
  <div class="vnc-viewer-container">
    <div v-if="loading" class="vnc-status">
      <p>正在连接到 VNC 服务器...</p>
      <p>URL: {{ vncUrl }}</p>
    </div>
    <div v-if="error" class="vnc-status vnc-error">
      <p>连接失败: {{ error }}</p>
      <button @click="reconnect">重新连接</button>
    </div>
    <!-- vncScreen 将作为 noVNC 的挂载点 -->
    <div ref="vncScreen" class="vnc-screen-container"></div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue';
import { useRoute } from 'vue-router';
import RFB from '@novnc/novnc/core/rfb';
import { useAuthStore } from '@/stores/auth';

const route = useRoute();
const authStore = useAuthStore();

const vncScreen = ref(null);
const loading = ref(true);
const error = ref(null);
const vncUrl = ref('');
let rfb = null;

const containerId = route.params.containerId;

const connectVNC = () => {
  if (!containerId) {
    error.value = "未提供容器 ID。";
    loading.value = false;
    return;
  }
  
  const token = authStore.token;
  if (!token) {
    error.value = "用户未认证，无法连接。";
    loading.value = false;
    return;
  }

  const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const backendHost = window.location.hostname === 'localhost' ? `${window.location.hostname}:8000` : window.location.hostname;
  const url = `${wsProtocol}//${backendHost}/api/containers/ws/${containerId}?token=${token}`;
  vncUrl.value = url;

  loading.value = true;
  error.value = null;

  try {
    // 使用 noVNC 的标准选项来启用自动缩放
    rfb = new RFB(vncScreen.value, url, {
    });

    rfb.scaleViewport = true;

    rfb.addEventListener('connect', () => {
      loading.value = false;
      error.value = null;
      console.log('VNC 连接成功');
    });

    rfb.addEventListener('disconnect', (e) => {
      loading.value = false;
      if (e.detail.clean) {
        error.value = '连接已正常断开。';
      } else {
        error.value = '连接意外断开，请检查网络或容器状态。';
      }
      console.log('VNC 连接已断开', e.detail);
    });

    rfb.addEventListener('securityfailure', (e) => {
      loading.value = false;
      error.value = `VNC 安全验证失败: ${e.detail.reason}`;
      console.error('VNC 安全验证失败', e.detail);
    });

  } catch (exc) {
    loading.value = false;
    error.value = `创建 VNC 连接时发生错误: ${exc.message}`;
    console.error('创建 VNC 连接时发生错误:', exc);
  }
};

const reconnect = () => {
  if (rfb) {
    rfb.disconnect();
    rfb = null;
  }
  connectVNC();
};

onMounted(() => {
  connectVNC();
});

onUnmounted(() => {
  if (rfb) {
    rfb.disconnect();
  }
});
</script>

<style scoped>
.vnc-viewer-container {
  width: 100vw;
  height: 100vh;
  background-color: #000;
  overflow: hidden;
}
.vnc-status {
  position: absolute;
  top: 0;
  left: 50%;
  transform: translateX(-50%);
  padding: 10px;
  text-align: center;
  background-color: rgba(255, 255, 255, 0.8);
  border-bottom: 1px solid #ddd;
  z-index: 10;
  color: #333;
}
.vnc-error {
  color: #f56c6c;
  background-color: #fef0f0;
}
/* noVNC 会将 canvas 挂载到这个容器中，
   并根据 scaleViewport: true 自动处理其大小和居中 */
.vnc-screen-container {
  width: 100%;
  height: 100%;
}
</style> 