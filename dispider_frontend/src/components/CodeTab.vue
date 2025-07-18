<template>
  <div class="code-tab-container">
    <!-- Files List -->
    <div v-if="codeFiles.length > 0" class="file-list-container">
      <h3>已上传文件:</h3>
      <el-card>
        <el-table :data="codeFiles" style="width: 100%">
          <el-table-column prop="name" label="文件名" />
        </el-table>
      </el-card>
    </div>
    <el-empty v-else description="暂未上传任何代码文件"></el-empty>

    <!-- Upload Button -->
    <div class="upload-section">
      <el-button type="primary" size="large" @click="openUploadDialog">
        {{ uploadButtonText }}
      </el-button>
    </div>

    <!-- Upload Dialog -->
    <el-dialog v-model="uploadDialogVisible" title="上传代码包" width="500px" @close="resetUpload">
      <el-alert title="重新上传将覆盖所有历史代码文件，此操作不可逆。" type="warning" show-icon :closable="false" />
      <el-upload
        ref="uploadRef"
        class="upload-dragger"
        drag
        action="#"
        :limit="1"
        :on-exceed="handleExceed"
        :before-upload="beforeUpload"
        :on-change="handleFileChange"
        :auto-upload="false"
      >
        <el-icon class="el-icon--upload"><upload-filled /></el-icon>
        <div class="el-upload__text">
          将文件拖到此处，或<em>点击上传</em>
        </div>
        <template #tip>
          <div class="el-upload__tip">
            请上传 ZIP 格式的代码包，大小不超过 500MB。
          </div>
        </template>
      </el-upload>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="uploadDialogVisible = false">取消</el-button>
          <el-button type="primary" @click="submitUpload" :loading="isUploading">
            确认上传
          </el-button>
        </span>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue';
import { useProjectStore } from '@/stores/project';
import { ElMessage } from 'element-plus';
import { UploadFilled } from '@element-plus/icons-vue';

const props = defineProps({
  projectId: {
    type: Number,
    required: true,
  }
});
const projectStore = useProjectStore();

const uploadDialogVisible = ref(false);
const isUploading = ref(false);
const uploadRef = ref(null);
const fileToUpload = ref(null);

/**
 * @computed
 * @description The list of code files from the store, formatted for the table.
 * @returns {{name: string}[]}
 */
const codeFiles = computed(() => projectStore.codeFiles.map(name => ({ name })));

/**
 * @computed
 * @description The text for the upload button, changes based on whether files exist.
 * @returns {string}
 */
const uploadButtonText = computed(() =>
  codeFiles.value.length > 0 ? '重新上传代码' : '上传代码'
);

/**
 * @description Opens the upload dialog.
 */
const openUploadDialog = () => {
  uploadDialogVisible.value = true;
};

/**
 * @description Handles the file change event from el-upload.
 * @param {object} file - The file object from el-upload.
 */
const handleFileChange = (file) => {
  // Store the raw file object to be used for manual upload
  if (file.status === 'ready') {
    fileToUpload.value = file.raw;
  }
};


/**
 * @description Handles the case where the user tries to upload more than one file.
 * @param {File[]} files - The array of files being uploaded.
 */
const handleExceed = (files) => {
  uploadRef.value.clearFiles();
  const file = files[0];
  uploadRef.value.handleStart(file);
};

/**
 * @description Validates the file before upload.
 * @param {File} rawFile - The raw file object.
 * @returns {boolean} - Whether the file is valid.
 */
const beforeUpload = (rawFile) => {
  if (!rawFile.type.includes('zip')) {
    ElMessage.error('代码包必须是 ZIP 格式!');
    return false;
  }
  if (rawFile.size / 1024 / 1024 > 500) {
    ElMessage.error('文件大小不能超过 500MB!');
    return false;
  }
  return true;
};

/**
 * @description Resets the upload component state.
 */
const resetUpload = () => {
  uploadRef.value.clearFiles();
  fileToUpload.value = null;
};

/**
 * @description Submits the selected file for upload.
 */
const submitUpload = async () => {
  if (!fileToUpload.value) {
    ElMessage.error('请选择要上传的文件!');
    return;
  }
  if (!beforeUpload(fileToUpload.value)) {
    return;
  }

  const formData = new FormData();
  formData.append('file', fileToUpload.value);

  isUploading.value = true;
  try {
    await projectStore.uploadCode(props.projectId, formData);
    ElMessage.success('上传成功!');
    uploadDialogVisible.value = false;
  } catch (error) {
    ElMessage.error('上传失败，请稍后重试。');
    console.error('Upload failed:', error);
  } finally {
    isUploading.value = false;
  }
};

/**
 * @description Fetches the code files when the component is mounted.
 */
onMounted(() => {
  projectStore.fetchCodeFiles(props.projectId);
});
</script>

<style scoped>
.code-tab-container {
  padding: 20px;
}

.file-list-container {
  margin-bottom: 30px;
}

.upload-section {
  text-align: center;
  margin-top: 20px;
}

.upload-dragger {
  margin-top: 20px;
}

.el-upload__tip {
  margin-top: 10px;
  text-align: center;
}
</style> 