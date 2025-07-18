<template>
  <div class="auth-layout">
    <!-- Layout for authentication pages like Login and Register -->
    <router-view />
  </div>
</template>

<script setup>
// Layout for authentication pages
</script>

<style scoped>
/* Add styles for the auth layout */
.auth-layout {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 100vh;
  background-color: var(--color-background);
}
</style> 