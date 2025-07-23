<template>
  <div class="tasks-tab">
    <!-- Section for Initializing Tables -->
    <el-row :gutter="20">
      <!-- Task Table Initialization Card -->
      <el-col :span="12">
        <el-card class="box-card">
          <template #header>
            <div class="card-header">
              <span>初始化任务表</span>
              <el-tooltip
                class="item"
                effect="dark"
                content="上传CSV文件。表头将定义列，数据行将作为新任务导入。"
                placement="top"
              >
                <el-icon><InfoFilled /></el-icon>
              </el-tooltip>
            </div>
          </template>
          <div v-if="canManageProject">
            <div class="upload-section">
              <el-upload
                ref="taskUploadRef"
                :auto-upload="false"
                :on-change="handleTaskFileChange"
                :limit="1"
                accept=".csv"
                :show-file-list="false"
              >
                <template #trigger>
                  <el-button type="primary">选择CSV文件</el-button>
                </template>
              </el-upload>
              <el-button
                class="ml-3"
                type="success"
                :loading="isTaskLoading"
                @click="submitTaskInitialization"
              >
                初始化并填充
              </el-button>
            </div>
             <div v-if="taskFile" class="file-name-display">
                已选择: {{ taskFile.name }}
            </div>
          </div>
          <div v-else>
            <p>仅项目所有者或管理员可初始化数据表。</p>
          </div>
        </el-card>
      </el-col>

      <!-- Result Table Initialization Card -->
      <el-col :span="12">
        <el-card class="box-card">
          <template #header>
            <div class="card-header">
              <span>初始化结果表</span>
              <el-tooltip
                class="item"
                effect="dark"
                content="上传CSV文件。仅使用表头来定义结果表的列。"
                placement="top"
              >
                <el-icon><InfoFilled /></el-icon>
              </el-tooltip>
            </div>
          </template>
          <div v-if="canManageProject">
            <div class="upload-section">
              <el-upload
                ref="resultUploadRef"
                :auto-upload="false"
                :on-change="handleResultFileChange"
                :limit="1"
                accept=".csv"
                :show-file-list="false"
              >
                <template #trigger>
                  <el-button type="primary">选择CSV文件</el-button>
                </template>
              </el-upload>
              <el-button
                class="ml-3"
                type="success"
                :loading="isResultLoading"
                @click="submitResultInitialization"
              >
                初始化
              </el-button>
            </div>
            <div v-if="resultFile" class="file-name-display">
                已选择: {{ resultFile.name }}
            </div>
          </div>
          <div v-else>
            <p>仅项目所有者或管理员可初始化数据表。</p>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- Section for Displaying Table Status -->
    <el-divider content-position="center">数据表状态</el-divider>
    <div class="status-header">
      <el-button :icon="Refresh" circle :loading="isStatusLoading" @click="refreshStatus" />
    </div>

    <el-row :gutter="20" class="status-row">
      <!-- Task Table Status -->
      <el-col :span="12">
        <el-card class="box-card status-card">
          <template #header>
            <div class="card-header">
              <span>任务表状态</span>
            </div>
          </template>
          <div class="status-content">
            <div class="status-item">
              <strong>完成度:</strong>
              <el-progress
                :percentage="formattedTaskProgress"
                :stroke-width="15"
                striped
                striped-flow
                :duration="20"
              />
            </div>
            <div class="status-item">
              <strong>列定义:</strong>
              <div v-if="projectStore.taskColumns && projectStore.taskColumns.length > 0" class="tag-group">
                <el-tag v-for="col in projectStore.taskColumns" :key="col" class="status-tag" type="info">{{ col }}</el-tag>
              </div>
              <el-text v-else type="info">暂未定义列</el-text>
            </div>
          </div>
        </el-card>
      </el-col>

      <!-- Result Table Status -->
      <el-col :span="12">
        <el-card class="box-card status-card">
          <template #header>
            <div class="card-header">
              <span>结果表状态</span>
            </div>
          </template>
          <div class="status-content">
            <div class="status-item">
              <strong>总行数:</strong>
              <el-statistic :value="projectStore.resultCount ?? 0" />
            </div>
            <div class="status-item">
              <strong>列定义:</strong>
              <div v-if="projectStore.resultColumns && projectStore.resultColumns.length > 0" class="tag-group">
                <el-tag v-for="col in projectStore.resultColumns" :key="col" class="status-tag" type="success">{{ col }}</el-tag>
              </div>
              <el-text v-else type="info">暂未定义列</el-text>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue';
import { useProjectStore } from '@/stores/project';
import { useAuthStore } from '@/stores/auth';
import { ElNotification } from 'element-plus';
import Papa from 'papaparse';
import { InfoFilled, Refresh } from '@element-plus/icons-vue';

const props = defineProps({
  projectId: {
    type: Number,
    required: true,
  },
  role: {
    type: String,
    required: true,
  },
});

const projectStore = useProjectStore();
const authStore = useAuthStore();

const taskFile = ref(null);
const resultFile = ref(null);
const isTaskLoading = ref(false);
const isResultLoading = ref(false);
const isStatusLoading = ref(false);


/**
 * Formats the task progress (a value between 0 and 1) into a percentage.
 * @returns {number} The progress as a percentage, rounded to 2 decimal places.
 */
const formattedTaskProgress = computed(() => {
    const progress = projectStore.taskProgress ?? 0;
    return parseFloat((progress * 100).toFixed(2));
});

/**
 * Fetches all status data for both tables.
 */
const refreshStatus = async () => {
  isStatusLoading.value = true;
  await Promise.all([
    projectStore.fetchTaskColumns(props.projectId),
    projectStore.fetchTaskProgress(props.projectId),
    projectStore.fetchResultColumns(props.projectId),
    projectStore.fetchResultCount(props.projectId),
  ]);
  isStatusLoading.value = false;
};

/**
 * Checks if the current user has permissions to manage project settings.
 * @returns {boolean} True if user is super admin, project owner, or project admin.
 */
const canManageProject = computed(() => {
  if (!authStore.user) return false;
  if (authStore.user.is_super_admin) return true;
  return ['project_owner', 'project_admin'].includes(props.role);
});

/**
 * Handles the change event when a task CSV file is selected.
 * @param {object} file - The file object from Element Plus upload component.
 */
const handleTaskFileChange = (file) => {
  taskFile.value = file.raw;
};

/**
 * Handles the change event when a result CSV file is selected.
 * @param {object} file - The file object from Element Plus upload component.
 */
const handleResultFileChange = (file) => {
  resultFile.value = file.raw;
};

/**
 * Parses a CSV file and returns its headers and data.
 * @param {File} file - The CSV file to parse.
 * @param {boolean} headerOnly - Whether to parse only the header.
 * @returns {Promise<{headers: string[], data: object[]}>}
 */
const parseCsv = (file, headerOnly = false) => {
  return new Promise((resolve, reject) => {
    Papa.parse(file, {
      header: true,
      skipEmptyLines: true,
      preview: headerOnly ? 1 : 0, // Preview only 1 row if headerOnly is true
      complete: (results) => {
        if (!results.meta.fields || results.meta.fields.length === 0) {
          reject(new Error('CSV 文件是空的或没有表头。'));
          return;
        }
        resolve({ headers: results.meta.fields, data: results.data });
      },
      error: (error) => reject(error),
    });
  });
};

/**
 * Submits the task table initialization request.
 */
const submitTaskInitialization = async () => {
  if (!taskFile.value) {
    ElNotification.warning('请先选择一个CSV文件。');
    return;
  }
  isTaskLoading.value = true;
  try {
    const { headers, data } = await parseCsv(taskFile.value);

    // Step 1: Initialize table schema with headers
    await projectStore.initializeTaskTable(props.projectId, headers);
    ElNotification.success('任务表结构初始化成功。');

    // Step 2: Batch add task data
    if (data.length > 0) {
      // API expects data in columnar format: { header1: [val1, val2], header2: [valA, valB] }
      const columnarData = headers.reduce((acc, header) => {
        acc[header] = data.map((row) => row[header]);
        return acc;
      }, {});
      await projectStore.batchAddTasks(props.projectId, columnarData);
      ElNotification.success(`成功添加 ${data.length} 个任务。`);
    } else {
      ElNotification.info('CSV 文件不包含数据行。');
    }
  } catch (error) {
    ElNotification.error(`初始化任务表失败：${error.message}`);
  } finally {
    isTaskLoading.value = false;
  }
};

/**
 * Submits the result table initialization request.
 */
const submitResultInitialization = async () => {
  if (!resultFile.value) {
    ElNotification.warning('请先选择一个CSV文件。');
    return;
  }
  isResultLoading.value = true;
  try {
    const { headers } = await parseCsv(resultFile.value, true); // Only parse header
    await projectStore.initializeResultTable(props.projectId, headers);
    ElNotification.success('结果表结构初始化成功。');
  } catch (error) {
    ElNotification.error(`初始化结果表失败：${error.message}`);
  } finally {
    isResultLoading.value = false;
  }
};

onMounted(() => {
  refreshStatus();
});
</script>

<style scoped>
.tasks-tab {
  padding: 20px;
}
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.upload-section {
  display: flex;
  align-items: center;
}
.ml-3 {
  margin-left: 12px;
}
.status-header {
  text-align: right;
  margin-bottom: 10px;
}
.status-row {
  margin-top: 20px;
  display: flex;
  flex-wrap: wrap;
}
.status-card {
  height: 100%;
}
.file-name-display {
  margin-top: 10px;
  color: var(--el-text-color-secondary);
  font-size: 14px;
}
.status-content {
  display: flex;
  flex-direction: column;
  gap: 20px;
}
.status-item {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.tag-group {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
}
.status-tag {
    font-size: 14px;
}
</style> 