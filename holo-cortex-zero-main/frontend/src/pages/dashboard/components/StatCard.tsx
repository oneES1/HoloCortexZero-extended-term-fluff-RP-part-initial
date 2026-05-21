import React from 'react'
import {
  Card,
  CardContent,
  Typography,
  Box,
  CircularProgress,
  useMediaQuery,
  useTheme,
  alpha,
} from '@mui/material'

interface StatCardProps {
  title: string
  value: number | string
  icon?: React.ReactNode
  color?: 'primary' | 'secondary' | 'success' | 'error' | 'warning' | 'info' | string
  loading?: boolean
}

export const StatCard: React.FC<StatCardProps> = ({
  title,
  value,
  icon,
  color = 'primary',
  loading = false,
}) => {
  const theme = useTheme()
  const isMobile = useMediaQuery(theme.breakpoints.down('sm'))

  // 获取颜色值
  const getCardColor = () => {
    // 使用预定义的颜色
    switch (color) {
      case 'primary':
        return theme.palette.primary.main
      case 'secondary':
        return theme.palette.secondary.main
      case 'success':
        return theme.palette.success.main
      case 'error':
        return theme.palette.error.main
      case 'warning':
        return theme.palette.warning.main
      case 'info':
        return theme.palette.info.main
      default:
        // 如果是自定义颜色代码，直接返回
        return color.startsWith('#') ? color : theme.palette.primary.main
    }
  }

  // 获取实际颜色
  const actualColor = getCardColor()

  return (
    <Card
      className="w-full"
      sx={{
        position: 'relative',
        overflow: 'hidden',
        '&::after': {
          content: '""',
          position: 'absolute',
          top: 0,
          left: 0,
          width: '4px',
          height: '100%',
          backgroundColor: actualColor,
          opacity: 0.8,
          boxShadow: `0 0 10px ${actualColor}`,
        }
      }}
    >
      <CardContent
        className={`flex items-center ${isMobile ? 'p-3' : 'p-4'}`}
      >
        {icon && (
          <Box
            className={`flex items-center justify-center rounded-full ${isMobile ? 'p-1.5 mr-2' : 'p-2 mr-3'}`}
            sx={{
              bgcolor: alpha(actualColor, 0.1),
              color: actualColor,
              transition: 'all 0.3s cubic-bezier(0.32, 0.72, 0, 1)',
              '&:hover': {
                transform: 'scale(1.1)',
                bgcolor: alpha(actualColor, 0.2),
              },
            }}
          >
            {icon}
          </Box>
        )}
        <Box className="flex-grow">
          <Typography
            variant={isMobile ? 'caption' : 'body2'}
            color="text.secondary"
            gutterBottom
            sx={{
              fontWeight: 500,
              opacity: 0.8,
              letterSpacing: '0.02em',
            }}
          >
            {title}
          </Typography>
          {loading ? (
            <CircularProgress size={isMobile ? 16 : 20} sx={{ color: actualColor }} />
          ) : (
            <Typography
              variant={isMobile ? 'h6' : 'h5'}
              component="div"
              fontWeight="bold"
              sx={{
                whiteSpace: 'nowrap',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                color: theme.palette.text.primary,
                letterSpacing: '-0.02em',
              }}
            >
              {value}
            </Typography>
          )}
        </Box>
      </CardContent>
    </Card>
  )
}
