import { useState } from 'react'
import { Box, Typography, alpha, useTheme } from '@mui/material'
import { useQuery } from '@tanstack/react-query'
import { oneBotV11Api } from '../../../services/api/adapters/onebot_v11'
import { unifiedConfigApi } from '../../../services/api/unified-config'
import { useTranslation } from 'react-i18next'

export default function OneBotV11NapCatPage() {
  const [iframeLoaded, setIframeLoaded] = useState(false)
  const { t } = useTranslation('adapter')
  const theme = useTheme()

  const { data: napCatConfig } = useQuery({
    queryKey: ['config', 'NAPCAT_ACCESS_URL'],
    queryFn: async () => {
      const response = await unifiedConfigApi.getConfigItem(
        'adapter_onebot_v11',
        'NAPCAT_ACCESS_URL'
      )
      return response.value as string
    },
  })

  const { data: napcatToken } = useQuery({
    queryKey: ['onebot-v11-napcat-token'],
    queryFn: () => oneBotV11Api.getNapcatToken(),
    refetchInterval: 10000,
  })

  const napcatAccessUrl = (() => {
    if (!napCatConfig) {
      return null
    }

    if (!napcatToken) {
      return napCatConfig
    }

    try {
      const url = new URL(napCatConfig, window.location.origin)
      url.searchParams.set('token', napcatToken)
      return url.toString()
    } catch {
      return napCatConfig
    }
  })()

  return (
    <Box
      sx={{
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden',
        p: { xs: 2, md: 3 },
        gap: 2,
      }}
    >
      {/* iframe 区域 */}
      <Box
        sx={{
          flex: 1,
          position: 'relative',
          borderRadius: 2,
          overflow: 'hidden',
          bgcolor:
            theme.palette.mode === 'dark'
              ? alpha(theme.palette.common.white, 0.02)
              : alpha(theme.palette.common.black, 0.01),
        }}
      >
        <Box
          sx={{
            position: 'absolute',
            inset: 8,
            borderRadius: 1.5,
            overflow: 'hidden',
            '& iframe': {
              width: '100%',
              height: '100%',
              border: 'none',
              opacity: iframeLoaded ? 1 : 0,
              transition: 'opacity 0.3s',
            },
          }}
        >
          {napcatAccessUrl && (
            <iframe src={napcatAccessUrl} onLoad={() => setIframeLoaded(true)} />
          )}
        </Box>

        {!iframeLoaded && (
          <Box
            sx={{
              position: 'absolute',
              inset: 0,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            {!napCatConfig ? (
              <Typography color="error">{t('napcat.cannotGetAddress')}</Typography>
            ) : (
              <Typography color="text.secondary">{t('napcat.serviceNotRunning')}</Typography>
            )}
          </Box>
        )}
      </Box>
    </Box>
  )
}
