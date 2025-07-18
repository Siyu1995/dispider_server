import { defineStore } from 'pinia';
import apiClient from '@/api/axios';

/**
 * @typedef {object} User
 * @property {number} id - The unique identifier for the user.
 * @property {string} username - The user's username.
 * @property {string} email - The user's email address.
 */

export const useUserStore = defineStore('user', {
  state: () => ({
    /** @type {User[]} */
    allUsers: [],
    /** @type {User[]} */
    searchResults: [],
    loading: false,
  }),
  actions: {
    /**
     * Fetches all users from the server.
     * This action is typically restricted to super administrators.
     */
    async fetchAllUsers() {
      this.loading = true;
      try {
        // As per API documentation, this endpoint retrieves all users.
        const response = await apiClient.get('/auth/users');
        // The API returns a standard response format, and the actual user list is in `response.data.data`.
        this.allUsers = response.data.data;
      } catch (error) {
        console.error('Error fetching all users:', error);
        this.allUsers = []; // On failure, clear the list to avoid displaying stale data.
      } finally {
        this.loading = false;
      }
    },

    /**
     * Searches for users.
     * @param {string} query
     */
    async searchUsers(query) {
      if (!query) {
        this.searchResults = [];
        return;
      }
      this.loading = true;
      try {
        const response = await apiClient.get(`/users/search?q=${query}`);
        this.searchResults = response.data;
      } catch (error) {
        console.error('Error searching users:', error);
      } finally {
        this.loading = false;
      }
    },
  },
}); 