import { Box, Button, Stack, Typography, useTheme } from '@mui/material'
import { useTranslation } from 'react-i18next'
import HCZDialog from '../../../components/common/HCZDialog'
import type { LogEntry } from '../../../services/api/logs'

const LEVEL_META: Record<string, { color: string }> = {
  DEBUG: { color: '#8e8e93' },
  INFO: { color: '#5c9dff' },
  WARNING: { color: '#ff9f0a' },
  ERROR: { color: '#ff453a' },
  SUCCESS: { color: '#32d74b' },
}

const MONO =
  "'ui-monospace', 'SFMono-Regular', 'SF Mono', 'JetBrains Mono', 'Fira Code', 'Menlo', 'Consolas', 'monospace'"

interface LogDetailDialogProps {
  log: LogEntry | null
  onClose: () => void
  onCopy: (log: LogEntry) => void
  open: boolean
}

export default function LogDetailDialog({
  log,
  onClose,
  onCopy,
  open,
}: LogDetailDialogProps) {
  const { t } = useTranslation('logs')
  const theme = useTheme()
  const meta = log ? LEVEL_META[log.level] || LEVEL_META.DEBUG : null

  return (
    <HCZDialog
      open={open}
      onClose={onClose}
      maxWidth="md"
      fullWidth
      title={
        log && (
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
            <Box
              sx={{
                width: 8,
                height: 8,
                borderRadius: '50%',
                backgroundColor: meta?.color,
                boxShadow: `0 0 8px ${meta?.color}`,
              }}
            />
            <Typography
              variant="h6"
              sx={{
                fontFamily: MONO,
                fontSize: '0.9rem',
                fontWeight: 600,
                letterSpacing: '0.04em',
              }}
            >
              {log.level}
            </Typography>
          </Box>
        )
      }
      titleActions={
        log && (
          <Button
            onClick={() => onCopy(log)}
            size="small"
            sx={{ textTransform: 'none', color: 'text.secondary' }}
          >
            {t('actions.copy', { ns: 'common' })}
          </Button>
        )
      }
      actions={
        <Button onClick={onClose} variant="contained" color="primary" size="small">
          {t('dialog.close')}
        </Button>
      }
    >
      {log && (
        <Stack spacing={2.5}>
          <Box
            sx={{
              display: 'grid',
              gridTemplateColumns: '72px 1fr',
              rowGap: 1,
              columnGap: 2,
            }}
          >
            <Typography variant="body2" sx={{ color: 'text.disabled', fontSize: '0.8rem' }}>
              {t('dialog.time')}
            </Typography>
            <Typography
              variant="body2"
              sx={{ fontFamily: MONO, fontSize: '0.85rem', color: 'text.primary' }}
            >
              {log.timestamp}
            </Typography>

            <Typography variant="body2" sx={{ color: 'text.disabled', fontSize: '0.8rem' }}>
              {t('dialog.source')}
            </Typography>
            <Typography
              variant="body2"
              sx={{ fontFamily: MONO, fontSize: '0.85rem', color: 'text.primary' }}
            >
              {log.source}
            </Typography>

            <Typography variant="body2" sx={{ color: 'text.disabled', fontSize: '0.8rem' }}>
              {t('dialog.module')}
            </Typography>
            <Typography
              variant="body2"
              sx={{ fontFamily: MONO, fontSize: '0.85rem', color: 'text.primary' }}
            >
              {log.function}
            </Typography>

            <Typography variant="body2" sx={{ color: 'text.disabled', fontSize: '0.8rem' }}>
              {t('dialog.line')}
            </Typography>
            <Typography
              variant="body2"
              sx={{ fontFamily: MONO, fontSize: '0.85rem', color: 'text.primary' }}
            >
              {t('dialog.lineNumber', { line: log.line })}
            </Typography>
          </Box>

          <Box>
            <Typography
              variant="body2"
              sx={{ color: 'text.disabled', fontSize: '0.8rem', mb: 1 }}
            >
              {t('dialog.messageContent')}
            </Typography>
            <Box
              sx={{
                p: 2,
                backgroundColor: theme.palette.action.hover,
                border: `1px solid ${theme.palette.divider}`,
                borderRadius: '10px',
                fontFamily: MONO,
                fontSize: '0.85rem',
                color: 'text.primary',
                whiteSpace: 'pre-wrap',
                wordBreak: 'break-word',
                maxHeight: '50vh',
                overflow: 'auto',
                lineHeight: 1.6,
              }}
            >
              {log.message}
            </Box>
          </Box>
        </Stack>
      )}
    </HCZDialog>
  )
}
