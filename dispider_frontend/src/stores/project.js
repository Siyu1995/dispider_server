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
     * Fetches projects from the API.
     */
    async fetchProjects() {
      this.loading = true;
      this.error = null;
      try {
        const response = await apiClient.get('/projects/');
        this.projects = response.data;
        console.log(this.projects);
      } catch (error) {
        // 全局拦截器已处理错误弹窗，此处仅在控制台记录错误
        console.error('Error fetching projects:', error);
      } finally {
        this.loading = false;
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
        await apiClient.post(`/projects/${projectId}/tasks/table`, { columns });
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
        await apiClient.post(`/projects/${projectId}/tasks/results/table`, { columns });
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
        await apiClient.post(`/projects/${projectId}/tasks`, tasksData);
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
        const response = await apiClient.get(`/projects/${projectId}/tasks/columns`);
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
        const response = await apiClient.get(`/projects/${projectId}/tasks/progress`);
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
        const response = await apiClient.get(`/projects/${projectId}/tasks/results/columns`);
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
        const response = await apiClient.get(`/projects/${projectId}/tasks/results/count`);
        // Use a nullish coalescing operator for safer assignment.
        this.resultCount = response.data ?? null;
      } catch (error) {
        this.resultCount = null;
        console.error(`Error fetching result count for project ${projectId}:`, error);
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