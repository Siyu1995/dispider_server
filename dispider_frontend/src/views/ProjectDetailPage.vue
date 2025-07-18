<template>
  <div v-if="projectStore.loading">
    <el-skeleton :rows="5" animated />
  </div>
  <div v-else-if="projectStore.error">
    <h1>Error</h1>
    <p>{{ projectStore.error.message }}</p>
  </div>
  <div v-else-if="projectStore.currentProject">
    <h1>{{ projectStore.currentProject.name }}</h1>
    <el-tabs v-model="activeTab" class="demo-tabs">
      <el-tab-pane label="总览" name="overview">
        <project-overview-tab :project="projectStore.currentProject" />
      </el-tab-pane>
      <el-tab-pane label="任务与数据" name="tasks">
        <h4>列名规避：id, status, worker_id, claimed_at, retry_count, note</h4>
        <tasks-tab
          v-if="projectStore.currentProject"
          :project-id="projectStore.currentProject.id"
          :role="projectStore.currentProject.role"
        />
      </el-tab-pane>
      <el-tab-pane label="代码" name="code">
        <CodeTab
          v-if="projectStore.currentProject"
          :project-id="projectStore.currentProject.id"
        />
      </el-tab-pane>
      <!-- <el-tab-pane label="编排" name="orchestration">
        容器编排功能在此处实现。
      </el-tab-pane> -->
      <el-tab-pane label="成员管理" name="members">
        <members-tab
          v-if="projectStore.currentProject"
          :project-id="projectStore.currentProject.id"
          :role="projectStore.currentProject.role"
        />
      </el-tab-pane>
    </el-tabs>
  </div>
  <div v-else>
    <h1>项目未找到。</h1>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue';
import { useRoute } from 'vue-router';
import { useProjectStore } from '@/stores/project';
import ProjectOverviewTab from '@/components/ProjectOverviewTab.vue';
import MembersTab from '@/components/MembersTab.vue';
import TasksTab from '@/components/TasksTab.vue';
import CodeTab from '@/components/CodeTab.vue';

const route = useRoute();
const projectStore = useProjectStore();
const activeTab = ref('overview');

onMounted(() => {
  const projectId = route.params.projectId;
  if (projectId) {
    projectStore.fetchProjectById(projectId);
  }
});
</script>

<style scoped>
.demo-tabs {
  margin-top: 20px;
}
</style> 