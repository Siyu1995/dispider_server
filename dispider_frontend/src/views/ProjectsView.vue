<template>
  <div>
    <div class="page-header">
      <h1>项目列表</h1>
      <el-button
        v-if="authStore.user && authStore.user.is_super_admin"
        type="primary"
        @click="openNewProjectDialog"
      >
        新建项目
      </el-button>
    </div>

    <el-dialog v-model="dialogVisible" title="创建新项目" width="500">
      <el-form :model="newProjectForm" label-width="120px">
        <el-form-item label="项目名称">
          <el-input v-model="newProjectForm.name" />
        </el-form-item>
      </el-form>
      <template #footer>
        <div class="dialog-footer">
          <el-button @click="dialogVisible = false">取消</el-button>
          <el-button type="primary" @click="handleCreateProject">
            创建
          </el-button>
        </div>
      </template>
    </el-dialog>

    <div v-if="projectStore.loading">
      <el-skeleton :rows="5" animated />
    </div>
    <div v-else-if="projectStore.error">
      <p>加载项目时出错: {{ projectStore.error.message }}</p>
    </div>
    <div v-else>
      <el-row :gutter="20">
        <el-col v-for="project in projectStore.projects" :key="project.id" :span="8" >
          <project-card
            :project="project"
            @click="goToProject(project.id)"
            @archive="handleArchiveProject"
            @delete="handleDeleteProject"
          />
        </el-col>
      </el-row>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue';
import { useProjectStore } from '@/stores/project';
import { useAuthStore } from '@/stores/auth';
import { useRouter } from 'vue-router';
import ProjectCard from '@/components/ProjectCard.vue';
import { ElMessageBox } from 'element-plus';

const projectStore = useProjectStore();
const authStore = useAuthStore();
const router = useRouter();

const dialogVisible = ref(false);
const newProjectForm = ref({
  name: '',
});

const openNewProjectDialog = () => {
  dialogVisible.value = true;
};

const handleCreateProject = async () => {
  await projectStore.createProject({
    name: newProjectForm.value.name,
    settings: {},
  });
  if (!projectStore.error) {
    dialogVisible.value = false;
    newProjectForm.value = { name: '' };
  } else {
    // Optionally, show an error message to the user
  }
};

const handleArchiveProject = async (projectId) => {
  await projectStore.archiveProject(projectId);
};

const handleDeleteProject = async (projectId) => {
  ElMessageBox.confirm(
    '此操作将永久删除该项目，是否继续？',
    '警告',
    {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning',
    }
  ).then(async () => {
    await projectStore.deleteProject(projectId);
  }).catch(() => {
    // Canceled
  });
};

onMounted(() => {
  projectStore.fetchProjects();
});

const goToProject = (projectId) => {
  router.push({ name: 'ProjectDetail', params: { projectId } });
};
</script>

<style scoped>
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}
</style> 