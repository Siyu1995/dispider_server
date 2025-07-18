import { defineStore } from 'pinia';
import apiClient from '@/api/axios';
import router from '@/router';

export const useAuthStore = defineStore('auth', {
  state: () => ({
    user: JSON.parse(localStorage.getItem('user')),
    token: localStorage.getItem('token'),
  }),
  getters: {
    isAuthenticated: (state) => !!state.token,
    currentUser: (state) => state.user,
  },
  actions: {
    /**
     * Handles user registration.
     * @param {object} registrationData - The user registration data.
     * @param {string} registrationData.username - The username.
     * @param {string} registrationData.email - The email address.
     * @param {string} registrationData.password - The password.
     * @param {string} registrationData.pushme_key - The PushMe key for notifications.
     * @returns {Promise} The promise from the API call.
     */
    async register(registrationData) {
      return apiClient.post('/auth/users/register', registrationData);
    },

    async login(email, password) {
      const params = new URLSearchParams();
      params.append('username', email);
      params.append('password', password);

      const response = await apiClient.post('/auth/token', params, {
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
        },
      });

      const { access_token } = response.data;
      this.token = access_token;
      localStorage.setItem('token', access_token);
      apiClient.defaults.headers.common['Authorization'] = `Bearer ${access_token}`;
      
      await this.fetchUser();
    },
    async fetchUser() {
        if (this.token) {
            try {
                const { data } = await apiClient.get('/auth/users/me');
                this.user = data.data;
                localStorage.setItem('user', JSON.stringify(this.user));
            } catch (error) {
                console.error("Failed to fetch user", error);
                this.logout();
            }
        }
    },
    logout() {
      this.user = null;
      this.token = null;
      localStorage.removeItem('token');
      localStorage.removeItem('user');
      delete apiClient.defaults.headers.common['Authorization'];
      router.push('/auth/login');
    },
    tryAutoLogin() {
        if(this.token) {
            apiClient.defaults.headers.common['Authorization'] = `Bearer ${this.token}`;
            this.fetchUser();
        }
    }
  },
}); 