import { describe, it, expect } from 'vitest'
import { DEVICE_TYPE_ICONS, DEVICE_TYPE_LABELS, allTypeOptions, typeIcon, typeLabel } from '../deviceTypes'

describe('deviceTypes', () => {
  it('内置类型有中文标签', () => {
    expect(typeLabel('camera')).toBe('摄像头')
    expect(typeLabel('nvr')).toBe('NVR')
    expect(typeLabel('group')).toBe('分组')
  })

  it('未知类型原样返回', () => {
    expect(typeLabel('bogus')).toBe('bogus')
  })

  it('内置类型有专属图标，自定义走默认，未知走问号', () => {
    expect(DEVICE_TYPE_ICONS.camera).toBe('VideoCamera')
    expect(typeIcon('nas2', ['nas2'])).toBe('Monitor')
    expect(typeIcon('bogus')).toBe('QuestionFilled')
  })

  it('unmanaged_switch 有标签与图标', () => {
    expect(DEVICE_TYPE_LABELS.unmanaged_switch).toBe('非管理型交换机')
    expect(DEVICE_TYPE_ICONS.unmanaged_switch).toBeTruthy()
  })

  it('allTypeOptions 合并内置中文与自定义原值', () => {
    const opts = allTypeOptions(['group', 'camera'], ['nas2'])
    expect(opts).toEqual([
      { value: 'group', label: '分组' },
      { value: 'camera', label: '摄像头' },
      { value: 'nas2', label: 'nas2' },
    ])
  })
})