/**
 * 统一的消息通知组件
 * PANEL 实色卡片 + 左侧强调色竖条，无图标
 */
import { forwardRef, ReactElement } from 'react'
import { SnackbarContent, CustomContentProps, SnackbarKey } from 'notistack'
import { Box, Paper, Typography, useTheme } from '@mui/material'

interface HCZNotificationProps extends Omit<CustomContentProps, 'style'> {
  message: string | ReactElement
  style?: React.CSSProperties
  onClose?: (event: React.SyntheticEvent<Element, Event> | null, reason: string | undefined, key: SnackbarKey) => void
}

const HCZNotification = forwardRef<HTMLDivElement, HCZNotificationProps>((props, ref) => {
  const { id, message, variant = 'default', onClose, style } = props
  const theme = useTheme()

  const getColor = () => {
    switch (variant) {
      case 'success':
        return theme.palette.success.main
      case 'error':
        return theme.palette.error.main
      case 'warning':
        return theme.palette.warning.main
      case 'info':
        return theme.palette.info.main
      default:
        return theme.palette.primary.main
    }
  }

  const color = getColor()

  return (
    <SnackbarContent ref={ref} style={style}>
      <Paper
        elevation={0}
        sx={{
          overflow: 'hidden',
          position: 'relative',
          display: 'flex',
          minWidth: 280,
          maxWidth: { xs: 'calc(100vw - 32px)', sm: 440 },
          borderRadius: '12px',
          border: `1px solid ${theme.palette.divider}`,
          backgroundColor: theme.palette.background.paper,
          boxShadow: theme.palette.mode === 'dark'
            ? '0 8px 32px rgba(0, 0, 0, 0.40)'
            : '0 8px 28px rgba(15, 23, 42, 0.12)',
          '&::before': {
            content: '""',
            position: 'absolute',
            top: 0,
            left: 0,
            width: '4px',
            height: '100%',
            backgroundColor: color,
          },
        }}
      >
        <Box
          sx={{
            display: 'flex',
            alignItems: 'center',
            padding: theme.spacing(1.5, 2),
            pl: theme.spacing(2.5),
            width: '100%',
          }}
        >
          <Typography
            variant="body2"
            sx={{
              flexGrow: 1,
              fontWeight: 500,
              color: theme.palette.text.primary,
            }}
          >
            {message}
          </Typography>

          {onClose && (
            <Typography
              component="span"
              onClick={() => onClose(null, 'timeout', id)}
              sx={{
                ml: 1.5,
                fontSize: '0.75rem',
                color: theme.palette.text.secondary,
                cursor: 'pointer',
                flexShrink: 0,
                '&:hover': { color: theme.palette.text.primary },
              }}
            >
              Close
            </Typography>
          )}
        </Box>
      </Paper>
    </SnackbarContent>
  )
})

HCZNotification.displayName = 'HCZNotification'

export default HCZNotification
