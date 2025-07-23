<template>
  <div class="side-nav">
    <el-menu
      :default-active="activeRoute"
      class="el-menu-vertical-demo"
      router
    >
      <el-menu-item index="/">
        <el-icon><Folder /></el-icon>
        <span>项目</span>
      </el-menu-item>
      <el-menu-item index="/containers">
        <el-icon><Box /></el-icon>
        <span>容器</span>
      </el-menu-item>
      <el-menu-item v-if="authStore.user?.is_super_admin" index="/proxies">
        <el-icon><DataLine /></el-icon>
        <span>代理</span>
      </el-menu-item>
    </el-menu>

    <div class="user-menu">
      <el-dropdown @command="handleCommand">
        <span class="el-dropdown-link">
          <el-avatar>{{ userInitial }}</el-avatar>
        </span>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item command="logout">退出登录</el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue';
import { useRoute } from 'vue-router';
import { useAuthStore } from '@/stores/auth';
import { Folder, Box, DataLine } from '@element-plus/icons-vue';

const route = useRoute();
const authStore = useAuthStore();

/**
 * Computes the active route path for the menu.
 * @returns {string} The current route path.
 */
const activeRoute = computed(() => route.path);

/**
 * Gets the first letter of the user's email for the avatar.
 * @returns {string} The initial of the user's email or 'U' if not available.
 */
const userInitial = computed(() =>
  authStore.user?.email ? authStore.user.email.charAt(0).toUpperCase() : 'U'
);

/**
 * Handles dropdown menu commands.
 * @param {string} command - The command from the dropdown item.
 */
const handleCommand = (command) => {
  if (command === 'logout') {
    authStore.logout();
  }
};
</script>

<style scoped>
.side-nav {
  display: flex;
  flex-direction: column;
  height: 100%;
  max-height: 100%;
  border-right: 1px solid var(--el-border-color);
  width: 100%;
  max-width: 100%;
  box-sizing: border-box; /* Ensures padding and border are included in the element's total width and height */
}

.el-menu-vertical-demo {
  flex-grow: 1;
  border-right: none;
  max-width: 100%;
}

.user-menu {
  padding: 20px;
  max-width: 100%;
  text-align: center;
  margin-top: auto; /* Pushes the user menu to the bottom */
  background-color: white;
}

.el-dropdown-link {
  cursor: pointer;
}
</style> 