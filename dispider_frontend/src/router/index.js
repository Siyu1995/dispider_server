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
      {
        path: '/proxies',
        name: 'proxies',
        component: () => import('@/views/ProxiesView.vue'),
        meta: { requiresAuth: true, requiresSuperuser: true }
      }
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

router.beforeEach(async (to, from, next) => {
  const authStore = useAuthStore();

  // 确保在检查权限之前，用户信息已经加载完毕
  // 如果 token 存在但用户信息不存在，则尝试获取用户信息
  if (authStore.token && !authStore.user) {
    await authStore.fetchUser();
  }

  const isAuthenticated = authStore.isAuthenticated;
  const requiresAuth = to.matched.some(record => record.meta.requiresAuth);
  const requiresSuperuser = to.matched.some(record => record.meta.requiresSuperuser);

  if (requiresAuth && !isAuthenticated) {
    // 如果路由需要认证但用户未登录，则重定向到登录页
    next('/auth/login');
  } else if (requiresSuperuser && !authStore.user?.is_super_admin) {
    // 如果路由需要超级用户权限但当前用户不是，则重定向到首页或错误页
    next('/'); // 或者 next('/unauthorized')
  } else {
    // 其他情况正常放行
    next();
  }
});

export default router; 