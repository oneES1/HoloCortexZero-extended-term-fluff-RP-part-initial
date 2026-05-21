import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react'
import { useTranslation } from 'react-i18next'
import { Box, Typography, useTheme, useMediaQuery, Paper, Divider, Stack } from '@mui/material'
import { QueryClient, QueryClientProvider, useQuery } from '@tanstack/react-query'
import { motion, AnimatePresence } from 'framer-motion'
import { dashboardApi, RealTimeDataPoint } from '../../services/api/dashboard'
import { toolTracesApi, type ToolTraceLog } from '../../services/api/tool-traces'
import { RealTimeStats } from './components/RealTimeStats'
import { createEventStream } from '../../services/api/utils/stream'
import { TraceDetailContent } from '../tool-traces'

const DEFAULT_TIME_SCALE_MINUTES = 24 * 60

const formatRelativeTime = (value: string | undefined, t: (key: string, options?: object) => string) => {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffSec = Math.floor(diffMs / 1000)
  if (diffSec < 60) return t('time.justNow')
  const diffMin = Math.floor(diffSec / 60)
  if (diffMin < 60) return t('time.minutesAgo', { count: diffMin })
  const diffHour = Math.floor(diffMin / 60)
  if (diffHour < 24) return t('time.hoursAgo', { count: diffHour })
  const diffDay = Math.floor(diffHour / 24)
  return t('time.daysAgo', { count: diffDay })
}

const formatDuration = (durationMs?: number) => {
  if (durationMs === undefined || durationMs === null) return '—'
  if (durationMs >= 1000) return `${(durationMs / 1000).toFixed(durationMs >= 10000 ? 0 : 1)}s`
  return `${durationMs}ms`
}

const getTraceSummary = (trace: ToolTraceLog) => {
  const events = trace.trace_data?.events ?? []
  const firstLlm = events.find(e => e.kind === 'llm')
  const model = firstLlm?.model || 'Unknown'
  const toolCount = events.filter(e => e.kind === 'tool').length
  const duration = trace.total_duration_ms
  return { model, toolCount, duration }
}

/* ── Live Pulse Dot ── */
function LivePulse() {
  return (
    <Box sx={{ position: 'relative', width: 8, height: 8, flexShrink: 0 }}>
      <Box
        sx={{
          position: 'absolute',
          inset: 0,
          borderRadius: '50%',
          background: '#32d74b',
          animation: 'pulse-ring 2s cubic-bezier(0.4, 0, 0.6, 1) infinite',
          opacity: 0.4,
        }}
      />
      <Box
        sx={{
          position: 'absolute',
          inset: 2,
          borderRadius: '50%',
          background: '#32d74b',
        }}
      />
      <style>{`
        @keyframes pulse-ring {
          0%, 100% { transform: scale(1); opacity: 0.4; }
          50% { transform: scale(2.2); opacity: 0; }
        }
      `}</style>
    </Box>
  )
}

/* ── Chain List Item ── */
function ChainListItem({ trace, selected, onClick, t }: { trace: ToolTraceLog; selected: boolean; onClick: () => void; t: (key: string, options?: object) => string }) {
  const theme = useTheme()
  const { model, toolCount, duration } = useMemo(() => getTraceSummary(trace), [trace])
  const relativeTime = formatRelativeTime(trace.create_time, t)

  return (
    <Box
      onClick={onClick}
      sx={{
        px: 1.5,
        py: 1.2,
        borderRadius: 2,
        cursor: 'pointer',
        userSelect: 'none',
        transition: 'all 0.18s ease',
        position: 'relative',
        overflow: 'hidden',
        bgcolor: selected ? theme.palette.action.selected : 'transparent',
        '&:hover': {
          bgcolor: selected ? theme.palette.action.selected : theme.palette.action.hover,
        },
        '&::before': {
          content: '""',
          position: 'absolute',
          top: 0,
          left: 0,
          width: '3px',
          height: '100%',
          bgcolor: selected ? 'primary.main' : 'transparent',
          transition: 'background 0.18s ease',
        },
      }}
    >
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 0.5 }}>
        <Typography sx={{ fontSize: '0.84rem', fontWeight: 600, color: 'text.primary', letterSpacing: '-0.015em' }}>
          {model}
        </Typography>
        <Box
          sx={{
            width: 6,
            height: 6,
            borderRadius: '50%',
            background: trace.success ? '#32d74b' : '#ff453a',
            flexShrink: 0,
          }}
        />
      </Box>
      <Typography sx={{ fontSize: '0.72rem', color: 'text.secondary', fontWeight: 500, mb: 0.35 }}>
        {relativeTime}
      </Typography>
      <Typography sx={{ fontSize: '0.68rem', color: 'text.disabled', fontWeight: 500 }}>
        {toolCount > 0 ? `${toolCount} tool${toolCount > 1 ? 's' : ''}` : 'No tools'}
        {duration ? ` · ${formatDuration(duration)}` : ''}
      </Typography>
    </Box>
  )
}

/* ── Main Dashboard ── */
const DashboardContent: React.FC = () => {
  const [realTimeData, setRealTimeData] = useState<RealTimeDataPoint[]>([])
  const [timeScaleMinutes, setTimeScaleMinutes] = useState<number>(DEFAULT_TIME_SCALE_MINUTES)
  const [selectedTraceId, setSelectedTraceId] = useState<number | null>(null)
  const { t } = useTranslation('dashboard')
  const theme = useTheme()
  const isMobile = useMediaQuery(theme.breakpoints.down('md'))
  const isSmall = useMediaQuery(theme.breakpoints.down('sm'))

  const handleRealTimeData = useCallback((data: string) => {
    try {
      const newData = JSON.parse(data) as RealTimeDataPoint
      setRealTimeData(prev => {
        const existingIndex = prev.findIndex(item => item.timestamp === newData.timestamp)
        if (existingIndex >= 0) {
          const updated = [...prev]
          updated[existingIndex] = newData
          return updated
        }
        const updated = [...prev, newData].sort((a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime())
        if (updated.length > 50) return updated.slice(updated.length - 50)
        return updated
      })
    } catch (error) {
      console.error('Failed to parse real-time data:', error)
    }
  }, [])

  useEffect(() => {
    setRealTimeData([])
    const cancelStream = createEventStream({
      endpoint: `/dashboard/stats/stream?window_minutes=${timeScaleMinutes}`,
      onMessage: handleRealTimeData,
      onError: error => console.error('Dashboard data stream error:', error),
    })
    return () => { cancelStream() }
  }, [handleRealTimeData, timeScaleMinutes])

  const { data: overview } = useQuery({
    queryKey: ['dashboard-overview', timeScaleMinutes],
    queryFn: () => dashboardApi.getOverview({ time_range: 'day', window_minutes: timeScaleMinutes }),
  })

  const { data: latestMessage } = useQuery({
    queryKey: ['dashboard-latest-message'],
    queryFn: () => dashboardApi.getLatestMessage(),
    refetchInterval: 10000,
  })

  const { data: recentTraces } = useQuery({
    queryKey: ['dashboard-latest-traces'],
    queryFn: () => toolTracesApi.getLogs({ page: 1, page_size: 20 }),
    refetchInterval: 10000,
  })

  const traces = useMemo(
    () => (recentTraces?.items ?? [])
      .sort((left, right) => new Date(right.create_time).getTime() - new Date(left.create_time).getTime()),
    [recentTraces]
  )

  const selectedTrace = useMemo(() =>
    traces.find(trace => trace.id === selectedTraceId),
    [traces, selectedTraceId]
  )

  const listScrollRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    const el = listScrollRef.current
    if (!el) return
    el.scrollTop = 0
  }, [traces])

  return (
    <Box sx={{
      height: '100%',
      minHeight: 0,
      display: 'flex',
      flexDirection: 'column',
      overflow: 'hidden',
      p: 2,
      gap: 1.5,
    }}>
      <Box sx={{
        flex: 1,
        minHeight: 0,
        display: 'grid',
        gridTemplateColumns: { xs: '1fr', md: '260px minmax(0, 1fr)' },
        gridTemplateRows: { xs: 'minmax(200px, 35%) minmax(0, 1fr)', md: 'minmax(0, 1fr)' },
        alignItems: 'stretch',
        gap: 1.5,
        overflow: 'hidden',
      }}>
        {/* ── Left Panel ── */}
        <Paper
          elevation={0}
          sx={{
            display: 'flex',
            flexDirection: 'column',
            minHeight: 0,
            height: '100%',
            overflow: 'hidden',
          }}
        >
          <Box ref={listScrollRef} sx={{ flex: 1, minHeight: 0, overflowY: 'auto', p: 1 }}>
            {/* Overview Option */}
            <Box
              onClick={() => setSelectedTraceId(null)}
              sx={{
                px: 1.5,
                py: 1.2,
                borderRadius: 2,
                cursor: 'pointer',
                userSelect: 'none',
                transition: 'all 0.18s ease',
                position: 'relative',
                overflow: 'hidden',
                bgcolor: selectedTraceId === null ? theme.palette.action.selected : 'transparent',
                '&:hover': {
                  bgcolor: selectedTraceId === null ? theme.palette.action.selected : theme.palette.action.hover,
                },
                '&::before': {
                  content: '""',
                  position: 'absolute',
                  top: 0,
                  left: 0,
                  width: '3px',
                  height: '100%',
                  bgcolor: selectedTraceId === null ? 'primary.main' : 'transparent',
                  transition: 'background 0.18s ease',
                },
              }}
            >
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.25, mb: 0.5 }}>
                <LivePulse />
                <Typography sx={{
                  fontSize: '0.88rem',
                  fontWeight: selectedTraceId === null ? 700 : 600,
                  color: 'text.primary',
                  letterSpacing: '-0.015em',
                }}>
                  {t('charts.realTimeData')}
                </Typography>
              </Box>
              <Typography sx={{ fontSize: '0.7rem', color: 'text.secondary', fontWeight: 500, pl: '20px' }}>
                {(overview?.total_messages ?? 0).toLocaleString()} msgs · {(overview?.total_tool_chain_runs ?? 0).toLocaleString()} runs
              </Typography>
            </Box>

            <Divider sx={{ my: 1, borderColor: 'divider' }} />

            {/* Chain List */}
            {traces.length === 0 ? (
              <Box sx={{ py: 4, textAlign: 'center' }}>
                <Typography sx={{ fontSize: '0.8rem', color: 'text.secondary' }}>
                  {t('panels.noTrace')}
                </Typography>
              </Box>
            ) : (
              <Stack spacing={0.75}>
                {traces.map(trace => (
                  <ChainListItem
                    key={trace.id}
                    trace={trace}
                    selected={selectedTraceId === trace.id}
                    onClick={() => setSelectedTraceId(trace.id)}
                    t={t}
                  />
                ))}
              </Stack>
            )}
          </Box>
        </Paper>

        {/* ── Right Panel ── */}
        <Paper
          elevation={0}
          sx={{
            display: 'flex',
            flexDirection: 'column',
            minHeight: 0,
            height: '100%',
            overflow: 'hidden',
          }}
        >
          <Box sx={{ flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
            <AnimatePresence mode="wait">
              {selectedTraceId === null ? (
                <motion.div
                  key="chart"
                  initial={{ opacity: 0, x: 12 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0, x: -12 }}
                  transition={{ duration: 0.25, ease: [0.4, 0, 0.2, 1] }}
                  style={{ flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column', padding: '24px 32px' }}
                >
                  <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: { xs: 2, md: 3 }, mb: 2.5 }}>
                    <Box>
                      <Typography sx={{ fontSize: '1.35rem', fontWeight: 700, color: 'text.primary', letterSpacing: '-0.02em', lineHeight: 1.2 }}>
                        {(overview?.total_messages ?? 0).toLocaleString()}
                      </Typography>
                      <Typography sx={{ fontSize: '0.72rem', color: 'text.secondary', mt: 0.25, fontWeight: 500 }}>
                        {t('stats.messages')}
                      </Typography>
                    </Box>
                    <Divider orientation="vertical" flexItem sx={{ borderColor: 'divider' }} />
                    <Box>
                      <Typography sx={{ fontSize: '1.35rem', fontWeight: 700, color: 'text.primary', letterSpacing: '-0.02em', lineHeight: 1.2 }}>
                        {(overview?.total_tool_chain_runs ?? 0).toLocaleString()}
                      </Typography>
                      <Typography sx={{ fontSize: '0.72rem', color: 'text.secondary', mt: 0.25, fontWeight: 500 }}>
                        {t('stats.runs')}
                      </Typography>
                    </Box>
                    <Divider orientation="vertical" flexItem sx={{ borderColor: 'divider' }} />
                    <Box>
                      <Typography sx={{ fontSize: '1.35rem', fontWeight: 700, color: 'text.primary', letterSpacing: '-0.02em', lineHeight: 1.2 }}>
                        {overview?.success_rate ?? 0}%
                      </Typography>
                      <Typography sx={{ fontSize: '0.72rem', color: 'text.secondary', mt: 0.25, fontWeight: 500 }}>
                        {t('stats.successRate')}
                      </Typography>
                    </Box>
                    <Divider orientation="vertical" flexItem sx={{ borderColor: 'divider' }} />
                    <Box>
                      <Typography sx={{ fontSize: '1.35rem', fontWeight: 700, color: 'text.primary', letterSpacing: '-0.02em', lineHeight: 1.2 }}>
                        {(overview?.active_sessions ?? 0).toLocaleString()}
                      </Typography>
                      <Typography sx={{ fontSize: '0.72rem', color: 'text.secondary', mt: 0.25, fontWeight: 500 }}>
                        {t('stats.sessions')}
                      </Typography>
                    </Box>
                  </Box>
                  <Box sx={{ flex: 1, minHeight: 0 }}>
                    <RealTimeStats
                      title={t('charts.realTimeData')}
                      data={realTimeData}
                      granularity={timeScaleMinutes}
                      onGranularityChange={setTimeScaleMinutes}
                    />
                  </Box>
                  <Box sx={{ mt: 2.5, pt: 2.5, borderTop: '1px solid', borderColor: 'divider' }}>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, mb: 0.75 }}>
                      <Typography sx={{ fontSize: '0.68rem', color: 'text.disabled', fontWeight: 600, letterSpacing: '0.05em', textTransform: 'uppercase' }}>
                        {t('latestMessage.label')}
                      </Typography>
                      {latestMessage ? (
                        <Typography sx={{ fontSize: '0.68rem', color: 'text.disabled', fontWeight: 500 }}>
                          {formatRelativeTime(latestMessage.create_time, t)}
                        </Typography>
                      ) : null}
                    </Box>
                    {latestMessage ? (
                      <Box sx={{ display: 'flex', alignItems: 'baseline', gap: 1, minWidth: 0 }}>
                        <Typography sx={{ fontSize: '0.78rem', color: 'text.secondary', fontWeight: 600, flexShrink: 0 }}>
                          {latestMessage.sender_name}
                        </Typography>
                        <Typography
                          sx={{
                            fontSize: '0.78rem',
                            color: 'text.primary',
                            fontWeight: 500,
                            whiteSpace: 'nowrap',
                            overflow: 'hidden',
                            textOverflow: 'ellipsis',
                            minWidth: 0,
                          }}
                        >
                          {latestMessage.content}
                        </Typography>
                      </Box>
                    ) : (
                      <Typography sx={{ fontSize: '0.78rem', color: 'text.disabled' }}>
                        {t('latestMessage.empty')}
                      </Typography>
                    )}
                  </Box>
                </motion.div>
              ) : selectedTrace ? (
                <motion.div
                  key={`trace-${selectedTraceId}`}
                  initial={{ opacity: 0, x: 12 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0, x: -12 }}
                  transition={{ duration: 0.25, ease: [0.4, 0, 0.2, 1] }}
                  style={{ flex: 1, minHeight: 0, overflow: 'auto' }}
                >
                  <Box sx={{
                    py: 2,
                    px: 3,
                    maxWidth: '100%',
                    overflow: 'hidden',
                  }}>
                    <TraceDetailContent
                      log={selectedTrace}
                      isMobile={isMobile}
                      isSmall={isSmall}
                      onCopy={(text) => {
                        if (text) navigator.clipboard.writeText(text).catch(() => {})
                      }}
                    />
                  </Box>
                </motion.div>
              ) : (
                <motion.div
                  key="empty"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center' }}
                >
                  <Typography sx={{ color: 'text.secondary' }}>{t('panels.noTrace')}</Typography>
                </motion.div>
              )}
            </AnimatePresence>
          </Box>
        </Paper>
      </Box>
    </Box>
  )
}

const DashboardPage: React.FC = () => {
  const queryClient = new QueryClient()
  return (
    <QueryClientProvider client={queryClient}>
      <DashboardContent />
    </QueryClientProvider>
  )
}

export default DashboardPage
