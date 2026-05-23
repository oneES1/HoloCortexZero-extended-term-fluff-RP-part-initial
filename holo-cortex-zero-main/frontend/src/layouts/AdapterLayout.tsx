import { Outlet, useNavigate, useLocation, useParams } from 'react-router-dom'
import {
  Box,
  Typography,
  Alert,
  CircularProgress,
  useTheme,
  Button,
} from '@mui/material'
import { useQuery } from '@tanstack/react-query'
import { motion } from 'framer-motion'
import { adaptersApi, AdapterDetailInfo } from '../services/api/adapters'
import {
  getAdapterConfig,
  getAdapterTabPath,
} from '../config/adapters'
import { Suspense } from 'react'
import { useTranslation } from 'react-i18next'

export default function AdapterLayout() {
  const navigate = useNavigate()
  const location = useLocation()
  const { adapterKey } = useParams<{ adapterKey: string }>()
  const theme = useTheme()
  const { t } = useTranslation('adapter')

  const adapterConfig = adapterKey ? getAdapterConfig(adapterKey) : undefined
  const tabs = (adapterConfig?.tabs || []).map(tab => ({
    label: tab.label,
    value: tab.value,
    path: getAdapterTabPath(adapterKey || '', tab.path),
  }))

  const {
    data: adapterInfo,
    isLoading,
    error,
  } = useQuery<AdapterDetailInfo>({
    queryKey: ['adapter-info', adapterKey],
    queryFn: () => adaptersApi.getAdapterInfo(adapterKey!),
    enabled: !!adapterKey && !!adapterConfig,
  })

  const activeTabValue = tabs.find(tab => tab.path === location.pathname)?.value
    || tabs[0]?.value
    || ''

  if (!adapterConfig) {
    return (
      <Box sx={{ p: 3 }}>
        <Alert severity="info">{t('tab.pageNotExist')}</Alert>
      </Box>
    )
  }

  if (isLoading) {
    return (
      <Box
        sx={{
          height: '100%',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          flexDirection: 'column',
          gap: 2,
        }}
      >
        <CircularProgress size={48} thickness={3.6} />
        <Typography variant="body2" color="text.secondary">
          {t('loading')}
        </Typography>
      </Box>
    )
  }

  if (error || !adapterInfo) {
    return (
      <Box sx={{ p: 3 }}>
        <Alert severity="error" sx={{ bgcolor: 'rgba(255, 69, 58, 0.08)', border: 'none' }}>
          <Typography variant="h6" gutterBottom>
            {t('loadFailed')}
          </Typography>
          {error instanceof Error ? error.message : t('loadAdapterFailed')}
        </Alert>
      </Box>
    )
  }

  const showSidebar = tabs.length > 1

  return (
    <Box
      sx={{
        height: '100%',
        display: 'flex',
        flexDirection: 'row',
        overflow: 'hidden',
      }}
    >
      {/* 左侧导航 */}
      {showSidebar && (
        <Box
          sx={{
            width: 180,
            flexShrink: 0,
            borderRight: `1px solid ${theme.palette.divider}`,
            py: 2.5,
            px: 1.5,
            display: 'flex',
            flexDirection: 'column',
            gap: 0.5,
          }}
        >
          {tabs.map(tab => {
            const isActive = tab.value === activeTabValue
            return (
              <Button
                key={tab.value}
                onClick={() => navigate(tab.path)}
                sx={{
                  justifyContent: 'flex-start',
                  width: '100%',
                  py: 0.75,
                  px: 1.5,
                  borderRadius: 1.5,
                  fontSize: '0.8125rem',
                  fontWeight: isActive ? 600 : 400,
                  color: isActive
                    ? theme.palette.primary.main
                    : theme.palette.text.secondary,
                  bgcolor: isActive
                    ? theme.palette.action.selected
                    : 'transparent',
                  transition: 'all 0.15s ease',
                  '&:hover': {
                    bgcolor: isActive
                      ? theme.palette.action.selected
                      : theme.palette.action.hover,
                  },
                }}
              >
                {t(tab.label)}
              </Button>
            )
          })}
        </Box>
      )}

      {/* 右侧内容 */}
      <Box sx={{ flex: 1, overflow: 'hidden', minHeight: 0 }}>
        <motion.div
          key={activeTabValue}
          initial={{ opacity: 0, y: 6 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.25, ease: [0.4, 0, 0.2, 1] }}
          style={{ height: '100%', overflow: 'auto' }}
        >
          <Suspense
            fallback={
              <Box
                sx={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  height: '100%',
                }}
              >
                <CircularProgress />
              </Box>
            }
          >
            <Outlet context={{ adapterInfo }} />
          </Suspense>
        </motion.div>
      </Box>
    </Box>
  )
}
