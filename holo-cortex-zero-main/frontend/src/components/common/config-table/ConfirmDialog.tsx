import type { ReactNode } from 'react'
import { Button, Dialog, DialogActions, DialogContent, DialogTitle } from '@mui/material'
import { useTranslation } from 'react-i18next'

interface ConfirmDialogProps {
  open: boolean
  onClose: () => void
  onConfirm: () => void
  title: string
  content: ReactNode
}

export default function ConfirmDialog({
  open,
  onClose,
  onConfirm,
  title,
  content,
}: ConfirmDialogProps) {
  const { t } = useTranslation('common')

  return (
    <Dialog open={open} onClose={onClose}>
      <DialogTitle>{title}</DialogTitle>
      <DialogContent>{content}</DialogContent>
      <DialogActions>
        <Button onClick={onClose}>{t('actions.cancel')}</Button>
        <Button onClick={onConfirm} color="primary" autoFocus>
          {t('actions.confirm')}
        </Button>
      </DialogActions>
    </Dialog>
  )
}
