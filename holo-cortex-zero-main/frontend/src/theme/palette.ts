/**
 * HCZ 调色板 — 静态常量，拒绝动态生成
 * 所有颜色直接从 glass.ts 的 COLORS 取值
 */
import { COLORS, getGlassTokens, ThemeMode } from './glass'

export function getMuiPaletteOptions(mode: ThemeMode = 'dark') {
  const { VOID, PANEL, TEXT } = getGlassTokens(mode)
  return {
    mode,
    primary: {
      main: COLORS.accent,
      contrastText: '#fff',
    },
    secondary: {
      main: TEXT.secondary,
      contrastText: '#fff',
    },
    success: {
      main: COLORS.success,
      contrastText: '#fff',
    },
    error: {
      main: COLORS.error,
      contrastText: '#fff',
    },
    warning: {
      main: COLORS.warning,
      contrastText: '#000',
    },
    info: {
      main: COLORS.info,
      contrastText: '#fff',
    },
    background: {
      default: VOID.base,
      paper: PANEL.background,
    },
    text: {
      primary: TEXT.primary,
      secondary: TEXT.secondary,
      disabled: TEXT.disabled,
    },
    divider: TEXT.divider,
    action: {
      active: TEXT.primary,
      hover: mode === 'dark' ? 'rgba(255, 255, 255, 0.08)' : 'rgba(15, 23, 42, 0.04)',
      selected: mode === 'dark' ? '#252528' : 'rgba(92, 157, 255, 0.12)',
      disabled: mode === 'dark' ? '#444444' : '#cbd5e1',
      disabledBackground: mode === 'dark' ? '#1a1a1a' : '#e5e7eb',
    },
  }
}
