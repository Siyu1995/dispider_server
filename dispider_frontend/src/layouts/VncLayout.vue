<template>
  <router-view />
</template>

<script setup>
// 这个布局文件不需要任何特定的逻辑，
// 它只是提供一个无干扰的、全屏的容器来展示 VncViewer 组件。
</script>

<style>
/* 可以在这里添加一些全局样式来确保布局完全占据屏幕 */
html, body {
  margin: 0;
  padding: 0;
  height: 100%;
  width: 100%;
  overflow: hidden; /* 防止出现意外的滚动条 */
}

#app {
  height: 100%;
  width: 100%;
}
</style> 