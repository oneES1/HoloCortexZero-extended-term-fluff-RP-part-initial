import { memo } from 'react'
import { Box, useTheme } from '@mui/material'
import type { LogEntry } from '../../../services/api/logs'

const LEVEL_META: Record<string, { color: string; bar: string }> = {
  DEBUG: { color: '#8e8e93', bar: '#8e8e93' },
  INFO: { color: '#5c9dff', bar: '#5c9dff' },
  WARNING: { color: '#ff9f0a', bar: '#ff9f0a' },
  ERROR: { color: '#ff453a', bar: '#ff453a' },
  SUCCESS: { color: '#32d74b', bar: '#32d74b' },
}

const MONO =
  "'ui-monospace', 'SFMono-Regular', 'SF Mono', 'JetBrains Mono', 'Fira Code', 'Menlo', 'Consolas', 'monospace'"

interface LogsTableRowProps {
  index: number
  style: React.CSSProperties
  log: LogEntry
  isMobile: boolean
  isSmall: boolean
  onLogClick: (log: LogEntry) => void
}

function LogsTableRowComponent({
  index,
  style,
  log,
  isMobile,
  isSmall,
  onLogClick,
}: LogsTableRowProps) {
  const theme = useTheme()
  const meta = LEVEL_META[log.level] || LEVEL_META.DEBUG

  return (
    <Box
      style={style}
      onClick={() => onLogClick(log)}
      sx={{
        cursor: 'pointer',
        display: 'flex',
        alignItems: 'center',
        px: 2,
        backgroundColor:
          index % 2 === 1
            ? (theme.palette.mode === 'dark' ? 'rgba(255,255,255,0.015)' : 'rgba(15,23,42,0.018)')
            : 'transparent',
        transition: 'background-color 0.12s ease',
        '&:hover': {
          backgroundColor: theme.palette.action.hover,
        },
      }}
    >
      <Box
        sx={{
          width: 3,
          height: 16,
          borderRadius: '2px',
          backgroundColor: meta.bar,
          mr: 1.5,
          flexShrink: 0,
        }}
      />
      <Box
        sx={{
          flex: isMobile ? '0 0 120px' : '0 0 172px',
          fontFamily: MONO,
          fontSize: isSmall ? '0.7rem' : '0.75rem',
          color: 'text.disabled',
          whiteSpace: 'nowrap',
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          flexShrink: 0,
        }}
      >
        {log.timestamp}
      </Box>
      <Box
        sx={{
          flex: '0 0 72px',
          fontFamily: MONO,
          fontSize: isSmall ? '0.62rem' : '0.68rem',
          fontWeight: 600,
          letterSpacing: '0.06em',
          textTransform: 'uppercase',
          color: meta.color,
          flexShrink: 0,
        }}
      >
        {log.level}
      </Box>
      <Box
        sx={{
          flex: 1,
          minWidth: 0,
          fontFamily: MONO,
          fontSize: isSmall ? '0.72rem' : '0.78rem',
          color: 'text.primary',
          whiteSpace: 'nowrap',
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          pl: 1,
        }}
      >
        {log.message}
      </Box>
      {!isMobile && (
        <Box
          sx={{
            flex: '0 0 140px',
            fontFamily: MONO,
            fontSize: '0.7rem',
            color: 'text.disabled',
            textAlign: 'right',
            whiteSpace: 'nowrap',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            pl: 1,
            flexShrink: 0,
          }}
        >
          {log.source}
        </Box>
      )}
    </Box>
  )
}

const LogsTableRow = memo(LogsTableRowComponent)
LogsTableRow.displayName = 'LogsTableRow'

export default LogsTableRow
