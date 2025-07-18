<template>
  <el-card class="project-card" @click="emit('click')">
    <template #header>
      <div class="card-header">
        <span @click="emit('click')" class="project-name">{{ project.name }}</span>
        <div class="header-right">
          <el-tag :type="statusType">{{ project.status || '未知' }}</el-tag>
          <el-dropdown
            v-if="authStore.user && authStore.user.is_super_admin"
            @command="handleCommand"
          >
            <span class="el-dropdown-link">
              ...
            </span>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="archive">归档</el-dropdown-item>
                <el-dropdown-item command="delete" divided>删除</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </div>
    </template>
    <div class="card-body">
      <p>{{ project.description }}</p>
      <div class="project-meta">
        <div><strong>角色:</strong> <el-tag size="small">{{ project.role || 'N/A' }}</el-tag></div>
        <div><strong>容器数:</strong> {{ project.container_count || 0 }}</div>
        <div :class="{ 'has-alerts': project.alert_count > 0 }">
          <strong>待处理警报:</strong> {{ project.alert_count || 0 }}
        </div>
      </div>
    </div>
  </el-card>
</template>

<script setup>
import { computed } from 'vue';
import { useAuthStore } from '@/stores/auth';

const props = defineProps({
  project: {
    type: Object,
    required: true,
  },
});

const authStore = useAuthStore();

const emit = defineEmits(['click', 'archive', 'delete']);

const statusType = computed(() => {
  switch (props.project.status) {
    case 'running':
      return 'success';
    case 'stopped':
      return 'info';
    case 'error':
      return 'danger';
    default:
      return 'primary';
  }
});

const handleCommand = (command) => {
  if (command === 'archive') {
    emit('archive', props.project.id);
  } else if (command === 'delete') {
    emit('delete', props.project.id);
  }
};
</script>

<style scoped>
.project-card {
  margin-bottom: 20px;
  cursor: pointer;
}

.project-name {
  cursor: pointer;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 10px;
}

.el-dropdown-link {
  cursor: pointer;
  font-size: 20px;
  font-weight: bold;
}

.project-meta {
  margin-top: 10px;
  display: grid;
  gap: 5px;
}

.has-alerts {
  color: red;
  font-weight: bold;
}
</style> 