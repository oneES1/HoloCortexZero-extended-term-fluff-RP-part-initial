import { useState, useEffect, useRef } from 'react'
import {
  Box,
  Chip,
  FormControlLabel,
  Switch,
  Button,
  Typography,
  alpha,
  useTheme,
  Stack,
} from '@mui/material'
import { useQuery } from '@tanstack/react-query'
import { oneBotV11Api } from '../../../services/api/adapters/onebot_v11'
import { useTranslation } from 'react-i18next'
import { useNotification } from '../../../hooks/useNotification'

const extractWebuiToken = (logs: string[]): string | undefined => {
  if (!logs?.length) return undefined
  const tokenRegex = /WebUi Local Panel Url: http:\/\/[^?]+\?token=([^\s]+)/
  for (let i = logs.length - 1; i >= 0; i--) {
    const match = logs[i].match(tokenRegex)
    if (match) return match[1]
  }
  return undefined
}

export default function OneBotV11LogsPage() {
  const [autoScroll, setAutoScroll] = useState(true)
  const [logs, setLogs] = useState<string[]>([])
  const [isReconnecting, setIsReconnecting] = useState(false)
  const [webuiToken, setWebuiToken] = useState<string>()
  const tableContainerRef = useRef<HTMLDivElement>(null)
  const notification = useNotification()
  const { t } = useTranslation('adapter')
  const theme = useTheme()

  const { data: status } = useQuery({
    queryKey: ['onebot-v11-container-status'],
    queryFn: () => oneBotV11Api.getContainerStatus(),
    refetchInterval: 5000,
  })

  useEffect(() => {
    let cleanup: (() => void) | undefined

    const connect = () => {
      try {
        cleanup = oneBotV11Api.streamContainerLogs(
          (data) => {
            setLogs((prev) => {
              const newLogs = [...prev, data].slice(-1000)
              setWebuiToken(extractWebuiToken(newLogs))
              return newLogs
            })
            setIsReconnecting(false)
          },
          () => {
            setIsReconnecting(true)
            setTimeout(() => connect(), 5000)
          }
        )
      } catch {
        setIsReconnecting(true)
      }
    }

    oneBotV11Api.getContainerLogs(500).then((logs) => {
      setLogs(logs || [])
      setWebuiToken(extractWebuiToken(logs || []))
    })

    connect()

    return () => {
      cleanup?.()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    if (autoScroll && tableContainerRef.current) {
      requestAnimationFrame(() => {
        if (tableContainerRef.current) {
          const { scrollHeight, clientHeight } = tableContainerRef.current
          tableContainerRef.current.scrollTop = scrollHeight - clientHeight
        }
      })
    }
  }, [logs, autoScroll])

  const handleAutoScrollChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    setAutoScroll(event.target.checked)
  }

  const handleClearLogs = () => {
    setLogs([])
    notification.success(t('logs.cleared'))
  }

  const handleCopyToken = async () => {
    if (webuiToken) {
      try {
        await navigator.clipboard.writeText(webuiToken)
        notification.success(t('logs.tokenCopied'))
      } catch {
        notification.error(t('logs.copyFailed'))
      }
    }
  }

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
      {/* 顶部工具栏 */}
      <Stack
        direction="row"
        spacing={1.5}
        alignItems="center"
        flexWrap="wrap"
        sx={{ flexShrink: 0 }}
      >
        <Chip
          size="small"
          label={status?.running ? 'running' : 'stopped'}
          color={status?.running ? 'success' : 'error'}
          sx={{ fontWeight: 600, borderRadius: 1.5 }}
        />
        {isReconnecting && (
          <Chip size="small" label={t('logs.disconnected')} color="warning" sx={{ fontWeight: 600, borderRadius: 1.5 }} />
        )}
        {webuiToken && !isReconnecting && (
          <Button
            variant="text"
            size="small"
            onClick={handleCopyToken}
            sx={{ textTransform: 'none' }}
          >
            {t('logs.copyToken')}
          </Button>
        )}
        <Box sx={{ flex: 1 }} />
        <FormControlLabel
          control={<Switch checked={autoScroll} onChange={handleAutoScrollChange} size="small" />}
          label={
            <Typography variant="caption" color="text.secondary" sx={{ opacity: 0.7 }}>
              {t('logs.autoScroll')}
            </Typography>
          }
        />
        <Button
          variant="text"
          size="small"
          onClick={handleClearLogs}
          sx={{ textTransform: 'none' }}
        >
          {t('logs.clear')}
        </Button>
      </Stack>

      {/* 日志区域 */}
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
          ref={tableContainerRef}
          sx={{
            position: 'absolute',
            inset: 12,
            overflow: 'auto',
            fontFamily: '"JetBrains Mono", "Fira Code", "Courier New", Consolas, monospace',
            fontSize: '13px',
            lineHeight: 1.65,
            '&::-webkit-scrollbar': { width: 5 },
            '&::-webkit-scrollbar-thumb': {
              background: alpha(theme.palette.primary.main, 0.15),
              borderRadius: 6,
            },
          }}
        >
          {logs.map((log, index) => (
            <Box
              key={index}
              sx={{
                py: 0.5,
                px: 1.25,
                borderRadius: 1,
                fontFamily: 'inherit',
                whiteSpace: 'pre-wrap',
                wordBreak: 'break-all',
                color: theme.palette.text.primary,
                ...(index % 2 === 0 && {
                  bgcolor:
                    theme.palette.mode === 'dark'
                      ? alpha(theme.palette.common.white, 0.02)
                      : alpha(theme.palette.common.black, 0.01),
                }),
                '&:hover': {
                  bgcolor: alpha(theme.palette.primary.main, 0.04),
                },
              }}
            >
              {log}
            </Box>
          ))}
          {logs.length === 0 && (
            <Typography variant="body2" color="text.secondary" sx={{ textAlign: 'center', py: 4, opacity: 0.6 }}>
              {t('logs.tokenNotFound')}
            </Typography>
          )}
        </Box>
      </Box>
    </Box>
  )
}
