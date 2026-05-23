import { useState, useEffect, useRef, useMemo, useCallback } from 'react'
import { Alert, Box, MenuItem, TextField, useMediaQuery, useTheme } from '@mui/material'
import { useQuery } from '@tanstack/react-query'
import { FixedSizeList as List, type ListOnScrollProps } from 'react-window'
import AutoSizer from 'react-virtualized-auto-sizer'
import { useTranslation } from 'react-i18next'
import type { LogEntry } from '../../services/api/logs'
import { logsApi } from '../../services/api/logs'
import {
  INITIAL_LOGS_COUNT,
  LOG_UPDATE_INTERVAL,
  MAX_REALTIME_LOGS,
  ROW_HEIGHT,
} from './constants'
import LogDetailDialog from './components/LogDetailDialog'
import LogsTableRow from './components/LogsTableRow'

interface LogsFiltersState {
  level: string
  message: string
}

export default function LogsPage() {
  const [realtimeLogs, setRealtimeLogs] = useState<LogEntry[]>([])
  const [isDisconnected, setIsDisconnected] = useState(false)
  const [filters, setFilters] = useState<LogsFiltersState>({
    level: '',
    message: '',
  })
  const [selectedLog, setSelectedLog] = useState<LogEntry | null>(null)
  const [dialogOpen, setDialogOpen] = useState(false)
  const [shouldStickToBottom, setShouldStickToBottom] = useState(true)
  const [viewportHeight, setViewportHeight] = useState(0)

  const listRef = useRef<List>(null)
  const logQueue = useRef<LogEntry[]>([])

  const theme = useTheme()
  const isMobile = useMediaQuery(theme.breakpoints.down('md'))
  const isSmall = useMediaQuery(theme.breakpoints.down('sm'))
  const { t } = useTranslation('logs')

  const { data: initialLogs = [] } = useQuery({
    queryKey: ['initial-logs'],
    queryFn: async () => {
      const response = await logsApi.getLogs({
        page: 1,
        pageSize: INITIAL_LOGS_COUNT,
      })
      return response.logs
    },
  })

  useEffect(() => {
    if (initialLogs.length > 0) {
      setRealtimeLogs(initialLogs)
    }
  }, [initialLogs])

  const filteredLogs = useMemo(() => {
    const lowerCaseMessage = filters.message.toLowerCase()
    return realtimeLogs.filter(
      log =>
        (!filters.level || log.level === filters.level) &&
        (!lowerCaseMessage || log.message.toLowerCase().includes(lowerCaseMessage))
    )
  }, [realtimeLogs, filters])

  useEffect(() => {
    if (shouldStickToBottom && listRef.current && filteredLogs.length > 0) {
      setTimeout(() => {
        listRef.current?.scrollToItem(filteredLogs.length - 1, 'end')
      }, 30)
    }
  }, [filteredLogs, shouldStickToBottom])

  useEffect(() => {
    let cleanup: (() => void) | undefined
    const intervalId = setInterval(() => {
      if (logQueue.current.length > 0) {
        const newLogs = [...logQueue.current]
        logQueue.current = []
        setRealtimeLogs(prev => [...prev, ...newLogs].slice(-MAX_REALTIME_LOGS))
      }
    }, LOG_UPDATE_INTERVAL)

    const connect = () => {
      try {
        cleanup = logsApi.streamLogs(
          data => {
            if (!data) return
            try {
              const log = JSON.parse(data) as LogEntry
              logQueue.current.push(log)
            } catch (error) {
              console.error('Failed to parse log data:', error)
            }
          },
          error => {
            console.error('EventSource error:', error)
            setIsDisconnected(true)
          }
        )
        setIsDisconnected(false)
      } catch (error) {
        console.error('Failed to create EventSource:', error)
        setIsDisconnected(true)
      }
    }

    connect()

    return () => {
      cleanup?.()
      clearInterval(intervalId)
    }
  }, [])

  const handleLogClick = useCallback((log: LogEntry) => {
    setSelectedLog(log)
    setDialogOpen(true)
  }, [])

  const copyLogContent = useCallback((log: LogEntry) => {
    const logText = `${log.timestamp} [${log.level}] [${log.source}] ${log.message}`
    navigator.clipboard.writeText(logText).catch(err => console.error('Could not copy log: ', err))
  }, [])

  const handleListScroll = useCallback(
    ({ scrollOffset, scrollUpdateWasRequested }: ListOnScrollProps) => {
      if (scrollUpdateWasRequested) return
      const totalHeight = filteredLogs.length * ROW_HEIGHT
      const threshold = ROW_HEIGHT * 1.5
      const atBottom = scrollOffset >= Math.max(totalHeight - viewportHeight - threshold, 0)
      setShouldStickToBottom(atBottom)
    },
    [filteredLogs.length, viewportHeight]
  )

  const renderRow = useCallback(
    ({ index, style }: { index: number; style: React.CSSProperties }) => {
      const log = filteredLogs[index]
      if (!log) return null

      return (
        <LogsTableRow
          index={index}
          style={style}
          log={log}
          isMobile={isMobile}
          isSmall={isSmall}
          onLogClick={handleLogClick}
        />
      )
    },
    [filteredLogs, handleLogClick, isMobile, isSmall]
  )

  return (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'column',
        height: 'calc(100vh - var(--hcz-page-offset, 64px))',
        minHeight: 0,
        overflow: 'hidden',
        p: 2,
        gap: 1.5,
      }}
    >
      {isDisconnected && (
        <Alert severity="warning" sx={{ flexShrink: 0, borderRadius: '12px' }}>
          {t('status.disconnected')}
        </Alert>
      )}

      <Box
        sx={{
          display: 'flex',
          flexDirection: { xs: 'column', md: 'row' },
          gap: 1.5,
          alignItems: { md: 'center' },
          flexShrink: 0,
          p: 1.5,
          borderRadius: '12px',
          background: theme.palette.background.paper,
          backdropFilter: 'blur(20px) saturate(150%)',
          WebkitBackdropFilter: 'blur(20px) saturate(150%)',
          border: `1px solid ${theme.palette.divider}`,
        }}
      >
        <TextField
          size="small"
          fullWidth
          placeholder={t('filters.messageContent')}
          value={filters.message}
          onChange={event => setFilters(prev => ({ ...prev, message: event.target.value }))}
        />
        <TextField
          select
          size="small"
          value={filters.level}
          onChange={event => setFilters(prev => ({ ...prev, level: event.target.value }))}
          sx={{ width: { xs: '100%', md: 130 }, flexShrink: 0 }}
        >
          <MenuItem value="">{t('filters.all')}</MenuItem>
          <MenuItem value="DEBUG">DEBUG</MenuItem>
          <MenuItem value="INFO">INFO</MenuItem>
          <MenuItem value="WARNING">WARNING</MenuItem>
          <MenuItem value="ERROR">ERROR</MenuItem>
          <MenuItem value="SUCCESS">SUCCESS</MenuItem>
        </TextField>
      </Box>

      <Box
        sx={{
          flexGrow: 1,
          minHeight: 0,
          overflow: 'hidden',
          display: 'flex',
          flexDirection: 'column',
          borderRadius: '12px',
          background: theme.palette.background.paper,
          border: `1px solid ${theme.palette.divider}`,
        }}
      >
        <Box
          sx={{
            display: 'flex',
            alignItems: 'center',
            px: 2,
            py: 1,
            backgroundColor: theme.palette.action.hover,
          }}
        >
          <Box sx={{ width: 3, mr: 1.5, flexShrink: 0 }} />
          <Box
            sx={{
              flex: isMobile ? '0 0 120px' : '0 0 172px',
              fontSize: '0.7rem',
              color: 'text.disabled',
              fontWeight: 600,
              letterSpacing: '0.04em',
              textTransform: 'uppercase',
              flexShrink: 0,
            }}
          >
            {t('header.time')}
          </Box>
          <Box
            sx={{
              flex: '0 0 72px',
              fontSize: '0.7rem',
              color: 'text.disabled',
              fontWeight: 600,
              letterSpacing: '0.04em',
              textTransform: 'uppercase',
              flexShrink: 0,
            }}
          >
            {t('header.level')}
          </Box>
          <Box
            sx={{
              flex: 1,
              fontSize: '0.7rem',
              color: 'text.disabled',
              fontWeight: 600,
              letterSpacing: '0.04em',
              textTransform: 'uppercase',
              pl: 1,
            }}
          >
            {t('header.message')}
          </Box>
          {!isMobile && (
            <Box
              sx={{
                flex: '0 0 140px',
                fontSize: '0.7rem',
                color: 'text.disabled',
                fontWeight: 600,
                letterSpacing: '0.04em',
                textTransform: 'uppercase',
                textAlign: 'right',
                pl: 1,
                flexShrink: 0,
              }}
            >
              {t('header.source')}
            </Box>
          )}
        </Box>

        <Box sx={{ flexGrow: 1, minHeight: 0, overflow: 'hidden' }}>
          <AutoSizer>
            {({ height, width }) => {
              if (viewportHeight !== height) {
                setTimeout(() => setViewportHeight(height), 0)
              }
              return (
                <List
                  ref={listRef}
                  height={height}
                  width={width}
                  itemCount={filteredLogs.length}
                  itemSize={ROW_HEIGHT}
                  overscanCount={20}
                  onScroll={handleListScroll}
                  style={{ overflowX: 'hidden' }}
                >
                  {renderRow}
                </List>
              )
            }}
          </AutoSizer>
        </Box>
      </Box>

      <LogDetailDialog
        log={selectedLog}
        onClose={() => setDialogOpen(false)}
        onCopy={copyLogContent}
        open={dialogOpen}
      />
    </Box>
  )
}
