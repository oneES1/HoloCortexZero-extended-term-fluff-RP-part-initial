import { useState } from 'react'
import {
  Button,
  Menu,
  MenuItem,
  ListItemText,
  Tooltip,
  Box,
  Typography,
} from '@mui/material'
import { useLocaleStore } from '../../stores/locale'
import type { SupportedLocale } from '../../config/i18n'
import { supportedLanguages } from '../../config/i18n'
import { useTranslation } from 'react-i18next'

interface LocaleToggleButtonProps {
  mode?: 'icon' | 'compact' | 'full'
}

const LOCALE_SHORT_NAMES: Record<SupportedLocale, string> = {
  'zh-CN': 'ZH',
  'en-US': 'EN',
}

export default function LocaleToggleButton({ mode = 'compact' }: LocaleToggleButtonProps) {
  const { currentLocale, setLocale } = useLocaleStore()
  const { t } = useTranslation('common')
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null)
  const open = Boolean(anchorEl)

  const handleClick = (event: React.MouseEvent<HTMLElement>) => {
    setAnchorEl(event.currentTarget)
  }

  const handleClose = () => {
    setAnchorEl(null)
  }

  const handleLocaleChange = (locale: SupportedLocale) => {
    setLocale(locale)
    handleClose()
  }

  const menuStyles = {
    '& .MuiPaper-root': {
      mt: 1,
      minWidth: 140,
      backgroundColor: '#1a1a1a',
      borderRadius: '12px',
      border: '1px solid rgba(255, 255, 255, 0.08)',
      boxShadow: 'none',
    },
  }

  const menuItemStyles = {
    py: 1,
    px: 1.5,
    transition: 'background-color 0.15s ease',
    '&.Mui-selected': {
      backgroundColor: 'rgba(92, 157, 255, 0.1)',
    },
    '&: hover': {
      backgroundColor: 'rgba(92, 157, 255, 0.06)',
    },
  }

  const triggerButton = (
    <Button
      onClick={handleClick}
      size="small"
      sx={{
        textTransform: 'none',
        fontWeight: 500,
        minWidth: 0,
        color: 'inherit',
      }}
      aria-label={t('locale.selectLanguage')}
      aria-controls={open ? 'locale-menu' : undefined}
      aria-haspopup="true"
      aria-expanded={open ? 'true' : undefined}
    >
      {LOCALE_SHORT_NAMES[currentLocale]}
    </Button>
  )

  return (
    <Box>
      <Tooltip title={t('locale.toggleTooltip')} arrow>
        {triggerButton}
      </Tooltip>

      <Menu
        id="locale-menu"
        anchorEl={anchorEl}
        open={open}
        onClose={handleClose}
        MenuListProps={{ 'aria-labelledby': 'locale-button' }}
        transformOrigin={{ horizontal: 'right', vertical: 'top' }}
        anchorOrigin={{ horizontal: 'right', vertical: 'bottom' }}
        sx={menuStyles}
      >
        {(Object.keys(supportedLanguages) as SupportedLocale[]).map(locale => (
          <MenuItem
            key={locale}
            onClick={() => handleLocaleChange(locale)}
            selected={currentLocale === locale}
            sx={menuItemStyles}
          >
            <ListItemText
              primary={supportedLanguages[locale]}
              primaryTypographyProps={{ fontSize: '0.875rem' }}
            />
            {currentLocale === locale && (
              <Typography
                variant="caption"
                sx={{ color: '#5c9dff', ml: 1, fontWeight: 600 }}
              >
                ✓
              </Typography>
            )}
          </MenuItem>
        ))}
      </Menu>
    </Box>
  )
}
