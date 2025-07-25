import { defineStore } from 'pinia';
import apiClient from '@/api/axios';

/**
 * @typedef {object} Project
 * @property {string} id
 * @property {string} name
 * @property {string} description
 */

/**
 * Store for managing projects.
 */
export const useProjectStore = defineStore('project', {
  state: () => ({
    /** @type {Project[]} */
    projects: [],
    /** @type {Project | null} */
    currentProject: null,
    /** @type {any[]} */
    currentProjectMembers: [],
    /** @type {string[]} */
    taskColumns: [],
    /** @type {number | null} */
    taskProgress: null,
    /** @type {string[]} */
    resultColumns: [],
    /** @type {number | null} */
    resultCount: null,
    /** @type {string[]} */
    codeFiles: [],
    loading: false,
    error: null,
  }),

  actions: {
    /**
     * Fetches projects from the API and enriches them with additional data.
     */
    async fetchProjects() {
      this.loading = true;
      this.error = null;
      try {
        const response = await apiClient.get('/projects/');
        this.projects = response.data;
        
        // Enrich each project with additional data
        await this.enrichProjectsWithStats();
      } catch (error) {
        // 全局拦截器已处理错误弹窗，此处仅在控制台记录错误
        console.error('Error fetching projects:', error);
      } finally {
        this.loading = false;
      }
    },

    /**
     * Enriches projects with container count, alert count, and task progress.
     */
    async enrichProjectsWithStats() {
      try {
        // Fetch all containers once (backend filters by user permissions)
        const allContainersResponse = await apiClient.get('/containers/');
        const allContainers = allContainersResponse.data;
        
        // Fetch all alerts once (using any project ID since backend returns all alerts anyway)
        let allAlerts = [];
        if (this.projects.length > 0) {
          try {
            const alertResponse = await apiClient.get(`/projects/${this.projects[0].id}/containers/alerts`);
            allAlerts = alertResponse.data;
          } catch (error) {
            console.error('Error fetching alerts:', error);
            allAlerts = [];
          }
        }
        
        // Use Promise.allSettled to prevent one failure from affecting others
        const enrichPromises = this.projects.map(async (project) => {
          try {
            // Filter containers by project_id on frontend
            const projectContainers = allContainers.filter(container => container.project_id === project.id);
            project.container_count = projectContainers.length;
            
            // Filter alerts by project_id on frontend
            const projectAlerts = allAlerts.filter(alert => alert.project_id === project.id);
            project.alert_count = projectAlerts.length;
            
            // Fetch task progress
            try {
              const progressResponse = await apiClient.get(`/${project.id}/tasks/progress`);
              project.task_progress = progressResponse.data;
            } catch {
              // If task progress fails, set to null
              project.task_progress = null;
            }
            
          } catch (error) {
            // Set default values if enrichment fails
            project.container_count = 0;
            project.alert_count = 0;
            project.task_progress = null;
            console.error(`Error enriching project ${project.id}:`, error);
          }
        });
        
        await Promise.allSettled(enrichPromises);
      } catch (error) {
        // If we can't fetch containers at all, set all projects to 0
        console.error('Error fetching containers:', error);
        this.projects.forEach(project => {
          project.container_count = 0;
          project.alert_count = 0;
          project.task_progress = null;
        });
      }
    },

    /**
     * Creates a new project.
     * @param {object} projectData - The data for the new project.
     * @param {string} projectData.name - The name of the project.
     * @param {object} [projectData.settings] - Optional settings for the project.
     */
    async createProject(projectData) {
      this.loading = true;
      this.error = null;
      try {
        // The API expects an object with 'name' and optional 'settings'.
        await apiClient.post('/projects/', projectData);
        // After creating, fetch the updated list of projects
        await this.fetchProjects();
      } catch (error) {
        // 全局拦截器已处理错误弹窗，此处仅在控制台记录错误
        console.error('Error creating project:', error);
      } finally {
        this.loading = false;
      }
    },

    /**
     * Archives a project.
     * @param {string} projectId
     */
    async archiveProject(projectId) {
      try {
        await apiClient.post(`/projects/${projectId}/archive`);
        await this.fetchProjects();
      } catch (error) {
        // 全局拦截器已处理错误弹窗，此处仅在控制台记录错误
        console.error('Error archiving project:', error);
      }
    },

    /**
     * Deletes a project.
     * @param {string} projectId
     */
    async deleteProject(projectId) {
      try {
        await apiClient.delete(`/projects/${projectId}`);
        await this.fetchProjects();
      } catch (error) {
        // 全局拦截器已处理错误弹窗，此处仅在控制台记录错误
        console.error('Error deleting project:', error);
      }
    },

    /**
     * Fetches a single project by its ID.
     * @param {string} projectId
     */
    async fetchProjectById(projectId) {
      this.loading = true;
      this.error = null;
      this.currentProject = null;
      try {
        const response = await apiClient.get(`/projects/${projectId}`);
        this.currentProject = response.data;
      } catch (error) {
        // 全局拦截器已处理错误弹窗，此处仅在控制台记录错误
        console.error(`Error fetching project ${projectId}:`, error);
      } finally {
        this.loading = false;
      }
    },

    /**
     * Fetches members for a project.
     * @param {string} projectId
     */
    async fetchMembers(projectId) {
      try {
        const response = await apiClient.get(`/projects/${projectId}/members`);
        this.currentProjectMembers = response.data;
      } catch (error) {
        console.error(`Error fetching members for project ${projectId}:`, error);
      }
    },

    /**
     * Adds a member to a project.
     * @param {string} projectId
     * @param {object} memberData
     * @param {string} memberData.user_id
     * @param {string} memberData.role
     */
    async addMember(projectId, memberData) {
      try {
        await apiClient.post(`/projects/${projectId}/members`, memberData);
        await this.fetchMembers(projectId);
      } catch (error) {
        console.error(`Error adding member to project ${projectId}:`, error);
      }
    },

    /**
     * Removes a member from a project.
     * @param {string} projectId
     * @param {string} userId
     */
    async removeMember(projectId, userId) {
      try {
        await apiClient.delete(`/projects/${projectId}/members/${userId}`);
        await this.fetchMembers(projectId);
      } catch (error) {
        console.error(`Error removing member from project ${projectId}:`, error);
        throw error; // Re-throw the error to be caught by the component
      }
    },

    /**
     * Initializes the task table with a given schema.
     * @param {string} projectId - The ID of the project.
     * @param {string[]} columns - An array of column names for the table.
     */
    async initializeTaskTable(projectId, columns) {
      try {
        await apiClient.post(`/${projectId}/tasks/table`, { columns });
      } catch (error) {
        console.error(`Error initializing task table for project ${projectId}:`, error);
        throw error;
      }
    },

    /**
     * Initializes the result table with a given schema.
     * @param {string} projectId - The ID of the project.
     * @param {string[]} columns - An array of column names for the table.
     */
    async initializeResultTable(projectId, columns) {
      try {
        await apiClient.post(`/${projectId}/tasks/results/table`, { columns });
      } catch (error) {
        console.error(`Error initializing result table for project ${projectId}:`, error);
        throw error;
      }
    },

    /**
     * Batch adds tasks to the project's task table.
     * @param {string} projectId - The ID of the project.
     * @param {object} tasksData - The tasks data in columnar format, e.g., { col1: [...], col2: [...] }.
     */
    async batchAddTasks(projectId, tasksData) {
      try {
        await apiClient.post(`/${projectId}/tasks`, tasksData);
      } catch (error) {
        console.error(`Error batch adding tasks for project ${projectId}:`, error);
        throw error;
      }
    },

    /**
     * Fetches the column names of the task table.
     * @param {string} projectId - The ID of the project.
     */
    async fetchTaskColumns(projectId) {
      try {
        const response = await apiClient.get(`/${projectId}/tasks/columns`);
        // Ensure data is an array before assignment.
        this.taskColumns = Array.isArray(response.data) ? response.data : [];
      } catch (error) {
        this.taskColumns = [];
        console.error(`Error fetching task columns for project ${projectId}:`, error);
      }
    },

    /**
     * Fetches the task completion progress.
     * @param {string} projectId - The ID of the project.
     */
    async fetchTaskProgress(projectId) {
      try {
        const response = await apiClient.get(`/${projectId}/tasks/progress`);
        // Use a nullish coalescing operator for safer assignment.
        this.taskProgress = response.data ?? null;
      } catch (error) {
        this.taskProgress = null;
        console.error(`Error fetching task progress for project ${projectId}:`, error);
      }
    },

    /**
     * Fetches the column names of the result table.
     * @param {string} projectId - The ID of the project.
     */
    async fetchResultColumns(projectId) {
      try {
        const response = await apiClient.get(`/${projectId}/tasks/results/columns`);
        // Ensure data is an array before assignment.
        this.resultColumns = Array.isArray(response.data) ? response.data : [];
      } catch (error) {
        this.resultColumns = [];
        console.error(`Error fetching result columns for project ${projectId}:`, error);
      }
    },

    /**
     * Fetches the total count of results.
     * @param {string} projectId - The ID of the project.
     */
    async fetchResultCount(projectId) {
      try {
        const response = await apiClient.get(`/${projectId}/tasks/results/count`);
        // Use a nullish coalescing operator for safer assignment.
        this.resultCount = response.data ?? null;
      } catch (error) {
        this.resultCount = null;
        console.error(`Error fetching result count for project ${projectId}:`, error);
      }
    },

    /**
     * Fetches the project tables structure (both task and result table columns).
     * @param {string} projectId - The ID of the project.
     */
    async fetchProjectTablesStructure(projectId) {
      try {
        const response = await apiClient.get(`/${projectId}/tasks/schema`);
        return response.data;
      } catch (error) {
        console.error(`Error fetching project tables structure for project ${projectId}:`, error);
        throw error;
      }
    },

    /**
     * Gets the next available task for a worker.
     * @param {string} projectId - The ID of the project.
     * @param {string} workerId - The ID of the worker requesting the task.
     */
    async getNextTask(projectId, workerId) {
      try {
        const response = await apiClient.get(`/${projectId}/tasks/next?worker_id=${workerId}`);
        return response.data;
      } catch (error) {
        // 204 No Content means no tasks available, which is not an error
        if (error.response?.status === 204) {
          return null;
        }
        console.error(`Error getting next task for project ${projectId}:`, error);
        throw error;
      }
    },

    /**
     * Submits the result of a completed task.
     * @param {string} projectId - The ID of the project.
     * @param {number} taskId - The ID of the task.
     * @param {object} resultData - The result data to submit.
     */
    async submitTaskResult(projectId, taskId, resultData) {
      try {
        const response = await apiClient.post(`/${projectId}/tasks/${taskId}/result`, resultData);
        return response.data;
      } catch (error) {
        console.error(`Error submitting result for task ${taskId} in project ${projectId}:`, error);
        throw error;
      }
    },

    /**
     * Reports a task failure.
     * @param {string} projectId - The ID of the project.
     * @param {number} taskId - The ID of the task that failed.
     * @param {string} [errorMessage] - Optional error message describing the failure.
     */
    async reportTaskFailure(projectId, taskId, errorMessage = null) {
      try {
        const payload = errorMessage ? { error: errorMessage } : {};
        const response = await apiClient.post(`/${projectId}/tasks/${taskId}/fail`, payload);
        return response.data;
      } catch (error) {
        console.error(`Error reporting failure for task ${taskId} in project ${projectId}:`, error);
        throw error;
      }
    },

    /**
     * Fetches the list of code files for a project.
     * @param {string} projectId - The ID of the project.
     */
    async fetchCodeFiles(projectId) {
      try {
        const response = await apiClient.get(`/projects/${projectId}/files`);
        this.codeFiles = response.data.files || [];
      } catch (error) {
        this.codeFiles = [];
        console.error(`Error fetching code files for project ${projectId}:`, error);
      }
    },

    /**
     * Uploads a code package for a project.
     * @param {string} projectId - The ID of the project.
     * @param {FormData} formData - The form data containing the file.
     */
    async uploadCode(projectId, formData) {
      this.loading = true;
      this.error = null;
      try {
        await apiClient.post(`/projects/${projectId}/code`, formData, {
          headers: {
            'Content-Type': 'multipart/form-data',
          },
        });
        // After successful upload, refresh the file list.
        await this.fetchCodeFiles(projectId);
      } catch (error) {
        // 全局拦截器已处理错误弹窗，此处仅在控制台记录错误
        console.error(`Error uploading code for project ${projectId}:`, error);
        throw error; // Re-throw to be handled by the component.
      } finally {
        this.loading = false;
      }
    },
  },
}); 