import type { CSSProperties } from 'vue'

// ============================================
// 公共组件类型定义
// ============================================

export interface FormField {
  prop: string
  label: string
  type: 'input' | 'number' | 'select' | 'textarea' | 'switch' | 'radio' | 'slot'
  required?: boolean
  placeholder?: string
  disabled?: boolean
  colSpan?: number
  inputType?: string
  rows?: number
  min?: number
  max?: number
  step?: number
  multiple?: boolean
  filterable?: boolean
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  activeValue?: any
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  inactiveValue?: any
  options?: { label: string; value: string | number | boolean }[]
}

export interface FormSection {
  title: string
  fields: FormField[]
}

export interface StepItem {
  step: number
  title: string
  desc: string
  icon?: string
  active?: boolean
}

export interface KvItem {
  key: string
  value: string
}

export interface CardItem {
  id: string
  name: string
  icon?: string
  iconBg?: string
  tags?: string[]
  description?: string
  ownerLabel?: string
  ownerValue?: string
  footerLabel?: string
  footerValue?: string
  isPublic?: boolean
}
