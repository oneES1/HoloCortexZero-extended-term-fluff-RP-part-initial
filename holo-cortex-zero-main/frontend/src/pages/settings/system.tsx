import { useState, useEffect } from 'react'
import { Box } from '@mui/material'
import { useQuery } from '@tanstack/react-query'
import { useLocation } from 'react-router-dom'
import ConfigTable from '../../components/common/ConfigTable'
import { createConfigService } from '../../services/api/unified-config'
import { useTranslation } from 'react-i18next'

export default function SettingsPage() {
  const location = useLocation()
  const [searchText, setSearchText] = useState<string>('')
  const { t } = useTranslation(['settings', 'common'])

  useEffect(() => {
    const searchParams = new URLSearchParams(location.search)
    const searchParamValue = searchParams.get('search')
    if (searchParamValue) {
      setSearchText(searchParamValue)
    }
  }, [location.search])

  const configService = createConfigService('system')

  const {
    data: configs = [],
    refetch,
    isLoading,
  } = useQuery({
    queryKey: ['system-configs'],
    queryFn: () => configService.getConfigList('system'),
  })

  const handleSearchChange = (text: string) => {
    setSearchText(text)
  }

  const handleRefresh = () => {
    refetch()
  }


  return (
    <Box
      sx={{
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden',
        p: 2,
      }}
    >
      <Box sx={{ flex: 1, minHeight: 0, overflow: 'hidden' }}>
        <ConfigTable
          configKey="system"
          configService={configService}
          configs={configs}
          loading={isLoading}
          searchText={searchText}
          onSearchChange={handleSearchChange}
          onRefresh={handleRefresh}
          showSearchBar={true}
          showToolbar={true}
          emptyMessage={t('system.emptyMessage', { ns: 'settings' })}
        />
      </Box>
    </Box>
  )
}
