<script setup>
import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useDevicesStore } from '../stores/devices'
import { useSettingsStore } from '../stores/settings'
import { allTypeOptions, typeIcon } from '../utils/deviceTypes'
import PortBindingDialog from './PortBindingDialog.vue'

const props = defineProps({ node: { type: Object, required: true } })
const emit = defineEmits(['open-history', 'open-detail', 'open-snmp'])
const store = useDevicesStore()
const settingsStore = useSettingsStore()
const dialogVisible = ref(false)
const portDialogVisible = ref(false)
const editing = ref(null)
const form = ref({ name: '', type: 'group', ip_address: '', port: null, location: '', port_count: null, uplink_port: null, port_bindings: {}, snmp_community: 'public', snmp_version: 'v2c', snmp_port: 161, parent_id: null })
const portChildDevices = computed(() =>
  editing.value ? (props.node.children || []).map((c) => ({ id: c.id, name: c.name })) : []
)

function openCreate(parentId) {
  editing.value = null
  form.value = { name: '', type: 'group', ip_address: '', port: null, location: '', port_count: null, uplink_port: null, port_bindings: {}, snmp_community: 'public', snmp_version: 'v2c', snmp_port: 161, parent_id: parentId }
  dialogVisible.value = true
}

function openEdit() {
  editing.value = props.node
  form.value = {
    name: props.node.name,
    type: props.node.type,
    ip_address: props.node.ip_address || '',
    port: props.node.port,
    location: props.node.location || '',
    port_count: props.node.port_count ?? null,
    uplink_port: props.node.uplink_port ?? null,
    port_bindings: props.node.port_bindings ?? {},
    snmp_community: props.node.snmp_community || 'public',
    snmp_version: props.node.snmp_version || 'v2c',
    snmp_port: props.node.snmp_port || 161,
    parent_id: props.node.parent_id,
  }
  dialogVisible.value = true
}

function openPortDialog() {
  portDialogVisible.value = true
}

function onPortBindingsSave(bindings) {
  form.value.port_bindings = bindings
}

async function submit() {
  const rawParentId = form.value.parent_id
  const parentId =
    rawParentId === '' || rawParentId === null || rawParentId === undefined
      ? null
      : Number(rawParentId)
  const payload = {
    ...form.value,
    parent_id: parentId,
    ip_address: form.value.ip_address || null,
    port: form.value.port || null,
    location: form.value.location || null,
    port_count: form.value.port_count,
    uplink_port: form.value.uplink_port,
    port_bindings: Object.keys(form.value.port_bindings).length ? form.value.port_bindings : null,
    snmp_community: form.value.snmp_community || 'public',
    snmp_version: form.value.snmp_version || 'v2c',
    snmp_port: form.value.snmp_port || 161,
  }
  try {
    if (editing.value) {
      await store.update(editing.value.id, payload)
    } else {
      await store.create(payload)
    }
    dialogVisible.value = false
    ElMessage.success('已保存')
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '保存失败')
  }
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
  else if (command === 'recheck') store.recheck(props.node.id)
  else if (command === 'delete') remove()
  else if (command === 'detail') emit('open-detail', props.node)
  else if (command === 'snmp') emit('open-snmp', props.node)
  else if (command === 'history') {
    if (props.node.ip_address) emit('open-history', props.node)
  }
}

function collectDescendantIds(node, acc) {
  if (!node.children) return acc
  for (const c of node.children) {
    acc.add(c.id)
    collectDescendantIds(c, acc)
  }
  return acc
}

const excludeIds = computed(() => {
  const acc = new Set([props.node.id])
  return collectDescendantIds(props.node, acc)
})

const parentCandidates = computed(() => {
  const result = []
  const walk = (nodes, depth) => {
    for (const n of nodes) {
      if (excludeIds.value.has(n.id)) continue
      result.push({ id: n.id, name: n.name, depth })
      if (n.children && n.children.length) walk(n.children, depth + 1)
    }
  }
  walk(store.tree, 0)
  return result
})

const typeOptions = computed(() =>
  allTypeOptions(settingsStore.builtinTypes, settingsStore.customTypes)
)

onMounted(() => {
  if (!settingsStore.typesLoaded) settingsStore.loadTypes()
})
</script>

<template>
  <el-dropdown trigger="contextmenu" @command="onCommand">
    <div class="node" :class="props.node.status">
      <el-icon class="type-icon">
        <component :is="typeIcon(props.node.type, settingsStore.customTypes)" />
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
        <el-dropdown-item command="detail">设备详情</el-dropdown-item>
        <el-dropdown-item v-if="props.node.type === 'switch'" command="snmp">端口与实时带宽(SNMP)</el-dropdown-item>
        <el-dropdown-item v-if="props.node.ip_address" command="history">查看历史</el-dropdown-item>
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
          <el-option
            v-for="opt in typeOptions"
            :key="opt.value"
            :label="opt.label"
            :value="opt.value"
          />
        </el-select>
      </el-form-item>
      <el-form-item label="上级分组">
        <el-select v-model="form.parent_id" clearable placeholder="根级" style="width: 100%">
          <el-option
            v-for="c in parentCandidates"
            :key="c.id"
            :value="c.id"
          >
            {{ '　'.repeat(c.depth) + c.name }}
          </el-option>
        </el-select>
      </el-form-item>
      <el-form-item label="IP 地址">
        <el-input v-model="form.ip_address" placeholder="留空表示纯分组节点" />
      </el-form-item>
      <el-form-item label="TCP 端口">
        <el-input-number v-model="form.port" :min="1" :max="65535" placeholder="可选" />
      </el-form-item>
      <el-form-item label="位置">
        <el-input v-model="form.location" placeholder="如：机房A/机架1（可选）" />
      </el-form-item>
      <el-form-item v-if="form.type === 'switch' || form.type === 'unmanaged_switch'" label="端口总数">
        <el-input-number v-model="form.port_count" :min="1" :max="48" />
      </el-form-item>
      <el-form-item v-if="form.type === 'switch' || form.type === 'unmanaged_switch'" label="上联端口">
        <el-input-number v-model="form.uplink_port" :min="1" :max="48" />
      </el-form-item>
      <el-form-item v-if="form.type === 'switch'" label="SNMP 团体字">
        <el-input v-model="form.snmp_community" placeholder="默认 public" />
      </el-form-item>
      <el-form-item v-if="form.type === 'switch'" label="SNMP 端口">
        <el-input-number v-model="form.snmp_port" :min="1" :max="65535" placeholder="默认 161" />
      </el-form-item>
      <el-form-item v-if="form.type === 'switch'" label="SNMP 版本">
        <el-select v-model="form.snmp_version" style="width: 100%">
          <el-option label="v2c" value="v2c" />
          <el-option label="v1" value="v1" />
        </el-select>
      </el-form-item>
      <el-form-item v-if="form.type === 'switch' || form.type === 'unmanaged_switch'" label="端口绑定">
        <el-button size="small" @click="openPortDialog">配置端口绑定</el-button>
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="dialogVisible = false">取消</el-button>
      <el-button type="primary" @click="submit">保存</el-button>
    </template>
  </el-dialog>

  <PortBindingDialog
    v-model="portDialogVisible"
    :port-count="form.port_count || 0"
    :bindings="form.port_bindings"
    :child-devices="portChildDevices"
    @save="onPortBindingsSave"
  />
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
