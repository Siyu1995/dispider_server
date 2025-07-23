<template>
  <div>
    <p>{{ project.description || '暂无项目描述。' }}</p>
    <el-descriptions title="项目详情" border :column="2">
      <el-descriptions-item label="状态">{{ project.status }}</el-descriptions-item>
      <el-descriptions-item label="我的角色">{{ project.role }}</el-descriptions-item>
      <el-descriptions-item label="容器数量">{{ project.container_count }}</el-descriptions-item>
      <el-descriptions-item label="待处理警报">{{ project.alert_count }}</el-descriptions-item>
    </el-descriptions>
    <el-button type="primary" style="margin-top: 20px;" @click="goToContainers">
      查看项目容器
    </el-button>
  </div>
</template>

<script setup>
import { useRouter } from 'vue-router';

const props = defineProps({
  project: {
    type: Object,
    required: true,
  },
});

const router = useRouter();

const goToContainers = () => {
  router.push({ path: '/containers', query: { projectId: props.project.id } });
};
</script> 