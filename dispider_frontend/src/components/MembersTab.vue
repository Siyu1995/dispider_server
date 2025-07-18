<template>
  <div>
    <div class="header">
      <el-button
        v-if="canManageMembers"
        type="primary"
        @click="openAddMemberDialog"
      >
        添加成员
      </el-button>
    </div>

    <el-dialog v-model="dialogVisible" title="添加新成员" width="500">
      <el-form :model="newMemberForm" label-width="120px">
        <el-form-item label="用户">
          <!-- Conditional dropdown for super admins -->
          <el-select
            v-if="isSuperAdmin"
            v-model="newMemberForm.user_id"
            filterable
            placeholder="请选择一个用户"
            style="width: 100%"
            :loading="userStore.loading"
          >
            <el-option
              v-for="item in userStore.allUsers"
              :key="item.id"
              :label="item.username"
              :value="item.id"
            />
          </el-select>
          <!-- Remote search for project admins -->
          <el-select
            v-else
            v-model="newMemberForm.user_id"
            filterable
            remote
            reserve-keyword
            placeholder="请输入关键词搜索用户"
            :remote-method="remoteSearchUsers"
            :loading="userStore.loading"
          >
            <el-option
              v-for="item in userStore.searchResults"
              :key="item.id"
              :label="item.username"
              :value="item.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="角色">
          <el-select v-model="newMemberForm.role" placeholder="请选择角色">
            <el-option label="管理员" value="project_admin" />
            <el-option label="成员" value="project_member" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <div class="dialog-footer">
          <el-button @click="dialogVisible = false">取消</el-button>
          <el-button type="primary" @click="handleAddMember">添加</el-button>
        </div>
      </template>
    </el-dialog>

    <div v-if="projectStore.loading">正在加载成员...</div>
    <el-table :data="projectStore.currentProjectMembers" style="width: 100%">
      <!-- <el-table-column prop="user.avatar" label="Avatar">
        <template #default="scope">
          <el-avatar :src="scope.row.user.avatar_url" />
        </template>
      </el-table-column> -->
      <el-table-column prop="username" label="用户名" />
      <el-table-column prop="role" label="角色" />
      <el-table-column
        v-if="canManageMembers"
        label="操作"
      >
        <template #default="scope">
          <el-button
            size="small"
            type="danger"
            @click="handleRemoveMember(scope.row.user_id)"
          >
            移除
          </el-button>
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>

<script setup>
import { onMounted, ref, computed } from 'vue';
import { useProjectStore } from '@/stores/project';
import { useAuthStore } from '@/stores/auth';
import { useUserStore } from '@/stores/user';
import { ElMessageBox } from 'element-plus';

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
const userStore = useUserStore();

/**
 * A computed property to quickly check if the logged-in user is a super admin.
 * @returns {boolean}
 */
const isSuperAdmin = computed(() => authStore.user?.is_super_admin);

/**
 * Determines if the current user can manage project members.
 * Access is granted to project owners, project admins, and super admins.
 * @returns {boolean}
 */
const canManageMembers = computed(() => {
  if (!authStore.user) return false;
  // Super admins can always manage members.
  if (authStore.user.is_super_admin) return true;
  // Project owners and admins can also manage members.
  return props.role === 'project_owner' || props.role === 'project_admin';
});

const dialogVisible = ref(false);
const newMemberForm = ref({
  user_id: '',
  role: 'project_member',
});

const openAddMemberDialog = () => {
  // Reset form before opening
  newMemberForm.value.user_id = '';
  newMemberForm.value.role = 'project_member';
  userStore.searchResults = [];

  dialogVisible.value = true;

  // For super admins, pre-fetch the full user list to populate the dropdown.
  if (isSuperAdmin.value) {
    userStore.fetchAllUsers();
  }
};

const remoteSearchUsers = (query) => {
  userStore.searchUsers(query);
};

const handleAddMember = async () => {
  if (!newMemberForm.value.user_id) {
    ElMessageBox.alert('请选择一个用户。', '输入错误', {
      confirmButtonText: '确定',
    });
    return;
  }
  await projectStore.addMember(props.projectId, newMemberForm.value);
  dialogVisible.value = false;
};

const handleRemoveMember = async (memberId) => {
  ElMessageBox.confirm(`您确定要移除该成员 (ID: ${memberId}) 吗？`, '警告', {
    confirmButtonText: '确定',
    cancelButtonText: '取消',
    type: 'warning',
  }).then(async () => {
    await projectStore.removeMember(props.projectId, memberId);
  });
};

onMounted(() => {
  if (props.projectId) {
    projectStore.fetchMembers(props.projectId);
  }
});
</script>

<style scoped>
.header {
  margin-bottom: 20px;
  text-align: right;
}
</style> 