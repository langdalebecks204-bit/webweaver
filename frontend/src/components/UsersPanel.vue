<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useUsersStore } from '../stores/users'

const store = useUsersStore()
const dialogVisible = ref(false)
const editing = ref(null)
const form = ref({ username: '', password: '', role: 'viewer' })

onMounted(() => store.load())

function openCreate() {
  editing.value = null
  form.value = { username: '', password: '', role: 'viewer' }
  dialogVisible.value = true
}

function openEdit(user) {
  editing.value = user
  form.value = { username: user.username, password: '', role: user.role }
  dialogVisible.value = true
}

async function onSave() {
  try {
    if (editing.value) {
      const payload = { role: form.value.role }
      if (form.value.password) payload.password = form.value.password
      await store.update(editing.value.id, payload)
    } else {
      await store.create({
        username: form.value.username,
        password: form.value.password,
        role: form.value.role,
      })
    }
    dialogVisible.value = false
    ElMessage.success('已保存')
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '保存失败')
  }
}

async function onDelete(user) {
  try {
    await ElMessageBox.confirm(`确定删除用户「${user.username}」？`, '删除确认')
  } catch (error) {
    return
  }
  try {
    await store.remove(user.id)
    ElMessage.success('已删除')
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '删除失败')
  }
}
</script>

<template>
  <el-card>
    <template #header>
      <div class="toolbar">
        <el-button type="primary" @click="openCreate">新增用户</el-button>
        <el-button @click="store.load()">刷新</el-button>
      </div>
    </template>
    <table class="users-table">
      <thead>
        <tr>
          <th>用户名</th>
          <th>角色</th>
          <th>创建时间</th>
          <th>操作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="u in store.users" :key="u.id">
          <td>{{ u.username }}</td>
          <td>
            <el-tag :type="u.role === 'admin' ? 'danger' : 'info'">{{ u.role }}</el-tag>
          </td>
          <td>{{ u.created_at }}</td>
          <td>
            <el-button size="small" @click="openEdit(u)">编辑</el-button>
            <el-button size="small" type="danger" @click="onDelete(u)">删除</el-button>
          </td>
        </tr>
      </tbody>
    </table>

    <el-dialog v-model="dialogVisible" :title="editing ? '编辑用户' : '新增用户'">
      <el-form label-width="80px">
        <el-form-item label="用户名">
          <el-input v-model="form.username" :disabled="!!editing" />
        </el-form-item>
        <el-form-item label="密码">
          <el-input v-model="form.password" type="password"
                    :placeholder="editing ? '留空则不修改' : ''" />
        </el-form-item>
        <el-form-item label="角色">
          <el-select v-model="form.role">
            <el-option label="管理员" value="admin" />
            <el-option label="只读用户" value="viewer" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="onSave">保存</el-button>
      </template>
    </el-dialog>
  </el-card>
</template>