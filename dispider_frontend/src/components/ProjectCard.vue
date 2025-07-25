<template>
  <el-card class="project-card" @click="emit('click')">
    <template #header>
      <div class="card-header">
        <span class="project-name" @click="emit('click')">{{ project.name }}</span>
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
        <div :class="{ 'has-alerts': (project.alert_count || 0) > 0 }">
          <strong>待处理警报:</strong> {{ project.alert_count || 0 }}
        </div>
        <div v-if="project.task_progress !== null && project.task_progress !== undefined" class="progress-item">
          <strong>任务进度:</strong>
          <el-progress
            :percentage="formattedTaskProgress"
            :stroke-width="15"
            striped
            striped-flow
            :duration="20"
            style="margin-top: 8px;"
          />
        </div>
        <div v-else class="progress-item">
          <strong>任务进度:</strong> 
          <span class="no-data">暂无数据</span>
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

/**
 * @description 格式化任务进度为百分比
 * @returns {number} - 格式化后的进度百分比 (0-100)
 */
const formattedTaskProgress = computed(() => {
  if (props.project.task_progress === null || props.project.task_progress === undefined) {
    return 0;
  }
  // 后端返回的是 0.0 到 1.0 之间的小数，需要转换为 0 到 100 的百分比
  return Math.round(props.project.task_progress * 100);
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

.progress-item {
  margin-top: 5px;
}

.no-data {
  color: #999;
  font-style: italic;
}

.has-alerts {
  color: red;
  font-weight: bold;
}
</style> 