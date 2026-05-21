import { useState, useEffect, useCallback, useMemo } from 'react'
import {
  Box,
  TextField,
  Switch,
  FormControlLabel,
  MenuItem,
  InputAdornment,
  Typography,
  Button,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  CircularProgress,
  useTheme,
  useMediaQuery,
  Stack,
  Alert,
  Table,
  TableBody,
} from '@mui/material'
import HelpOutlineIcon from '@mui/icons-material/HelpOutline'
import { PANEL, PANEL_NESTED } from '../../theme/glass'
import { useNotification } from '../../hooks/useNotification'
import { restartApi } from '../../services/api/restart'
import { ThemedTooltip } from './ThemedTooltip'
import { useTranslation } from 'react-i18next'
import { getLocalizedText } from '../../services/api/types'
import type {
  ConfigItem,
  ConfigTableProps,
  ExpandedRowsState,
  ModelGroupConfig,
  ModelTypeOption,
} from './config-table/types'
import { renderNestedConfigRows } from './config-table/helpers'

export type {
  ConfigItem,
  ConfigTableProps,
  ExpandedRowsState,
  ModelGroupConfig,
  ModelTypeOption,
} from './config-table/types'

const HtmlTooltip = ThemedTooltip
const emphasizedConfigKeys = new Set(['ADVANCED_CONTEXT_MODE_DEEK_MODEL_GROUP'])

export default function ConfigTable({
  configKey,
  configService,
  configs,
  loading = false,
  searchText = '',
  onSearchChange,
  onRefresh,
  showSearchBar = true,
  showToolbar = true,
  title,
  emptyMessage, // Will handle default in component body
  infoBox,
  showHidden = false,
  resetButtonColor = 'secondary',
  fillHeight = true,
}: ConfigTableProps) {
  const notification = useNotification()
  const theme = useTheme()
  const { t, i18n } = useTranslation('common')
  const defaultEmptyMessage = t('messages.noData')
  const actualEmptyMessage = emptyMessage || defaultEmptyMessage
  const isSmall = useMediaQuery(theme.breakpoints.down('sm'))

  // i18n 辅助函数：获取本地化的配置项标题和描述
  const getConfigTitle = useCallback(
    (config: ConfigItem) => {
      return getLocalizedText(config.i18n_title, config.title, i18n.language)
    },
    [i18n.language]
  )

  const getConfigDescription = useCallback(
    (config: ConfigItem) => {
      return config.description
        ? getLocalizedText(config.i18n_description, config.description, i18n.language)
        : undefined
    },
    [i18n.language]
  )

  const [editingValues, setEditingValues] = useState<Record<string, string>>({})
  const [dirtyKeys, setDirtyKeys] = useState<Set<string>>(new Set())
  const [visibleSecrets, setVisibleSecrets] = useState<Record<string, boolean>>({})
  const [modelGroups, setModelGroups] = useState<Record<string, ModelGroupConfig>>({})
  const [modelTypes, setModelTypes] = useState<ModelTypeOption[]>([])
  const [expandedRows, setExpandedRows] = useState<ExpandedRowsState>({})
  const [restartDialogOpen, setRestartDialogOpen] = useState(false)
  const [helpDialog, setHelpDialog] = useState<{ title: string; text: string } | null>(null)
  const [isRestarting, setIsRestarting] = useState(false)
  const [saveStatus, setSaveStatus] = useState<'idle' | 'saving' | 'saved'>('idle')

  useEffect(() => {
    const loadData = async () => {
      try {
        if (configService.getModelGroups) {
          const groups = await configService.getModelGroups()
          setModelGroups(groups)
        }
        if (configService.getModelTypes) {
          const types = await configService.getModelTypes()
          setModelTypes(types)
        }
      } catch (error) {
        console.error('Failed to load model data:', error)
      }
    }
    loadData()
  }, [configService])

  const modelTypeMap = useMemo(
    () => Object.fromEntries(modelTypes.map(mt => [mt.value, mt])),
    [modelTypes]
  )

  const handleSaveAllChanges = useCallback(
    async () => {
      if (dirtyKeys.size === 0) return
      setSaveStatus('saving')
      try {
        const changedConfigs = Object.fromEntries(
          Array.from(dirtyKeys).map(key => [key, editingValues[key]])
        )
        // 主干保存路径：后端 batch 接口负责更新并持久化配置。
        await configService.batchUpdateConfig(configKey, changedConfigs)
        setDirtyKeys(new Set())
        setSaveStatus('saved')
        onRefresh?.()

        // 检查是否有需要重启的配置项
        const needRestartConfigs = configs.filter(config => {
          if (!dirtyKeys.has(config.key)) return false
          if (config.is_need_restart === true) return true
          const fieldInfo = config.field_schema?.[config.key]
          if (fieldInfo && fieldInfo.is_need_restart === true) return true
          return false
        })

        if (needRestartConfigs.length > 0) {
          setRestartDialogOpen(true)
        }
      } catch (error) {
        setSaveStatus('idle')
        const errorMessage = error instanceof Error ? error.message : t('messages.saveFailed')
        notification.error(errorMessage)
      }
    },
    [editingValues, dirtyKeys, configService, configKey, onRefresh, configs, notification, t]
  )

  // 自动保存：修改后延迟 1s 自动保存
  useEffect(() => {
    if (dirtyKeys.size === 0) return
    const timer = setTimeout(() => {
      handleSaveAllChanges()
    }, 1000)
    return () => clearTimeout(timer)
  }, [dirtyKeys, editingValues, handleSaveAllChanges])

  // 保存状态自动恢复 idle
  useEffect(() => {
    if (saveStatus !== 'saved') return
    const timer = setTimeout(() => setSaveStatus('idle'), 2000)
    return () => clearTimeout(timer)
  }, [saveStatus])

  // 处理重启系统
  const handleRestartSystem = async () => {
    setIsRestarting(true)
    try {
      const response = await restartApi.restartSystem()
      if (response.code === 200) {
        notification.success(t('configTable.restartSent'))
        setRestartDialogOpen(false)
      } else {
        notification.error(response.msg || t('messages.operationFailed'))
      }
    } catch (error) {
      console.error('Failed to restart system:', error)
      notification.error(t('configTable.restartFailed'))
    } finally {
      setIsRestarting(false)
    }
  }

  const toggleSecretVisibility = (key: string) => {
    setVisibleSecrets(prev => ({ ...prev, [key]: !prev[key] }))
  }

  const handleConfigChange = (key: string, value: string) => {
    setEditingValues(prev => ({ ...prev, [key]: value }))
    setDirtyKeys(prev => new Set(prev).add(key))
  }

  const filteredConfigs = useMemo(() => {
    if (!configs) {
      return []
    }

    const processedConfigs = configs.filter(config => showHidden || !config.is_hidden)

    if (searchText) {
      const lowerSearchText = searchText.toLowerCase()
      return processedConfigs.filter(config => {
        const title = getConfigTitle(config)
        const description = getConfigDescription(config)
        return (
          title.toLowerCase().includes(lowerSearchText) ||
          config.key.toLowerCase().includes(lowerSearchText) ||
          (description && description.toLowerCase().includes(lowerSearchText))
        )
      })
    }

    return processedConfigs
  }, [configs, searchText, getConfigTitle, getConfigDescription, showHidden])

  useEffect(() => {
    if (configs) {
      const initialValues: Record<string, string> = {}
      configs
        .filter(c => showHidden || !c.is_hidden)
        .forEach(config => {
          const value =
            typeof config.value === 'object' && config.value !== null
              ? JSON.stringify(config.value, null, 2)
              : String(config.value)
          initialValues[config.key] = value
        })
      setEditingValues(initialValues)
      setDirtyKeys(new Set())
    }
  }, [configs, showHidden])

  const renderConfigInput = (config: ConfigItem, disabled: boolean = false) => {
    const isEditing = Object.prototype.hasOwnProperty.call(editingValues, config.key)
    const rawValue = isEditing ? editingValues[config.key] : String(config.value)
    const isSecret = config.is_secret

    if (config.ref_model_groups) {
      const typeOption = modelTypeMap[config.model_type as string]
      let entries = Object.entries(modelGroups)
      if (typeOption) {
        entries = entries.filter(([, group]) => group.MODEL_TYPE === typeOption.value)
      }
      const modelGroupNames = entries.map(([name]) => name)
      const allowEmptyModelGroup = !config.required
      const isEmptyValue = rawValue === ''
      const isInvalidValue = !(allowEmptyModelGroup && isEmptyValue) && !modelGroupNames.includes(rawValue)

      return (
        <TextField
          select
          value={rawValue}
          onChange={e => handleConfigChange(config.key, e.target.value)}
          size="small"
          fullWidth
          error={isInvalidValue}
          helperText={isInvalidValue ? t('configTable.currentModelGroupMissing') : undefined}
          placeholder={config.placeholder}
          disabled={disabled}
        >
          {allowEmptyModelGroup && (
            <MenuItem value="">
              <em>{t('configTable.emptyModelGroupFallback')}</em>
            </MenuItem>
          )}
          {modelGroupNames.map(name => (
            <MenuItem key={name} value={name}>
              {name}
            </MenuItem>
          ))}
        </TextField>
      )
    }

    if (config.enum) {
      return (
        <TextField
          select
          value={rawValue}
          onChange={e => handleConfigChange(config.key, e.target.value)}
          size="small"
          fullWidth
          placeholder={config.placeholder}
          disabled={disabled}
        >
          {config.enum.map(option => (
            <MenuItem key={option} value={option}>
              {option}
            </MenuItem>
          ))}
        </TextField>
      )
    }

    const canBeNested =
      config.type === 'list' || config.is_complex || (config.type === 'dict' && !config.is_complex)

    if (canBeNested) {
      const isExpanded = expandedRows[config.key] || false
      let displayValue: string
      try {
        const parsedValue = isEditing ? JSON.parse(rawValue) : config.value
        if (config.type === 'list') {
          displayValue = t('configTable.listCount', {
            count: (Array.isArray(parsedValue) ? parsedValue : []).length,
          })
        } else {
          displayValue = t('configTable.dictCount', {
            count: Object.keys(typeof parsedValue === 'object' && parsedValue ? parsedValue : {})
              .length,
          })
        }
      } catch {
        displayValue = t('configTable.invalidJson')
      }

      if (canBeNested) {
        return (
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, width: '100%' }}>
            <TextField
              value={displayValue}
              size="small"
              fullWidth
              InputProps={{
                readOnly: true,
                sx: {
                  cursor: 'pointer',
                  bgcolor: 'transparent',
                  '&:hover': { bgcolor: 'action.hover' },
                },
              }}
              onClick={() =>
                !disabled && setExpandedRows(prev => ({ ...prev, [config.key]: !prev[config.key] }))
              }
              variant="outlined"
              sx={{
                '& .MuiOutlinedInput-root': {
                  '&:hover .MuiOutlinedInput-notchedOutline': {
                    borderColor: 'primary.main',
                  },
                },
              }}
              disabled={disabled}
            />
            <Button
              size="small"
              onClick={() =>
                setExpandedRows(prev => ({ ...prev, [config.key]: !prev[config.key] }))
              }
              disabled={disabled}
              sx={{ textTransform: 'none', minWidth: 0, px: 1, fontSize: '0.75rem' }}
            >
              {isExpanded ? t('configTable.collapse') : t('configTable.expand')}
            </Button>
          </Box>
        )
      }
    }

    switch (config.type) {
      case 'bool':
        return (
          <FormControlLabel
            control={
              <Switch
                checked={rawValue === 'true'}
                onChange={e => handleConfigChange(config.key, String(e.target.checked))}
                color="primary"
                disabled={disabled}
              />
            }
            label={rawValue === 'true' ? t('common.yes') : t('common.no')}
            disabled={disabled}
          />
        )
      case 'int':
      case 'float':
        return (
          <TextField
            type="number"
            value={rawValue}
            onChange={e => handleConfigChange(config.key, e.target.value)}
            size="small"
            fullWidth
            placeholder={config.placeholder}
            disabled={disabled}
          />
        )
      default:
        return (
          <TextField
            value={rawValue}
            onChange={e => handleConfigChange(config.key, e.target.value)}
            size="small"
            fullWidth
            type="text"
            placeholder={config.placeholder}
            multiline={config.is_textarea}
            minRows={config.is_textarea ? 3 : 1}
            maxRows={config.is_textarea ? 8 : 1}
            disabled={disabled}
            InputProps={{
              sx:
                isSecret && !visibleSecrets[config.key]
                  ? {
                      '& .MuiInputBase-input, & textarea': {
                        WebkitTextSecurity: 'disc',
                      },
                    }
                  : undefined,
              endAdornment: isSecret ? (
                <InputAdornment position="end">
                  <Button
                    onClick={() => toggleSecretVisibility(config.key)}
                    disabled={disabled}
                    size="small"
                    sx={{ textTransform: 'none', minWidth: 0, px: 0.5, fontSize: '0.7rem' }}
                  >
                    {visibleSecrets[config.key] ? t('configTable.hide') : t('configTable.show')}
                  </Button>
                </InputAdornment>
              ) : undefined,
            }}
          />
        )
    }
  }

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%' }}>
        <CircularProgress />
      </Box>
    )
  }

  return (
    <Box sx={{ height: fillHeight ? '100%' : 'auto', minHeight: 0, display: 'flex', flexDirection: 'column', gap: 1.5 }}>
      <Stack direction="row" spacing={2} alignItems="center" sx={{ flexShrink: 0 }}>
        {title && (
          <Typography variant="h5" component="h2" sx={{ fontWeight: 600 }}>
            {title}
          </Typography>
        )}
        <Box sx={{ flex: 1 }} />
        {saveStatus === 'saving' && (
          <Stack direction="row" spacing={0.75} alignItems="center">
            <CircularProgress size={14} thickness={4} />
            <Typography variant="caption" color="text.secondary">
              {t('configTable.saving')}
            </Typography>
          </Stack>
        )}
        {saveStatus === 'saved' && (
          <Typography variant="caption" color="success.main">
            {t('configTable.saved')}
          </Typography>
        )}
      </Stack>

      <Box
        sx={{
          flex: fillHeight ? 1 : '0 0 auto',
          overflow: fillHeight ? 'auto' : 'visible',
          minHeight: 0,
          ...PANEL,
        }}
      >
      <Stack
        spacing={0}
        sx={{ minHeight: 0 }}
      >
        {filteredConfigs.map(config => {
          const canBeNested =
            config.type === 'list' || config.is_complex || (config.type === 'dict' && !config.is_complex)
          return (
            <Box key={config.key}>
              <Box
                sx={{
                  display: 'flex',
                  alignItems: 'flex-start',
                  gap: 3,
                  py: 2.5,
                  px: { xs: 1, md: 2 },
                  borderBottom: `1px solid ${theme.palette.divider}`,
                  transition: 'background-color 0.15s ease',
                  '&:hover': {
                    bgcolor: theme.palette.action.hover,
                  },
                }}
              >
                <Box sx={{ width: { xs: '45%', md: '38%' }, minWidth: 0, pt: 0.5 }}>
                  <Stack direction="row" spacing={0.5} alignItems="center" flexWrap="wrap">
                    {(config.required || emphasizedConfigKeys.has(config.key)) && (
                      <Typography component="span" color="error" sx={{ fontWeight: 'bold', fontSize: '0.75rem' }}>
                        *
                      </Typography>
                    )}
                    <Typography variant="body2" fontWeight={500} color="text.primary">
                      {getConfigTitle(config)}
                    </Typography>
                    {getConfigDescription(config) && (
                      <HtmlTooltip
                        title={<div dangerouslySetInnerHTML={{ __html: getConfigDescription(config) || '' }} />}
                        placement="right"
                      >
                        <Typography
                          component="span"
                          variant="caption"
                          sx={{
                            color: 'text.secondary',
                            cursor: 'help',
                            opacity: 0.5,
                            ml: 0.5,
                            fontSize: '0.7rem',
                          }}
                        >
                          ?
                        </Typography>
                      </HtmlTooltip>
                    )}
                    {(config.help_text || config.i18n_help_text) && (
                      <Button
                        size="small"
                        startIcon={<HelpOutlineIcon fontSize="inherit" />}
                        onClick={() =>
                          setHelpDialog({
                            title: getConfigTitle(config),
                            text: getLocalizedText(config.i18n_help_text, config.help_text || '', i18n.language),
                          })
                        }
                        sx={{
                          minWidth: 0,
                          px: 0.75,
                          py: 0.15,
                          fontSize: '0.72rem',
                          textTransform: 'none',
                        }}
                      >
                        {getLocalizedText(config.i18n_help_label, config.help_label, i18n.language) || t('common.description')}
                      </Button>
                    )}
                  </Stack>
                </Box>

                <Box sx={{ flex: 1, minWidth: 0 }}>
                  {renderConfigInput(config, false)}
                </Box>
              </Box>
              {canBeNested && expandedRows[config.key] && (
                <Box sx={{ borderTop: `1px solid ${theme.palette.divider}` }}>
                  <Table size="small" sx={{ width: '100%' }}>
                    <TableBody>
                      {renderNestedConfigRows(config, editingValues, handleConfigChange, isSmall, expandedRows, setExpandedRows, t)}
                    </TableBody>
                  </Table>
                </Box>
              )}
            </Box>
          )
        })}
        {filteredConfigs.length === 0 && (
          <Box
            sx={{
              p: 4,
              display: 'flex',
              justifyContent: 'center',
              alignItems: 'center',
            }}
          >
            <Typography variant="body1" color="text.secondary">
              {actualEmptyMessage}
            </Typography>
          </Box>
        )}
      </Stack>
      </Box>
      {/* 重启系统确认对话框 */}
      <Dialog
        open={restartDialogOpen}
        onClose={() => !isRestarting && setRestartDialogOpen(false)}
        PaperProps={{
          sx: {
            borderRadius: '12px',
            maxWidth: '500px',
          },
        }}
      >
        <DialogTitle
          sx={{
            px: 3,
            py: 2,
            background: theme.palette.action.hover,
          }}
        >
          {t('configTable.restartConfirmTitle')}
        </DialogTitle>
        <DialogContent sx={{ p: 3 }}>
          <Alert severity="warning" sx={{ mb: 2 }}>
            {t('messages.connectionLost')}
          </Alert>
          <Typography sx={{ mt: 1, mb: 2 }}>{t('configTable.restartConfirm')}</Typography>
        </DialogContent>
        <DialogActions sx={{ px: 3, py: 2 }}>
          <Button onClick={() => setRestartDialogOpen(false)} disabled={isRestarting}>
            {t('actions.cancel')}
          </Button>
          <Button
            onClick={handleRestartSystem}
            color="error"
            variant="contained"
            disabled={isRestarting}
          >
            {isRestarting ? t('configTable.restarting') : t('configTable.restartBtn')}
          </Button>
        </DialogActions>
      </Dialog>
      <Dialog
        open={Boolean(helpDialog)}
        onClose={() => setHelpDialog(null)}
        fullWidth
        maxWidth="sm"
        PaperProps={{ sx: { borderRadius: '12px' } }}
      >
        <DialogTitle sx={{ px: 3, py: 2 }}>
          {helpDialog?.title || t('common.description')}
        </DialogTitle>
        <DialogContent dividers sx={{ px: 3, py: 2 }}>
          <Typography
            component="pre"
            sx={{
              m: 0,
              whiteSpace: 'pre-wrap',
              wordBreak: 'break-word',
              fontFamily: 'inherit',
              fontSize: '0.9rem',
              lineHeight: 1.7,
            }}
          >
            {helpDialog?.text || ''}
          </Typography>
        </DialogContent>
        <DialogActions sx={{ px: 3, py: 2 }}>
          <Button onClick={() => setHelpDialog(null)}>{t('actions.close')}</Button>
        </DialogActions>
      </Dialog>
    </Box>
  )
}
