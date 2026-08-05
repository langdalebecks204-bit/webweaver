<script setup>
import { ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useDevicesStore } from '../stores/devices'

const props = defineProps({ node: { type: Object, required: true } })
const store = useDevicesStore()
const dialogVisible = ref(false)
const editing = ref(null)
const form = ref({ name: '', type: 'group', ip_address: '', port: null, parent_id: null })

function openCreate(parentId) {
  editing.value = null
  form.value = { name: '', type: 'group', ip_address: '', port: null, parent_id: parentId }
  dialogVisible.value = true
}

function openEdit() {
  editing.value = props.node
  form.value = {
    name: props.node.name,
    type: props.node.type,
    ip_address: props.node.ip_address || '',
    port: props.node.port,
    parent_id: props.node.parent_id,
  }
  dialogVisible.value = true
}

async function submit() {
  const payload = {
    ...form.value,
    ip_address: form.value.ip_address || null,
    port: form.value.port || null,
  }
  if (editing.value) {
    await store.update(editing.value.id, payload)
  } else {
    await store.create(payload)
  }
  dialogVisible.value = false
  ElMessage.success('已保存')
}

async function remove() {
  try {
    await ElMessageBox.confirm(
      `确定删除"${props.node.name}"及其全部子节点？`,
      '删除确认',
      { type: 'warning' }
    )
  } catch {
    return
  }
  await store.remove(props.node.id)
  ElMessage.success('已删除')
}

function onCommand(command) {
  if (command === 'add-child') openCreate(props.node.id)
  else if (command === 'add-sibling') openCreate(props.node.parent_id)
  else if (command === 'edit') openEdit()
  else if (command === 'delete') remove()
  else if (command === 'recheck') store.recheck(props.node.id)
}
</script>

<template>
  <el-dropdown trigger="contextmenu" @command="onCommand">
    <div class="node">
      <el-icon class="type-icon">
        <component
          :is="props.node.type === 'group' ? 'Folder'
            : props.node.type === 'switch' ? 'Connection' : 'Monitor'"
        />
      </el-icon>
      <span class="status-dot" :class="props.node.status" />
      <span class="node-name">{{ props.node.name }}</span>
      <span v-if="props.node.ip_address" class="node-meta">{{ props.node.ip_address }}</span>
      <span v-if="props.node.latency_ms != null" class="node-meta">
        {{ props.node.latency_ms }}ms
      </span>
    </div>
    <template #dropdown>
      <el-dropdown-menu>
        <el-dropdown-item command="add-child">添加子节点</el-dropdown-item>
        <el-dropdown-item command="add-sibling">添加同级</el-dropdown-item>
        <el-dropdown-item command="edit">编辑</el-dropdown-item>
        <el-dropdown-item command="recheck">立即巡检</el-dropdown-item>
        <el-dropdown-item command="delete" divided>删除</el-dropdown-item>
      </el-dropdown-menu>
    </template>
  </el-dropdown>

  <el-dialog v-model="dialogVisible" :title="editing ? '编辑节点' : '新增节点'" width="460px">
    <el-form label-width="90px">
      <el-form-item label="名称">
        <el-input v-model="form.name" />
      </el-form-item>
      <el-form-item label="类型">
        <el-select v-model="form.type" style="width: 100%">
          <el-option label="分组" value="group" />
          <el-option label="服务器" value="server" />
          <el-option label="交换机" value="switch" />
          <el-option label="终端" value="terminal" />
        </el-select>
      </el-form-item>
      <el-form-item label="IP 地址">
        <el-input v-model="form.ip_address" placeholder="留空表示纯分组节点" />
      </el-form-item>
      <el-form-item label="TCP 端口">
        <el-input-number v-model="form.port" :min="1" :max="65535" placeholder="可选" />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="dialogVisible = false">取消</el-button>
      <el-button type="primary" @click="submit">保存</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.node {
  display: flex;
  align-items: center;
  gap: 6px;
}
.type-icon {
  color: #909399;
}
.status-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  display: inline-block;
}
.status-dot.online {
  background: #67c23a;
}
.status-dot.offline {
  background: #f56c6c;
}
.status-dot.warning {
  background: #e6a23c;
}
.status-dot.unknown {
  background: #909399;
}
.node-meta {
  color: #909399;
  font-size: 12px;
}
</style>
