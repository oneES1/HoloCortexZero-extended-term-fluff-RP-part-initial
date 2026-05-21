import React, { ReactNode } from 'react'
import {
  Dialog as MuiDialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  DialogProps as MuiDialogProps,
  Button,
  Typography,
  Divider,
  Box,
} from '@mui/material'
import { SIDEBAR_GLASS } from '../../theme/glass'
import { useTranslation } from 'react-i18next'

export interface HCZDialogProps extends Omit<MuiDialogProps, 'title'> {
  open: boolean
  onClose: () => void
  title?: ReactNode
  titleActions?: ReactNode
  actions?: ReactNode
  maxWidth?: MuiDialogProps['maxWidth']
  showCloseButton?: boolean
  fullWidth?: boolean
  dividers?: boolean
}

const HCZDialog: React.FC<HCZDialogProps> = ({
  open,
  onClose,
  title,
  titleActions,
  children,
  actions,
  maxWidth = 'md',
  showCloseButton = true,
  fullWidth = true,
  dividers = false,
  ...props
}) => {
  const { t } = useTranslation('common')

  return (
    <MuiDialog
      open={open}
      onClose={onClose}
      maxWidth={maxWidth}
      fullWidth={fullWidth}
      PaperProps={{
        elevation: 0,
        sx: {
          borderRadius: '16px',
          background: SIDEBAR_GLASS.background,
          backdropFilter: SIDEBAR_GLASS.backdropFilter,
          WebkitBackdropFilter: SIDEBAR_GLASS.WebkitBackdropFilter,
          border: '1px solid rgba(255, 255, 255, 0.08)',
          boxShadow: '0 16px 64px rgba(0, 0, 0, 0.60)',
          overflow: 'hidden',
          maxHeight: '80vh',
        },
      }}
      {...props}
    >
      {title && (
        <>
          <DialogTitle
            sx={{
              pb: 1,
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              borderBottom: dividers ? '1px solid rgba(255, 255, 255, 0.06)' : 'none',
            }}
          >
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              {typeof title === 'string' ? (
                <Typography variant="h6">{title}</Typography>
              ) : (
                title
              )}
            </Box>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              {titleActions}
              {showCloseButton && (
                <Button
                  onClick={onClose}
                  size="small"
                  sx={{ textTransform: 'none', color: '#8e8e93', minWidth: 0 }}
                >
                  {t('actions.close')}
                </Button>
              )}
            </Box>
          </DialogTitle>
          {dividers && <Divider sx={{ borderColor: 'rgba(255, 255, 255, 0.06)' }} />}
        </>
      )}
      <DialogContent sx={{ pt: title ? 2 : 0 }}>{children}</DialogContent>
      {actions && (
        <>
          {!dividers && <Divider sx={{ borderColor: 'rgba(255, 255, 255, 0.06)' }} />}
          <DialogActions>{actions}</DialogActions>
        </>
      )}
    </MuiDialog>
  )
}

export default HCZDialog
