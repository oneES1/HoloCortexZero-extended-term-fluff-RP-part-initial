import { Box } from '@mui/material'
import { Outlet } from 'react-router-dom'

export const monitorTabs = [
  { label: 'nav.dashboard', path: '/monitor/dashboard' },
  { label: 'nav.logs', path: '/monitor/logs' },
  { label: 'nav.traces', path: '/monitor/traces' },
  { label: 'nav.channels', path: '/monitor/channels' },
] as const

export default function MonitorPage() {
  return (
    <Box
      sx={{
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        minHeight: 0,
        overflow: 'hidden',
      }}
    >
      <Box sx={{ flex: 1, minHeight: 0, overflow: 'hidden' }}>
        <Outlet />
      </Box>
    </Box>
  )
}
