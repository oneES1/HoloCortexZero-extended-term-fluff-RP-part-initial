/**
 * HCZ Glass & Panel Design System
 * 同一主干按 theme mode 分支：dark / light
 */

export type ThemeMode = 'light' | 'dark'

export const COLORS = {
  accent: '#5c9dff',
  accentGlow: 'rgba(92, 157, 255, 0.15)',
  success: '#32d74b',
  error: '#ff453a',
  warning: '#ff9f0a',
  info: '#5c9dff',
  textPrimary: 'var(--hcz-text-primary)',
  textSecondary: 'var(--hcz-text-secondary)',
  textDisabled: 'var(--hcz-text-disabled)',
} as const

const DARK_TEXT = {
  primary: '#f5f5f7',
  secondary: '#8e8e93',
  disabled: '#636366',
  divider: 'rgba(255, 255, 255, 0.06)',
} as const

const LIGHT_TEXT = {
  primary: '#111827',
  secondary: '#5b6472',
  disabled: '#9ca3af',
  divider: 'rgba(15, 23, 42, 0.08)',
} as const

const DARK_TOKENS = {
  VOID: {
    base: '#000000',
    contentBase: '#0d0d0f',
  },
  GLASS_PILL: {
    inactive: {
      background: 'rgba(30, 30, 35, 0.60)',
      backdropFilter: 'blur(20px) saturate(150%)',
      WebkitBackdropFilter: 'blur(20px) saturate(150%)',
      borderRadius: '9999px',
      border: '1px solid rgba(255, 255, 255, 0.06)',
      boxShadow: 'inset 0 1px 0 rgba(255, 255, 255, 0.08)',
      color: '#e8e8e8',
    },
    active: {
      background: 'rgba(92, 157, 255, 0.20)',
      backdropFilter: 'blur(20px) saturate(180%)',
      WebkitBackdropFilter: 'blur(20px) saturate(180%)',
      borderRadius: '9999px',
      border: '1px solid rgba(92, 157, 255, 0.30)',
      boxShadow: 'inset 0 1px 0 rgba(255, 255, 255, 0.15), 0 0 12px rgba(92, 157, 255, 0.15)',
      color: '#5c9dff',
    },
    hover: {
      background: 'rgba(255, 255, 255, 0.08)',
      boxShadow: 'inset 0 1px 0 rgba(255, 255, 255, 0.12)',
    },
  },
  SIDEBAR_GLASS: {
    background: 'rgba(20, 20, 25, 0.50)',
    backdropFilter: 'blur(40px) saturate(160%)',
    WebkitBackdropFilter: 'blur(40px) saturate(160%)',
    borderRight: '1px solid rgba(255, 255, 255, 0.06)',
    border: '1px solid rgba(255, 255, 255, 0.08)',
    boxShadow: 'inset 0 1px 0 rgba(255, 255, 255, 0.08), 4px 0 24px rgba(0, 0, 0, 0.4)',
  },
  TOP_BAR: {
    background: 'rgba(0, 0, 0, 0.70)',
    backdropFilter: 'blur(40px) saturate(160%)',
    WebkitBackdropFilter: 'blur(40px) saturate(160%)',
    borderBottom: '1px solid rgba(255, 255, 255, 0.06)',
    boxShadow: 'inset 0 1px 0 rgba(255, 255, 255, 0.05)',
  },
  PANEL: {
    background: '#1c1c1e',
    borderRadius: '16px',
    border: '1px solid rgba(255, 255, 255, 0.06)',
    boxShadow: '0 4px 24px rgba(0, 0, 0, 0.4)',
  },
  PANEL_NESTED: {
    background: '#252528',
    borderRadius: '12px',
    border: '1px solid rgba(255, 255, 255, 0.05)',
  },
  INPUT: {
    background: '#252528',
    borderRadius: '12px',
    border: '1px solid rgba(255, 255, 255, 0.08)',
    boxShadow: 'inset 0 1px 0 rgba(255, 255, 255, 0.04)',
    color: '#e8e8e8',
  },
  INPUT_HOVER: {
    background: '#2a2a2e',
    borderColor: 'rgba(255, 255, 255, 0.12)',
  },
  INPUT_FOCUS: {
    background: '#2a2a2e',
    borderColor: 'rgba(92, 157, 255, 0.50)',
    boxShadow: 'inset 0 1px 0 rgba(255, 255, 255, 0.06), 0 0 0 3px rgba(92, 157, 255, 0.15)',
  },
  TEXT: DARK_TEXT,
  SHADOWS: {
    float: '0 4px 24px rgba(0, 0, 0, 0.40)',
    deep: '0 8px 32px rgba(0, 0, 0, 0.50)',
    dialog: '0 16px 64px rgba(0, 0, 0, 0.60)',
  },
} as const

const LIGHT_TOKENS = {
  VOID: {
    base: '#f4f7fb',
    contentBase: '#f8fafc',
  },
  GLASS_PILL: {
    inactive: {
      background: 'rgba(255, 255, 255, 0.70)',
      backdropFilter: 'blur(20px) saturate(160%)',
      WebkitBackdropFilter: 'blur(20px) saturate(160%)',
      borderRadius: '9999px',
      border: '1px solid rgba(15, 23, 42, 0.08)',
      boxShadow: 'inset 0 1px 0 rgba(255, 255, 255, 0.75)',
      color: '#334155',
    },
    active: {
      background: 'rgba(92, 157, 255, 0.16)',
      backdropFilter: 'blur(20px) saturate(180%)',
      WebkitBackdropFilter: 'blur(20px) saturate(180%)',
      borderRadius: '9999px',
      border: '1px solid rgba(92, 157, 255, 0.24)',
      boxShadow: 'inset 0 1px 0 rgba(255, 255, 255, 0.80), 0 0 12px rgba(92, 157, 255, 0.10)',
      color: '#2563eb',
    },
    hover: {
      background: 'rgba(15, 23, 42, 0.04)',
      boxShadow: 'inset 0 1px 0 rgba(255, 255, 255, 0.45)',
    },
  },
  SIDEBAR_GLASS: {
    background: 'rgba(255, 255, 255, 0.72)',
    backdropFilter: 'blur(40px) saturate(140%)',
    WebkitBackdropFilter: 'blur(40px) saturate(140%)',
    borderRight: '1px solid rgba(15, 23, 42, 0.08)',
    border: '1px solid rgba(15, 23, 42, 0.08)',
    boxShadow: 'inset 0 1px 0 rgba(255, 255, 255, 0.85), 4px 0 24px rgba(15, 23, 42, 0.08)',
  },
  TOP_BAR: {
    background: 'rgba(255, 255, 255, 0.78)',
    backdropFilter: 'blur(40px) saturate(140%)',
    WebkitBackdropFilter: 'blur(40px) saturate(140%)',
    borderBottom: '1px solid rgba(15, 23, 42, 0.08)',
    boxShadow: 'inset 0 1px 0 rgba(255, 255, 255, 0.85)',
  },
  PANEL: {
    background: 'rgba(255, 255, 255, 0.90)',
    borderRadius: '16px',
    border: '1px solid rgba(15, 23, 42, 0.08)',
    boxShadow: '0 10px 28px rgba(15, 23, 42, 0.08)',
  },
  PANEL_NESTED: {
    background: 'rgba(248, 250, 252, 0.96)',
    borderRadius: '12px',
    border: '1px solid rgba(15, 23, 42, 0.06)',
  },
  INPUT: {
    background: 'rgba(255, 255, 255, 0.92)',
    borderRadius: '12px',
    border: '1px solid rgba(15, 23, 42, 0.08)',
    boxShadow: 'inset 0 1px 0 rgba(255, 255, 255, 0.75)',
    color: '#111827',
  },
  INPUT_HOVER: {
    background: 'rgba(255, 255, 255, 0.98)',
    borderColor: 'rgba(15, 23, 42, 0.12)',
  },
  INPUT_FOCUS: {
    background: 'rgba(255, 255, 255, 1)',
    borderColor: 'rgba(92, 157, 255, 0.42)',
    boxShadow: 'inset 0 1px 0 rgba(255, 255, 255, 0.85), 0 0 0 3px rgba(92, 157, 255, 0.14)',
  },
  TEXT: LIGHT_TEXT,
  SHADOWS: {
    float: '0 4px 20px rgba(15, 23, 42, 0.08)',
    deep: '0 8px 28px rgba(15, 23, 42, 0.10)',
    dialog: '0 18px 60px rgba(15, 23, 42, 0.16)',
  },
} as const

export function getGlassTokens(mode: ThemeMode = 'dark') {
  return mode === 'light' ? LIGHT_TOKENS : DARK_TOKENS
}

export const VOID = {
  base: 'var(--hcz-void-base)',
  contentBase: 'var(--hcz-void-content-base)',
} as const

export const GLASS_PILL = {
  inactive: {
    background: 'var(--hcz-glass-pill-inactive-background)',
    backdropFilter: 'var(--hcz-glass-pill-inactive-backdrop-filter)',
    WebkitBackdropFilter: 'var(--hcz-glass-pill-inactive-backdrop-filter)',
    borderRadius: '9999px',
    border: 'var(--hcz-glass-pill-inactive-border)',
    boxShadow: 'var(--hcz-glass-pill-inactive-box-shadow)',
    color: 'var(--hcz-glass-pill-inactive-color)',
  },
  active: {
    background: 'var(--hcz-glass-pill-active-background)',
    backdropFilter: 'var(--hcz-glass-pill-active-backdrop-filter)',
    WebkitBackdropFilter: 'var(--hcz-glass-pill-active-backdrop-filter)',
    borderRadius: '9999px',
    border: 'var(--hcz-glass-pill-active-border)',
    boxShadow: 'var(--hcz-glass-pill-active-box-shadow)',
    color: 'var(--hcz-glass-pill-active-color)',
  },
  hover: {
    background: 'var(--hcz-glass-pill-hover-background)',
    boxShadow: 'var(--hcz-glass-pill-hover-box-shadow)',
  },
} as const

export const SIDEBAR_GLASS = {
  background: 'var(--hcz-sidebar-glass-background)',
  backdropFilter: 'var(--hcz-sidebar-glass-backdrop-filter)',
  WebkitBackdropFilter: 'var(--hcz-sidebar-glass-backdrop-filter)',
  borderRight: 'var(--hcz-sidebar-glass-border-right)',
  border: 'var(--hcz-sidebar-glass-border)',
  boxShadow: 'var(--hcz-sidebar-glass-box-shadow)',
} as const

export const TOP_BAR = {
  background: 'var(--hcz-top-bar-background)',
  backdropFilter: 'var(--hcz-top-bar-backdrop-filter)',
  WebkitBackdropFilter: 'var(--hcz-top-bar-backdrop-filter)',
  borderBottom: 'var(--hcz-top-bar-border-bottom)',
  boxShadow: 'var(--hcz-top-bar-box-shadow)',
} as const

export const PANEL = {
  background: 'var(--hcz-panel-background)',
  borderRadius: 'var(--hcz-panel-border-radius)',
  border: 'var(--hcz-panel-border)',
  boxShadow: 'var(--hcz-panel-box-shadow)',
} as const

export const PANEL_NESTED = {
  background: 'var(--hcz-panel-nested-background)',
  borderRadius: 'var(--hcz-panel-nested-border-radius)',
  border: 'var(--hcz-panel-nested-border)',
} as const

export const INPUT = {
  background: 'var(--hcz-input-background)',
  borderRadius: 'var(--hcz-input-border-radius)',
  border: 'var(--hcz-input-border)',
  boxShadow: 'var(--hcz-input-box-shadow)',
  color: 'var(--hcz-input-color)',
} as const

export const INPUT_HOVER = {
  background: 'var(--hcz-input-hover-background)',
  borderColor: 'var(--hcz-input-hover-border-color)',
}

export const INPUT_FOCUS = {
  background: 'var(--hcz-input-focus-background)',
  borderColor: 'var(--hcz-input-focus-border-color)',
  boxShadow: 'var(--hcz-input-focus-box-shadow)',
}

export const SHADOWS = {
  float: 'var(--hcz-shadow-float)',
  deep: 'var(--hcz-shadow-deep)',
  dialog: 'var(--hcz-shadow-dialog)',
} as const

// ── 10. 日志表格样式 ────────────────────────────────────────────
export const LOG_TABLE_STYLES = {
  SEVERITY: {
    INFO: { backgroundColor: 'rgba(92,157,255,0.12)', color: '#5c9dff', borderRadius: '4px', padding: '2px 8px' },
    DEBUG: { backgroundColor: 'rgba(142,142,147,0.12)', color: '#8e8e93', borderRadius: '4px', padding: '2px 8px' },
    ERROR: { backgroundColor: 'rgba(255,69,58,0.12)', color: '#ff453a', borderRadius: '4px', padding: '2px 8px' },
    WARNING: { backgroundColor: 'rgba(255,159,10,0.12)', color: '#ff9f0a', borderRadius: '4px', padding: '2px 8px' },
    SUCCESS: { backgroundColor: 'rgba(50,215,75,0.12)', color: '#32d74b', borderRadius: '4px', padding: '2px 8px' },
  },
  ROW: {
    ALTERNATE: 'rgba(255,255,255,0.02)',
    HOVER: 'rgba(255,255,255,0.06)',
  },
} as const

export const metricColors = {
  tool_chain_runs: '#5c9dff',
  success_calls: '#32d74b',
  failed_calls: '#ff453a',
} as const

// ── 11. 动画系统（Spring 物理）─────────────────────────────────
export const MOTION = {
  panelEnter: { type: 'spring' as const, stiffness: 300, damping: 30 },
  pillTap: { scale: 0.96, transition: { type: 'spring' as const, stiffness: 500, damping: 30 } },
  hover: { transition: { type: 'spring' as const, stiffness: 400, damping: 30 } },
  accordion: { type: 'spring' as const, stiffness: 400, damping: 35 },
} as const

export const RADIUS = {
  panel: '16px',
  card: '12px',
  control: '12px',
  pill: '9999px',
  small: '8px',
} as const
