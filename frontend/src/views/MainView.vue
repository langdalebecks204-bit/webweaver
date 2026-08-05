<script setup>
import { onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useAuthStore } from '../stores/auth'
import { useDevicesStore } from '../stores/devices'
import DeviceTree from '../components/DeviceTree.vue'

const router = useRouter()
const auth = useAuthStore()
const store = useDevicesStore()

onMounted(async () => {
  await auth.loadMe()
  await store.load()
})

function onLogout() {
  auth.logout()
  router.push('/login')
}

async function onCreateRoot() {
  try {
    const { value } = await ElMessageBox.prompt('请输入分组名称', '新增根分组', {
      confirmButtonText: '创建',
      cancelButtonText: '取消',
      inputPattern: /\S+/,
      inputErrorMessage: '分组名称不能为空',
    })
    await store.create({ name: value, type: 'group' })
  } catch (error) {
    if (error === 'cancel' || error === 'close') return
    ElMessage.error(error.response?.data?.detail || '创建失败')
  }
}
</script>

<template>
  <el-container class="layout">
    <el-header class="header">
      <span class="title">织网 WebWeaver</span>
      <span class="user-info">用户：{{ auth.user?.username }}（{{ auth.user?.role }}）</span>
      <el-button link @click="onLogout">退出登录</el-button>
    </el-header>
    <el-main>
      <el-card>
        <template #header>
          <div class="toolbar">
            <el-button type="primary" @click="onCreateRoot">
              新增根分组
            </el-button>
            <el-button @click="store.load()">刷新</el-button>
            <div class="stats">
              <el-tag type="success">在线 {{ store.stats.online }}</el-tag>
              <el-tag type="warning">警告 {{ store.stats.warning }}</el-tag>
              <el-tag type="danger">离线 {{ store.stats.offline }}</el-tag>
              <el-tag type="info">未知 {{ store.stats.unknown }}</el-tag>
            </div>
          </div>
        </template>
        <el-tree
          :data="store.tree"
          :props="{ label: 'name', children: 'children' }"
          node-key="id"
          default-expand-all
          :expand-on-click-node="false"
        >
          <template #default="{ data }">
            <DeviceTree :node="data" />
          </template>
        </el-tree>
      </el-card>
    </el-main>
  </el-container>
</template>

<style scoped>
.layout {
  height: 100vh;
}
.header {
  display: flex;
  align-items: center;
  gap: 16px;
  background: #fff;
  border-bottom: 1px solid #eee;
}
.title {
  font-weight: 600;
  font-size: 18px;
}
.user-info {
  margin-left: auto;
  color: #606266;
}
.toolbar {
  display: flex;
  align-items: center;
  gap: 8px;
}
.stats {
  margin-left: auto;
  display: flex;
  gap: 8px;
}
</style>
