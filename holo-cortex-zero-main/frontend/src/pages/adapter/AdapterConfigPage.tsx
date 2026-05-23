import { useParams, useOutletContext } from 'react-router-dom'
import { Box, Typography, Alert, alpha } from '@mui/material'
import { useTranslation } from 'react-i18next'
import { useQuery } from '@tanstack/react-query'
import ConfigTable from '../../components/common/ConfigTable'
import { createConfigService } from '../../services/api/unified-config'
import { AdapterDetailInfo } from '../../services/api/adapters'
import { useTheme } from '@mui/material'

interface AdapterContextType {
  adapterInfo: AdapterDetailInfo
}

export default function AdapterConfigPage() {
  const { adapterKey } = useParams<{ adapterKey: string }>()
  const { adapterInfo } = useOutletContext<AdapterContextType>()
  const { t } = useTranslation('adapter')
  const theme = useTheme()

  const configKey = `adapter_${adapterKey}`
  const configService = createConfigService(configKey)

  const {
    data: configs = [],
    refetch,
    isLoading,
  } = useQuery({
    queryKey: ['adapter-configs', adapterKey],
    queryFn: () => configService.getConfigList(configKey),
    enabled: adapterInfo.has_config,
  })

  if (!adapterInfo.has_config) {
    return (
      <Box sx={{ p: 3 }}>
        <Alert severity="info" sx={{ bgcolor: alpha(theme.palette.info.main, 0.06), border: 'none' }}>
          <Typography variant="h6" gutterBottom>
            {t('config.notSupportedTitle')}
          </Typography>
          {t('config.notSupportedMessage')}
        </Alert>
      </Box>
    )
  }

  return (
    <Box
      sx={{
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden',
        p: { xs: 2, md: 3 },
      }}
    >
      {/* 配置列表 */}
      <Box sx={{ flex: 1, minHeight: 0, overflow: 'hidden' }}>
        <ConfigTable
          configKey={configKey}
          configService={configService}
          configs={configs}
          loading={isLoading}
          onRefresh={refetch}
          showSearchBar={false}
          showToolbar={false}
          emptyMessage={t('config.emptyMessage', { name: adapterInfo.name })}
        />
      </Box>
    </Box>
  )
}
