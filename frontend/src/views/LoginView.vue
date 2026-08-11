<script setup>
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '../stores/auth'

const router = useRouter()
const auth = useAuthStore()
const form = reactive({ username: '', password: '' })
const rememberPassword = ref(false)
const rememberLogin = ref(true)
const loading = ref(false)

onMounted(() => {
  const saved = auth.loadCredentials()
  if (saved) {
    form.username = saved.username
    form.password = saved.password
    rememberPassword.value = true
  }
})

function onRememberPasswordChange(val) {
  if (!val) auth.clearCredentials()
}

async function onSubmit() {
  loading.value = true
  try {
    await auth.login(form.username, form.password, { rememberLogin: rememberLogin.value })
    if (rememberPassword.value) {
      auth.saveCredentials(form.username, form.password)
    } else {
      auth.clearCredentials()
    }
    router.push('/')
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '登录失败')
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="login-page">
    <el-card class="login-card">
      <h2>织网 WebWeaver</h2>
      <el-form label-position="top" @submit.prevent="onSubmit">
        <el-form-item label="用户名">
          <el-input v-model="form.username" />
        </el-form-item>
        <el-form-item label="密码">
          <el-input v-model="form.password" type="password" show-password />
        </el-form-item>
        <div class="checks">
          <el-checkbox v-model="rememberPassword" @change="onRememberPasswordChange">
            记住密码
          </el-checkbox>
          <el-checkbox v-model="rememberLogin">记住登录状态</el-checkbox>
        </div>
        <el-button type="primary" native-type="submit" :loading="loading" style="width: 100%">
          登录
        </el-button>
      </el-form>
    </el-card>
  </div>
</template>

<style scoped>
.login-page {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 100vh;
  background: #f5f7fa;
}
.login-card {
  width: 360px;
}
.login-card h2 {
  text-align: center;
}
.checks {
  display: flex;
  justify-content: space-between;
  margin-bottom: 12px;
}
</style>