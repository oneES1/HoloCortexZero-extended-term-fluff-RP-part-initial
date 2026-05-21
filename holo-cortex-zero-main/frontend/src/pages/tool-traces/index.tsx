import React, { useState } from 'react'
import {
  Box,
  CircularProgress,
  Collapse,
  IconButton,
  Paper,
  Stack,
  Typography,
  useMediaQuery,
  useTheme,
} from '@mui/material'
import KeyboardArrowDown from '@mui/icons-material/KeyboardArrowDown'
import KeyboardArrowUp from '@mui/icons-material/KeyboardArrowUp'
import ContentCopy from '@mui/icons-material/ContentCopy'
import { useQuery } from '@tanstack/react-query'
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter'
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism'
import { oneLight } from 'react-syntax-highlighter/dist/esm/styles/prism'
import { useTranslation } from 'react-i18next'

import TablePaginationStyled from '../../components/common/TablePaginationStyled'
import { useNotification } from '../../hooks/useNotification'
import {
  toolTracesApi,
  ToolTraceChainEvent,
  ToolTraceChainData,
  ToolTraceLog,
} from '../../services/api/tool-traces'

const formatTraceDuration = (durationMs?: number | null) => {
  if (!durationMs || Number.isNaN(durationMs)) return '0ms'
  if (durationMs >= 1000) return `${(durationMs / 1000).toFixed(durationMs >= 10000 ? 1 : 2)}s`
  return `${durationMs}ms`
}

const stringifyTraceValue = (value: unknown) => {
  if (value === undefined || value === null) return ''
  if (typeof value === 'string') return value
  try {
    return JSON.stringify(value, null, 2)
  } catch {
    return String(value)
  }
}

const formatCacheRatio = (cachedTokens?: number, promptTokens?: number) => {
  const cached = Number(cachedTokens || 0)
  const prompt = Number(promptTokens || 0)
  if (!prompt || Number.isNaN(prompt) || Number.isNaN(cached)) return '0.0%'
  return `${((cached / prompt) * 100).toFixed(1)}%`
}

const extractReasoningContent = (value: unknown) => {
  if (typeof value !== 'string') return ''
  const raw = value.trim()
  if (!raw) return ''
  try {
    const parsed = JSON.parse(raw)
    if (parsed && typeof parsed === 'object') {
      if (typeof parsed.reasoning_content === 'string' && parsed.reasoning_content.trim()) {
        return parsed.reasoning_content.trim()
      }
      if (typeof parsed.text === 'string' && parsed.text.trim()) {
        return parsed.text.trim()
      }
      return JSON.stringify(parsed, null, 2)
    }
  } catch {
    return raw
  }
  return raw
}

const getTraceEventTitle = (
  event: ToolTraceChainEvent,
  t: (key: string, options?: Record<string, unknown>) => string
) => {
  if (event.kind === 'llm') return t('detail.trace.llmRoundTitle', { iteration: event.iteration })
  if (event.kind === 'assistant') return t('detail.trace.assistantTitle', { iteration: event.iteration })
  if (event.kind === 'tool') {
    return t('detail.trace.toolTitle', { iteration: event.iteration, name: event.tool_name || 'tool' })
  }
  return t('detail.trace.errorTitle', { iteration: event.iteration })
}

const EVENT_KIND_COLORS: Record<ToolTraceChainEvent['kind'], string> = {
  llm: '#5c9dff',
  assistant: '#32d74b',
  tool: '#ff9f0a',
  error: '#ff453a',
}

const getKindBadgeStyle = (kind: ToolTraceChainEvent['kind']) => {
  const color = EVENT_KIND_COLORS[kind]
  const bgMap: Record<string, string> = {
    '#5c9dff': 'rgba(92,157,255,0.12)',
    '#32d74b': 'rgba(50,215,75,0.12)',
    '#ff9f0a': 'rgba(255,159,10,0.12)',
    '#ff453a': 'rgba(255,69,58,0.12)',
  }
  return {
    backgroundColor: bgMap[color],
    color,
    borderRadius: '4px',
    padding: '2px 8px',
    fontSize: '0.72rem',
    fontWeight: 600,
    lineHeight: 1.4,
    display: 'inline-block',
  } as const
}

const sectionLabelSx = {
  fontSize: '0.65rem',
  letterSpacing: '0.1em',
  textTransform: 'uppercase' as const,
  color: 'text.disabled',
  fontWeight: 600,
}

const scrollableBlockSx = {
  bgcolor: 'action.hover',
  border: '1px solid',
  borderColor: 'divider',
  borderRadius: '8px',
  p: '12px 16px',
  overflow: 'auto',
  position: 'relative',
  '&::-webkit-scrollbar': { width: '4px', height: '4px' },
  '&::-webkit-scrollbar-thumb': { backgroundColor: 'rgba(255,255,255,0.08)', borderRadius: '2px' },
}

const bodyTextSx = {
  whiteSpace: 'pre-wrap',
  wordBreak: 'break-word',
  overflowWrap: 'break-word',
  fontSize: '0.82rem',
  color: 'text.secondary',
  lineHeight: 1.6,
}

/* ── Timeline Event Card ── */
export function TimelineEventCard({
  event,
  traceData,
}: {
  event: ToolTraceChainEvent
  traceData: ToolTraceChainData
}) {
  const { t } = useTranslation('tool-traces')
  const theme = useTheme()
  const reasoningContent = extractReasoningContent(event.reasoning_content)
  const kindColor = EVENT_KIND_COLORS[event.kind]
  const isError = event.kind === 'error' || (event.kind === 'tool' && event.is_error)

  return (
    <Box sx={{ display: 'flex' }}>
      {/* Timeline column */}
      <Box sx={{ width: 24, position: 'relative', flexShrink: 0, display: 'flex', justifyContent: 'center' }}>
        <Box
          sx={{
            position: 'absolute',
            top: 0,
            bottom: 0,
            width: '2px',
            bgcolor: 'divider',
          }}
        />
        <Box
          sx={{
            mt: 2.5,
            width: 8,
            height: 8,
            borderRadius: '50%',
            bgcolor: kindColor,
            flexShrink: 0,
            position: 'relative',
            zIndex: 1,
            boxShadow: `0 0 8px ${kindColor}40`,
          }}
        />
      </Box>

      {/* Content */}
      <Box sx={{ flex: 1, minWidth: 0, pb: 2.5 }}>
        <Box
          sx={{
            bgcolor: isError ? 'rgba(255,69,58,0.06)' : 'action.hover',
            borderRadius: '12px',
            p: '16px 20px',
            transition: 'background 0.15s ease',
          }}
        >
          {/* Header */}
          <Box
            sx={{
              display: 'flex',
              alignItems: { xs: 'flex-start', sm: 'center' },
              justifyContent: 'space-between',
              gap: 1,
              mb: 1,
              flexWrap: 'wrap',
            }}
          >
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap' }}>
              <Box component="span" sx={getKindBadgeStyle(event.kind)}>
                {t(`detail.trace.kind.${event.kind}`)}
              </Box>
              <Typography
                sx={{ fontSize: '0.88rem', fontWeight: 600, color: 'text.primary', letterSpacing: '-0.01em' }}
              >
                {getTraceEventTitle(event, t as (key: string, options?: Record<string, unknown>) => string)}
              </Typography>
            </Box>
            <Box
              sx={{
                display: 'flex',
                alignItems: 'center',
                gap: 1.5,
                color: 'text.secondary',
                fontSize: '0.75rem',
                fontWeight: 500,
                flexShrink: 0,
              }}
            >
              {event.model && <span>{event.model}</span>}
              {event.duration_ms !== undefined && <span>{formatTraceDuration(event.duration_ms)}</span>}
            </Box>
          </Box>

          {/* LLM Meta */}
          {event.kind === 'llm' && (
            <Box
              sx={{
                color: 'text.disabled',
                fontSize: '0.7rem',
                fontWeight: 500,
                mb: 1.5,
                lineHeight: 1.6,
              }}
            >
              {event.finish_reason && `${t('detail.trace.finishReason', { value: event.finish_reason })} · `}
              {t('detail.trace.toolCalls', { count: event.tool_call_count || 0 })} ·{' '}
              {t('detail.trace.textLength', { count: event.text_length || 0 })} ·{' '}
              {event.usage &&
                t('detail.trace.tokenUsage', {
                  prompt: event.usage.prompt_tokens,
                  completion: event.usage.completion_tokens,
                  total: event.usage.total_tokens,
                })}
              {event.usage && event.usage.cached_tokens !== undefined && (
                ` · ${t('detail.trace.cacheUsage', {
                  cached: event.usage.cached_tokens,
                  ratio: formatCacheRatio(event.usage.cached_tokens, event.usage.prompt_tokens),
                })}`
              )}
              {` · ${t('detail.trace.totalIterations', { count: traceData.total_iterations })}`}
            </Box>
          )}

          {/* Reasoning */}
          {event.kind === 'llm' && (
            <Box sx={{ mt: 1 }}>
              <Typography sx={{ ...sectionLabelSx, mb: 0.75 }}>
                {t('detail.trace.reasoningContent')}
              </Typography>
              <Box sx={scrollableBlockSx}>
                <Typography sx={bodyTextSx}>
                  {reasoningContent || t('detail.trace.noReasoningContent')}
                </Typography>
              </Box>
            </Box>
          )}

          {/* Assistant text */}
          {event.kind === 'assistant' && event.text && (
            <Box sx={{ mt: 1 }}>
              <Typography sx={{ ...sectionLabelSx, mb: 0.75 }}>
                {t('detail.trace.kind.assistant')}
              </Typography>
              <Box sx={scrollableBlockSx}>
                <Typography sx={bodyTextSx}>{event.text}</Typography>
              </Box>
            </Box>
          )}

          {/* Tool */}
          {event.kind === 'tool' && (
            <Stack spacing={1.5} sx={{ mt: 1 }}>
              <Box>
                <Typography sx={{ ...sectionLabelSx, mb: 0.75 }}>
                  {t('detail.trace.arguments')}
                </Typography>
                <Box sx={scrollableBlockSx}>
                  <SyntaxHighlighter
                    language="json"
                    style={theme.palette.mode === 'dark' ? vscDarkPlus : oneLight}
                    customStyle={{ margin: 0, background: 'transparent' }}
                    wrapLines
                    wrapLongLines
                  >
                    {stringifyTraceValue(event.arguments || {})}
                  </SyntaxHighlighter>
                </Box>
              </Box>
              <Box>
                <Typography sx={{ ...sectionLabelSx, mb: 0.75 }}>
                  {t('detail.trace.resultPreview')}
                </Typography>
                <Box sx={scrollableBlockSx}>
                  <Typography sx={bodyTextSx}>
                    {event.result_preview || t('detail.empty')}
                  </Typography>
                </Box>
              </Box>
            </Stack>
          )}

          {/* Error */}
          {event.kind === 'error' && (
            <Box sx={{ mt: 1, bgcolor: 'rgba(255,69,58,0.04)', borderRadius: '8px', p: '12px 16px' }}>
              <Typography sx={{ color: '#ff6b61', fontSize: '0.82rem', lineHeight: 1.6 }}>
                {event.message || t('detail.empty')}
              </Typography>
            </Box>
          )}
        </Box>
      </Box>
    </Box>
  )
}

/* ── Trace Detail View ── */
export function TraceDetailView({
  log,
  isMobile,
  isSmall,
  onCopy,
}: {
  log: ToolTraceLog
  isMobile: boolean
  isSmall: boolean
  onCopy: (text: string | null | undefined, contentType: string) => void
}) {
  const { t } = useTranslation('tool-traces')
  const { data: traceData = log.trace_data } = useQuery({
    queryKey: ['tool-traces-log-content', log.id],
    queryFn: () => toolTracesApi.getLogContent(log.id),
    initialData: log.trace_data,
  })

  const triggerPreview = log.trigger_message_text
    ? log.trigger_message_text.slice(0, 80) + (log.trigger_message_text.length > 80 ? '…' : '')
    : t('detail.noTrigger')

  const copyBtnSx = {
    position: 'absolute' as const,
    top: 8,
    right: 8,
    opacity: 0,
    transition: 'opacity 0.15s ease',
    color: 'text.disabled',
    '&:hover': { color: 'text.primary' },
  }

  return (
    <Box sx={{ py: 2, px: isMobile ? 2 : 3, maxWidth: '100%', overflow: 'hidden' }}>
      {/* Header */}
      <Box sx={{ mb: 2.5 }}>
        <Typography
          sx={{
            fontSize: isSmall ? '1rem' : '1.1rem',
            fontWeight: 600,
            color: 'text.primary',
            letterSpacing: '-0.02em',
            lineHeight: 1.3,
            mb: 0.5,
          }}
        >
          {triggerPreview}
        </Typography>
        <Typography sx={{ fontSize: '0.75rem', color: 'text.secondary', fontWeight: 500 }}>
          {log.create_time}
          {log.total_duration_ms !== undefined && ` · ${formatTraceDuration(log.total_duration_ms)}`}
          {log.token_total !== undefined && ` · ${log.token_total} tokens`}
        </Typography>
      </Box>

      {/* Metadata bar */}
      <Box
        sx={{
          fontSize: '0.7rem',
          color: 'text.disabled',
          fontWeight: 500,
          mb: 3,
          lineHeight: 1.6,
        }}
      >
        {t('detail.contextId')} {log.context_id}
        {' · '}
        {t('detail.activeDialog')} {log.active_dialog_id}
        {' · '}
        {t('detail.permission')} {log.permission_level}
        {log.use_model && ` · ${log.use_model}`}
      </Box>

      {/* Trigger Section */}
      <Box sx={{ mb: 3 }}>
        <Typography sx={{ ...sectionLabelSx, mb: 1 }}>{t('detail.trigger')}</Typography>
        <Box sx={{ ...scrollableBlockSx, '&:hover .copy-btn': { opacity: 1 } }}>
          <Typography sx={bodyTextSx}>{log.trigger_message_text || t('detail.noTrigger')}</Typography>
          <IconButton
            size="small"
            className="copy-btn"
            onClick={() => onCopy(log.trigger_message_text, t('detail.trigger'))}
            sx={copyBtnSx}
          >
            <ContentCopy fontSize="small" />
          </IconButton>
        </Box>
      </Box>

      {/* Summary Section */}
      <Box sx={{ mb: 3 }}>
        <Typography sx={{ ...sectionLabelSx, mb: 1 }}>{t('detail.summary')}</Typography>
        <Box sx={{ ...scrollableBlockSx, '&:hover .copy-btn': { opacity: 1 } }}>
          <Typography sx={bodyTextSx}>{log.summary_text || t('detail.noResult')}</Typography>
          <IconButton
            size="small"
            className="copy-btn"
            onClick={() => onCopy(log.summary_text, t('detail.summary'))}
            sx={copyBtnSx}
          >
            <ContentCopy fontSize="small" />
          </IconButton>
        </Box>
      </Box>

      {/* Trace Events Section */}
      <Box sx={{ mb: 2 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 2 }}>
          <Typography sx={{ ...sectionLabelSx, mb: 0 }}>{t('detail.trace.title')}</Typography>
          <IconButton
            size="small"
            onClick={() => onCopy(stringifyTraceValue(traceData), t('detail.trace.title'))}
            sx={{ color: 'text.disabled', '&:hover': { color: 'text.primary' } }}
          >
            <ContentCopy fontSize="small" />
          </IconButton>
        </Box>

        {traceData?.error_message && (
          <Box sx={{ mb: 2, bgcolor: 'rgba(255,159,10,0.04)', borderRadius: '8px', p: '12px 16px' }}>
            <Typography sx={{ color: '#ff9f0a', fontSize: '0.82rem' }}>
              {traceData.error_message}
            </Typography>
          </Box>
        )}

        <Box>
          {(traceData?.events || []).map((event, index) => (
            <TimelineEventCard
              key={`${log.id}-${event.kind}-${index}`}
              event={event}
              traceData={traceData}
            />
          ))}
        </Box>
      </Box>
    </Box>
  )
}

/* ── backward-compatible re-export for Dashboard ── */
export { TraceDetailView as TraceDetailContent }

/* ── Tool Traces Page ── */
export default function ToolTracesPage() {
  const [page, setPage] = useState(0)
  const [rowsPerPage, setRowsPerPage] = useState(50)
  const [expandedRows, setExpandedRows] = useState<Record<number, boolean>>({})
  const theme = useTheme()
  const isMobile = useMediaQuery(theme.breakpoints.down('md'))
  const isSmall = useMediaQuery(theme.breakpoints.down('sm'))
  const notification = useNotification()
  const { t } = useTranslation('tool-traces')

  const { data: stats } = useQuery({
    queryKey: ['tool-traces-stats'],
    queryFn: () => toolTracesApi.getStats(500),
    refetchInterval: 10000,
  })

  const {
    data: logs,
    isLoading,
    isPlaceholderData,
  } = useQuery({
    queryKey: ['tool-traces-logs', page, rowsPerPage],
    queryFn: () =>
      toolTracesApi.getLogs({
        page: page + 1,
        page_size: rowsPerPage,
      }),
    placeholderData: previous => previous,
  })

  const handleChangePage = (_: unknown, newPage: number) => setPage(newPage)

  const handleChangeRowsPerPage = (event: React.ChangeEvent<HTMLInputElement>) => {
    setRowsPerPage(parseInt(event.target.value, 10))
    setPage(0)
  }

  const toggleRow = (id: number) => {
    setExpandedRows(prev => ({
      ...prev,
      [id]: !prev[id],
    }))
  }

  const copyToClipboard = (text: string | null | undefined, contentType: string) => {
    if (!text) {
      notification.warning(t('actions.noContent'))
      return
    }
    navigator.clipboard
      .writeText(text)
      .then(() => notification.success(t('actions.copied', { content: contentType })))
      .catch(() => notification.error(t('actions.copyFailed')))
  }

  const getTraceSummaryMeta = (log: ToolTraceLog) => {
    const events = log.trace_data?.events ?? []
    const toolCount = events.filter(e => e.kind === 'tool').length
    return { toolCount }
  }

  return (
    <Box className="h-full overflow-hidden flex flex-col" sx={{ minHeight: 0 }}>
      <Box
        sx={{
          flexGrow: 1,
          minHeight: 0,
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
          bgcolor: 'transparent',
        }}
      >
        {/* Stats bar */}
        <Box
          sx={{
            px: isSmall ? 2 : 3,
            py: 1.5,
            display: 'flex',
            alignItems: { xs: 'flex-start', sm: 'center' },
            justifyContent: 'space-between',
            gap: 2,
            flexDirection: { xs: 'column', sm: 'row' },
            borderBottom: `1px solid ${theme.palette.divider}`,
          }}
        >
          <Box>
            <Typography
              sx={{
                fontSize: '0.65rem',
                letterSpacing: '0.1em',
                textTransform: 'uppercase',
                color: 'text.disabled',
                fontWeight: 600,
              }}
            >
              {t('stats.successRateRecent')}
            </Typography>
            <Typography sx={{ fontSize: '1.1rem', fontWeight: 700, color: 'text.primary', letterSpacing: '-0.02em' }}>
              {stats?.success_rate ?? 0}%
            </Typography>
          </Box>
          <Box sx={{ flex: 1, minWidth: 0, maxWidth: { sm: '70%' } }}>
            <Typography
              sx={{
                fontSize: '0.65rem',
                letterSpacing: '0.1em',
                textTransform: 'uppercase',
                color: 'text.disabled',
                fontWeight: 600,
                textAlign: { xs: 'left', sm: 'right' },
              }}
            >
              {t('stats.successRunsRecent')}
            </Typography>
            <Typography
              sx={{
                fontSize: '1.1rem',
                color: '#32d74b',
                fontWeight: 700,
                letterSpacing: '-0.02em',
                textAlign: { xs: 'left', sm: 'right' },
              }}
            >
              {(stats?.success ?? 0).toLocaleString()}
            </Typography>
          </Box>
        </Box>

        {/* Card list */}
        <Box sx={{ flexGrow: 1, minHeight: 0, overflow: 'auto', px: isSmall ? 1.5 : 2, py: 1.5 }}>
          {isLoading && !isPlaceholderData ? (
            <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%' }}>
              <CircularProgress size={28} sx={{ color: 'text.secondary' }} />
            </Box>
          ) : (
            <Stack spacing={1}>
              {logs?.items.map(log => {
                const { toolCount } = getTraceSummaryMeta(log)
                const isExpanded = !!expandedRows[log.id]
                return (
                  <Paper
                    key={log.id}
                    elevation={0}
                    sx={{
                      bgcolor: 'background.paper',
                      borderRadius: '12px',
                      overflow: 'hidden',
                      transition: 'background 0.15s ease',
                      '&:hover': { bgcolor: 'action.hover' },
                    }}
                  >
                    <Box
                      onClick={() => toggleRow(log.id)}
                      sx={{
                        px: 2,
                        py: 1.5,
                        cursor: 'pointer',
                        display: 'flex',
                        alignItems: 'center',
                        gap: 1.5,
                      }}
                    >
                      {/* Status dot */}
                      <Box
                        sx={{
                          width: 6,
                          height: 6,
                          borderRadius: '50%',
                          bgcolor: log.success ? '#32d74b' : '#ff453a',
                          flexShrink: 0,
                        }}
                      />
                      <Box sx={{ flex: 1, minWidth: 0 }}>
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, mb: 0.35 }}>
                          <Typography
                            sx={{
                              fontFamily: 'monospace',
                              fontSize: '0.72rem',
                              color: 'text.secondary',
                              flexShrink: 0,
                            }}
                          >
                            {log.create_time}
                          </Typography>
                          <Typography
                            sx={{
                              fontSize: '0.88rem',
                              color: 'text.primary',
                              whiteSpace: 'nowrap',
                              overflow: 'hidden',
                              textOverflow: 'ellipsis',
                              minWidth: 0,
                              fontWeight: 500,
                            }}
                          >
                            {log.summary_text || log.trigger_message_text || t('detail.noResult')}
                          </Typography>
                        </Box>
                        <Box
                          sx={{
                            display: 'flex',
                            alignItems: 'center',
                            gap: 1,
                            color: 'text.disabled',
                            fontSize: '0.7rem',
                            fontWeight: 500,
                          }}
                        >
                          <span>{log.use_model || '—'}</span>
                          <span>·</span>
                          <span>{formatTraceDuration(log.total_duration_ms)}</span>
                          <span>·</span>
                          <span>{toolCount > 0 ? `${toolCount} tools` : 'No tools'}</span>
                        </Box>
                      </Box>
                      <Box sx={{ flexShrink: 0, color: 'text.disabled' }}>
                        {isExpanded ? (
                          <KeyboardArrowUp fontSize="small" />
                        ) : (
                          <KeyboardArrowDown fontSize="small" />
                        )}
                      </Box>
                    </Box>

                    <Collapse in={isExpanded} timeout="auto" unmountOnExit>
                      <Box sx={{ px: 2, pb: 2 }}>
                        <TraceDetailView
                          log={log}
                          isMobile={isMobile}
                          isSmall={isSmall}
                          onCopy={copyToClipboard}
                        />
                      </Box>
                    </Collapse>
                  </Paper>
                )
              })}
            </Stack>
          )}
        </Box>

        <TablePaginationStyled
          component="div"
          count={logs?.total || 0}
          page={page}
          onPageChange={handleChangePage}
          rowsPerPage={rowsPerPage}
          onRowsPerPageChange={handleChangeRowsPerPage}
          rowsPerPageOptions={[50, 100]}
        />
      </Box>
    </Box>
  )
}
