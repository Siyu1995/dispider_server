<template>
  <div class="proxies-view-container">
    <h1>代理管理</h1>
    <p class="description">管理您的Clash代理供应商配置和健康监控。您可以上传新的配置文件，刷新Clash配置，并监控代理组的健康状态。</p>
    
    <!-- 健康监控面板 -->
    <div class="health-section">
      <div class="section-header">
        <h2>🎯 健康监控面板</h2>
        <div class="header-actions">
          <button 
            class="btn btn-outline" 
            :disabled="clashStore.isLoadingHealth" 
            @click="refreshHealthData"
          >
            <span v-if="clashStore.isLoadingHealth">🔄 加载中...</span>
            <span v-else>🔄 刷新数据</span>
          </button>
          <div class="auto-refresh-toggle">
            <input 
              id="autoRefresh" 
              v-model="autoRefreshEnabled" 
              type="checkbox" 
              @change="toggleAutoRefresh"
            >
            <label for="autoRefresh">自动刷新 (30s)</label>
          </div>
        </div>
      </div>

      <!-- 系统健康摘要 -->
      <div v-if="clashStore.systemHealth" class="health-summary-grid">
        <div class="health-card overall-status">
          <div class="health-card-header">
            <h3>🎯 系统状态</h3>
            <span 
              class="status-badge" 
              :class="getStatusClass(clashStore.systemHealth.overall_status)"
            >
              {{ clashStore.systemStatusText }}
            </span>
          </div>
          <div class="health-metrics">
            <div class="metric">
              <span class="metric-label">健康率</span>
              <span class="metric-value" :style="{ color: clashStore.healthRateColor }">
                {{ clashStore.systemHealth.health_rate }}%
              </span>
            </div>
            <div class="metric">
              <span class="metric-label">最后更新</span>
              <span class="metric-value">{{ formatTime(clashStore.lastHealthUpdate) }}</span>
            </div>
          </div>
        </div>

        <div class="health-card proxy-stats">
          <div class="health-card-header">
            <h3>📊 代理组统计</h3>
          </div>
          <div class="stats-grid">
            <div class="stat-item">
              <span class="stat-number healthy">{{ clashStore.systemHealth.proxy_groups.healthy }}</span>
              <span class="stat-label">健康</span>
            </div>
            <div class="stat-item">
              <span class="stat-number unhealthy">{{ clashStore.systemHealth.proxy_groups.unhealthy }}</span>
              <span class="stat-label">不健康</span>
            </div>
            <div class="stat-item">
              <span class="stat-number blacklisted">{{ clashStore.systemHealth.proxy_groups.blacklisted }}</span>
              <span class="stat-label">黑名单</span>
            </div>
            <div class="stat-item">
              <span class="stat-number total">{{ clashStore.systemHealth.proxy_groups.total }}</span>
              <span class="stat-label">总计</span>
            </div>
          </div>
        </div>

        <div class="health-card container-stats">
          <div class="health-card-header">
            <h3>🐳 容器统计</h3>
          </div>
          <div class="stats-grid">
            <div class="stat-item">
              <span class="stat-number total">{{ clashStore.systemHealth.containers.total }}</span>
              <span class="stat-label">活跃容器</span>
            </div>
            <div class="stat-item">
              <span class="stat-number">{{ clashStore.systemHealth.containers.active_mappings }}</span>
              <span class="stat-label">代理映射</span>
            </div>
          </div>
        </div>
      </div>

      <!-- 快速操作面板 -->
      <div class="quick-actions">
        <button 
          class="btn btn-warning" 
          :disabled="operationLoading.reassignAll" 
          @click="handleReassignAll"
        >
          <span v-if="operationLoading.reassignAll">🔄 处理中...</span>
          <span v-else>🔄 重新分配所有不健康容器</span>
        </button>
        <button 
          class="btn btn-info" 
          :disabled="operationLoading.clearBlacklist" 
          @click="handleClearBlacklist"
        >
          <span v-if="operationLoading.clearBlacklist">🧹 清理中...</span>
          <span v-else>🧹 清理过期黑名单</span>
        </button>
        <button 
          class="btn btn-secondary" 
          :disabled="operationLoading.initialize" 
          @click="handleInitializeServices"
        >
          <span v-if="operationLoading.initialize">⚙️ 初始化中...</span>
          <span v-else>⚙️ 重新初始化服务</span>
        </button>
        <button 
          class="btn btn-success" 
          :disabled="operationLoading.diagnose" 
          @click="handleRunDiagnosis"
        >
          <span v-if="operationLoading.diagnose">🔍 诊断中...</span>
          <span v-else>🔍 运行系统诊断</span>
        </button>
      </div>

      <!-- Clash状态和诊断面板 -->
      <div v-if="clashStatus || diagnosisResult" class="diagnosis-section">
        <!-- Clash服务状态 -->
        <div v-if="clashStatus" class="clash-status-card">
          <div class="card-header">
            <h3>🚀 Clash服务状态</h3>
            <div class="status-indicators">
              <span 
                class="service-status" 
                :class="{ 
                  'online': clashStatus.service_reachable, 
                  'offline': !clashStatus.service_reachable 
                }"
              >
                {{ clashStatus.service_reachable ? '🟢 在线' : '🔴 离线' }}
              </span>
            </div>
          </div>
          <div class="clash-info-grid">
            <div class="info-item">
              <span class="info-label">版本</span>
              <span class="info-value">{{ clashStatus.clash_version || '未知' }}</span>
            </div>
            <div class="info-item">
              <span class="info-label">API响应时间</span>
              <span class="info-value">
                {{ clashStatus.api_response_time >= 999 ? '超时' : `${(clashStatus.api_response_time * 1000).toFixed(0)}ms` }}
              </span>
            </div>
            <div class="info-item">
              <span class="info-label">代理节点</span>
              <span class="info-value">{{ clashStatus.total_proxies }}</span>
            </div>
            <div class="info-item">
              <span class="info-label">代理组</span>
              <span class="info-value">{{ clashStatus.proxy_groups_count }}</span>
            </div>
            <div class="info-item">
              <span class="info-label">运行模式</span>
              <span class="info-value">{{ clashStatus.current_mode || '未知' }}</span>
            </div>
            <div class="info-item">
              <span class="info-label">日志级别</span>
              <span class="info-value">{{ clashStatus.log_level || '未知' }}</span>
            </div>
          </div>
          
          <!-- Clash错误信息 -->
          <div v-if="clashStatus.errors && clashStatus.errors.length > 0" class="clash-errors">
            <h4>⚠️ 检测到的问题</h4>
            <ul class="error-list">
              <li v-for="error in clashStatus.errors" :key="error" class="error-item">
                {{ error }}
              </li>
            </ul>
          </div>
        </div>

        <!-- 系统诊断结果 -->
        <div v-if="diagnosisResult" class="diagnosis-card">
          <div class="card-header">
            <h3>🔍 系统诊断结果</h3>
            <div class="diagnosis-status">
              <span 
                class="health-badge" 
                :class="getDiagnosisStatusClass(diagnosisResult.overall_health)"
              >
                {{ getDiagnosisStatusText(diagnosisResult.overall_health) }}
              </span>
            </div>
          </div>
          
          <!-- 发现的问题 -->
          <div v-if="diagnosisResult.issues_found && diagnosisResult.issues_found.length > 0" class="issues-section">
            <h4>❗ 发现的问题 ({{ diagnosisResult.issues_found.length }})</h4>
            <ul class="issues-list">
              <li v-for="issue in diagnosisResult.issues_found" :key="issue" class="issue-item">
                {{ issue }}
              </li>
            </ul>
          </div>
          
          <!-- 修复建议 -->
          <div v-if="diagnosisResult.recommendations && diagnosisResult.recommendations.length > 0" class="recommendations-section">
            <h4>💡 修复建议 ({{ diagnosisResult.recommendations.length }})</h4>
            <ul class="recommendations-list">
              <li v-for="recommendation in diagnosisResult.recommendations" :key="recommendation" class="recommendation-item">
                {{ recommendation }}
              </li>
            </ul>
          </div>
          
          <!-- 诊断时间 -->
          <div class="diagnosis-footer">
            <span class="diagnosis-time">
              诊断时间: {{ formatTime(new Date(diagnosisResult.timestamp * 1000)) }}
            </span>
          </div>
        </div>
      </div>

      <!-- 代理组健康状态列表 -->
      <div v-if="clashStore.proxyGroupsHealth" class="proxy-groups-health">
        <div class="section-header-with-toggle">
          <h3>📋 代理组详细状态</h3>
          <button 
            class="btn btn-outline btn-sm toggle-button" 
            @click="showProxyGroupsDetails = !showProxyGroupsDetails"
          >
            <span v-if="showProxyGroupsDetails">🔼 收起详情</span>
            <span v-else>🔽 展开详情 ({{ clashStore.proxyGroupsHealth.groups_status?.length || 0 }})</span>
          </button>
        </div>
        <div v-show="showProxyGroupsDetails" class="groups-grid">
          <div 
            v-for="group in clashStore.proxyGroupsHealth.groups_status" 
            :key="group.name" 
            class="group-card"
            :class="{ 
              'healthy': group.is_healthy && !group.is_blacklisted,
              'unhealthy': !group.is_healthy && !group.is_blacklisted,
              'blacklisted': group.is_blacklisted 
            }"
          >
            <div class="group-header">
              <span class="group-name">{{ group.name }}</span>
              <div class="group-badges">
                <span v-if="group.is_healthy && !group.is_blacklisted" class="badge healthy">✅ 健康</span>
                <span v-else-if="group.is_blacklisted" class="badge blacklisted">🚫 黑名单</span>
                <span v-else class="badge unhealthy">❌ 不健康</span>
              </div>
            </div>
            <div class="group-details">
              <div class="detail-row">
                <span class="detail-label">响应时间:</span>
                <span class="detail-value">
                  {{ group.response_time >= 999 ? '超时' : `${(group.response_time * 1000).toFixed(0)}ms` }}
                </span>
              </div>
              <div class="detail-row">
                <span class="detail-label">失败次数:</span>
                <span class="detail-value">{{ group.failure_count }}</span>
              </div>
              <div v-if="group.last_check" class="detail-row">
                <span class="detail-label">最后检查:</span>
                <span class="detail-value">{{ formatTime(new Date(group.last_check * 1000)) }}</span>
              </div>
              <div v-if="group.is_blacklisted && group.blacklist_until" class="detail-row">
                <span class="detail-label">黑名单到期:</span>
                <span class="detail-value">{{ formatTime(new Date(group.blacklist_until * 1000)) }}</span>
              </div>
            </div>
            <div v-if="group.is_blacklisted" class="group-actions">
              <button 
                class="btn btn-sm btn-success" 
                :disabled="operationLoading.clearSpecific === group.name"
                @click="handleClearSpecificBlacklist(group.name)"
              >
                <span v-if="operationLoading.clearSpecific === group.name">清理中...</span>
                <span v-else>解除黑名单</span>
              </button>
            </div>
          </div>
        </div>
      </div>

      <!-- 容器代理映射表 -->
      <div v-if="clashStore.containerMappings" class="container-mappings">
        <div class="section-header-with-toggle">
          <h3>🐳 容器代理映射</h3>
          <button 
            class="btn btn-outline btn-sm toggle-button" 
            @click="showContainerMappings = !showContainerMappings"
          >
            <span v-if="showContainerMappings">🔼 收起列表</span>
            <span v-else>🔽 展开列表 ({{ clashStore.containerMappings.mappings?.length || 0 }})</span>
          </button>
        </div>
        <div v-show="showContainerMappings">
          <div v-if="clashStore.containerMappings.mappings.length > 0" class="mappings-table">
            <div class="table-header">
              <div class="table-cell">容器IP</div>
              <div class="table-cell">分配的代理组</div>
              <div class="table-cell">操作</div>
            </div>
            <div 
              v-for="mapping in clashStore.containerMappings.mappings" 
              :key="mapping.container_ip"
              class="table-row"
            >
              <div class="table-cell">
                <code>{{ mapping.container_ip }}</code>
              </div>
              <div class="table-cell">
                <span 
                  class="proxy-group-tag"
                  :class="getProxyGroupStatus(mapping.assigned_group)"
                >
                  {{ mapping.assigned_group }}
                </span>
              </div>
              <div class="table-cell">
                <button 
                  class="btn btn-sm btn-primary" 
                  :disabled="operationLoading.reassign === mapping.container_ip"
                  @click="handleReassignContainer(mapping.container_ip)"
                >
                  <span v-if="operationLoading.reassign === mapping.container_ip">重新分配中...</span>
                  <span v-else>🔄 重新分配</span>
                </button>
              </div>
            </div>
          </div>
          <div v-else class="no-data">
            <p>暂无容器代理映射数据</p>
          </div>
        </div>
      </div>
    </div>

    <!-- 配置管理面板 -->
    <div v-if="authStore.isSuperuser" class="config-section">
      <div class="section-header">
        <h2>⚙️ 配置管理</h2>
      </div>
      
      <div class="card">
        <div class="card-header">
          <h3>上传供应商配置</h3>
        </div>
        <div class="card-body">
          <p>请选择一个 <code>.yml</code> 或 <code>.yaml</code> 格式的供应商配置文件进行上传。</p>
          <div class="upload-section">
            <input ref="fileInput" class="file-input" type="file" accept=".yml,.yaml" @change="handleFileChange">
            <button class="btn btn-primary" :disabled="!selectedFile || isLoadingUpload" @click="handleUpload">
              <span v-if="isLoadingUpload">上传中...</span>
              <span v-else>上传文件</span>
            </button>
          </div>
          <p v-if="uploadMessage" :class="['message', uploadStatus]">{{ uploadMessage }}</p>
        </div>
      </div>

      <div class="card">
        <div class="card-header">
          <h3>刷新配置</h3>
        </div>
        <div class="card-body">
          <p>点击下方按钮将合并所有供应商配置，并热加载到Clash服务中。</p>
          <button class="btn btn-secondary" :disabled="isLoadingRefresh" @click="handleRefresh">
            <span v-if="isLoadingRefresh">刷新中...</span>
            <span v-else>刷新Clash配置</span>
          </button>
          <p v-if="refreshMessage" :class="['message', refreshStatus]">{{ refreshMessage }}</p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, onUnmounted } from 'vue';
import { useClashStore } from '@/stores/clash';
import { useAuthStore } from '@/stores/auth';

const clashStore = useClashStore();
const authStore = useAuthStore();

// 原有的配置管理状态
const selectedFile = ref(null);
const fileInput = ref(null);
const isLoadingUpload = ref(false);
const uploadMessage = ref('');
const uploadStatus = ref('');
const isLoadingRefresh = ref(false);
const refreshMessage = ref('');
const refreshStatus = ref('');

// 健康监控相关状态
const autoRefreshEnabled = ref(true);
const autoRefreshTimer = ref(null);
const operationLoading = reactive({
  reassignAll: false,
  clearBlacklist: false,
  clearSpecific: null,
  reassign: null,
  initialize: false,
  diagnose: false
});

// 新增的Clash状态和诊断结果状态
const clashStatus = ref(null);
const diagnosisResult = ref(null);

// 界面折叠状态控制
const showProxyGroupsDetails = ref(false);
const showContainerMappings = ref(false);

/**
 * @description 格式化时间显示
 * @param {Date} date - 时间对象
 * @returns {string} - 格式化的时间字符串
 */
const formatTime = (date) => {
  if (!date) return '未知';
  return date.toLocaleString('zh-CN', {
    month: 'numeric',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit'
  });
};

/**
 * @description 获取状态样式类
 * @param {string} status - 状态值
 * @returns {string} - CSS类名
 */
const getStatusClass = (status) => {
  const statusMap = {
    'healthy': 'status-healthy',
    'degraded': 'status-degraded', 
    'unhealthy': 'status-unhealthy',
    'error': 'status-error'
  };
  return statusMap[status] || 'status-unknown';
};

/**
 * @description 获取代理组状态
 * @param {string} groupName - 代理组名称
 * @returns {string} - 状态类名
 */
const getProxyGroupStatus = (groupName) => {
  if (!clashStore.proxyGroupsHealth) return '';
  const group = clashStore.proxyGroupsHealth.groups_status?.find(g => g.name === groupName);
  if (!group) return '';
  
  if (group.is_blacklisted) return 'blacklisted';
  if (group.is_healthy) return 'healthy';
  return 'unhealthy';
};

/**
 * @description 获取诊断状态样式类
 * @param {string} status - 诊断状态
 * @returns {string} - CSS类名
 */
const getDiagnosisStatusClass = (status) => {
  const statusMap = {
    'healthy': 'healthy',
    'degraded': 'degraded', 
    'unhealthy': 'unhealthy',
    'critical': 'unhealthy',
    'error': 'unhealthy'
  };
  return statusMap[status] || 'unhealthy';
};

/**
 * @description 获取诊断状态文本
 * @param {string} status - 诊断状态
 * @returns {string} - 状态文本
 */
const getDiagnosisStatusText = (status) => {
  const statusMap = {
    'healthy': '系统运行正常',
    'degraded': '系统存在轻微问题',
    'unhealthy': '系统存在严重问题',
    'critical': '系统处于危险状态',
    'error': '系统无法正常运行'
  };
  return statusMap[status] || '未知状态';
};

/**
 * @description 刷新健康监控数据
 */
const refreshHealthData = async () => {
  try {
    await clashStore.fetchAllHealthData();
  } catch (error) {
    console.error('刷新健康数据失败:', error);
  }
};

/**
 * @description 切换自动刷新
 */
const toggleAutoRefresh = () => {
  if (autoRefreshEnabled.value) {
    startAutoRefresh();
  } else {
    stopAutoRefresh();
  }
};

/**
 * @description 启动自动刷新
 */
const startAutoRefresh = () => {
  stopAutoRefresh(); // 先停止现有的定时器
  autoRefreshTimer.value = setInterval(() => {
    if (!clashStore.isLoadingHealth) {
      refreshHealthData();
    }
  }, 30000); // 30秒
};

/**
 * @description 停止自动刷新
 */
const stopAutoRefresh = () => {
  if (autoRefreshTimer.value) {
    clearInterval(autoRefreshTimer.value);
    autoRefreshTimer.value = null;
  }
};

/**
 * @description 重新分配所有不健康容器
 */
const handleReassignAll = async () => {
  operationLoading.reassignAll = true;
  try {
    const result = await clashStore.reassignAllUnhealthyContainers();
    alert(`操作完成: ${result.message}`);
    await refreshHealthData();
  } catch (error) {
    alert(`操作失败: ${error.msg || error.message || '未知错误'}`);
  } finally {
    operationLoading.reassignAll = false;
  }
};

/**
 * @description 清理过期黑名单
 */
const handleClearBlacklist = async () => {
  operationLoading.clearBlacklist = true;
  try {
    const result = await clashStore.clearBlacklist();
    alert(`操作完成: ${result.message}`);
    await refreshHealthData();
  } catch (error) {
    alert(`操作失败: ${error.msg || error.message || '未知错误'}`);
  } finally {
    operationLoading.clearBlacklist = false;
  }
};

/**
 * @description 清理特定代理组黑名单
 * @param {string} groupName - 代理组名称
 */
const handleClearSpecificBlacklist = async (groupName) => {
  operationLoading.clearSpecific = groupName;
  try {
    const result = await clashStore.clearBlacklist(groupName);
    alert(`操作完成: ${result.message}`);
    await refreshHealthData();
  } catch (error) {
    alert(`操作失败: ${error.msg || error.message || '未知错误'}`);
  } finally {
    operationLoading.clearSpecific = null;
  }
};

/**
 * @description 重新分配特定容器
 * @param {string} containerIp - 容器IP
 */
const handleReassignContainer = async (containerIp) => {
  operationLoading.reassign = containerIp;
  try {
    const result = await clashStore.reassignContainer(containerIp);
    alert(`操作完成: ${result.message}`);
    await refreshHealthData();
  } catch (error) {
    alert(`操作失败: ${error.msg || error.message || '未知错误'}`);
  } finally {
    operationLoading.reassign = null;
  }
};

/**
 * @description 初始化健康监控服务
 */
const handleInitializeServices = async () => {
  operationLoading.initialize = true;
  try {
    const result = await clashStore.initializeHealthServices();
    alert(`操作完成: ${result.message}`);
    await refreshHealthData();
  } catch (error) {
    alert(`操作失败: ${error.msg || error.message || '未知错误'}`);
  } finally {
    operationLoading.initialize = false;
  }
};

/**
 * @description 运行系统诊断
 */
const handleRunDiagnosis = async () => {
  operationLoading.diagnose = true;
  try {
    const result = await clashStore.runSystemDiagnosis();
    
    // 同时获取Clash状态
    const clashStatusResult = await clashStore.fetchClashServiceStatus();
    
    clashStatus.value = clashStatusResult;
    diagnosisResult.value = result;
    
    const issueCount = result.issues_found?.length || 0;
    alert(`系统诊断完成！发现 ${issueCount} 个问题，请查看详细结果。`);
  } catch (error) {
    alert(`操作失败: ${error.msg || error.message || '未知错误'}`);
  } finally {
    operationLoading.diagnose = false;
  }
};

// 原有的配置管理方法
const handleFileChange = (event) => {
  selectedFile.value = event.target.files[0];
  uploadMessage.value = '';
};

const handleUpload = async () => {
  if (!selectedFile.value) {
    uploadMessage.value = '请先选择一个文件。';
    uploadStatus.value = 'error';
    return;
  }

  isLoadingUpload.value = true;
  uploadMessage.value = '';
  uploadStatus.value = '';

  try {
    const response = await clashStore.uploadProvider(selectedFile.value);
    uploadMessage.value = response.message || '文件上传成功！';
    uploadStatus.value = 'success';
    if (fileInput.value) {
      fileInput.value.value = '';
    }
    selectedFile.value = null;
  } catch (error) {
    uploadMessage.value = error.msg || '文件上传失败，请检查网络或联系管理员。';
    uploadStatus.value = 'error';
  } finally {
    isLoadingUpload.value = false;
  }
};

const handleRefresh = async () => {
  isLoadingRefresh.value = true;
  refreshMessage.value = '';
  refreshStatus.value = '';

  try {
    const response = await clashStore.refreshClashConfig();
    refreshMessage.value = response.message || 'Clash配置刷新成功！';
    refreshStatus.value = 'success';
    // 配置刷新后，同时刷新健康数据
    setTimeout(() => {
      refreshHealthData();
    }, 2000);
  } catch (error) {
    refreshMessage.value = error.msg || 'Clash配置刷新失败，请检查服务状态。';
    refreshStatus.value = 'error';
  } finally {
    isLoadingRefresh.value = false;
  }
};

// 组件生命周期
onMounted(async () => {
  // 初始加载健康数据
  await refreshHealthData();
  
  // 初始加载Clash状态
  try {
    clashStatus.value = await clashStore.fetchClashServiceStatus();
  } catch (error) {
    console.error('获取Clash状态失败:', error);
  }
  
  // 启动自动刷新
  if (autoRefreshEnabled.value) {
    startAutoRefresh();
  }
});

onUnmounted(() => {
  stopAutoRefresh();
});
</script>

<style scoped>
.proxies-view-container {
  padding: 2rem;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
  max-width: 1400px;
  margin: 0 auto;
}

h1 {
  color: #333;
  margin-bottom: 0.5rem;
}

.description {
  color: #666;
  margin-bottom: 2rem;
}

/* 分节样式 */
.health-section,
.config-section {
  margin-bottom: 3rem;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1.5rem;
  padding-bottom: 0.5rem;
  border-bottom: 2px solid #f0f0f0;
}

.section-header h2 {
  margin: 0;
  color: #333;
  font-size: 1.5rem;
}

.section-header-with-toggle {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1rem;
  padding-bottom: 0.5rem;
  border-bottom: 1px solid #f0f0f0;
}

.section-header-with-toggle h3 {
  margin: 0;
  color: #333;
  font-size: 1.2rem;
}

.toggle-button {
  font-size: 0.9rem;
  padding: 0.4rem 0.8rem;
  min-height: 32px;
  min-width: 150px;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 1rem;
}

.auto-refresh-toggle {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.9rem;
  color: #666;
}

/* 健康摘要网格 */
.health-summary-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: 1.5rem;
  margin-bottom: 2rem;
}

.health-card {
  background: white;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  padding: 1.5rem;
  border-left: 4px solid #007bff;
}

.health-card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1rem;
}

.health-card-header h3 {
  margin: 0;
  font-size: 1.1rem;
  color: #333;
}

.status-badge {
  padding: 0.25rem 0.75rem;
  border-radius: 12px;
  font-size: 0.8rem;
  font-weight: 600;
  text-transform: uppercase;
}

.status-healthy { background: #d4edda; color: #155724; }
.status-degraded { background: #fff3cd; color: #856404; }
.status-unhealthy { background: #f8d7da; color: #721c24; }
.status-error { background: #f5c6cb; color: #721c24; }

.health-metrics,
.stats-grid {
  display: grid;
  gap: 1rem;
}

.health-metrics {
  grid-template-columns: 1fr 1fr;
}

.stats-grid {
  grid-template-columns: repeat(auto-fit, minmax(80px, 1fr));
}

.metric {
  display: flex;
  flex-direction: column;
}

.metric-label {
  font-size: 0.8rem;
  color: #666;
  margin-bottom: 0.25rem;
}

.metric-value {
  font-size: 1.1rem;
  font-weight: 600;
  color: #333;
}

.stat-item {
  text-align: center;
}

.stat-number {
  display: block;
  font-size: 1.5rem;
  font-weight: 700;
  margin-bottom: 0.25rem;
}

.stat-number.healthy { color: #28a745; }
.stat-number.unhealthy { color: #dc3545; }
.stat-number.blacklisted { color: #6c757d; }
.stat-number.total { color: #007bff; }

.stat-label {
  font-size: 0.8rem;
  color: #666;
  text-transform: uppercase;
}

/* 快速操作 */
.quick-actions {
  display: flex;
  gap: 1rem;
  margin-bottom: 2rem;
  flex-wrap: wrap;
}

/* Clash状态和诊断面板 */
.diagnosis-section {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
  gap: 1.5rem;
  margin-top: 2rem;
}

.clash-status-card,
.diagnosis-card {
  background: white;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  padding: 1.5rem;
  border-left: 4px solid #007bff;
}

.clash-status-card.healthy { border-left-color: #28a745; }
.clash-status-card.unhealthy { border-left-color: #dc3545; }
.clash-status-card.blacklisted { border-left-color: #6c757d; }

.clash-status-card .card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1rem;
}

.clash-status-card .card-header h3 {
  margin: 0;
  font-size: 1.1rem;
  color: #333;
}

.clash-status-card .status-indicators {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.clash-status-card .service-status {
  padding: 0.25rem 0.75rem;
  border-radius: 12px;
  font-size: 0.8rem;
  font-weight: 600;
  text-transform: uppercase;
}

.clash-status-card .service-status.online { background: #d4edda; color: #155724; }
.clash-status-card .service-status.offline { background: #f8d7da; color: #721c24; }

.clash-info-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 0.75rem;
}

.clash-info-grid .info-item {
  display: flex;
  justify-content: space-between;
  font-size: 0.9rem;
  color: #555;
}

.clash-info-grid .info-label {
  font-weight: 500;
  color: #333;
}

.clash-info-grid .info-value {
  font-weight: 600;
  color: #007bff;
  font-family: monospace;
}

.clash-errors {
  margin-top: 1rem;
  padding-top: 1rem;
  border-top: 1px solid #eee;
}

.clash-errors h4 {
  margin-bottom: 0.5rem;
  color: #dc3545;
}

.error-list {
  list-style: none;
  padding: 0;
  margin: 0;
}

.error-item {
  font-size: 0.85rem;
  color: #721c24;
  margin-bottom: 0.25rem;
}

.diagnosis-card {
  border-left-color: #28a745; /* 绿色边框 */
}

.diagnosis-card .card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1rem;
}

.diagnosis-card .card-header h3 {
  margin: 0;
  font-size: 1.1rem;
  color: #333;
}

.diagnosis-card .diagnosis-status {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.diagnosis-card .health-badge {
  padding: 0.25rem 0.75rem;
  border-radius: 12px;
  font-size: 0.8rem;
  font-weight: 600;
  text-transform: uppercase;
}

.diagnosis-card .health-badge.healthy { background: #d4edda; color: #155724; }
.diagnosis-card .health-badge.degraded { background: #fff3cd; color: #856404; }
.diagnosis-card .health-badge.unhealthy { background: #f8d7da; color: #721c24; }
.diagnosis-card .health-badge.blacklisted { background: #e2e3e5; color: #383d41; }

.issues-section,
.recommendations-section {
  margin-top: 1rem;
  padding-top: 1rem;
  border-top: 1px solid #eee;
}

.issues-section h4 {
  margin-bottom: 0.5rem;
  color: #dc3545; /* 红色标题 */
}

.recommendations-section h4 {
  margin-bottom: 0.5rem;
  color: #28a745; /* 绿色标题 */
}

.issues-list,
.recommendations-list {
  list-style: none;
  padding: 0;
  margin: 0;
}

.issue-item,
.recommendation-item {
  font-size: 0.85rem;
  color: #333;
  margin-bottom: 0.25rem;
}

.diagnosis-footer {
  margin-top: 1rem;
  padding-top: 1rem;
  border-top: 1px solid #eee;
  font-size: 0.8rem;
  color: #666;
}

.diagnosis-footer .diagnosis-time {
  font-weight: 500;
  color: #333;
}

/* 代理组健康状态 */
.proxy-groups-health {
  margin-top: 3rem;
}


.proxy-groups-health h3 {
  margin-bottom: 1rem;
  color: #333;
}

.groups-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
  gap: 1rem;
}

.group-card {
  background: white;
  border-radius: 8px;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
  padding: 1rem;
  border-left: 4px solid #6c757d;
}

.group-card.healthy { border-left-color: #28a745; }
.group-card.unhealthy { border-left-color: #dc3545; }
.group-card.blacklisted { border-left-color: #6c757d; }

.group-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.75rem;
}

.group-name {
  font-weight: 600;
  color: #333;
  font-family: monospace;
}

.badge {
  padding: 0.2rem 0.5rem;
  border-radius: 4px;
  font-size: 0.75rem;
  font-weight: 600;
}

.badge.healthy { background: #d4edda; color: #155724; }
.badge.unhealthy { background: #f8d7da; color: #721c24; }
.badge.blacklisted { background: #e2e3e5; color: #383d41; }

.group-details {
  margin-bottom: 0.75rem;
}

.detail-row {
  display: flex;
  justify-content: space-between;
  margin-bottom: 0.25rem;
  font-size: 0.85rem;
}

.detail-label {
  color: #666;
}

.detail-value {
  font-weight: 500;
  font-family: monospace;
}

.group-actions {
  display: flex;
  gap: 0.5rem;
}

/* 容器映射表 */
.container-mappings{
  margin-top: 2rem;
}


.container-mappings h3 {
  color: #333;
}

.mappings-table {
  background: white;
  border-radius: 8px;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
  overflow: hidden;
}

.table-header,
.table-row {
  display: grid;
  grid-template-columns: 1fr 2fr 1fr;
  gap: 1rem;
  padding: 0.75rem 1rem;
}

.table-header {
  background: #f8f9fa;
  font-weight: 600;
  color: #495057;
  border-bottom: 1px solid #dee2e6;
}

.table-row {
  border-bottom: 1px solid #f8f9fa;
}

.table-row:last-child {
  border-bottom: none;
}

.table-row:hover {
  background: #f8f9fa;
}

.table-cell {
  display: flex;
  align-items: center;
}

.proxy-group-tag {
  padding: 0.25rem 0.5rem;
  border-radius: 4px;
  font-size: 0.8rem;
  font-weight: 500;
  font-family: monospace;
}

.proxy-group-tag.healthy { background: #d4edda; color: #155724; }
.proxy-group-tag.unhealthy { background: #f8d7da; color: #721c24; }
.proxy-group-tag.blacklisted { background: #e2e3e5; color: #383d41; }

.no-data {
  text-align: center;
  padding: 2rem;
  color: #666;
  background: white;
  border-radius: 8px;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}

/* 原有样式保持不变 */
.card {
  background-color: #fff;
  border-radius: 8px;
  box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
  margin-bottom: 2rem;
  overflow: hidden;
}

.card-header {
  background-color: #f7f7f7;
  padding: 1rem 1.5rem;
  border-bottom: 1px solid #eee;
}

.card-header h3 {
  margin: 0;
  font-size: 1.25rem;
  color: #333;
}

.card-body {
  padding: 1.5rem;
}

.card-body p {
  color: #555;
  margin-top: 0;
  margin-bottom: 1rem;
}

.upload-section {
  display: flex;
  align-items: center;
  gap: 1rem;
}

.file-input {
  border: 1px solid #ccc;
  border-radius: 4px;
  padding: 0.5rem;
  flex-grow: 1;
}

/* 按钮样式 */
.btn {
  padding: 0.6rem 1.2rem;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 1rem;
  font-weight: 500;
  transition: all 0.2s ease-in-out;
  text-decoration: none;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 38px;
}

.btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.btn-primary { background: #007bff; color: white; }
.btn-primary:hover:not(:disabled) { background: #0056b3; }

.btn-secondary { background: #6c757d; color: white; }
.btn-secondary:hover:not(:disabled) { background: #5a6268; }

.btn-success { background: #28a745; color: white; }
.btn-success:hover:not(:disabled) { background: #1e7e34; }

.btn-warning { background: #ffc107; color: #212529; }
.btn-warning:hover:not(:disabled) { background: #e0a800; }

.btn-info { background: #17a2b8; color: white; }
.btn-info:hover:not(:disabled) { background: #138496; }

.btn-outline {
  background: transparent;
  color: #007bff;
  border: 1px solid #007bff;
}

.btn-outline:hover:not(:disabled) {
  background: #007bff;
  color: white;
}

.btn-sm {
  padding: 0.4rem 0.8rem;
  font-size: 0.875rem;
  min-height: 32px;
}

.message {
  margin-top: 1rem;
  padding: 0.75rem 1.25rem;
  border-radius: 4px;
  font-weight: 500;
}

.message.success {
  background-color: #d4edda;
  color: #155724;
  border: 1px solid #c3e6cb;
}

.message.error {
  background-color: #f8d7da;
  color: #721c24;
  border: 1px solid #f5c6cb;
}

/* 响应式设计 */
@media (max-width: 768px) {
  .proxies-view-container {
    padding: 1rem;
  }
  
  .health-summary-grid {
    grid-template-columns: 1fr;
  }
  
  .groups-grid {
    grid-template-columns: 1fr;
  }
  
  .header-actions {
    flex-direction: column;
    align-items: flex-end;
    gap: 0.5rem;
  }
  
  .quick-actions {
    flex-direction: column;
  }
  
  .table-header,
  .table-row {
    grid-template-columns: 1fr;
    gap: 0.5rem;
  }
  
  .upload-section {
    flex-direction: column;
    align-items: stretch;
  }
}
</style> 