import { Box } from '@mui/material'
import { Outlet } from 'react-router-dom'

export const manageTabs = [
  { label: 'nav.system', path: '/settings/system' },
  { label: 'nav.prompts', path: '/manage/prompts' },
  { label: 'nav.tools', path: '/manage/tools' },
] as const

export default function ManagePage() {
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
