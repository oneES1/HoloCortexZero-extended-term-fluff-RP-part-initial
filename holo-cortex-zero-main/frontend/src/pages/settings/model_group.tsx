import { useState, useEffect, useMemo } from 'react'
import { useTranslation } from 'react-i18next'
import {
  Box,
  Paper,
  Typography,
  TextField,
  Autocomplete,
  Button,
  Stack,
  Alert,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  InputAdornment,
  Tooltip,
  MenuItem,
  FormControlLabel,
  Switch,
  useTheme,
  useMediaQuery,
  CircularProgress,
  IconButton,
  Collapse,
} from '@mui/material'
import { alpha } from '@mui/material/styles'
import {
  OpenInNew as OpenInNewIcon,
  ContentCopy as ContentCopyIcon,
  DeleteOutline as DeleteOutlineIcon,
  ExpandMore as ExpandMoreIcon,
  ChevronRight as ChevronRightIcon,
  Add as AddIcon,
  ChatBubbleOutline as ChatBubbleOutlineIcon,
  ScatterPlot as ScatterPlotIcon,
  ImageOutlined as ImageOutlinedIcon,
} from '@mui/icons-material'
import { PANEL, PANEL_NESTED, COLORS, SHADOWS } from '../../theme/glass'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import type { ModelGroupConfig } from '../../components/common/ConfigTable'
import { ModelGroupConnectivityResult, unifiedConfigApi } from '../../services/api/unified-config'
import { useNotification } from '../../hooks/useNotification'

// 常用的 OpenAI 兼容供应商地址（可扩展）
const OPENAI_COMPAT_PROVIDERS: Array<{ key: string; url: string }> = [
  { key: 'deepseek', url: 'https://api.deepseek.com/v1' },
  { key: 'googleGemini', url: 'https://generativelanguage.googleapis.com/v1beta/openai' },
  { key: 'tongyiQianwen', url: 'https://dashscope.aliyuncs.com/compatible-mode/v1' },
  { key: 'doubao', url: 'https://ark.cn-beijing.volces.com/api/v3' },
  { key: 'kimi', url: 'https://api.moonshot.cn/v1' },
  { key: 'zhipuQingyan', url: 'https://open.bigmodel.cn/api/paas/v4' },
  { key: 'baiduQianfan', url: 'https://qianfan.baidubce.com/v2' },
  { key: 'iflytekSpark', url: 'https://spark-api-open.xf-yun.com/v1' },
  { key: 'baichuan', url: 'https://api.baichuan-ai.com/v1' },
  { key: 'tencentHunyuan', url: 'https://api.hunyuan.cloud.tencent.com/v1' },
  { key: 'sensetimeRixin', url: 'https://api.sensenova.cn/compatible-mode/v1' },
]

const PROVIDER_WEBSITE_RULES: Array<{ host: string; url: string }> = [
  { host: 'api.deepseek.com', url: 'https://platform.deepseek.com/' },
  { host: 'generativelanguage.googleapis.com', url: 'https://ai.google.dev/gemini-api/docs/openai' },
  { host: 'dashscope.aliyuncs.com', url: 'https://bailian.console.aliyun.com/' },
  { host: 'ark.cn-beijing.volces.com', url: 'https://www.volcengine.com/product/ark' },
  { host: 'api.moonshot.cn', url: 'https://platform.moonshot.cn/' },
  { host: 'api.moonshot.ai', url: 'https://platform.moonshot.ai/' },
  { host: 'open.bigmodel.cn', url: 'https://open.bigmodel.cn/' },
  { host: 'qianfan.baidubce.com', url: 'https://qianfan.cloud.baidu.com/modelbuilder' },
  { host: 'spark-api-open.xf-yun.com', url: 'https://xinghuo.xfyun.cn/sparkapi' },
  { host: 'api.baichuan-ai.com', url: 'https://platform.baichuan-ai.com/' },
  { host: 'api.hunyuan.cloud.tencent.com', url: 'https://cloud.tencent.com/product/hunyuan' },
  { host: 'api.sensenova.cn', url: 'https://www.sensenova.cn/' },
  { host: 'api.uniapi.io', url: 'https://uniapi.ai/' },
]

const isLocalProviderHost = (host: string): boolean => {
  const hostname = host.split(':')[0].toLowerCase()
  if (['localhost', '127.0.0.1', '::1', 'host.docker.internal'].includes(hostname)) return true
  if (/^10\./.test(hostname)) return true
  if (/^192\.168\./.test(hostname)) return true
  if (/^172\.(1[6-9]|2\d|3[0-1])\./.test(hostname)) return true
  return false
}

const resolveProviderWebsiteUrl = (baseUrl: string): string | null => {
  try {
    const parsed = new URL(baseUrl.trim())
    const host = parsed.host.toLowerCase()
    const hostname = parsed.hostname.toLowerCase()
    if (isLocalProviderHost(host)) return null
    const rule = PROVIDER_WEBSITE_RULES.find(item => item.host === hostname)
    return rule?.url || null
  } catch {
    return null
  }
}

const normalizeImageMaxCount = (value: ModelGroupConfig['IMAGE_MAX_COUNT']): number | null => {
  if (value === null || value === undefined) return null
  const parsed = Number(value)
  if (!Number.isFinite(parsed)) return null
  return Math.max(Math.trunc(parsed), 0)
}

// 配置分区卡片组件
function ConfigSection({
  title,
  defaultExpanded = true,
  children,
}: {
  title: string
  defaultExpanded?: boolean
  children: React.ReactNode
}) {
  const [expanded, setExpanded] = useState(defaultExpanded)
  const theme = useTheme()
  return (
    <Box sx={{ bgcolor: PANEL_NESTED.background, borderRadius: PANEL_NESTED.borderRadius, p: 0, overflow: 'hidden' }}>
      <Box
        onClick={() => setExpanded(!expanded)}
        sx={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          px: 2.5,
          py: 1.5,
          cursor: 'pointer',
          userSelect: 'none',
          '&:hover': { bgcolor: theme.palette.action.hover },
        }}
      >
        <Typography variant="subtitle2" sx={{ fontWeight: 600, fontSize: '0.85rem', color: 'text.primary' }}>
          {title}
        </Typography>
        {expanded ? (
          <ExpandMoreIcon fontSize="small" sx={{ color: 'text.secondary', transition: 'transform 0.2s' }} />
        ) : (
          <ChevronRightIcon fontSize="small" sx={{ color: 'text.secondary', transition: 'transform 0.2s' }} />
        )}
      </Box>
      <Collapse in={expanded} timeout="auto" unmountOnExit>
        <Box sx={{ px: 2.5, pb: 2.5, display: 'flex', flexDirection: 'column', gap: 2 }}>
          {children}
        </Box>
      </Collapse>
    </Box>
  )
}

// 类型专属 vibrant 颜色
const typeColorMap: Record<string, { main: string; glow: string; bg: string }> = {
  chat: { main: '#5c9dff', glow: 'rgba(92,157,255,0.20)', bg: 'rgba(92,157,255,0.10)' },
  embedding: { main: '#32d74b', glow: 'rgba(50,215,75,0.20)', bg: 'rgba(50,215,75,0.10)' },
  draw: { main: '#ff9f0a', glow: 'rgba(255,159,10,0.20)', bg: 'rgba(255,159,10,0.10)' },
}

interface EditDialogProps {
  open: boolean
  onClose: () => void
  groupName: string
  initialConfig?: ModelGroupConfig
  onSubmit: (groupName: string, config: ModelGroupConfig) => Promise<void>
  onGroupNameChange: (name: string) => void
  isCopy?: boolean
  existingGroups: Record<string, ModelGroupConfig>
  onCopy?: () => void
  onDelete?: () => void
}

function EditDialog({
  open,
  onClose,
  groupName,
  initialConfig,
  onSubmit,
  onGroupNameChange,
  isCopy,
  existingGroups,
  onCopy,
  onDelete,
}: EditDialogProps) {
  const [config, setConfig] = useState<ModelGroupConfig>({
    CHAT_MODEL: '',
    USE_GLOBAL_PROXY: false,
    CHAT_PROXY: '',
    BASE_URL: '',
    API_KEY: '',
    MODEL_TYPE: 'chat',
    WIRE_API: 'default',
    CACHE_TRANSPORT_PROFILE: 'default',
    TEMPERATURE: null,
    TOP_P: null,
    TOP_K: null,
    MAX_OUTPUT_TOKENS: null,
    IMAGE_MAX_COUNT: null,
    REASONING_MODE: 'default',
    TEXT_VERBOSITY: 'default',
    REPLAY_REASONING_CONTENT: false,
    EXTRA_BODY: null,
  })
  const [error, setError] = useState('')
  const [groupNameError, setGroupNameError] = useState('')
  const [showApiKey, setShowApiKey] = useState(false)
  const theme = useTheme()
  const isSmall = useMediaQuery(theme.breakpoints.down('sm'))
  const notification = useNotification()
  const { t } = useTranslation('settings')

  const [modelOptions, setModelOptions] = useState<string[]>([])
  const [fetchingModels, setFetchingModels] = useState(false)
  const [testingConnection, setTestingConnection] = useState(false)
  const [connectionResult, setConnectionResult] = useState<{
    severity: 'success' | 'warning' | 'error'
    message: string
  } | null>(null)

  const inputSize: 'small' | 'medium' = isSmall ? 'small' : 'medium'
  const inputHeight = isSmall ? 40 : 56

  const canFetchModels = Boolean(config.BASE_URL && config.API_KEY && !fetchingModels)
  const fetchTooltipTitle = canFetchModels ? '' : t('modelGroup.helpers.fetchPrecondition')
  const canTestConnection = Boolean(config.BASE_URL && config.CHAT_MODEL && !testingConnection)
  const testTooltipTitle = canTestConnection ? '' : t('modelGroup.helpers.connectionPrecondition')
  const providerWebsiteUrl = resolveProviderWebsiteUrl(config.BASE_URL)
  const providerWebsiteTooltip = providerWebsiteUrl
    ? t('modelGroup.tooltips.visitProvider')
    : t('modelGroup.tooltips.providerWebsiteUnavailable')

  const providerOptions = OPENAI_COMPAT_PROVIDERS.map(p => p.url)
  const providerMetaByUrl = new Map(
    OPENAI_COMPAT_PROVIDERS.map(p => [p.url, t(`modelGroup.providers.${p.key}`) || p.key])
  )

  interface OpenAIModelListResponse {
    data?: Array<string | { id?: string }>
    models?: Array<string | { id?: string }>
  }

  const buildModelsUrl = (base: string): string => {
    const trimmed = base.trim().replace(/\/$/, '')
    return `${trimmed}/models`
  }

  const parseModelIds = (payload: OpenAIModelListResponse): string[] => {
    const pick = (arr: Array<string | { id?: string }> | undefined) =>
      (arr || [])
        .map(m => (typeof m === 'string' ? m : typeof m.id === 'string' ? m.id : undefined))
        .filter((x): x is string => typeof x === 'string')
    const fromData = pick(payload.data)
    const fromModels = pick(payload.models)
    return Array.from(new Set([...fromData, ...fromModels])).sort()
  }

  const fetchAvailableModels = async () => {
    if (!config.BASE_URL || !config.API_KEY) return
    const url = buildModelsUrl(config.BASE_URL)
    setFetchingModels(true)
    try {
      const resp = await fetch(url, {
        method: 'GET',
        headers: {
          Authorization: `Bearer ${config.API_KEY}`,
          'Content-Type': 'application/json',
        },
      })
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
      const data: OpenAIModelListResponse = await resp.json()
      const models = parseModelIds(data)
      setModelOptions(models)
      if (models.length > 0) {
        notification.success(t('modelGroup.validation.fetchSuccess', { count: models.length }))
      } else {
        notification.info(t('modelGroup.validation.fetchEmpty'))
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : t('common.unknownError', { ns: 'common' })
      notification.error(t('modelGroup.validation.fetchError', { error: message }))
    } finally {
      setFetchingModels(false)
    }
  }

  const testConnection = async () => {
    if (!config.BASE_URL || !config.CHAT_MODEL) return
    setTestingConnection(true)
    setConnectionResult(null)
    try {
      const result = await unifiedConfigApi.testModelGroupConnectivity(
        {
          ...config,
          CHAT_MODEL: (config.CHAT_MODEL || '').trim(),
          BASE_URL: (config.BASE_URL || '').trim(),
          API_KEY: (config.API_KEY || '').trim(),
        },
        groupName
      )
      const message = result.ok
        ? t('modelGroup.validation.connectionSuccess', { protocol: result.protocol, latency: result.latency_ms })
        : result.suspected
        ? t('modelGroup.validation.connectionSuspected', {
            protocol: result.protocol,
            error: result.error || t('common.unknownError', { ns: 'common' }),
          })
        : t('modelGroup.validation.connectionError', {
            protocol: result.protocol,
            error: result.error || t('common.unknownError', { ns: 'common' }),
          })
      setConnectionResult({
        severity: result.ok ? 'success' : result.suspected ? 'warning' : 'error',
        message,
      })
      if (result.ok) notification.success(message)
      else if (result.suspected) notification.warning(message, { duration: 8000 })
      else notification.error(message)
    } catch (err) {
      const message = t('modelGroup.validation.connectionError', {
        protocol: '-',
        error: err instanceof Error ? err.message : t('common.unknownError', { ns: 'common' }),
      })
      setConnectionResult({ severity: 'error', message })
      notification.error(message)
    } finally {
      setTestingConnection(false)
    }
  }

  useEffect(() => {
    if (initialConfig) {
      setConfig({
        ...initialConfig,
        MODEL_TYPE: initialConfig.MODEL_TYPE || 'chat',
        WIRE_API: initialConfig.WIRE_API || 'default',
        CACHE_TRANSPORT_PROFILE: initialConfig.CACHE_TRANSPORT_PROFILE || 'default',
        REASONING_MODE: initialConfig.REASONING_MODE || 'default',
        TEXT_VERBOSITY: initialConfig.TEXT_VERBOSITY || 'default',
        REPLAY_REASONING_CONTENT: Boolean(initialConfig.REPLAY_REASONING_CONTENT),
        IMAGE_MAX_COUNT: normalizeImageMaxCount(initialConfig.IMAGE_MAX_COUNT),
      })
    } else {
      setConfig({
        CHAT_MODEL: '',
        USE_GLOBAL_PROXY: false,
        CHAT_PROXY: '',
        BASE_URL: '',
        API_KEY: '',
        MODEL_TYPE: 'chat',
        WIRE_API: 'default',
        CACHE_TRANSPORT_PROFILE: 'default',
        TEMPERATURE: null,
        TOP_P: null,
        TOP_K: null,
        MAX_OUTPUT_TOKENS: null,
        IMAGE_MAX_COUNT: null,
        REASONING_MODE: 'default',
        TEXT_VERBOSITY: 'default',
        REPLAY_REASONING_CONTENT: false,
        EXTRA_BODY: null,
      })
    }
  }, [initialConfig, open, isCopy])

  const validateGroupName = (name: string): boolean => {
    const invalidChars = /[/\\?&#=%]/
    return name.trim().length > 0 && !invalidChars.test(name)
  }

  const handleGroupNameChange = (name: string) => {
    if (!name) {
      setGroupNameError('')
      onGroupNameChange(name)
      return
    }
    if (!validateGroupName(name)) {
      setGroupNameError(t('modelGroup.validation.nameInvalid'))
    } else if (existingGroups[name] && (isCopy || !initialConfig)) {
      setGroupNameError(t('modelGroup.validation.nameExists', { name }))
    } else {
      setGroupNameError('')
    }
    onGroupNameChange(name)
  }

  const handleSubmit = async () => {
    const trimmedGroupName = groupName.trim()
    const sanitizedConfig: ModelGroupConfig = {
      ...config,
      CHAT_MODEL: (config.CHAT_MODEL || '').trim(),
      USE_GLOBAL_PROXY: Boolean(config.USE_GLOBAL_PROXY),
      CHAT_PROXY: (config.CHAT_PROXY || '').trim(),
      BASE_URL: (config.BASE_URL || '').trim(),
      API_KEY: (config.API_KEY || '').trim(),
      MODEL_TYPE: (config.MODEL_TYPE || 'chat').trim(),
      WIRE_API: config.WIRE_API || 'default',
      IMAGE_MAX_COUNT: normalizeImageMaxCount(config.IMAGE_MAX_COUNT),
      REASONING_MODE: config.REASONING_MODE || 'default',
      TEXT_VERBOSITY: config.TEXT_VERBOSITY || 'default',
      REPLAY_REASONING_CONTENT: Boolean(config.REPLAY_REASONING_CONTENT),
      EXTRA_BODY: config.EXTRA_BODY ? config.EXTRA_BODY.trim() || null : null,
    }
    if (trimmedGroupName && !validateGroupName(trimmedGroupName)) {
      setGroupNameError(t('modelGroup.validation.nameInvalid'))
      return
    }
    if (!trimmedGroupName) {
      setGroupNameError(t('modelGroup.validation.nameRequired'))
      return
    }
    if (existingGroups[trimmedGroupName] && (isCopy || !initialConfig)) {
      setGroupNameError(t('modelGroup.validation.nameExists', { name: groupName }))
      return
    }
    try {
      await onSubmit(trimmedGroupName, sanitizedConfig)
      onClose()
    } catch (error) {
      if (error instanceof Error) setError(error.message)
      else setError(t('modelGroup.actions.saveFailed'))
    }
  }

  const typeColors = typeColorMap[config.MODEL_TYPE || 'chat'] || typeColorMap.chat

  return (
    <Dialog
      open={open}
      onClose={onClose}
      maxWidth="md"
      fullWidth
      scroll="body"
      PaperProps={{
        sx: {
          bgcolor: PANEL.background,
          backgroundColor: PANEL.background,
          borderRadius: PANEL.borderRadius,
          border: PANEL.border,
          boxShadow: SHADOWS.dialog,
          backgroundImage: 'none',
          overflow: 'hidden',
          outline: 'none',
        },
      }}
    >
      {/* 头部：标题 + 操作按钮 */}
      <DialogTitle
        sx={{
          px: 3,
          pt: 2.5,
          pb: 1.5,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: 2,
          m: 0,
        }}
      >
        <Typography sx={{ fontSize: '1.1rem', fontWeight: 600 }}>
          {isCopy
            ? t('modelGroup.dialog.copyTitle')
            : initialConfig && !isCopy
            ? t('modelGroup.dialog.editTitle')
            : t('modelGroup.dialog.createTitle')}
        </Typography>
        <Stack direction="row" spacing={0.5} alignItems="center">
          {initialConfig && (
            <Tooltip title={providerWebsiteTooltip}>
              <span>
                <IconButton
                  size="small"
                  onClick={() => providerWebsiteUrl && window.open(providerWebsiteUrl, '_blank')}
                  disabled={!providerWebsiteUrl}
                  sx={{
                    color: 'text.secondary',
                    '&:hover': { color: COLORS.accent, bgcolor: 'rgba(92,157,255,0.08)' },
                  }}
                >
                  <OpenInNewIcon fontSize="small" />
                </IconButton>
              </span>
            </Tooltip>
          )}
          {initialConfig && onCopy && (
            <Tooltip title={t('modelGroup.tooltips.copy')}>
              <IconButton
                size="small"
                onClick={onCopy}
                sx={{
                  color: 'text.secondary',
                  '&:hover': { color: COLORS.accent, bgcolor: 'rgba(92,157,255,0.08)' },
                }}
              >
                <ContentCopyIcon fontSize="small" />
              </IconButton>
            </Tooltip>
          )}
          {initialConfig && onDelete && (
            <Tooltip title={t('modelGroup.tooltips.delete')}>
              <IconButton
                size="small"
                onClick={onDelete}
                sx={{
                  color: 'text.secondary',
                  '&:hover': { color: COLORS.error, bgcolor: 'rgba(255,69,58,0.08)' },
                }}
              >
                <DeleteOutlineIcon fontSize="small" />
              </IconButton>
            </Tooltip>
          )}
        </Stack>
      </DialogTitle>

      <DialogContent sx={{ px: 3, pb: 1, bgcolor: 'transparent' }}>
        <Stack spacing={3} sx={{ mt: 0.5 }}>
          {/* Block 1 — Connection Config */}
          <ConfigSection title={t('modelGroup.form.connectionConfig')} defaultExpanded>
            <Stack spacing={1.5}>
              <TextField
                label={t('modelGroup.form.groupName')}
                value={groupName}
                onChange={e => handleGroupNameChange(e.target.value)}
                disabled={!!initialConfig && !isCopy}
                fullWidth
                autoComplete="off"
                required
                error={!!groupNameError}
                helperText={
                  groupNameError ||
                  (groupName ? '' : isCopy ? t('modelGroup.helpers.nameCopy') : t('modelGroup.helpers.nameChar'))
                }
                inputProps={{ autoComplete: 'new-password', form: { autoComplete: 'off' } }}
                size={inputSize}
              />
              <Autocomplete
                freeSolo
                options={providerOptions}
                value={config.BASE_URL}
                onChange={(_, newValue) => {
                  if (typeof newValue === 'string') setConfig({ ...config, BASE_URL: newValue })
                }}
                onInputChange={(_, newInputValue) => {
                  setConfig({ ...config, BASE_URL: newInputValue })
                }}
                renderOption={(props, option) => (
                  <li {...props} key={option}>
                    <Box sx={{ display: 'flex', flexDirection: 'column' }}>
                      <Typography variant="body2">{providerMetaByUrl.get(option) || t('common.custom', { ns: 'common' })}</Typography>
                      <Typography variant="caption" color="text.secondary">{option}</Typography>
                    </Box>
                  </li>
                )}
                renderInput={params => (
                  <TextField
                    {...params}
                    label={t('modelGroup.form.apiAddress')}
                    placeholder={t('modelGroup.placeholders.apiAddress')}
                    autoComplete="off"
                    size={inputSize}
                    inputProps={{
                      ...params.inputProps,
                      autoComplete: 'new-password',
                      form: { autoComplete: 'off' },
                    }}
                    helperText={t('modelGroup.helpers.apiAddress')}
                  />
                )}
              />
              <TextField
                label={t('modelGroup.form.apiKey')}
                value={config.API_KEY}
                onChange={e => setConfig({ ...config, API_KEY: e.target.value })}
                type="text"
                fullWidth
                autoComplete="off"
                size={inputSize}
                name={`apikey_${Math.random().toString(36).slice(2)}`}
                inputProps={{
                  autoComplete: 'new-password',
                  form: { autoComplete: 'off' },
                  style: !showApiKey
                    ? ({ '-webkit-text-security': 'disc', 'text-security': 'disc' } as React.CSSProperties)
                    : undefined,
                }}
                InputProps={{
                  endAdornment: (
                    <InputAdornment position="end">
                      <Button
                        onClick={() => setShowApiKey(!showApiKey)}
                        size="small"
                        sx={{ textTransform: 'none', minWidth: 0, px: 0.75, fontSize: '0.75rem', color: 'text.secondary' }}
                      >
                        {showApiKey ? t('configTable.hide', { ns: 'common' }) : t('configTable.show', { ns: 'common' })}
                      </Button>
                    </InputAdornment>
                  ),
                }}
              />
              <Box sx={{ display: 'flex', gap: 1 }}>
                <Box sx={{ flex: 1 }}>
                  <Autocomplete
                    freeSolo
                    options={modelOptions}
                    value={config.CHAT_MODEL}
                    onChange={(_, newValue) => {
                      if (typeof newValue === 'string') setConfig({ ...config, CHAT_MODEL: newValue })
                    }}
                    onInputChange={(_, newInputValue) => {
                      setConfig({ ...config, CHAT_MODEL: newInputValue })
                    }}
                    renderInput={params => (
                      <TextField
                        {...params}
                        label={t('modelGroup.form.modelName')}
                        autoComplete="off"
                        helperText={t('modelGroup.helpers.modelName')}
                        inputProps={{
                          ...params.inputProps,
                          autoComplete: 'new-password',
                          form: { autoComplete: 'off' },
                        }}
                        size={inputSize}
                      />
                    )}
                  />
                </Box>
              </Box>
              <Stack direction="row" spacing={1}>
                <Tooltip title={fetchTooltipTitle}>
                  <span style={{ flex: 1 }}>
                    <Button
                      variant="outlined"
                      onClick={fetchAvailableModels}
                      disabled={!canFetchModels}
                      size={inputSize}
                      fullWidth
                      sx={{ height: inputHeight, borderColor: 'divider', color: 'text.secondary' }}
                    >
                      {fetchingModels ? (
                        <>
                          <CircularProgress size={16} sx={{ mr: 1 }} /> {t('modelGroup.actions.fetching')}
                        </>
                      ) : (
                        t('modelGroup.actions.fetchModels')
                      )}
                    </Button>
                  </span>
                </Tooltip>
                <Tooltip title={testTooltipTitle}>
                  <span style={{ flex: 1 }}>
                    <Button
                      variant="outlined"
                      onClick={testConnection}
                      disabled={!canTestConnection}
                      size={inputSize}
                      fullWidth
                      sx={{ height: inputHeight, borderColor: 'divider', color: 'text.secondary' }}
                    >
                      {testingConnection ? (
                        <>
                          <CircularProgress size={16} sx={{ mr: 1 }} /> {t('modelGroup.actions.testingConnection')}
                        </>
                      ) : (
                        t('modelGroup.actions.testConnection')
                      )}
                    </Button>
                  </span>
                </Tooltip>
              </Stack>
              {connectionResult && (
                <Alert severity={connectionResult.severity} sx={{ borderRadius: '10px' }}>
                  {connectionResult.message}
                </Alert>
              )}
              <Stack direction="row" spacing={2}>
                <Box sx={{ flex: 1 }}>
                  <TextField
                    label={t('modelGroup.form.wireApi')}
                    select
                    value={config.WIRE_API || 'default'}
                    onChange={e => setConfig({ ...config, WIRE_API: e.target.value as ModelGroupConfig['WIRE_API'] })}
                    fullWidth
                    size={inputSize}
                    helperText={t('modelGroup.helpers.wireApi')}
                  >
                    <MenuItem value="default">{t('modelGroup.options.default')}</MenuItem>
                    <MenuItem value="chat">{t('modelGroup.options.chat')}</MenuItem>
                    <MenuItem value="responses">{t('modelGroup.options.responses')}</MenuItem>
                    <MenuItem value="gemini">{t('modelGroup.options.gemini')}</MenuItem>
                  </TextField>
                </Box>
                <Box sx={{ flex: 1 }}>
                  <TextField
                    label={t('modelGroup.form.cacheTransportProfile')}
                    select
                    value={config.CACHE_TRANSPORT_PROFILE || 'default'}
                    onChange={e =>
                      setConfig({ ...config, CACHE_TRANSPORT_PROFILE: e.target.value as ModelGroupConfig['CACHE_TRANSPORT_PROFILE'] })
                    }
                    fullWidth
                    size={inputSize}
                    helperText={t('modelGroup.helpers.cacheTransportProfile')}
                  >
                    <MenuItem value="default">{t('modelGroup.options.cacheDefault')}</MenuItem>
                    <MenuItem value="cache_control">{t('modelGroup.options.cacheControl')}</MenuItem>
                    <MenuItem value="prompt_cache_key">{t('modelGroup.options.promptCacheKey')}</MenuItem>
                    <MenuItem value="cache_prompt">{t('modelGroup.options.cachePrompt')}</MenuItem>
                    <MenuItem value="off">{t('modelGroup.options.cacheOff')}</MenuItem>
                  </TextField>
                </Box>
              </Stack>
              <Box>
                <FormControlLabel
                  control={
                    <Switch
                      checked={Boolean(config.USE_GLOBAL_PROXY)}
                      onChange={(_, checked) => setConfig({ ...config, USE_GLOBAL_PROXY: checked })}
                    />
                  }
                  label={t('modelGroup.form.useGlobalProxy')}
                  sx={{ ml: 0.25 }}
                />
                <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: -0.5, ml: 0.25 }}>
                  {t('modelGroup.helpers.useGlobalProxy')}
                </Typography>
              </Box>
              {!config.USE_GLOBAL_PROXY && (
                <TextField
                  label={t('modelGroup.form.proxyAddress')}
                  value={config.CHAT_PROXY || ''}
                  onChange={e => setConfig({ ...config, CHAT_PROXY: e.target.value })}
                  fullWidth
                  size={inputSize}
                  placeholder="http://..."
                />
              )}
            </Stack>
          </ConfigSection>

          {/* Block 2 — Model Type & Behavior */}
          <ConfigSection title={t('modelGroup.form.modelType')} defaultExpanded>
            <Stack spacing={2}>
              {/* Type Selector Cards */}
              <Stack direction="row" spacing={1.5}>
                {([
                  { value: 'chat', icon: <ChatBubbleOutlineIcon sx={{ fontSize: 28, color: config.MODEL_TYPE === 'chat' ? typeColorMap.chat.main : 'text.secondary' }} />, label: t('modelGroup.types.chat'), subLabel: t('modelGroup.typeDescriptions.chat'), color: typeColorMap.chat.main },
                  { value: 'embedding', icon: <ScatterPlotIcon sx={{ fontSize: 28, color: config.MODEL_TYPE === 'embedding' ? typeColorMap.embedding.main : 'text.secondary' }} />, label: t('modelGroup.types.embedding'), subLabel: t('modelGroup.typeDescriptions.embedding'), color: typeColorMap.embedding.main },
                  { value: 'draw', icon: <ImageOutlinedIcon sx={{ fontSize: 28, color: config.MODEL_TYPE === 'draw' ? typeColorMap.draw.main : 'text.secondary' }} />, label: t('modelGroup.types.draw'), subLabel: t('modelGroup.typeDescriptions.draw'), color: typeColorMap.draw.main },
                ] as const).map(type => {
                  const selected = config.MODEL_TYPE === type.value
                  return (
                    <Box
                      key={type.value}
                      onClick={() => setConfig({ ...config, MODEL_TYPE: type.value })}
                      sx={{
                        flex: 1,
                        p: 2,
                        borderRadius: '12px',
                        cursor: 'pointer',
                        textAlign: 'center',
                        transition: 'all 0.2s ease',
                        bgcolor: selected ? alpha(type.color, 0.12) : PANEL_NESTED.background,
                        border: `1.5px solid ${selected ? type.color : 'transparent'}`,
                        boxShadow: selected ? `0 0 0 3px ${alpha(type.color, 0.15)}` : 'none',
                        '&:hover': {
                          bgcolor: selected ? alpha(type.color, 0.15) : theme.palette.action.hover,
                        },
                      }}
                    >
                      <Box sx={{ mb: 1, display: 'flex', justifyContent: 'center' }}>{type.icon}</Box>
                      <Typography variant="body2" fontWeight={600} color={selected ? type.color : 'text.primary'}>
                        {type.label}
                      </Typography>
                      <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 0.25 }}>
                        {type.subLabel}
                      </Typography>
                    </Box>
                  )
                })}
              </Stack>

              {/* Behavior Pair */}
              <Stack direction="row" spacing={2}>
                <Box sx={{ flex: 1 }}>
                  <TextField
                    label={t('modelGroup.form.imageMaxCount')}
                    type="number"
                    value={config.IMAGE_MAX_COUNT ?? ''}
                    onChange={e =>
                      setConfig({ ...config, IMAGE_MAX_COUNT: e.target.value === '' ? null : Math.max(parseInt(e.target.value, 10) || 0, 0) })
                    }
                    fullWidth
                    size={inputSize}
                    inputProps={{ step: 1, min: 0 }}
                    helperText={t('modelGroup.helpers.imageMaxCount')}
                  />
                </Box>
                <Box sx={{ flex: 1, display: 'flex', alignItems: 'center' }}>
                  <Box sx={{ width: '100%' }}>
                    <FormControlLabel
                      control={
                        <Switch
                          checked={Boolean(config.REPLAY_REASONING_CONTENT)}
                          onChange={(_, checked) => setConfig({ ...config, REPLAY_REASONING_CONTENT: checked })}
                        />
                      }
                      label={t('modelGroup.form.replayReasoningContent')}
                      sx={{ ml: 0.25 }}
                    />
                    <Typography variant="caption" color="text.secondary" sx={{ display: 'block', ml: 0.25 }}>
                      {t('modelGroup.helpers.replayReasoningContent')}
                    </Typography>
                  </Box>
                </Box>
              </Stack>
            </Stack>
          </ConfigSection>

          {/* Block 3 — Advanced Parameters */}
          <ConfigSection title={t('modelGroup.helpers.advanced')} defaultExpanded={false}>
            <Box
              sx={{
                display: 'grid',
                gridTemplateColumns: 'repeat(3, 1fr)',
                gap: 2,
                '@media (max-width: 900px)': { gridTemplateColumns: 'repeat(2, 1fr)' },
                '@media (max-width: 600px)': { gridTemplateColumns: '1fr' },
              }}
            >
              <TextField
                label={t('modelGroup.form.temperature')}
                type="number"
                value={config.TEMPERATURE ?? ''}
                onChange={e => setConfig({ ...config, TEMPERATURE: e.target.value ? parseFloat(e.target.value) : null })}
                fullWidth
                size={inputSize}
                inputProps={{ step: 0.1, min: 0, max: 2 }}
                helperText={t('modelGroup.helpers.temperature')}
              />
              <TextField
                label={t('modelGroup.form.topP')}
                type="number"
                value={config.TOP_P ?? ''}
                onChange={e => setConfig({ ...config, TOP_P: e.target.value ? parseFloat(e.target.value) : null })}
                fullWidth
                size={inputSize}
                inputProps={{ step: 0.1, min: 0, max: 1 }}
                helperText={t('modelGroup.helpers.topP')}
              />
              <TextField
                label={t('modelGroup.form.topK')}
                type="number"
                value={config.TOP_K ?? ''}
                onChange={e => setConfig({ ...config, TOP_K: e.target.value ? parseInt(e.target.value, 10) : null })}
                fullWidth
                size={inputSize}
                inputProps={{ step: 1, min: 0 }}
                helperText={t('modelGroup.helpers.topK')}
              />
              <TextField
                label={t('modelGroup.form.maxOutputTokens')}
                type="number"
                value={config.MAX_OUTPUT_TOKENS ?? ''}
                onChange={e => setConfig({ ...config, MAX_OUTPUT_TOKENS: e.target.value ? parseInt(e.target.value, 10) : null })}
                fullWidth
                size={inputSize}
                inputProps={{ step: 1, min: 1 }}
                helperText={t('modelGroup.helpers.maxOutputTokens')}
              />
              <TextField
                label={t('modelGroup.form.presencePenalty')}
                type="number"
                value={config.PRESENCE_PENALTY ?? ''}
                onChange={e =>
                  setConfig({ ...config, PRESENCE_PENALTY: e.target.value ? parseFloat(e.target.value) : null })
                }
                fullWidth
                size={inputSize}
                inputProps={{ step: 0.1, min: -2, max: 2 }}
                helperText={t('modelGroup.helpers.presencePenalty')}
              />
              <TextField
                label={t('modelGroup.form.frequencyPenalty')}
                type="number"
                value={config.FREQUENCY_PENALTY ?? ''}
                onChange={e =>
                  setConfig({ ...config, FREQUENCY_PENALTY: e.target.value ? parseFloat(e.target.value) : null })
                }
                fullWidth
                size={inputSize}
                inputProps={{ step: 0.1, min: -2, max: 2 }}
                helperText={t('modelGroup.helpers.frequencyPenalty')}
              />
              <TextField
                label={t('modelGroup.form.reasoningMode')}
                select
                value={config.REASONING_MODE || 'default'}
                onChange={e => setConfig({ ...config, REASONING_MODE: e.target.value as ModelGroupConfig['REASONING_MODE'] })}
                fullWidth
                size={inputSize}
                helperText={t('modelGroup.helpers.reasoningMode')}
              >
                <MenuItem value="default">{t('modelGroup.options.default')}</MenuItem>
                <MenuItem value="off">{t('modelGroup.options.off')}</MenuItem>
                <MenuItem value="minimal">{t('modelGroup.options.minimal')}</MenuItem>
                <MenuItem value="low">{t('modelGroup.options.low')}</MenuItem>
                <MenuItem value="medium">{t('modelGroup.options.medium')}</MenuItem>
                <MenuItem value="high">{t('modelGroup.options.high')}</MenuItem>
              </TextField>
              <TextField
                label={t('modelGroup.form.textVerbosity')}
                select
                value={config.TEXT_VERBOSITY || 'default'}
                onChange={e => setConfig({ ...config, TEXT_VERBOSITY: e.target.value as ModelGroupConfig['TEXT_VERBOSITY'] })}
                fullWidth
                size={inputSize}
                helperText={t('modelGroup.helpers.textVerbosity')}
              >
                <MenuItem value="default">{t('modelGroup.options.default')}</MenuItem>
                <MenuItem value="low">{t('modelGroup.options.low')}</MenuItem>
                <MenuItem value="medium">{t('modelGroup.options.medium')}</MenuItem>
                <MenuItem value="high">{t('modelGroup.options.high')}</MenuItem>
              </TextField>
              <TextField
                label={t('modelGroup.form.extraBody')}
                value={config.EXTRA_BODY ?? ''}
                onChange={e => setConfig({ ...config, EXTRA_BODY: e.target.value || null })}
                fullWidth
                size={inputSize}
                helperText={t('modelGroup.helpers.extraBody')}
                placeholder='{"key": "value"}'
                sx={{ gridColumn: '1 / -1' }}
              />
            </Box>
          </ConfigSection>

          {error && <Alert severity="error" sx={{ borderRadius: '10px' }}>{error}</Alert>}
        </Stack>
      </DialogContent>
      <DialogActions sx={{ px: 3, pb: 2.5, pt: 1 }}>
        <Button
          onClick={onClose}
          sx={{ minWidth: { xs: 64, sm: 80 }, minHeight: { xs: 36, sm: 40 }, color: 'text.secondary' }}
        >
          {t('actions.cancel', { ns: 'common' })}
        </Button>
        <Button
          onClick={handleSubmit}
          variant="contained"
          disabled={!!groupNameError || !groupName}
          sx={{
            minWidth: { xs: 64, sm: 80 },
            minHeight: { xs: 36, sm: 40 },
            bgcolor: typeColors.bg,
            color: typeColors.main,
            boxShadow: 'none',
            '&:hover': { bgcolor: typeColors.glow, boxShadow: 'none' },
            '&.Mui-disabled': { bgcolor: theme.palette.action.disabledBackground, color: 'text.disabled' },
          }}
        >
          {isCopy ? t('modelGroup.actions.createCopy') : t('actions.save', { ns: 'common' })}
        </Button>
      </DialogActions>
    </Dialog>
  )
}

export default function ModelGroupsPage() {
  const queryClient = useQueryClient()
  const notification = useNotification()
  const [editDialogOpen, setEditDialogOpen] = useState(false)
  const [editingGroup, setEditingGroup] = useState<{
    name: string
    config?: ModelGroupConfig
    isCopy?: boolean
  }>({ name: '' })
  const [dialogKey, setDialogKey] = useState(0)
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false)
  const [deletingGroupName, setDeletingGroupName] = useState('')
  const theme = useTheme()
  const isSmall = useMediaQuery(theme.breakpoints.down('sm'))
  const { t } = useTranslation('settings')

  const { data: modelGroups = {}, isLoading: modelGroupsLoading } = useQuery({
    queryKey: ['model-groups'],
    queryFn: () => unifiedConfigApi.getModelGroups(),
  })

  const modelGroupEntries = useMemo(() => Object.entries(modelGroups), [modelGroups])

  const { data: modelTypes = [] } = useQuery({
    queryKey: ['model-types'],
    queryFn: () => unifiedConfigApi.getModelTypes(),
  })

  const getModelTypeLabel = (type: string | undefined) => {
    if (!type) return t('modelGroup.types.chat', { ns: 'settings', defaultValue: 'Chat' })
    return t(`modelGroup.types.${type as 'chat' | 'embedding' | 'draw'}`, {
      ns: 'settings',
      defaultValue: modelTypes.find(mt => mt.value === type)?.label || type,
    })
  }

  const getTypeColors = (type: string | undefined) => {
    return typeColorMap[type || 'chat'] || typeColorMap.chat
  }

  const handleAdd = () => {
    setEditingGroup({ name: '' })
    setDialogKey(prev => prev + 1)
    setEditDialogOpen(true)
  }

  const handleEdit = (name: string) => {
    setEditingGroup({ name: '', config: undefined, isCopy: false })
    setDialogKey(prev => prev + 1)
    Promise.resolve().then(() => {
      setEditingGroup({ name, config: modelGroups[name] })
      setEditDialogOpen(true)
    })
  }

  const handleCopy = (name: string) => {
    setEditingGroup({ name: '', config: undefined, isCopy: false })
    setDialogKey(prev => prev + 1)
    Promise.resolve().then(() => {
      setEditingGroup({ name: name, config: { ...modelGroups[name] }, isCopy: true })
      setEditDialogOpen(true)
    })
  }

  const handleDelete = async (name: string) => {
    try {
      await unifiedConfigApi.deleteModelGroup(name)
      notification.success(t('modelGroup.notifications.deleteSuccess', { name }))
      queryClient.invalidateQueries({ queryKey: ['model-groups'] })
      setDeleteDialogOpen(false)
    } catch (error) {
      if (error instanceof Error) notification.error(error.message)
      else notification.error(t('modelGroup.notifications.deleteFailed'))
    }
  }

  const confirmDelete = (name: string) => {
    setDeletingGroupName(name)
    setDeleteDialogOpen(true)
  }

  const handleSubmit = async (groupName: string, config: ModelGroupConfig) => {
    const trimmedName = groupName.trim()
    const sanitizedConfig: ModelGroupConfig = {
      ...config,
      CHAT_MODEL: (config.CHAT_MODEL || '').trim(),
      USE_GLOBAL_PROXY: Boolean(config.USE_GLOBAL_PROXY),
      CHAT_PROXY: (config.CHAT_PROXY || '').trim(),
      BASE_URL: (config.BASE_URL || '').trim(),
      API_KEY: (config.API_KEY || '').trim(),
      MODEL_TYPE: (config.MODEL_TYPE || 'chat').trim(),
      WIRE_API: config.WIRE_API || 'default',
      CACHE_TRANSPORT_PROFILE: config.CACHE_TRANSPORT_PROFILE || 'default',
      IMAGE_MAX_COUNT: normalizeImageMaxCount(config.IMAGE_MAX_COUNT),
      REPLAY_REASONING_CONTENT: Boolean(config.REPLAY_REASONING_CONTENT),
      EXTRA_BODY: config.EXTRA_BODY ? config.EXTRA_BODY.trim() || null : null,
    }
    if (modelGroups[trimmedName] && !editingGroup.isCopy && editingGroup.name === trimmedName) {
      const result = await unifiedConfigApi.updateModelGroup(trimmedName, sanitizedConfig)
      notifyConnectivityAfterSave(trimmedName, result.connectivity)
    } else if (!modelGroups[trimmedName]) {
      const result = await unifiedConfigApi.updateModelGroup(trimmedName, sanitizedConfig)
      notifyConnectivityAfterSave(trimmedName, result.connectivity)
    } else {
      notification.error(t('modelGroup.notifications.nameExists', { name: trimmedName }))
      return
    }
    queryClient.invalidateQueries({ queryKey: ['model-groups'] })
  }

  const notifyConnectivityAfterSave = (
    groupName: string,
    result: ModelGroupConnectivityResult | undefined
  ) => {
    if (!result) {
      notification.success(t('modelGroup.notifications.saveSuccess'))
      return
    }
    if (result.ok) {
      notification.success(
        t('modelGroup.validation.saveConnectionSuccess', { name: groupName, protocol: result.protocol, latency: result.latency_ms })
      )
      return
    }
    if (result.suspected) {
      notification.warning(
        t('modelGroup.validation.saveConnectionSuspected', {
          name: groupName,
          protocol: result.protocol,
          error: result.error || t('common.unknownError', { ns: 'common' }),
        }),
        { duration: 8000 }
      )
      return
    }
    notification.warning(
      t('modelGroup.validation.saveConnectionError', {
        name: groupName,
        protocol: result.protocol,
        error: result.error || t('common.unknownError', { ns: 'common' }),
      }),
      { duration: 8000 }
    )
  }

  return (
    <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column', overflow: 'hidden', p: 2 }}>
      {/* 顶部工具栏 */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2, flexShrink: 0, flexWrap: 'wrap', gap: 1 }}>
        <Typography variant="h6" sx={{ fontWeight: 600, fontSize: isSmall ? '1rem' : '1.25rem' }}>
          {t('modelGroup.title')}
        </Typography>
        <Button
          variant="contained"
          onClick={handleAdd}
          startIcon={<AddIcon />}
          size={isSmall ? 'small' : 'medium'}
          sx={{
            minWidth: { xs: 120, sm: 140 },
            minHeight: { xs: 36, sm: 40 },
            color: 'text.primary',
            bgcolor: theme.palette.action.selected,
            border: '1px solid',
            borderColor: 'divider',
            boxShadow: 'none',
            '&:hover': { bgcolor: theme.palette.action.hover, boxShadow: 'none' },
          }}
        >
          {t('modelGroup.addGroup')}
        </Button>
      </Box>

      {/* 卡片列表容器 */}
      <Paper
        elevation={0}
        sx={{
          flex: 1,
          display: 'flex',
          flexDirection: 'column',
          minHeight: 0,
          overflow: 'hidden',
          bgcolor: 'transparent',
          border: 'none',
          boxShadow: 'none',
        }}
      >
        <Box sx={{ flex: 1, overflow: 'auto', px: 0.5, py: 0.5 }}>
          {modelGroupsLoading ? (
            <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%' }}>
              <CircularProgress size={32} />
            </Box>
          ) : modelGroupEntries.length === 0 ? (
            <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%' }}>
              <Typography variant="body1" color="text.secondary">
                {t('modelGroup.emptyMessage')}
              </Typography>
            </Box>
          ) : (
            <Stack spacing={1.5}>
              {modelGroupEntries.map(([name, config]) => {
                const colors = getTypeColors(config.MODEL_TYPE)
                return (
                  <Box
                    key={name}
                    onClick={() => handleEdit(name)}
                    sx={{
                      position: 'relative',
                      display: 'flex',
                      alignItems: 'center',
                      gap: 2,
                      px: 2.5,
                      py: 1.75,
                      borderRadius: '12px',
                      bgcolor: PANEL.background,
                      border: `1px solid ${theme.palette.divider}`,
                      cursor: 'pointer',
                      transition: 'all 0.2s ease',
                      '&:hover': {
                        bgcolor: theme.palette.action.hover,
                        borderColor: colors.main,
                        boxShadow: theme.palette.mode === 'dark'
                          ? `0 0 20px ${colors.glow}, 0 4px 12px rgba(0,0,0,0.3)`
                          : `0 10px 24px ${alpha(colors.main, 0.12)}`,
                        transform: 'translateY(-1px)',
                      },
                    }}
                  >
                    {/* 左侧颜色条 */}
                    <Box
                      sx={{
                        position: 'absolute',
                        left: 0,
                        top: 10,
                        bottom: 10,
                        width: 4,
                        borderRadius: '0 4px 4px 0',
                        bgcolor: colors.main,
                        boxShadow: `0 0 8px ${colors.glow}`,
                      }}
                    />

                    {/* 主内容区 */}
                    <Box sx={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', gap: 0.5, ml: 1 }}>
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, flexWrap: 'wrap' }}>
                        <Typography
                          variant="body1"
                          sx={{
                            fontWeight: 600,
                            fontSize: isSmall ? '0.9rem' : '1rem',
                            color: 'text.primary',
                            overflow: 'hidden',
                            textOverflow: 'ellipsis',
                            whiteSpace: 'nowrap',
                          }}
                        >
                          {name}
                        </Typography>
                        <Typography
                          variant="caption"
                          sx={{
                            color: colors.main,
                            fontWeight: 600,
                            fontSize: '0.7rem',
                            textTransform: 'uppercase',
                            letterSpacing: '0.05em',
                          }}
                        >
                          {getModelTypeLabel(config.MODEL_TYPE)}
                        </Typography>
                      </Box>
                      <Typography
                        variant="body2"
                        sx={{
                          fontSize: isSmall ? '0.75rem' : '0.85rem',
                          color: 'text.secondary',
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                          whiteSpace: 'nowrap',
                        }}
                      >
                        {config.CHAT_MODEL || t('modelGroup.emptyMessage')}
                      </Typography>
                    </Box>

                    {/* 右侧代理状态 */}
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexShrink: 0, ml: 'auto' }}>
                      <Box
                        sx={{
                          width: 6,
                          height: 6,
                          borderRadius: '50%',
                          bgcolor: config.USE_GLOBAL_PROXY ? COLORS.accent : config.CHAT_PROXY ? COLORS.warning : COLORS.textSecondary,
                          boxShadow: config.USE_GLOBAL_PROXY
                            ? '0 0 6px rgba(92,157,255,0.5)'
                            : config.CHAT_PROXY
                            ? '0 0 6px rgba(255,159,10,0.5)'
                            : 'none',
                        }}
                      />
                      <Typography
                        variant="caption"
                        sx={{
                          color: 'text.secondary',
                          fontSize: '0.7rem',
                          whiteSpace: 'nowrap',
                          display: { xs: 'none', sm: 'block' },
                        }}
                      >
                        {config.USE_GLOBAL_PROXY
                          ? t('modelGroup.chips.globalProxyEnabled')
                          : config.CHAT_PROXY
                          ? t('modelGroup.table.proxyAddress')
                          : t('modelGroup.table.proxyMode')}
                      </Typography>
                    </Box>
                  </Box>
                )
              })}
            </Stack>
          )}
        </Box>
      </Paper>

      <EditDialog
        key={dialogKey}
        open={editDialogOpen}
        onClose={() => setEditDialogOpen(false)}
        groupName={editingGroup.name}
        initialConfig={editingGroup.config}
        onSubmit={handleSubmit}
        onGroupNameChange={name => setEditingGroup(prev => ({ ...prev, name }))}
        isCopy={editingGroup.isCopy}
        existingGroups={modelGroups}
        onCopy={editingGroup.name && !editingGroup.isCopy ? () => handleCopy(editingGroup.name) : undefined}
        onDelete={editingGroup.name && !editingGroup.isCopy ? () => { setEditDialogOpen(false); confirmDelete(editingGroup.name); } : undefined}
      />

      <Dialog
        open={deleteDialogOpen}
        onClose={() => setDeleteDialogOpen(false)}
        fullWidth
        maxWidth="xs"
        PaperProps={{
          sx: {
            bgcolor: PANEL.background,
            backgroundColor: PANEL.background,
            borderRadius: PANEL.borderRadius,
            border: PANEL.border,
            boxShadow: SHADOWS.dialog,
            backgroundImage: 'none',
            outline: 'none',
          },
        }}
      >
        <DialogTitle sx={{ fontSize: '1.05rem', fontWeight: 600, m: 0 }}>
          {t('modelGroup.deleteDialog.title')}
        </DialogTitle>
        <DialogContent sx={{ bgcolor: 'transparent' }}>
          <Typography sx={{ fontSize: isSmall ? '0.9rem' : 'inherit', color: 'text.secondary' }}>
            {t('modelGroup.deleteDialog.content', { name: deletingGroupName })}
          </Typography>
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 2 }}>
          <Button
            onClick={() => setDeleteDialogOpen(false)}
            sx={{ minWidth: { xs: 64, sm: 80 }, minHeight: { xs: 36, sm: 40 }, color: 'text.secondary' }}
          >
            {t('actions.cancel', { ns: 'common' })}
          </Button>
          <Button
            onClick={() => handleDelete(deletingGroupName)}
            sx={{
              minWidth: { xs: 64, sm: 80 },
              minHeight: { xs: 36, sm: 40 },
              bgcolor: 'rgba(255,69,58,0.12)',
              color: COLORS.error,
              '&:hover': { bgcolor: 'rgba(255,69,58,0.2)' },
            }}
          >
            {t('modelGroup.deleteDialog.confirm')}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  )
}
