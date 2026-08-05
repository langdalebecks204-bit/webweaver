// @vitest-environment happy-dom
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const {
  createMock,
  updateMock,
  removeMock,
  recheckMock,
  successMock,
  errorMock,
  confirmMock,
} = vi.hoisted(() => ({
  createMock: vi.fn(),
  updateMock: vi.fn(),
  removeMock: vi.fn(),
  recheckMock: vi.fn(),
  successMock: vi.fn(),
  errorMock: vi.fn(),
  confirmMock: vi.fn(),
}))

vi.mock('element-plus', () => ({
  ElMessage: { success: successMock, error: errorMock },
  ElMessageBox: { confirm: confirmMock, prompt: vi.fn() },
}))

vi.mock('../../stores/devices', () => ({
  useDevicesStore: () => ({
    create: createMock,
    update: updateMock,
    remove: removeMock,
    recheck: recheckMock,
  }),
}))

import DeviceTree from '../DeviceTree.vue'

function mountTree() {
  return mount(DeviceTree, {
    props: {
      node: { id: 1, name: 'root', type: 'group', status: 'unknown', children: [] },
    },
    global: {
      stubs: {
        'el-dropdown': {
          emits: ['command'],
          template: '<div class="dd" @click="$emit(\'command\', \'add-child\')"><slot /></div>',
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
    const wrapper = mountTree()
    await wrapper.find('.dd').trigger('click')
    await wrapper.find('.dlg input').setValue('dup')
    await wrapper.findAll('.dlg button').find((b) => b.text() === '保存').trigger('click')
    await flushPromises()
    expect(errorMock).toHaveBeenCalledWith('同一父节点下名称已存在')
    expect(successMock).not.toHaveBeenCalled()
  })
})
