import { createRouter, createWebHistory } from 'vue-router';
import DefaultLayout from '@/layouts/DefaultLayout.vue';
import AuthLayout from '@/layouts/AuthLayout.vue';
import VncLayout from '@/layouts/VncLayout.vue'; // 1. 导入新的 VNC 布局
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
        path: 'projects/:projectId',
        name: 'ProjectDetail',
        component: () => import('@/views/ProjectDetailPage.vue'),
        meta: { requiresAuth: true, layout: 'DefaultLayout' }
      },
      {
        path: 'containers',
        name: 'Containers',
        component: () => import('@/views/ContainersView.vue'),
        meta: { requiresAuth: true, layout: 'DefaultLayout' }
      },
    ],
  },
  // 2. 将 VNC 路由作为一个独立的顶级路由
  {
    path: '/vnc/:containerId',
    component: VncLayout, // 使用 VncLayout
    meta: { requiresAuth: true },
    children: [
        {
            path: '', // 子路由使用父路径
            name: 'VncViewer',
            component: () => import('@/views/VncViewer.vue'),
        }
    ]
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
];

const router = createRouter({
  history: createWebHistory(),
  routes,
});

router.beforeEach((to, from, next) => {
    const authStore = useAuthStore();
    if (to.matched.some(record => record.meta.requiresAuth) && !authStore.isAuthenticated) {
        next({ name: 'Login' });
    } else {
        next();
    }
});

export default router; 