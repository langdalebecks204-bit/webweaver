// @vitest-environment happy-dom
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import PortBindingDialog from '../PortBindingDialog.vue'

const childDevices = [
  { id: 101, name: '服务器A' },
  { id: 102, name: '摄像头B' },
]

const parentDevices = [
  { id: 201, name: '核心交换机', isParent: true },
  { id: 202, name: '备用核心', isParent: false },
]

const stubs = {
  ElDialog: {
    props: ['modelValue'],
    template: '<div v-if="modelValue" class="dlg"><slot /><slot name="footer" /></div>',
  },
  ElSelect: {
    props: ['modelValue'],
    emits: ['update:modelValue'],
    template: '<div class="sel"><slot /></div>',
  },
  ElOption: {
    props: ['label', 'value'],
    template: '<div class="opt" :data-label="label" :data-value="value"><slot /></div>',
  },
  ElInput: {
    props: ['modelValue'],
    emits: ['update:modelValue'],
    template: '<input class="input" :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />',
  },
  ElButton: { template: '<button @click="$emit(\'click\')"><slot /></button>' },
}

describe('PortBindingDialog', () => {
  it('按端口总数渲染端口行', () => {
    const wrapper = mount(PortBindingDialog, {
      props: { modelValue: true, portCount: 4, bindings: {}, childDevices },
      global: { stubs },
    })
    expect(wrapper.findAll('.port-row').length).toBe(4)
  })

  it('保存时仅保留绑定了设备的端口', async () => {
    const wrapper = mount(PortBindingDialog, {
      props: { modelValue: true, portCount: 3, bindings: { 1: { target_id: 101, type: 'uplink' } }, childDevices },
      global: { stubs },
    })
    const save = wrapper.findAll('button').find((b) => b.text() === '保存')
    await save.trigger('click')
    expect(wrapper.emitted('save')).toBeTruthy()
    expect(wrapper.emitted('save')[0][0]).toEqual({ 1: { target_id: 101, type: 'uplink' } })
    expect(wrapper.emitted('update:modelValue')[0][0]).toBe(false)
  })

  it('上联端口支持选择上级设备', async () => {
    const wrapper = mount(PortBindingDialog, {
      props: {
        modelValue: true,
        portCount: 2,
        bindings: {},
        childDevices,
        parentDevices,
      },
      global: { stubs },
    })

    // Port 1 defaults to downlink; change to uplink
    wrapper.vm.rows[0].type = 'uplink'
    wrapper.vm.onTypeChange(wrapper.vm.rows[0])
    expect(wrapper.vm.rows[0].target_id).toBe(201)

    const save = wrapper.findAll('button').find((b) => b.text() === '保存')
    await save.trigger('click')
    expect(wrapper.emitted('save')[0][0]).toEqual({
      1: { target_id: 201, type: 'uplink' },
    })
  })

  it('支持保存端口自定义说明与绑定', async () => {
    const wrapper = mount(PortBindingDialog, {
      props: {
        modelValue: true,
        portCount: 2,
        bindings: {
          1: { target_id: 101, type: 'downlink', description: 'Web服务器' },
          2: { target_id: null, type: 'downlink', description: '外网光纤' },
        },
        childDevices,
      },
      global: { stubs },
    })

    const save = wrapper.findAll('button').find((b) => b.text() === '保存')
    await save.trigger('click')
    expect(wrapper.emitted('save')[0][0]).toEqual({
      1: { target_id: 101, type: 'downlink', description: 'Web服务器' },
      2: { target_id: null, type: 'downlink', description: '外网光纤' },
    })
  })
})
