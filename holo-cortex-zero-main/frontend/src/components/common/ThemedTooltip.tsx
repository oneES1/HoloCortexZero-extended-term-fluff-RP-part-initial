/**
 * 主题化的 Tooltip 组件
 * Glass 轻量材质
 */
import { Tooltip, tooltipClasses, TooltipProps, styled } from '@mui/material'
import { COLORS } from '../../theme/glass'

export const ThemedTooltip = styled(({ className, ...props }: TooltipProps) => (
  <Tooltip {...props} classes={{ popper: className }} />
))(() => ({
  [`& .${tooltipClasses.tooltip}`]: {
    backgroundColor: 'rgba(20, 20, 25, 0.85)',
    backdropFilter: 'blur(20px) saturate(160%)',
    WebkitBackdropFilter: 'blur(20px) saturate(160%)',
    color: COLORS.textPrimary,
    maxWidth: 300,
    fontSize: '0.75rem',
    border: '1px solid rgba(255, 255, 255, 0.08)',
    borderRadius: '12px',
    boxShadow: '0 4px 16px rgba(0, 0, 0, 0.25)',
    lineHeight: 1.4,
    padding: '8px 12px',
    '& a': {
      color: COLORS.accent,
      textDecoration: 'none',
      fontWeight: 500,
      '&:hover': { textDecoration: 'underline' },
    },
    '& strong': {
      fontWeight: 600,
      color: COLORS.textPrimary,
    },
    '& code': {
      backgroundColor: 'rgba(255, 255, 255, 0.08)',
      color: COLORS.accent,
      padding: '2px 4px',
      borderRadius: '3px',
      fontSize: '0.85em',
      fontFamily: 'Monaco, Consolas, "Courier New", monospace',
    },
  },
  [`& .${tooltipClasses.arrow}`]: {
    color: 'rgba(20, 20, 25, 0.85)',
  },
}))

export default ThemedTooltip
