<template>
  <div>
    <h1>容器集群</h1>

    <el-form :inline="true" class="filter-form">
      <el-form-item label="项目">
        <el-select v-model="selectedProject" placeholder="所有项目" clearable style="width: 120px;">
          <el-option
            v-for="project in projectStore.projects"
            :key="project.id"
            :label="project.name"
            :value="project.id"
          />
        </el-select>
      </el-form-item>
      <el-form-item label="状态">
        <el-radio-group v-model="selectedStatus">
          <el-radio-button label="">全部</el-radio-button>
          <el-radio-button label="running">运行中</el-radio-button>
          <el-radio-button label="manual">待干预</el-radio-button>
        </el-radio-group>
      </el-form-item>
      <el-form-item>
        <el-button type="primary" @click="openCreateDialog">创建容器</el-button>
      </el-form-item>
    </el-form>

    <div v-if="containerStore.loading">
      <el-skeleton :rows="5" animated />
    </div>
    <div v-else-if="containerStore.error">
      <p>加载容器时出错: {{ containerStore.error.message }}</p>
    </div>
    <div v-else>
      <div v-for="(project, projectId) in groupedContainers" :key="projectId" class="project-group">
        <h2>{{ project.projectName }}</h2>
        <el-table :data="project.containers" style="width: 100%" row-key="id">
          <el-table-column prop="container_name" label="名称" width="350" :show-overflow-tooltip="true" />
          <el-table-column prop="container_id" label="容器ID" width="800" :show-overflow-tooltip="true" />
          <!-- <el-table-column prop="host_port" label="主机端口" /> -->
          <el-table-column prop="status" label="状态">
            <template #default="scope">
              <el-tag :type="statusType(scope.row.status)">{{ scope.row.status }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="360">
            <template #default="scope">
              <el-button
                type="success"
                size="small"
                @click="handleCommand(scope.row.id, 'restart', scope.row.project_id, scope.row.worker_id)"
              >
                重启
              </el-button>
              <el-button
                type="warning"
                size="small"
                @click="handleCommand(scope.row.id, 'stop', scope.row.project_id, scope.row.worker_id)"
              >
                停止
              </el-button>
              <el-button
                type="danger"
                size="small"
                @click="handleCommand(scope.row.id, 'destroy', scope.row.project_id, scope.row.worker_id)"
              >
                销毁
              </el-button>
              <el-button
                type="primary"
                size="small"
                style="margin-left: 10px;"
                @click="openVncViewer(scope.row.id)"
              >
                VNC
              </el-button>
              <el-button
                type="info"
                size="small"
                style="margin-left: 10px;"
                @click="handleCommand(scope.row.id, 'refresh_status', scope.row.project_id, scope.row.worker_id)"
              >
                刷新
              </el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </div>

    <!-- 批量创建容器的对话框 -->
    <el-dialog v-model="createDialogVisible" title="批量创建容器" width="500px">
      <el-form ref="createFormRef" :model="createForm" label-width="120px" >
        <el-form-item 
          label="选择项目" 
          prop="projectId" 
          :rules="[{ required: true, message: '请选择一个项目', trigger: 'change' }]">
          <el-select v-model="createForm.projectId" placeholder="请选择项目" style="width: 100%;">
            <el-option
              v-for="project in projectStore.projects"
              :key="project.id"
              :label="project.name"
              :value="project.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item 
          label="容器数量" 
          prop="containerCount" 
          :rules="[{ required: true, message: '请输入要创建的容器数量'}]">
          <el-input-number v-model="createForm.containerCount" :min="1" :max="100" />
        </el-form-item>
      </el-form>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="createDialogVisible = false">取消</el-button>
          <el-button type="primary" :loading="isCreating" @click="handleCreateContainers" >
            确定
          </el-button>
        </span>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { onMounted, computed, ref, watch, onBeforeUnmount } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { useContainerStore } from '@/stores/container';
import { useProjectStore } from '@/stores/project';
import { ElMessageBox, ElMessage } from 'element-plus';

const route = useRoute();
const router = useRouter();
const containerStore = useContainerStore();
const projectStore = useProjectStore();

const selectedProject = ref('');
const selectedStatus = ref('');
let pollingInterval = null;

// 用于创建容器对话框的状态
const createDialogVisible = ref(false);
const createFormRef = ref(null);
const isCreating = ref(false);
const createForm = ref({
  projectId: null,
  containerCount: 1,
});

const projectMap = computed(() =>
  projectStore.projects.reduce((map, project) => {
    map[project.id] = project.name;
    return map;
  }, {})
);

const processedContainers = computed(() => {
  const alertIds = new Set(containerStore.alertContainerIds);
  return containerStore.containers.map(container => {
    // 使用 'worker_id'进行匹配，而不是 'container_id'
    if (alertIds.has(container.worker_id)) {
      return { ...container, status: 'manual' };
    }
    return container;
  });
});

const groupedContainers = computed(() => {
  let filteredContainers = processedContainers.value;

  if (selectedProject.value) {
    filteredContainers = filteredContainers.filter(
      (c) => c.project_id === selectedProject.value
    );
  }

  if (selectedStatus.value) {
    filteredContainers = filteredContainers.filter(
      (c) => c.status === selectedStatus.value
    );
  }

  // Add 'manual' to the status filter options if any container has this status
  if (!selectedStatus.value && processedContainers.value.some(c => c.status === 'manual')) {
    // This part is tricky. For now, manual status will show up under '全部'
  }

  return filteredContainers.reduce((acc, container) => {
    const { project_id } = container;
    const projectName = projectMap.value[project_id] || `Project ID: ${project_id}`;
    if (!acc[project_id]) {
      acc[project_id] = {
        projectName: projectName,
        containers: [],
      };
    }
    acc[project_id].containers.push(container);
    return acc;
  }, {});
});

/**
 * @description 打开批量创建容器的对话框。
 * 如果筛选器中已选定项目，则自动填充。
 */
const openCreateDialog = () => {
  createForm.value.projectId = selectedProject.value || null;
  createForm.value.containerCount = 1;
  createDialogVisible.value = true;
};

/**
 * @description 处理批量创建容器的逻辑。
 * 首先验证表单，然后调用 store 中的 action。
 */
const handleCreateContainers = async () => {
  if (!createFormRef.value) return;
  await createFormRef.value.validate(async (valid) => {
    if (valid) {
      isCreating.value = true;
      try {
        await containerStore.batchStartContainers(
          createForm.value.projectId,
          createForm.value.containerCount
        );
        ElMessage.success('容器创建任务已成功发送。');
        createDialogVisible.value = false;
      } catch (error) {
        console.error('创建容器失败:', error);
        ElMessage.error(error.response?.data?.detail || '创建容器失败，请检查网络或联系管理员。');
      } finally {
        isCreating.value = false;
      }
    }
  });
};

const statusType = (status) => {
  switch (status) {
    case 'running':
      return 'success';
    case 'exited':
      return 'info';
    case 'created':
        return 'primary';
    case 'manual':
        return 'danger';
    default:
      return 'danger';
  }
};

const openVncViewer = (containerId) => {
  // router.push({ name: 'VncViewer', params: { containerId } });
  // 解析路由以获取 URL
  const routeData = router.resolve({ name: 'VncViewer', params: { containerId } });
  // 使用 window.open 在新标签页中打开 URL
  window.open(routeData.href, '_blank');
};

const handleCommand = async (containerId, command, projectId, workerId) => {
  switch (command) {
    case 'restart':
    case 'stop':
    case 'destroy':
      try {
        await ElMessageBox.confirm(
          `确定要 ${command} 这个容器吗?`,
          '警告',
          {
            confirmButtonText: '确定',
            cancelButtonText: '取消',
            type: 'warning',
          }
        );
        await containerStore.sendContainerCommand(containerId, command);
        ElMessage.success(`容器 ${command} 命令已发送。`);
      } catch (error) {
        if (error !== 'cancel') {
          console.error(`执行命令 ${command} 失败:`, error);
          ElMessage.error(`执行命令 ${command} 失败。`);
        }
      }
      break;
    
    case 'refresh_status':
        if (!projectId || !workerId) {
            ElMessage.error("缺少项目 ID 或工作器 ID，无法刷新状态。");
            return;
        }
        try {
            await containerStore.reportContainerStatus(projectId, workerId);
            ElMessage.success(`容器 ${workerId} 的状态已上报为 'running'。`);
        } catch (error) {
            ElMessage.error(error.response?.data?.detail || `上报容器 ${workerId} 状态时出错。`);
        }
        break;

    default:
      console.warn(`未知的命令: ${command}`);
  }
};

const startPolling = (projectId) => {
  // Clear any existing polling interval to prevent multiple intervals running.
  if (pollingInterval) {
    clearInterval(pollingInterval);
  }

  let fetchData;

  if (projectId) {
    // If a specific project is selected, define a fetcher for that project.
    fetchData = () => {
      containerStore.fetchContainers(projectId);
      containerStore.fetchContainerAlerts(projectId);
    };
  } else {
    // If "All Projects" is selected (projectId is empty), define a fetcher for all.
    fetchData = () => {
      containerStore.fetchContainers(); // Fetch all containers
      containerStore.fetchAllContainerAlerts(); // Fetch alerts for all projects
    };
  }

  fetchData(); // Execute fetch immediately without waiting for the interval.
  pollingInterval = setInterval(fetchData, 60000); // Set up the polling interval.
};

onMounted(async () => {
  await projectStore.fetchProjects();

  const projectIdFromQuery = route.query.projectId;
  if (projectIdFromQuery) {
    selectedProject.value = parseInt(projectIdFromQuery, 10);
  }
  
  // Start polling based on the selected project
  startPolling(selectedProject.value);
});

onBeforeUnmount(() => {
  if (pollingInterval) {
    clearInterval(pollingInterval);
  }
});

// Watch for changes in the selected project and restart polling
watch(selectedProject, (newProjectId) => {
  startPolling(newProjectId);
});
</script>

<style scoped>
.project-group {
  margin-bottom: 30px;
}

.filter-form {
  margin-bottom: 20px;
}
</style>