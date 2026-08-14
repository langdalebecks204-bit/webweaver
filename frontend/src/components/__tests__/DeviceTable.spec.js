// @vitest-environment happy-dom
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const { removeMock, recheckMock, successMock, errorMock, confirmMock, warningMock } = vi.hoisted(() => ({
  removeMock: vi.fn(),
  recheckMock: vi.fn(),
  successMock: vi.fn(),
  errorMock: vi.fn(),
  confirmMock: vi.fn(),
  warningMock: vi.fn(),
}))

vi.mock('element-plus', async (importOriginal) => {
  const actual = await importOriginal()
  return {
    ...actual,
    ElMessage: { success: successMock, error: errorMock, warning: warningMock },
    ElMessageBox: { confirm: confirmMock },
  }
})

const treeMock = vi.hoisted(() => [
  {
    id: 1,
    name: '机房A',
    type: 'group',
    parent_id: null,
    location: null,
    status: 'unknown',
    children: [
      {
        id: 2,
        name: '核心交换机',
        type: 'switch',
        parent_id: 1,
        ip_address: '10.0.0.1',
        port: 22,
        location: '机架1',
        status: 'online',
        latency_ms: 5,
        last_check: '2026-08-01T00:00:00',
        image_url: null,
        children: [],
      },
      {
        id: 3,
        name: '终端B',
        type: 'terminal',
        parent_id: 1,
        ip_address: '10.0.0.2',
        port: null,
        location: null,
        status: 'offline',
        latency_ms: null,
        last_check: null,
        image_url: null,
        children: [],
      },
    ],
  },
])

vi.mock('../../stores/devices', () => ({
  useDevicesStore: () => ({
    tree: treeMock,
    remove: removeMock,
    recheck: recheckMock,
  }),
}))

vi.mock('../../stores/auth', () => ({
  useAuthStore: () => ({ user: { role: 'admin' } }),
}))

import DeviceTable from '../DeviceTable.vue'
import ElementPlus from 'element-plus'

function mountTable({ onEdit } = {}) {
  return mount(DeviceTable, {
    props: { onEdit },
    global: { plugins: [ElementPlus] },
  })
}

describe('DeviceTable', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('扁平化展示节点并推导所属分组', async () => {
    const wrapper = mountTable()
    await flushPromises()
    const rows = wrapper.findAll('.el-table__row')
    expect(rows).toHaveLength(3)
    const groupRow = rows.find((r) => r.text().includes('机房A'))
    expect(groupRow.text()).toContain('未知')
    const swRow = rows.find((r) => r.text().includes('核心交换机'))
    expect(swRow.text()).toContain('机架1')
    expect(swRow.text()).toContain('在线')
  })

  it('按关键字搜索名称/IP/位置', async () => {
    const wrapper = mountTable()
    await flushPromises()
    const input = wrapper.find('input[placeholder*="搜索"]')
    await input.setValue('终端')
    await flushPromises()
    expect(wrapper.findAll('.el-table__row')).toHaveLength(1)
    await input.setValue('10.0.0.2')
    await flushPromises()
    expect(wrapper.findAll('.el-table__row')).toHaveLength(1)
    await input.setValue('机架1')
    await flushPromises()
    expect(wrapper.findAll('.el-table__row')).toHaveLength(1)
  })

  it('删除需确认', async () => {
    confirmMock.mockResolvedValue()
    removeMock.mockResolvedValue()
    const wrapper = mountTable()
    await flushPromises()
    const delBtn = wrapper.findAll('button').find((b) => b.text() === '删除')
    await delBtn.trigger('click')
    await flushPromises()
    expect(confirmMock).toHaveBeenCalled()
    expect(removeMock).toHaveBeenCalled()
  })

  it('编辑按钮触发 onEdit 回调并传入行数据', async () => {
    const onEdit = vi.fn()
    const wrapper = mountTable({ onEdit })
    await flushPromises()
    const editBtn = wrapper.findAll('button').find((b) => b.text() === '编辑')
    await editBtn.trigger('click')
    expect(onEdit).toHaveBeenCalledTimes(1)
    expect(onEdit).toHaveBeenCalledWith(expect.objectContaining({ name: '机房A' }))
  })
})

describe('DeviceTable 导出 ZIP', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('工具栏只有导出 ZIP 按钮，无导出 CSV 按钮', async () => {
    const wrapper = mountTable()
    await flushPromises()
    const btns = wrapper.findAll('button').map((b) => b.text())
    expect(btns).toContain('导出 ZIP')
    expect(btns).not.toContain('导出 CSV')
  })

  it('有数据时导出并提示条数', async () => {
    const wrapper = mountTable()
    await flushPromises()
    const btn = wrapper.findAll('button').find((b) => b.text() === '导出 ZIP')
    expect(btn).toBeTruthy()
    await btn.trigger('click')
    await new Promise((r) => setTimeout(r, 50))
    await flushPromises()
    expect(successMock).toHaveBeenCalledWith(expect.stringContaining('已导出'))
  })

  it('无数据时提示无数据可导出', async () => {
    const wrapper = mountTable()
    await flushPromises()
    const input = wrapper.find('input[placeholder*="搜索"]')
    await input.setValue('完全不存在的关键词xyz')
    await flushPromises()
    const btn = wrapper.findAll('button').find((b) => b.text() === '导出 ZIP')
    await btn.trigger('click')
    await flushPromises()
    expect(warningMock).toHaveBeenCalledWith('无数据可导出')
  })
})