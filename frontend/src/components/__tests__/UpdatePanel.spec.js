// @vitest-environment happy-dom
import { mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import UpdatePanel from '../UpdatePanel.vue'
import { useSystemStore } from '../../stores/system'

describe('UpdatePanel', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('renders check button and version info', () => {
    const store = useSystemStore()
    store.currentVersion = '0.5.4'
    const wrapper = mount(UpdatePanel, {
      global: {
        stubs: {
          'el-card': { template: '<div class="el-card"><slot name="header"/><slot/></div>' },
          'el-tag': { template: '<span class="el-tag"><slot/></span>' },
          'el-select': { template: '<div class="el-select"><slot/></div>' },
          'el-option': true,
          'el-button': { template: '<button><slot/></button>' },
          'el-dialog': { template: '<div class="el-dialog"><slot/></div>' },
          'el-progress': true,
          'el-input': true,
          'el-alert': { template: '<div class="el-alert"><slot/></div>' },
        },
      },
    })
    expect(wrapper.text()).toContain('系统差量更新')
    expect(wrapper.text()).toContain('检查更新')
  })

  it('shows update available details when hasUpdate is true', () => {
    const store = useSystemStore()
    store.currentVersion = '0.5.4'
    store.latestVersion = '0.5.5'
    store.hasUpdate = true
    store.releaseNotes = 'Bug fixes and performance boost'
    store.packageSize = 3145728

    const wrapper = mount(UpdatePanel, {
      global: {
        stubs: {
          'el-card': { template: '<div class="el-card"><slot name="header"/><slot/></div>' },
          'el-tag': { template: '<span class="el-tag"><slot/></span>' },
          'el-select': { template: '<div class="el-select"><slot/></div>' },
          'el-option': true,
          'el-button': { template: '<button><slot/></button>' },
          'el-dialog': { template: '<div class="el-dialog"><slot/></div>' },
          'el-progress': true,
          'el-input': true,
          'el-alert': { template: '<div class="el-alert"><slot/></div>' },
        },
      },
    })
    expect(wrapper.text()).toContain('发现新版本')
    expect(wrapper.text()).toContain('v0.5.5')
    expect(wrapper.text()).toContain('一键差量热更新')
    expect(wrapper.text()).toContain('Bug fixes and performance boost')
  })
})
