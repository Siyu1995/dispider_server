import { defineStore } from 'pinia';
import api from '../api/axios';

export const useClashStore = defineStore('clash', {
  state: () => ({
    // 健康监控状态
    systemHealth: null,
    proxyGroupsHealth: null,
    containerMappings: null,
    isLoadingHealth: false,
    lastHealthUpdate: null,
  }),
  
  getters: {
    /**
     * 获取健康率的颜色
     */
    healthRateColor: (state) => {
      if (!state.systemHealth) return 'gray';
      const rate = state.systemHealth.health_rate;
      if (rate >= 80) return 'green';
      if (rate >= 50) return 'orange';
      return 'red';
    },
    
    /**
     * 获取系统状态的显示文本
     */
    systemStatusText: (state) => {
      if (!state.systemHealth) return '未知';
      const status = state.systemHealth.overall_status;
      switch (status) {
        case 'healthy': return '健康';
        case 'degraded': return '降级';
        case 'unhealthy': return '不健康';
        case 'error': return '错误';
        default: return '未知';
      }
    },
    
    /**
     * 获取健康的代理组列表
     */
    healthyGroups: (state) => {
      if (!state.proxyGroupsHealth) return [];
      return state.proxyGroupsHealth.groups_status?.filter(group => 
        group.is_healthy && !group.is_blacklisted
      ) || [];
    },
    
    /**
     * 获取不健康的代理组列表  
     */
    unhealthyGroups: (state) => {
      if (!state.proxyGroupsHealth) return [];
      return state.proxyGroupsHealth.groups_status?.filter(group => 
        !group.is_healthy || group.is_blacklisted
      ) || [];
    }
  },
  
  actions: {
    /**
     * 上传供应商配置文件
     * @param {File} file - 要上传的 YML 文件
     * @returns {Promise<object>} - 后端返回的响应数据
     */
    async uploadProvider(file) {
      const formData = new FormData();
      formData.append('file', file);

      try {
        const response = await api.post('/proxy_manager/providers', formData, {
          headers: {
            'Content-Type': 'multipart/form-data',
          },
        });
        return response.data;
      } catch (error) {
        console.error('Error uploading provider configuration:', error);
        throw error.response?.data || error;
      }
    },

    /**
     * 触发刷新并热加载Clash配置
     * @returns {Promise<object>} - 后端返回的响应数据
     */
    async refreshClashConfig() {
      try {
        const response = await api.post('/proxy_manager/refresh');
        return response.data;
      } catch (error) {
        console.error('Error refreshing Clash configuration:', error);
        throw error.response?.data || error;
      }
    },
    
    /**
     * 获取系统健康摘要
     * @returns {Promise<object>} - 系统健康摘要数据
     */
    async fetchSystemHealth() {
      try {
        const response = await api.get('/proxy_manager/health/summary');
        this.systemHealth = response.data;
        this.lastHealthUpdate = new Date();
        return response.data;
      } catch (error) {
        console.error('Error fetching system health:', error);
        throw error.response?.data || error;
      }
    },
    
    /**
     * 获取代理组健康状态
     * @returns {Promise<object>} - 代理组健康状态数据
     */
    async fetchProxyGroupsHealth() {
      try {
        const response = await api.get('/proxy_manager/health/groups');
        this.proxyGroupsHealth = response.data;
        return response.data;
      } catch (error) {
        console.error('Error fetching proxy groups health:', error);
        throw error.response?.data || error;
      }
    },
    
    /**
     * 获取容器代理映射
     * @returns {Promise<object>} - 容器代理映射数据
     */
    async fetchContainerMappings() {
      try {
        const response = await api.get('/proxy_manager/health/containers');
        this.containerMappings = response.data;
        return response.data;
      } catch (error) {
        console.error('Error fetching container mappings:', error);
        throw error.response?.data || error;
      }
    },
    
    /**
     * 获取所有健康监控数据
     * @returns {Promise<void>}
     */
    async fetchAllHealthData() {
      this.isLoadingHealth = true;
      try {
        await Promise.all([
          this.fetchSystemHealth(),
          this.fetchProxyGroupsHealth(),
          this.fetchContainerMappings()
        ]);
      } catch (error) {
        console.error('Error fetching health data:', error);
        throw error;
      } finally {
        this.isLoadingHealth = false;
      }
    },
    
    /**
     * 手动重新分配容器代理
     * @param {string} containerIp - 容器IP地址
     * @returns {Promise<object>} - 操作结果
     */
    async reassignContainer(containerIp) {
      try {
        const response = await api.post(`/proxy_manager/containers/${containerIp}/reassign`);
        return response.data;
      } catch (error) {
        console.error('Error reassigning container:', error);
        throw error.response?.data || error;
      }
    },
    
    /**
     * 重新分配所有不健康的容器
     * @returns {Promise<object>} - 操作结果
     */
    async reassignAllUnhealthyContainers() {
      try {
        const response = await api.post('/proxy_manager/health/reassign-all');
        return response.data;
      } catch (error) {
        console.error('Error reassigning all unhealthy containers:', error);
        throw error.response?.data || error;
      }
    },
    
    /**
     * 清理代理组黑名单
     * @param {string|null} groupName - 要清理的组名，null表示清理所有过期项
     * @returns {Promise<object>} - 操作结果
     */
    async clearBlacklist(groupName = null) {
      try {
        const params = groupName ? { group_name: groupName } : {};
        const response = await api.delete('/proxy_manager/health/blacklist', { params });
        return response.data;
      } catch (error) {
        console.error('Error clearing blacklist:', error);
        throw error.response?.data || error;
      }
    },
    
    /**
     * 初始化健康监控服务
     * @returns {Promise<object>} - 操作结果
     */
    async initializeHealthServices() {
      try {
        const response = await api.post('/proxy_manager/health/initialize');
        return response.data;
      } catch (error) {
        console.error('Error initializing health services:', error);
        throw error.response?.data || error;
      }
    },
    
    /**
     * 检查Clash服务状态
     * @returns {Promise<object>} - Clash服务状态信息
     */
    async fetchClashServiceStatus() {
      try {
        const response = await api.get('/proxy_manager/health/clash-status');
        return response.data;
      } catch (error) {
        console.error('Error fetching Clash service status:', error);
        throw error.response?.data || error;
      }
    },
    
    /**
     * 运行系统诊断
     * @returns {Promise<object>} - 系统诊断结果
     */
    async runSystemDiagnosis() {
      try {
        const response = await api.get('/proxy_manager/health/diagnose');
        return response.data;
      } catch (error) {
        console.error('Error running system diagnosis:', error);
        throw error.response?.data || error;
      }
    },
  },
});
