import { useEffect, useMemo, useState } from 'react'
import { Outlet, useNavigate, useLocation } from 'react-router-dom'
import { Box, Menu, MenuItem, Divider, Dialog, DialogTitle, DialogContent, DialogActions, Button, Stack } from '@mui/material'
import { useLocaleStore } from '../stores/locale'
import { useColorMode } from '../stores/theme'
import { getAdapterNavigationConfigs } from '../config/adapters'
import { supportedLanguages } from '../config/i18n'
import logoDarkImage from '../assets/logo_darkmode.png'
import logoLightImage from '../assets/logo_lightmode.png'
import { monitorTabs } from '../pages/monitor'
import { manageTabs } from '../pages/manage'
import { useNotification } from '../hooks/useNotification'
import { unifiedConfigApi } from '../services/api/unified-config'
import { restartApi } from '../services/api/restart'
import { getGlassTokens } from '../theme/glass'
import { useTranslation } from 'react-i18next'

const topTabs = [
  { key: 'monitor', label: 'nav.monitor', path: '/monitor/dashboard' },
  { key: 'manage', label: 'nav.manage', path: '/settings/system' },
] as const

const secondaryTabMap = {
  monitor: monitorTabs,
  manage: manageTabs,
} as const

export default function MainLayoutNew() {
  const navigate = useNavigate()
  const location = useLocation()
  const { currentLocale, setLocale } = useLocaleStore()
  const { mode, toggleColorMode } = useColorMode()
  const themeTokens = useMemo(() => getGlassTokens(mode), [mode])
  const notification = useNotification()
  const { t } = useTranslation('common')
  const [logoMenuAnchor, setLogoMenuAnchor] = useState<null | HTMLElement>(null)
  const [dangerDialogOpen, setDangerDialogOpen] = useState(false)
  const [dangerAction, setDangerAction] = useState<'reset' | 'restart' | null>(null)

  const activeTab =
    topTabs.find(tab => {
      if (tab.key === 'manage') {
        return location.pathname.startsWith('/manage/') || location.pathname.startsWith('/settings/')
      }
      return location.pathname === `/${tab.key}` || location.pathname.startsWith(`/${tab.key}/`)
    })?.key ?? null

  const secondaryTabs = activeTab ? secondaryTabMap[activeTab] : []
  const activeSecondaryTab =
    secondaryTabs.find(tab => location.pathname === tab.path || location.pathname.startsWith(`${tab.path}/`))?.path ?? null

  const adapterMenuItems = useMemo(() => getAdapterNavigationConfigs(), [])

  useEffect(() => {
    const applyViewportHeight = () => {
      const viewportHeight = window.visualViewport?.height || window.innerHeight
      document.documentElement.style.setProperty('--hcz-viewport-height', `${Math.round(viewportHeight)}px`)
    }
    applyViewportHeight()
    window.addEventListener('resize', applyViewportHeight)
    window.addEventListener('orientationchange', applyViewportHeight)
    window.visualViewport?.addEventListener('resize', applyViewportHeight)
    return () => {
      window.removeEventListener('resize', applyViewportHeight)
      window.removeEventListener('orientationchange', applyViewportHeight)
      window.visualViewport?.removeEventListener('resize', applyViewportHeight)
    }
  }, [])

  const handleLogoClick = (event: React.MouseEvent<HTMLElement>) => {
    setLogoMenuAnchor(event.currentTarget)
  }
  const handleLogoMenuClose = () => {
    setLogoMenuAnchor(null)
  }
  const handleMenuNavigate = (path: string) => {
    handleLogoMenuClose()
    navigate(path)
  }
  const handleOpenDangerDialog = () => {
    handleLogoMenuClose()
    setDangerDialogOpen(true)
  }
  const handleCloseDangerDialog = () => {
    if (dangerAction) return
    setDangerDialogOpen(false)
  }
  const handleDangerReset = async () => {
    setDangerAction('reset')
    try {
      await unifiedConfigApi.reloadConfig('system')
      notification.success(t('configTable.reloadSuccess'))
      setDangerDialogOpen(false)
    } catch (error) {
      const message = error instanceof Error ? error.message : t('configTable.resetConfig')
      notification.error(message)
    } finally {
      setDangerAction(null)
    }
  }
  const handleDangerRestart = async () => {
    setDangerAction('restart')
    try {
      const response = await restartApi.restartSystem()
      if (response.code === 200) {
        notification.success(t('configTable.restartSent'))
        setDangerDialogOpen(false)
      } else {
        notification.error(response.msg || t('configTable.restartFailed'))
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : t('configTable.restartFailed')
      notification.error(message)
    } finally {
      setDangerAction(null)
    }
  }

  const getPillSx = (isActive: boolean) => ({
    px: 2.5,
    py: 0.75,
    fontSize: '0.875rem',
    fontWeight: 500,
    cursor: 'pointer',
    whiteSpace: 'nowrap',
    flexShrink: 0,
    ...(isActive ? themeTokens.GLASS_PILL.active : themeTokens.GLASS_PILL.inactive),
    '&:hover': isActive ? {} : { ...themeTokens.GLASS_PILL.hover },
  })

  return (
    <Box sx={{ display: 'flex', height: 'var(--hcz-viewport-height, 100vh)', minHeight: 'var(--hcz-viewport-height, 100vh)', overflow: 'hidden', background: themeTokens.VOID.base }}>
      {/* Top Bar */}
      <Box
        sx={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          height: 52,
          zIndex: 1300,
          display: 'flex',
          alignItems: 'center',
          px: 2,
          gap: 2,
          minWidth: 0,
          ...themeTokens.TOP_BAR,
        }}
      >
        <Box
          component="img"
          src={mode === 'dark' ? logoDarkImage : logoLightImage}
          alt="HCZ"
          onClick={handleLogoClick}
          sx={{
            width: 40,
            height: 40,
            cursor: 'pointer',
            borderRadius: '10px',
            flexShrink: 0,
          }}
        />

        <Box sx={{ display: 'flex', gap: 1, minWidth: 0, flexShrink: 0 }}>
          {topTabs.map(tab => (
            <Box
              key={tab.key}
              onClick={() => navigate(tab.path)}
              sx={getPillSx(activeTab === tab.key)}
            >
              {t(tab.label)}
            </Box>
          ))}
        </Box>

        <Box
          sx={{
            ml: 'auto',
            display: 'flex',
            gap: 0.75,
            minWidth: 0,
            overflowX: 'auto',
            scrollbarWidth: 'none',
            '&::-webkit-scrollbar': { display: 'none' },
          }}
        >
          {secondaryTabs.map(tab => (
            <Box
              key={tab.path}
              onClick={() => navigate(tab.path)}
              sx={{
                px: 1.75,
                py: 0.55,
                fontSize: '0.8rem',
                fontWeight: 500,
                whiteSpace: 'nowrap',
                cursor: 'pointer',
                flexShrink: 0,
                ...(activeSecondaryTab === tab.path ? themeTokens.GLASS_PILL.active : themeTokens.GLASS_PILL.inactive),
                '&:hover': activeSecondaryTab === tab.path ? {} : { ...themeTokens.GLASS_PILL.hover },
              }}
            >
              {t(tab.label)}
            </Box>
          ))}
        </Box>
      </Box>

      {/* Logo Menu */}
      <Menu
        anchorEl={logoMenuAnchor}
        open={Boolean(logoMenuAnchor)}
        onClose={handleLogoMenuClose}
        sx={{
          '& .MuiPaper-root': {
            background: themeTokens.SIDEBAR_GLASS.background,
            backdropFilter: themeTokens.SIDEBAR_GLASS.backdropFilter,
            WebkitBackdropFilter: themeTokens.SIDEBAR_GLASS.WebkitBackdropFilter,
            border: themeTokens.SIDEBAR_GLASS.border,
            borderRadius: '16px',
            width: 280,
            mt: 1,
            boxShadow: themeTokens.SIDEBAR_GLASS.boxShadow,
          },
        }}
      >
        {adapterMenuItems.map(item => (
          <MenuItem key={item.path} onClick={() => handleMenuNavigate(item.path)}>
            {item.text}
          </MenuItem>
        ))}
        <Divider sx={{ borderColor: themeTokens.TEXT.divider }} />
        <MenuItem onClick={() => handleMenuNavigate('/manage/users')}>{t('nav.users')}</MenuItem>
        <MenuItem onClick={() => handleMenuNavigate('/settings/model-groups')}>{t('nav.models')}</MenuItem>
        <Divider sx={{ borderColor: themeTokens.TEXT.divider }} />
        <MenuItem onClick={handleOpenDangerDialog}>{t('actions.reset')}</MenuItem>
        <MenuItem onClick={toggleColorMode}>
          {mode === 'dark' ? t('menu.lightMode') : t('menu.darkMode')}
        </MenuItem>
        <MenuItem onClick={() => setLocale(currentLocale === 'zh-CN' ? 'en-US' : 'zh-CN')}>
          {currentLocale === 'zh-CN' ? supportedLanguages['en-US'] : supportedLanguages['zh-CN']}
        </MenuItem>
      </Menu>

      {/* Main Content */}
      <Box
        component="main"
        sx={{
          flexGrow: 1,
          minWidth: 0,
          height: 'calc(var(--hcz-viewport-height, 100vh) - 52px)',
          mt: '52px',
          p: 0,
          overflow: 'hidden',
          ['--hcz-page-offset' as string]: '52px',
          background: themeTokens.VOID.contentBase,
        }}
      >
        <Outlet />
      </Box>

      {/* Danger Dialog */}
      <Dialog open={dangerDialogOpen} onClose={handleCloseDangerDialog} maxWidth="xs" fullWidth>
        <DialogTitle sx={{ textAlign: 'center', background: themeTokens.PANEL.background }}>{t('menu.dangerTitle')}</DialogTitle>
        <DialogContent sx={{ background: themeTokens.PANEL.background }}>
          <Stack spacing={1.5} sx={{ pt: 1 }}>
            <Button
              fullWidth
              color="error"
              variant="contained"
              onClick={handleDangerReset}
              disabled={Boolean(dangerAction)}
            >
              {dangerAction === 'reset' ? t('menu.processing') : t('configTable.resetConfig')}
            </Button>
            <Button
              fullWidth
              color="error"
              variant="outlined"
              onClick={handleDangerRestart}
              disabled={Boolean(dangerAction)}
            >
              {dangerAction === 'restart' ? t('menu.processing') : t('configTable.restartAction')}
            </Button>
          </Stack>
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 2, justifyContent: 'center', background: themeTokens.PANEL.background }}>
          <Button onClick={handleCloseDangerDialog} disabled={Boolean(dangerAction)}>
            {t('actions.cancel')}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  )
}
