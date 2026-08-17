// @vitest-environment happy-dom
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import PortBindingDialog from '../PortBindingDialog.vue'

const childDevices = [
  { id: 101, name: '服务器A' },
  { id: 102, name: '摄像头B' },
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
  ElOption: { template: '<div><slot /></div>' },
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
})
