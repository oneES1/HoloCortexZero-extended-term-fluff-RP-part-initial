import React, { useState } from 'react'
import {
  Box,
  Table,
  TableBody,
  TableCell,
  TableRow,
  Tooltip,
  Dialog,
  Button,
  CircularProgress,
  Typography,
  Chip,
  TextField,
  IconButton,
  useTheme,
  useMediaQuery,
} from '@mui/material'
import VisibilityOutlined from '@mui/icons-material/VisibilityOutlined'
import Block from '@mui/icons-material/Block'
import HowToReg from '@mui/icons-material/HowToReg'
import LockOutlined from '@mui/icons-material/LockOutlined'
import LockOpenOutlined from '@mui/icons-material/LockOpenOutlined'
import DeleteOutline from '@mui/icons-material/DeleteOutline'
import { User } from '../../../services/api/user-manager'
import { format } from 'date-fns'
import { useTranslation } from 'react-i18next'

interface UserTableProps {
  users: User[]
  loading: boolean
  onViewDetail: (userId: number) => void
  onDeleteUser: (userId: number) => Promise<unknown>
  onBanUser: (params: { id: number; banUntil: string | null }) => Promise<unknown>
  onSetPreventTrigger: (params: {
    id: number
    preventTriggerUntil: string | null
  }) => Promise<unknown>
  tableProps?: React.ComponentProps<typeof Table>
}

const PRESETS = [
  { label: '1h', days: 0, hours: 1, minutes: 0 },
  { label: '6h', days: 0, hours: 6, minutes: 0 },
  { label: '1d', days: 1, hours: 0, minutes: 0 },
  { label: '7d', days: 7, hours: 0, minutes: 0 },
  { label: '30d', days: 30, hours: 0, minutes: 0 },
]

const UserTable: React.FC<UserTableProps> = ({
  users,
  loading,
  onViewDetail,
  onDeleteUser,
  onBanUser,
  onSetPreventTrigger,
  tableProps,
}) => {
  const { t } = useTranslation('user-manager')
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false)
  const [banDialogOpen, setBanDialogOpen] = useState(false)
  const [preventTriggerDialogOpen, setPreventTriggerDialogOpen] = useState(false)
  const [selectedUser, setSelectedUser] = useState<User | null>(null)
  const [banDuration, setBanDuration] = useState({ days: 0, hours: 0, minutes: 0 })
  const [preventTriggerDuration, setPreventTriggerDuration] = useState({ days: 0, hours: 0, minutes: 0 })
  const [isPermanentBan, setIsPermanentBan] = useState(false)
  const [isPermanentPreventTrigger, setIsPermanentPreventTrigger] = useState(false)

  const theme = useTheme()
  const isMobile = useMediaQuery(theme.breakpoints.down('md'))
  const isSmall = useMediaQuery(theme.breakpoints.down('sm'))

  const handleDeleteClick = (user: User) => {
    setSelectedUser(user)
    setDeleteDialogOpen(true)
  }

  const handleBanClick = (user: User) => {
    setSelectedUser(user)
    setBanDuration({ days: 0, hours: 0, minutes: 0 })
    setIsPermanentBan(false)
    setBanDialogOpen(true)
  }

  const handlePreventTriggerClick = (user: User) => {
    setSelectedUser(user)
    setPreventTriggerDuration({ days: 0, hours: 0, minutes: 0 })
    setIsPermanentPreventTrigger(false)
    setPreventTriggerDialogOpen(true)
  }

  const handleDeleteConfirm = async () => {
    if (selectedUser) {
      await onDeleteUser(selectedUser.id)
      setDeleteDialogOpen(false)
    }
  }

  const calculateEndTime = (duration: { days: number; hours: number; minutes: number }) => {
    const { days, hours, minutes } = duration
    if (days === 0 && hours === 0 && minutes === 0) {
      return null
    }
    const now = new Date()
    now.setDate(now.getDate() + days)
    now.setHours(now.getHours() + hours)
    now.setMinutes(now.getMinutes() + minutes)
    return now.toISOString()
  }

  const handleBanConfirm = async () => {
    if (selectedUser) {
      await onBanUser({
        id: selectedUser.id,
        banUntil: isPermanentBan ? '2099-12-31T23:59:59Z' : calculateEndTime(banDuration),
      })
      setBanDialogOpen(false)
    }
  }

  const handlePreventTriggerConfirm = async () => {
    if (selectedUser) {
      await onSetPreventTrigger({
        id: selectedUser.id,
        preventTriggerUntil: isPermanentPreventTrigger
          ? '2099-12-31T23:59:59Z'
          : calculateEndTime(preventTriggerDuration),
      })
      setPreventTriggerDialogOpen(false)
    }
  }

  const formatDate = (dateString: string | null) => {
    if (!dateString) return t('common.none', { ns: 'common' })
    try {
      return format(new Date(dateString), isMobile ? 'MM-dd HH:mm' : 'yyyy-MM-dd HH:mm:ss')
    } catch {
      return t('common.invalidDate', { ns: 'common' })
    }
  }

  const DurationSelector = ({
    duration,
    setDuration,
    isPermanent,
    setIsPermanent,
    title,
  }: {
    duration: { days: number; hours: number; minutes: number }
    setDuration: React.Dispatch<React.SetStateAction<{ days: number; hours: number; minutes: number }>>
    isPermanent: boolean
    setIsPermanent: React.Dispatch<React.SetStateAction<boolean>>
    title: string
  }) => {
    const [activePreset, setActivePreset] = useState<string | null>(null)

    const applyPreset = (preset: typeof PRESETS[0]) => {
      setIsPermanent(false)
      setActivePreset(preset.label)
      setDuration({ days: preset.days, hours: preset.hours, minutes: preset.minutes })
    }

    const togglePermanent = () => {
      const next = !isPermanent
      setIsPermanent(next)
      if (next) {
        setActivePreset('permanent')
      } else {
        setActivePreset(null)
      }
    }

    const handleInputChange =
      (field: 'days' | 'hours' | 'minutes') => (e: React.ChangeEvent<HTMLInputElement>) => {
        if (isPermanent) return
        const value = parseInt(e.target.value) || 0
        const maxValues = { days: 365, hours: 24, minutes: 60 }
        setDuration(prev => ({ ...prev, [field]: Math.max(0, Math.min(value, maxValues[field])) }))
        setActivePreset(null)
      }

    return (
      <Box sx={{ pt: 1 }}>
        <Typography variant="subtitle2" sx={{ fontWeight: 600, mb: 2 }}>
          {title}
        </Typography>

        <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, mb: 3 }}>
          {PRESETS.map(preset => (
            <Chip
              key={preset.label}
              label={preset.label}
              onClick={() => applyPreset(preset)}
              variant={activePreset === preset.label ? 'filled' : 'outlined'}
              color={activePreset === preset.label ? 'primary' : 'default'}
              sx={{
                borderRadius: 1.5,
                fontWeight: 500,
                px: 0.5,
                transition: 'all 0.2s ease',
                cursor: 'pointer',
              }}
            />
          ))}
          <Chip
            label={t('duration.permanent')}
            onClick={togglePermanent}
            variant={activePreset === 'permanent' ? 'filled' : 'outlined'}
            color={activePreset === 'permanent' ? 'error' : 'default'}
            sx={{
              borderRadius: 1.5,
              fontWeight: 500,
              px: 0.5,
              transition: 'all 0.2s ease',
              cursor: 'pointer',
            }}
          />
        </Box>

        <Box
          sx={{
            display: 'flex',
            gap: 2,
            alignItems: 'center',
            opacity: isPermanent ? 0.4 : 1,
            pointerEvents: isPermanent ? 'none' : 'auto',
            transition: 'opacity 0.2s ease',
          }}
        >
          <TextField
            label={t('duration.days')}
            type="number"
            size="small"
            value={duration.days}
            onChange={handleInputChange('days')}
            InputProps={{
              inputProps: { min: 0 },
            }}
            sx={{ flex: 1 }}
          />
          <TextField
            label={t('duration.hours')}
            type="number"
            size="small"
            value={duration.hours}
            onChange={handleInputChange('hours')}
            InputProps={{
              inputProps: { min: 0, max: 24 },
            }}
            sx={{ flex: 1 }}
          />
          <TextField
            label={t('duration.minutes')}
            type="number"
            size="small"
            value={duration.minutes}
            onChange={handleInputChange('minutes')}
            InputProps={{
              inputProps: { min: 0, max: 60 },
            }}
            sx={{ flex: 1 }}
          />
        </Box>
      </Box>
    )
  }

  return (
    <>
      <Table
        size={isSmall ? 'small' : 'medium'}
        sx={{ tableLayout: 'fixed', width: '100%' }}
        {...tableProps}
      >
        <TableBody>
          {loading ? (
            <TableRow>
              <TableCell colSpan={2} align="center" sx={{ py: 4 }}>
                <CircularProgress size={24} />
              </TableCell>
            </TableRow>
          ) : users.length === 0 ? (
            <TableRow>
              <TableCell colSpan={2} align="center" sx={{ py: 4 }}>
                {t('list.noData')}
              </TableCell>
            </TableRow>
          ) : (
            users.map(user => (
              <TableRow key={user.id} hover>
                <TableCell
                  sx={{
                    width: '100%',
                    py: isSmall ? 0.9 : 1.1,
                  }}
                >
                  <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.45, minWidth: 0 }}>
                    <Typography
                      variant={isSmall ? 'body2' : 'subtitle2'}
                      sx={{ fontWeight: 600, lineHeight: 1.25 }}
                    >
                      {user.username || '-'}
                    </Typography>
                    <Box
                      sx={{
                        display: 'flex',
                        alignItems: 'center',
                        flexWrap: 'wrap',
                        columnGap: 1.5,
                        rowGap: 0.35,
                        color: 'text.secondary',
                      }}
                    >
                      <Typography variant="caption" sx={{ lineHeight: 1.35 }}>
                        {t('table.adapterPlatform')}: {user.adapter_key || '-'}
                      </Typography>
                      <Typography variant="caption" sx={{ lineHeight: 1.35 }}>
                        {t('table.platformUserId')}: {user.platform_userid || '-'}
                      </Typography>
                      <Typography variant="caption" sx={{ lineHeight: 1.35 }}>
                        {t('table.createdAt')}: {formatDate(user.create_time)}
                      </Typography>
                    </Box>
                  </Box>
                </TableCell>
                <TableCell
                  align="right"
                  sx={{
                    width: '1%',
                    whiteSpace: 'nowrap',
                    py: isSmall ? 0.75 : 0.9,
                  }}
                >
                  <Box sx={{ display: 'flex', justifyContent: 'flex-end', gap: 0.25 }}>
                    <Tooltip title={t('tooltips.view')}>
                      <IconButton
                        size="small"
                        onClick={() => onViewDetail(user.id)}
                        sx={{
                          color: 'text.secondary',
                          '&:hover': { color: 'primary.main', bgcolor: 'primary.50' },
                        }}
                      >
                        <VisibilityOutlined fontSize="small" />
                      </IconButton>
                    </Tooltip>
                    <Tooltip title={user.is_active ? t('tooltips.ban') : t('tooltips.unban')}>
                      <IconButton
                        size="small"
                        onClick={() => handleBanClick(user)}
                        sx={{
                          color: user.is_active ? 'warning.main' : 'success.main',
                          '&:hover': {
                            bgcolor: user.is_active ? 'warning.50' : 'success.50',
                          },
                        }}
                      >
                        {user.is_active ? (
                          <Block fontSize="small" />
                        ) : (
                          <HowToReg fontSize="small" />
                        )}
                      </IconButton>
                    </Tooltip>
                    <Tooltip
                      title={
                        !user.is_prevent_trigger
                          ? t('tooltips.preventTrigger')
                          : t('tooltips.restoreTrigger')
                      }
                    >
                      <IconButton
                        size="small"
                        onClick={() => handlePreventTriggerClick(user)}
                        sx={{
                          color: !user.is_prevent_trigger ? 'secondary.main' : 'info.main',
                          '&:hover': {
                            bgcolor: !user.is_prevent_trigger ? 'secondary.50' : 'info.50',
                          },
                        }}
                      >
                        {!user.is_prevent_trigger ? (
                          <LockOutlined fontSize="small" />
                        ) : (
                          <LockOpenOutlined fontSize="small" />
                        )}
                      </IconButton>
                    </Tooltip>
                    <Tooltip title={t('tooltips.delete')}>
                      <IconButton
                        size="small"
                        onClick={() => handleDeleteClick(user)}
                        sx={{
                          color: 'error.main',
                          '&:hover': { bgcolor: 'error.50' },
                        }}
                      >
                        <DeleteOutline fontSize="small" />
                      </IconButton>
                    </Tooltip>
                  </Box>
                </TableCell>
              </TableRow>
            ))
          )}
        </TableBody>
      </Table>

      <Dialog
        open={deleteDialogOpen}
        onClose={() => setDeleteDialogOpen(false)}
        PaperProps={{
          sx: {
            borderRadius: 3,
            overflow: 'hidden',
            width: '100%',
            maxWidth: 420,
            boxShadow: theme.shadows[24],
          },
        }}
      >
        <Box sx={{ p: isSmall ? 2.5 : 4, textAlign: 'center' }}>
          <Box
            sx={{
              width: 64,
              height: 64,
              borderRadius: '50%',
              bgcolor: 'error.50',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              mx: 'auto',
              mb: 2,
            }}
          >
            <DeleteOutline sx={{ fontSize: 32, color: 'error.main' }} />
          </Box>
          <Typography variant="h6" sx={{ fontWeight: 700, mb: 1 }}>
            {t('dialogs.deleteTitle')}
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
            {t('dialogs.deleteConfirm', { username: selectedUser?.username })}
          </Typography>

          <Box sx={{ display: 'flex', gap: 1.5 }}>
            <Button
              fullWidth
              variant="outlined"
              onClick={() => setDeleteDialogOpen(false)}
              size="medium"
              sx={{ borderRadius: 2, textTransform: 'none', fontWeight: 600 }}
            >
              {t('actions.cancel', { ns: 'common' })}
            </Button>
            <Button
              fullWidth
              variant="contained"
              color="error"
              onClick={handleDeleteConfirm}
              size="medium"
              sx={{ borderRadius: 2, textTransform: 'none', fontWeight: 600 }}
            >
              {t('actions.delete', { ns: 'common' })}
            </Button>
          </Box>
        </Box>
      </Dialog>

      <Dialog
        open={banDialogOpen}
        onClose={() => setBanDialogOpen(false)}
        PaperProps={{
          sx: {
            borderRadius: 3,
            overflow: 'hidden',
            width: '100%',
            maxWidth: 480,
            boxShadow: theme.shadows[24],
          },
        }}
      >
        <Box sx={{ px: isSmall ? 2.5 : 4, pt: isSmall ? 2.5 : 3.5, pb: 1 }}>
          <Typography variant="h6" sx={{ fontWeight: 700 }}>
            {selectedUser?.is_active ? t('tooltips.ban') : t('dialogs.unbanTitle')}
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
            {selectedUser?.username}
          </Typography>
        </Box>
        <Box sx={{ px: isSmall ? 2.5 : 4, pb: isSmall ? 2 : 3 }}>
          {selectedUser?.is_active ? (
            <DurationSelector
              duration={banDuration}
              setDuration={setBanDuration}
              isPermanent={isPermanentBan}
              setIsPermanent={setIsPermanentBan}
              title={t('duration.banTitle')}
            />
          ) : (
            <Box sx={{ py: 2 }}>
              <Typography variant="body1" color="text.secondary">
                {t('dialogs.unbanConfirm', { username: selectedUser?.username })}
              </Typography>
            </Box>
          )}
        </Box>
        <Box
          sx={{
            display: 'flex',
            justifyContent: 'flex-end',
            gap: 1.5,
            px: isSmall ? 2.5 : 4,
            pb: isSmall ? 2 : 3,
            pt: 1,
          }}
        >
          <Button
            variant="outlined"
            onClick={() => setBanDialogOpen(false)}
            size="medium"
            sx={{ borderRadius: 2, textTransform: 'none', fontWeight: 600, minWidth: 96 }}
          >
            {t('actions.cancel', { ns: 'common' })}
          </Button>
          <Button
            variant="contained"
            onClick={handleBanConfirm}
            size="medium"
            sx={{ borderRadius: 2, textTransform: 'none', fontWeight: 600, minWidth: 96 }}
          >
            {t('actions.confirm', { ns: 'common' })}
          </Button>
        </Box>
      </Dialog>

      <Dialog
        open={preventTriggerDialogOpen}
        onClose={() => setPreventTriggerDialogOpen(false)}
        PaperProps={{
          sx: {
            borderRadius: 3,
            overflow: 'hidden',
            width: '100%',
            maxWidth: 480,
            boxShadow: theme.shadows[24],
          },
        }}
      >
        <Box sx={{ px: isSmall ? 2.5 : 4, pt: isSmall ? 2.5 : 3.5, pb: 1 }}>
          <Typography variant="h6" sx={{ fontWeight: 700 }}>
            {!selectedUser?.is_prevent_trigger
              ? t('tooltips.preventTrigger')
              : t('dialogs.restoreTriggerTitle')}
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
            {selectedUser?.username}
          </Typography>
        </Box>
        <Box sx={{ px: isSmall ? 2.5 : 4, pb: isSmall ? 2 : 3 }}>
          {!selectedUser?.is_prevent_trigger ? (
            <DurationSelector
              duration={preventTriggerDuration}
              setDuration={setPreventTriggerDuration}
              isPermanent={isPermanentPreventTrigger}
              setIsPermanent={setIsPermanentPreventTrigger}
              title={t('duration.preventTriggerTitle')}
            />
          ) : (
            <Box sx={{ py: 2 }}>
              <Typography variant="body1" color="text.secondary">
                {t('dialogs.restoreTriggerConfirm', { username: selectedUser?.username })}
              </Typography>
            </Box>
          )}
        </Box>
        <Box
          sx={{
            display: 'flex',
            justifyContent: 'flex-end',
            gap: 1.5,
            px: isSmall ? 2.5 : 4,
            pb: isSmall ? 2 : 3,
            pt: 1,
          }}
        >
          <Button
            variant="outlined"
            onClick={() => setPreventTriggerDialogOpen(false)}
            size="medium"
            sx={{ borderRadius: 2, textTransform: 'none', fontWeight: 600, minWidth: 96 }}
          >
            {t('actions.cancel', { ns: 'common' })}
          </Button>
          <Button
            variant="contained"
            onClick={handlePreventTriggerConfirm}
            size="medium"
            sx={{ borderRadius: 2, textTransform: 'none', fontWeight: 600, minWidth: 96 }}
          >
            {t('actions.confirm', { ns: 'common' })}
          </Button>
        </Box>
      </Dialog>
    </>
  )
}

export default UserTable
