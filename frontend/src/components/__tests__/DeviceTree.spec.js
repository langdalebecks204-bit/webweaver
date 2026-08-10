// @vitest-environment happy-dom
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const { createMock, updateMock, removeMock, recheckMock, successMock, errorMock, confirmMock, treeMock } =
  vi.hoisted(() => ({
    createMock: vi.fn(),
    updateMock: vi.fn(),
    removeMock: vi.fn(),
    recheckMock: vi.fn(),
    successMock: vi.fn(),
    errorMock: vi.fn(),
    confirmMock: vi.fn(),
    treeMock: [
      {
        id: 1,
        name: 'root',
        parent_id: null,
        type: 'group',
        status: 'unknown',
        children: [
          { id: 2, name: 'child', parent_id: 1, type: 'server', status: 'unknown', children: [] },
          {
            id: 3,
            name: 'sibling',
            parent_id: 1,
            type: 'server',
            status: 'unknown',
            children: [
              { id: 4, name: 'sub', parent_id: 3, type: 'server', status: 'unknown', children: [] },
            ],
          },
        ],
      },
    ],
  }))

vi.mock('element-plus', () => ({
  ElMessage: { success: successMock, error: errorMock },
  ElMessageBox: { confirm: confirmMock, prompt: vi.fn() },
}))

vi.mock('../../stores/devices', () => ({
  useDevicesStore: () => ({
    tree: treeMock,
    create: createMock,
    update: updateMock,
    remove: removeMock,
    recheck: recheckMock,
  }),
}))

import DeviceTree from '../DeviceTree.vue'

const defaultNode = {
  id: 3,
  name: 'sibling',
  parent_id: 1,
  type: 'server',
  ip_address: '10.0.0.3',
  status: 'unknown',
  children: [
    { id: 4, name: 'sub', parent_id: 3, type: 'server', status: 'unknown', children: [] },
  ],
}

function mountTree(command = 'add-child', node = defaultNode) {
  return mount(DeviceTree, {
    props: { node },
    global: {
      stubs: {
        'el-dropdown': {
          emits: ['command'],
          template: `<div class="dd" @click="$emit('command', '${command}')"><slot /></div>`,
        },
        'el-dropdown-menu': { template: '<div><slot /></div>' },
        'el-dropdown-item': { template: '<span><slot /></span>' },
        'el-dialog': {
          props: ['modelValue'],
          template: '<div class="dlg"><slot /><slot name="footer" /></div>',
        },
        'el-form': { template: '<div><slot /></div>' },
        'el-form-item': { template: '<div><slot /></div>' },
        'el-input': {
          props: ['modelValue'],
          emits: ['update:modelValue'],
          template: '<input :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />',
        },
        'el-select': {
          props: ['modelValue'],
          emits: ['update:modelValue'],
          template: '<select :value="modelValue" @change="$emit(\'update:modelValue\', $event.target.value)"><slot /></select>',
        },
        'el-option': {
          props: ['value'],
          template: '<option :value="value"><slot /></option>',
        },
        'el-input-number': {
          props: ['modelValue'],
          emits: ['update:modelValue'],
          template: '<input :value="modelValue" @input="$emit(\'update:modelValue\', Number($event.target.value))" />',
        },
        'el-icon': { template: '<span><slot /></span>' },
        'el-button': {
          emits: ['click'],
          template: '<button @click="$emit(\'click\')"><slot /></button>',
        },
        Folder: { template: '<span />' },
        Connection: { template: '<span />' },
        Monitor: { template: '<span />' },
      },
    },
  })
}

describe('DeviceTree 提交', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('创建失败（如同名被拒）时提示后端错误，不静默失败', async () => {
    createMock.mockRejectedValue({ response: { data: { detail: '同一父节点下名称已存在' } } })
    const wrapper = mountTree('add-child')
    await wrapper.find('.dd').trigger('click')
    await wrapper.find('.dlg input').setValue('dup')
    await wrapper.findAll('.dlg button').find((b) => b.text() === '保存').trigger('click')
    await flushPromises()
    expect(errorMock).toHaveBeenCalledWith('同一父节点下名称已存在')
    expect(successMock).not.toHaveBeenCalled()
  })
})

describe('DeviceTree 父级选择', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('编辑时父级选择器排除自身及其后代', async () => {
    const wrapper = mountTree('edit')
    await wrapper.find('.dd').trigger('click')
    const options = wrapper.findAll('.dlg select').at(1).findAll('option')
    const ids = options.map((o) => Number(o.attributes('value')))
    expect(ids).toEqual([1, 2])
  })

  it('保存时提交所选父级 id', async () => {
    updateMock.mockResolvedValue({})
    const wrapper = mountTree('edit')
    await wrapper.find('.dd').trigger('click')
    await wrapper.findAll('.dlg select').at(1).setValue('2')
    await wrapper.findAll('.dlg button').find((b) => b.text() === '保存').trigger('click')
    await flushPromises()
    expect(updateMock).toHaveBeenCalledWith(3, expect.objectContaining({ parent_id: 2 }))
    expect(successMock).toHaveBeenCalledWith('已保存')
  })

  it('清空父级选择表示移到根级', async () => {
    updateMock.mockResolvedValue({})
    const wrapper = mountTree('edit')
    await wrapper.find('.dd').trigger('click')
    await wrapper.findAll('.dlg select').at(1).setValue('')
    await wrapper.findAll('.dlg button').find((b) => b.text() === '保存').trigger('click')
    await flushPromises()
    expect(updateMock).toHaveBeenCalledWith(3, expect.objectContaining({ parent_id: null }))
  })
})

describe('DeviceTree 查看历史', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('带 IP 节点右键发射 open-history', async () => {
    const wrapper = mountTree('history', defaultNode)
    await wrapper.find('.dd').trigger('click')
    const emitted = wrapper.emitted('open-history')
    expect(emitted).toBeTruthy()
    expect(emitted[0][0]).toEqual(defaultNode)
  })

  it('不带 IP 的节点不发射 open-history', async () => {
    const wrapper = mountTree('history', { ...defaultNode, ip_address: null })
    await wrapper.find('.dd').trigger('click')
    expect(wrapper.emitted('open-history')).toBeFalsy()
  })
})
