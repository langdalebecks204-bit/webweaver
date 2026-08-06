// @vitest-environment happy-dom
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const { loadMock, createMock, updateMock, removeMock, successMock, errorMock, confirmMock } = vi.hoisted(() => ({
  loadMock: vi.fn(),
  createMock: vi.fn(),
  updateMock: vi.fn(),
  removeMock: vi.fn(),
  successMock: vi.fn(),
  errorMock: vi.fn(),
  confirmMock: vi.fn(),
}))

const users = vi.hoisted(() => [
  { id: 1, username: 'admin', role: 'admin', created_at: '2026-01-01T00:00:00' },
  { id: 2, username: 'u1', role: 'viewer', created_at: '2026-01-02T00:00:00' },
])

vi.mock('element-plus', () => ({
  ElMessage: { success: successMock, error: errorMock },
  ElMessageBox: { confirm: confirmMock },
}))

vi.mock('../../stores/users', () => ({
  useUsersStore: () => ({
    users,
    load: loadMock,
    create: createMock,
    update: updateMock,
    remove: removeMock,
  }),
}))

import UsersPanel from '../UsersPanel.vue'

function mountPanel() {
  return mount(UsersPanel, {
    global: {
      stubs: {
        'el-card': { template: '<div><slot name="header" /><slot /></div>' },
        'el-tag': { template: '<span><slot /></span>' },
        'el-dialog': {
          props: ['modelValue'],
          template: '<div class="dlg"><slot /><slot name="footer" /></div>',
        },
        'el-form': { template: '<div><slot /></div>' },
        'el-form-item': { template: '<div><slot /></div>' },
        'el-input': {
          props: ['modelValue'],
          emits: ['update:modelValue'],
          template: '<input class="t-input" :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />',
        },
        'el-select': {
          props: ['modelValue'],
          emits: ['update:modelValue'],
          template: '<select class="role-select" :value="modelValue" @change="$emit(\'update:modelValue\', $event.target.value)"><slot /></select>',
        },
        'el-option': {
          props: ['value'],
          template: '<option :value="value"><slot /></option>',
        },
        'el-button': {
          emits: ['click'],
          template: '<button @click="$emit(\'click\')"><slot /></button>',
        },
      },
    },
  })
}

function buttonByText(wrapper, text) {
  return wrapper.findAll('button').find((b) => b.text() === text)
}

describe('UsersPanel 用户管理', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('挂载后加载用户列表并渲染', async () => {
    const wrapper = mountPanel()
    await flushPromises()
    expect(loadMock).toHaveBeenCalledTimes(1)
    expect(wrapper.text()).toContain('admin')
    expect(wrapper.text()).toContain('u1')
  })

  it('新增用户提交用户名/密码/角色', async () => {
    createMock.mockResolvedValue({})
    const wrapper = mountPanel()
    await flushPromises()
    await buttonByText(wrapper, '新增用户').trigger('click')
    await wrapper.findAll('.dlg input.t-input').at(0).setValue('u2')
    await wrapper.findAll('.dlg input.t-input').at(1).setValue('pw123456')
    await wrapper.find('.dlg select.role-select').setValue('admin')
    await buttonByText(wrapper, '保存').trigger('click')
    await flushPromises()
    expect(createMock).toHaveBeenCalledWith({ username: 'u2', password: 'pw123456', role: 'admin' })
    expect(successMock).toHaveBeenCalledWith('已保存')
  })

  it('编辑用户改角色且可选重置密码', async () => {
    updateMock.mockResolvedValue({})
    const wrapper = mountPanel()
    await flushPromises()
    const editButtons = wrapper.findAll('button').filter((b) => b.text() === '编辑')
    await editButtons[1].trigger('click')
    await wrapper.find('.dlg select.role-select').setValue('admin')
    await buttonByText(wrapper, '保存').trigger('click')
    await flushPromises()
    expect(updateMock).toHaveBeenCalledWith(2, { role: 'admin' })
    expect(successMock).toHaveBeenCalledWith('已保存')
  })

  it('删除用户需确认并调用 remove', async () => {
    confirmMock.mockResolvedValue()
    removeMock.mockResolvedValue()
    const wrapper = mountPanel()
    await flushPromises()
    const deleteButtons = wrapper.findAll('button').filter((b) => b.text() === '删除')
    await deleteButtons[1].trigger('click')
    await flushPromises()
    expect(confirmMock).toHaveBeenCalled()
    expect(removeMock).toHaveBeenCalledWith(2)
    expect(successMock).toHaveBeenCalledWith('已删除')
  })

  it('删除自己被拒时提示后端错误', async () => {
    confirmMock.mockResolvedValue()
    removeMock.mockRejectedValue({ response: { data: { detail: 'cannot delete yourself' } } })
    const wrapper = mountPanel()
    await flushPromises()
    await buttonByText(wrapper, '删除').trigger('click')
    await flushPromises()
    expect(errorMock).toHaveBeenCalledWith('cannot delete yourself')
  })
})