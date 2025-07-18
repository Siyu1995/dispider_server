<template>
  <div class="common-layout">
    <el-container>
      <el-aside width="200px">
        <side-nav />
      </el-aside>
      <el-main>
        <router-view />
      </el-main>
    </el-container>
  </div>
</template>

<script setup>
import SideNav from '@/components/SideNav.vue';
</script>

<style scoped>
.common-layout, .el-container {
  height: 100vh;
}

.el-main {
  padding: 20px;
  overflow-y: auto;
}
</style> 