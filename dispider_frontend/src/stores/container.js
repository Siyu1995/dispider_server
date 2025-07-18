import { defineStore } from 'pinia';
import apiClient from '@/api/axios';
import { useProjectStore } from '@/stores/project';

/**
 * @typedef {object} Container
 * @property {number} id - Database ID for the container.
 * @property {string} container_id - Docker container ID.
 * @property {string} worker_id - The dispider worker's unique ID.
 * @property {string} container_name - Docker container name.
 * @property {string} status - Container status (e.g., 'running', 'exited').
 * @property {string} [host_port] - The host port mapping for the container.
 * @property {number} project_id - ID of the parent project.
 */

export const useContainerStore = defineStore('container', {
  state: () => ({
    /** @type {Container[]} */
    containers: [],
    /** @type {string[]} */
    alertContainerIds: [],
    loading: false,
    error: null,
  }),
  actions: {
    /**
     * Fetches containers from the API.
     * @param {string} [projectId] - Optional project ID to filter containers.
     */
    async fetchContainers(projectId) {
      this.loading = true;
      this.error = null;
      try {
        let url = '/containers/';
        if (projectId) {
          url += `?project_id=${projectId}`;
        }
        const response = await apiClient.get(url);
        this.containers = response.data;
      } catch (error) {
        // 全局拦截器已处理错误弹窗，此处仅在控制台记录错误
        console.error('Error fetching containers:', error);
      } finally {
        this.loading = false;
      }
    },

    /**
     * Fetches container alerts from the API.
     * @param {string} projectId - The project ID to fetch alerts for.
     */
    async fetchContainerAlerts(projectId) {
      try {
        const response = await apiClient.get(`/projects/${projectId}/containers/alerts`);
        // 存储需要人工干预的容器 worker_id 列表
        this.alertContainerIds = response.data.map(alert => alert.worker_id);
        console.log("alertContainerIds", this.alertContainerIds);
      } catch (error) {
        console.error(`Error fetching container alerts for project ${projectId}:`, error);
        // On failure, clear the list to avoid displaying stale alert statuses
        this.alertContainerIds = [];
      }
    },
    
    /**
     * Fetches container alerts for ALL projects by iterating through them.
     */
    async fetchAllContainerAlerts() {
      const projectStore = useProjectStore();
      // Ensure we have the project list before proceeding.
      if (projectStore.projects.length === 0) {
        await projectStore.fetchProjects();
      }

      try {
        // Create an array of promises, each fetching alerts for a single project.
        const alertPromises = projectStore.projects.map(project =>
          apiClient.get(`/projects/${project.id}/containers/alerts`)
        );
        
        // Await all promises to resolve concurrently.
        const responses = await Promise.all(alertPromises);
        
        // Flatten the array of arrays of alerts, and extract the worker_id from each.
        const allWorkerIds = responses.flatMap(response => 
          response.data.map(alert => alert.worker_id)
        );
        
        // Use a Set to ensure uniqueness and update the state.
        this.alertContainerIds = [...new Set(allWorkerIds)];
      } catch (error) {
        console.error('Error fetching alerts for all projects:', error);
        this.alertContainerIds = [];
      }
    },

    /**
     * 上报指定容器的状态为 'running'。
     * @param {number} projectId - 容器所在项目的 ID。
     * @param {string} containerId - 目标容器的 ID (worker_id)。
     */
    async reportContainerStatus(projectId, workerId) {
      try {
        await apiClient.post(`/projects/${projectId}/containers/${workerId}/status`, {
          status: 'running',
          message: 'Manually reported as running by user.',
        });
        // 状态上报成功后，立即刷新当前项目的容器列表以更新UI
        await this.fetchContainers(projectId);
      } catch (error) {
        console.error(`为容器 ${workerId} 上报状态时出错:`, error);
        throw error;
      }
    },

    /**
     * Sends a command to a container (stop, restart, destroy).
     * @param {string | number} containerId - The container's database ID.
     * @param {'stop' | 'restart' | 'destroy'} command - The command to execute.
     */
    async sendContainerCommand(containerId, command) {
      try {
        if (command === 'destroy') {
          // 根据 API 文档, 'destroy' (移除) 操作需要使用 DELETE 方法。
          // 端点是 /api/containers/{container_db_id}。
          await apiClient.delete(`/containers/${containerId}`);
        } else {
          // 'stop' 和 'restart' 命令使用 POST 方法。
          await apiClient.post(`/containers/${containerId}/${command}`);
        }
        // 命令发送成功后，刷新容器列表以更新UI状态。
        await this.fetchContainers();
      } catch (error) {
        // 将错误记录到控制台。
        console.error(`向容器 ${containerId} 发送 '${command}' 命令时出错:`, error);
        // 重新抛出错误，以便调用方（组件）可以捕获并处理UI反馈。
        throw error;
      }
    },

    /**
     * 为指定项目批量启动容器。
     * @param {number} projectId - 目标项目的 ID。
     * @param {number} count - 要创建的容器数量。
     */
    async batchStartContainers(projectId, count) {
      try {
        // 调用后端 API，请求批量创建容器
        await apiClient.post(`/projects/${projectId}/containers/batch/start`, {
          container_count: count,
          image: "dispider:4.1.0", // 根据文档，此为默认镜像，后续可配置
          volumes: null,              // 根据文档，此项可为空
          proxy_config: null          // 根据文档，此项可为空
        });
        // 启动成功后，刷新容器列表以显示新创建的容器
        await this.fetchContainers(projectId);
      } catch (error) {
        console.error(`为项目 ${projectId} 批量启动容器时出错:`, error);
        // 重新抛出错误，以便调用方（组件）可以捕获并处理
        throw error;
      }
    },
  },
}); 