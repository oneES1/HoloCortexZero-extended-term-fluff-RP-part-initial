import { useParams, useLocation, useOutletContext } from 'react-router-dom'
import { Box, Alert, Typography } from '@mui/material'
import { getAdapterConfig } from '../../config/adapters'
import { useTranslation } from 'react-i18next'
import { AdapterDetailInfo } from '../../services/api/adapters'

interface AdapterContextType {
  adapterInfo: AdapterDetailInfo
}

export default function AdapterTabPage() {
  const { adapterKey } = useParams<{ adapterKey: string }>()
  const location = useLocation()
  const { t } = useTranslation('adapter')
  const { adapterInfo } = useOutletContext<AdapterContextType>()

  if (!adapterKey) {
    return <div>{t('tab.adapterNotExist')}</div>
  }

  // 获取当前适配器配置
  const adapterConfig = getAdapterConfig(adapterKey)
  if (!adapterConfig) {
    return <div>{t('tab.pageNotExist')}</div>
  }

  if (adapterConfig.tabs.length === 0) {
    return (
      <Box sx={{ p: 3 }}>
        <Alert severity="info">
          <Typography variant="h6" gutterBottom>
            {t('config.notSupportedTitle')}
          </Typography>
          {t('config.notSupportedMessage')}
        </Alert>
      </Box>
    )
  }

  // 根据当前路径找到对应的选项卡配置
  const currentPath = location.pathname
  const basePath = `/adapters/${adapterKey}`

  // 确定当前选项卡的路径部分
  const tabPath = currentPath === basePath ? '' : currentPath.replace(`${basePath}/`, '')

  // 找到匹配的选项卡配置
  const currentTab =
    adapterConfig.tabs.find(tab => tab.path === tabPath) ||
    (tabPath === '' ? adapterConfig.tabs[0] : undefined)

  if (!currentTab) {
    return <div>{t('tab.pageNotExist')}</div>
  }

  // 渲染对应的组件
  return currentTab.component
}
