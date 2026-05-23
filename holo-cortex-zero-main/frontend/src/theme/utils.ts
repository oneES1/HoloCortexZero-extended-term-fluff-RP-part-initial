/**
 * 主题工具函数
 */
import { ExecStopType } from '../services/api/tool-traces'
import { COLORS } from './glass'

// 获取颜色值函数
function getMetricColor(type: string): string {
  switch (type) {
    case 'success_calls':
      return COLORS.success
    case 'failed_calls':
      return COLORS.error
    default:
      return '#9e9e9e'
  }
}

// 停止类型颜色映射（统一使用具体颜色值）
export const stopTypeColorValues = {
  [ExecStopType.NORMAL]: getMetricColor('success_calls'),
  [ExecStopType.ERROR]: getMetricColor('failed_calls'),
  [ExecStopType.TIMEOUT]: '#ff9800',
  [ExecStopType.AGENT]: '#2196f3',
  [ExecStopType.MANUAL]: '#9e9e9e',
  [ExecStopType.SECURITY]: '#f44336',
  [ExecStopType.MULTIMODAL_AGENT]: '#9c27b0',
} as const

// 停止类型到 i18n 键的映射
export const STOP_TYPE_I18N_KEYS: Record<ExecStopType, string> = {
  [ExecStopType.NORMAL]: 'stopType.normal',
  [ExecStopType.ERROR]: 'stopType.error',
  [ExecStopType.TIMEOUT]: 'stopType.timeout',
  [ExecStopType.AGENT]: 'stopType.agent',
  [ExecStopType.MANUAL]: 'stopType.manual',
  [ExecStopType.SECURITY]: 'stopType.security',
  [ExecStopType.MULTIMODAL_AGENT]: 'stopType.multimodal',
} as const

/**
 * 获取停止类型的 i18n 键
 */
export function getStopTypeI18nKey(stopType: number): string {
  const key = STOP_TYPE_I18N_KEYS[stopType as ExecStopType]
  if (!key) {
    console.warn(`Invalid stop type: ${stopType}, falling back to NORMAL`)
    return STOP_TYPE_I18N_KEYS[ExecStopType.NORMAL]
  }
  return key
}

/**
 * 获取停止类型的翻译文本（需要传入 t 函数）
 */
export function getStopTypeTranslatedText(
  stopType: number,
  t: (key: string, options?: { ns?: string }) => string
): string {
  const key = getStopTypeI18nKey(stopType)
  return t(key, { ns: 'common' })
}

/**
 * 获取停止类型颜色值
 */
export function getStopTypeColorValue(stopType: number): string {
  return stopTypeColorValues[stopType as ExecStopType] || '#9e9e9e'
}

