import { useCallback, useEffect, useMemo, useState } from 'react'
import { Box, Paper, Stack, TextField, Typography } from '@mui/material'
import { useQuery } from '@tanstack/react-query'
import { createConfigService, unifiedConfigApi } from '../../services/api/unified-config'
import type { ConfigItem } from '../../components/common/ConfigTable'
import { useTranslation } from 'react-i18next'
import { getLocalizedText } from '../../services/api/types'
import { useNotification } from '../../hooks/useNotification'

const DEFAULT_PROMPT_KEY = 'MAIN_SYSTEM_PROMPT_ADVANCED'
const PROMPT_KEYS = [
  'BOT_PERSONA_DISPLAY_NAME',
  'MAIN_SYSTEM_PROMPT_ADVANCED',
  'MAIN_SYSTEM_PROMPT_ADVANCED_DEEK',
  'MAIN_SYSTEM_PROMPT_ADVANCED_DEEP',
  'MAIN_SYSTEM_PROMPT_NORMAL',
  'AI_REPLY_JUDGE_SYSTEM_PROMPT',
  'SUBCONSCIOUS_SYSTEM_PROMPT',
  'AUTO_MEMORY_SYSTEM_PROMPT',
  'MEMORY_ARBITER_SYSTEM_PROMPT',
  'TIMELINE_SYSTEM_PROMPT',
] as const

const orderConfigs = (configs: ConfigItem[], order: readonly string[]) => {
  const map = new Map(configs.map(config => [config.key, config]))
  return order.map(key => map.get(key)).filter((item): item is ConfigItem => Boolean(item))
}

const toEditableValue = (config: ConfigItem | undefined) => {
  if (!config) return ''
  return typeof config.value === 'string' ? config.value : String(config.value ?? '')
}

export default function PromptManagementPage() {
  const { t, i18n } = useTranslation(['prompt-management', 'common'])
  const notification = useNotification()
  const configService = createConfigService('system')
  const [selectedKey, setSelectedKey] = useState<string>(DEFAULT_PROMPT_KEY)
  const [editingValues, setEditingValues] = useState<Record<string, string>>({})
  const [initialValues, setInitialValues] = useState<Record<string, string>>({})

  const {
    data: configs = [],
    refetch,
    isLoading,
  } = useQuery({
    queryKey: ['prompt-management-system-configs'],
    queryFn: () => unifiedConfigApi.getConfigList('system', { includeHidden: true }),
  })

  const promptConfigs = useMemo(() => orderConfigs(configs, PROMPT_KEYS), [configs])

  const getTitle = useCallback(
    (config: ConfigItem) => getLocalizedText(config.i18n_title, config.title, i18n.language),
    [i18n.language]
  )

  useEffect(() => {
    const nextValues = Object.fromEntries(
      promptConfigs
        .filter((config): config is ConfigItem => Boolean(config))
        .map(config => [config.key, toEditableValue(config)])
    )
    setInitialValues(nextValues)
    setEditingValues(prev => {
      const preserved: Record<string, string> = {}
      for (const key of Object.keys(prev)) {
        if ((prev[key] ?? '') !== (nextValues[key] ?? '')) {
          preserved[key] = prev[key]
        }
      }
      return { ...nextValues, ...preserved }
    })
  }, [promptConfigs])

  useEffect(() => {
    if (promptConfigs.length === 0) {
      setSelectedKey('')
      return
    }
    const exists = promptConfigs.some(config => config.key === selectedKey)
    if (exists) return
    const defaultConfig = promptConfigs.find(config => config.key === DEFAULT_PROMPT_KEY)
    setSelectedKey(defaultConfig?.key || promptConfigs[0].key)
  }, [promptConfigs, selectedKey])

  const dirtyKeys = useMemo(
    () =>
      Object.keys(editingValues).filter(
        key => (editingValues[key] ?? '') !== (initialValues[key] ?? '')
      ),
    [editingValues, initialValues]
  )

  const selectedConfig = useMemo(
    () => promptConfigs.find(config => config.key === selectedKey),
    [promptConfigs, selectedKey]
  )

  const handleValueChange = (key: string, value: string) => {
    setEditingValues(prev => ({ ...prev, [key]: value }))
  }

  const handleReset = () => {
    setEditingValues(initialValues)
  }

  const handleSave = useCallback(
    async (isAutoSave: boolean = false) => {
      const changedConfigs = Object.fromEntries(
        dirtyKeys
          .map(key => [key, editingValues[key] ?? ''])
          .filter(([key]) => key in initialValues)
      )

      if (Object.keys(changedConfigs).length === 0) {
        return
      }

      try {
        // 主干保存路径：后端 batch 接口负责更新并持久化配置。
        await configService.batchUpdateConfig('system', changedConfigs)
        if (!isAutoSave) {
          notification.success(t('configTable.saveSuccess', { ns: 'common' }))
        }
        setInitialValues(prev => ({ ...prev, ...changedConfigs }))
        refetch()
      } catch (error) {
        const message = error instanceof Error ? error.message : t('messages.saveFailed', { ns: 'common' })
        notification.error(message)
      }
    },
    [dirtyKeys, editingValues, initialValues, configService, notification, t, refetch]
  )

  // 自动保存：修改后延迟 1s 自动保存
  useEffect(() => {
    if (dirtyKeys.length === 0) return
    const timer = setTimeout(() => {
      handleSave(true)
    }, 1000)
    return () => clearTimeout(timer)
  }, [dirtyKeys, editingValues, handleSave])

  return (
    <Box
      sx={{
        height: '100%',
        minHeight: 0,
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden',
        p: 2,
        gap: 1.5,
      }}
    >
      <Box
        sx={{
          flex: 1,
          minHeight: 0,
          display: 'grid',
          gridTemplateColumns: { xs: '1fr', md: '260px minmax(0, 1fr)' },
          gridTemplateRows: { xs: 'minmax(180px, 32%) minmax(0, 1fr)', md: 'minmax(0, 1fr)' },
          alignItems: 'stretch',
          gap: 1.5,
          overflow: 'hidden',
        }}
      >
        <Paper
          elevation={0}
          sx={{
            display: 'flex',
            flexDirection: 'column',
            minHeight: 0,
            height: '100%',
            overflow: 'hidden',
            borderRadius: 3,
            border: '1px solid',
            borderColor: 'divider',
            bgcolor: 'background.paper',
          }}
        >
          <Box sx={{ flex: 1, minHeight: 0, overflowY: 'auto', p: 1 }}>
            <Stack spacing={0.75}>
              {promptConfigs.map(config => {
                const active = config.key === selectedKey
                return (
                  <Box
                    key={config.key}
                    onClick={() => setSelectedKey(config.key)}
                    sx={{
                      px: 1.5,
                      py: 1.2,
                      borderRadius: 2,
                      cursor: 'pointer',
                      userSelect: 'none',
                      transition: 'all 0.18s ease',
                      bgcolor: active ? 'action.selected' : 'transparent',
                      border: '1px solid',
                      borderColor: active ? 'primary.main' : 'divider',
                      '&:hover': {
                        bgcolor: active ? 'action.selected' : 'action.hover',
                        borderColor: active ? 'primary.main' : 'text.disabled',
                      },
                    }}
                  >
                    <Typography variant="body2" sx={{ fontWeight: active ? 700 : 500, lineHeight: 1.4 }}>
                      {getTitle(config)}
                    </Typography>
                  </Box>
                )
              })}
              {promptConfigs.length === 0 && (
                <Typography variant="body2" color="text.secondary" sx={{ px: 1, py: 1.5 }}>
                  {t('empty')}
                </Typography>
              )}
            </Stack>
          </Box>
        </Paper>

        <Paper
          elevation={0}
          sx={{
            display: 'flex',
            flexDirection: 'column',
            minHeight: 0,
            height: '100%',
            overflow: 'hidden',
            borderRadius: 3,
            border: '1px solid',
            borderColor: 'divider',
            bgcolor: 'background.paper',
          }}
        >
          {selectedConfig ? (
            selectedConfig.is_textarea ? (
              <Box
                component="textarea"
                value={editingValues[selectedConfig.key] ?? ''}
                onChange={event => handleValueChange(selectedConfig.key, event.target.value)}
                spellCheck={false}
                placeholder={getTitle(selectedConfig)}
                sx={{
                  flex: 1,
                  width: '100%',
                  minHeight: 0,
                  resize: 'none',
                  border: 'none',
                  outline: 'none',
                  bgcolor: 'transparent',
                  color: 'text.primary',
                  p: 2,
                  fontSize: '0.92rem',
                  lineHeight: 1.65,
                  fontFamily:
                    'ui-monospace, SFMono-Regular, SF Mono, Menlo, Monaco, Consolas, Liberation Mono, monospace',
                  overflowY: 'auto',
                  '&::placeholder': {
                    color: 'text.disabled',
                  },
                }}
              />
            ) : (
              <Box sx={{ flex: 1, p: 2 }}>
                <TextField
                  value={editingValues[selectedConfig.key] ?? ''}
                  onChange={event => handleValueChange(selectedConfig.key, event.target.value)}
                  fullWidth
                  size="small"
                  placeholder={getTitle(selectedConfig)}
                />
              </Box>
            )
          ) : (
            <Box
              sx={{
                flex: 1,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: 'text.secondary',
                px: 2,
              }}
            >
              <Typography variant="body2">{t('empty')}</Typography>
            </Box>
          )}
        </Paper>
      </Box>
    </Box>
  )
}
