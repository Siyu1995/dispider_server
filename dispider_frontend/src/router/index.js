import { createRouter, createWebHistory } from 'vue-router';
import DefaultLayout from '@/layouts/DefaultLayout.vue';
import AuthLayout from '@/layouts/AuthLayout.vue';
import VncLayout from '@/layouts/VncLayout.vue';
import { useAuthStore } from '@/stores/auth';

const routes = [
  {
    path: '/',
    component: DefaultLayout,
    meta: { requiresAuth: true },
    children: [
      {
        path: '',
        name: 'Projects',
        component: () => import('@/views/ProjectsView.vue'),
      },
      {
        path: '/projects/:id',
        name: 'ProjectDetail',
        component: () => import('@/views/ProjectDetailPage.vue'),
        props: true,
      },
      {
        path: '/containers',
        name: 'Containers',
        component: () => import('@/views/ContainersView.vue'),
      },
      {
        path: '/proxies',
        name: 'Proxies',
        component: () => import('@/views/ProxiesView.vue'),
      },
    ],
  },
  {
    path: '/tutorial',
    name: 'Tutorial',
    component: () => import('@/views/TutorialView.vue'),
    meta: { requiresAuth: true }, // Keep auth guard, but no default layout
  },
  {
    path: '/auth',
    component: AuthLayout,
    children: [
      {
        path: 'login',
        name: 'Login',
        component: () => import('@/views/LoginPage.vue'),
      },
      {
        path: 'register',
        name: 'Register',
        component: () => import('@/views/RegisterPage.vue'),
      },
    ],
  },
  {
    path: '/vnc/:containerId',
    name: 'VncViewer',
    component: () => import('@/views/VncViewer.vue'),
    meta: { layout: VncLayout, requiresAuth: true },
    props: true,
  },
];

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes,
});

router.beforeEach((to, from, next) => {
  const authStore = useAuthStore();
  const isAuthenticated = authStore.isAuthenticated;

  if (to.meta.requiresAuth && !isAuthenticated) {
    next({ name: 'Login' });
  } else {
    next();
  }
});

export default router; 