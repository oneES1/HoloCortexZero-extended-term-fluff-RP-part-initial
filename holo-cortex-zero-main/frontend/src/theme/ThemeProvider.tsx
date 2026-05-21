/**
 * ThemeProvider.tsx
 * Dark / Light 共用主干，按 mode 分支输出 glass tokens
 */
import { ReactNode, useEffect, useMemo } from 'react'
import { CssBaseline } from '@mui/material'
import { createTheme, ThemeProvider as MuiThemeProvider } from '@mui/material/styles'
import { MotionConfig } from 'framer-motion'
import { useColorMode } from '../stores/theme'
import { getMuiPaletteOptions } from './palette'
import { COLORS, getGlassTokens, RADIUS } from './glass'

const FONT_PRIMARY = `'Inter', 'SF Pro Display', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif`

export default function ThemeProvider({ children }: { children: ReactNode }) {
  const { mode } = useColorMode()
  const tokens = useMemo(() => getGlassTokens(mode), [mode])

  useEffect(() => {
    document.documentElement.style.colorScheme = mode
    document.documentElement.dataset.theme = mode
  }, [mode])

  const muiTheme = useMemo(
    () =>
      createTheme({
        palette: getMuiPaletteOptions(mode),
        shape: { borderRadius: 12 },
        typography: {
          fontFamily: FONT_PRIMARY,
          button: {
            fontWeight: 600,
            letterSpacing: '0.01em',
            textTransform: 'none',
          },
          h1: { fontWeight: 700, fontSize: '2.5rem', lineHeight: 1.2, letterSpacing: '-0.02em' },
          h2: { fontWeight: 700, fontSize: '2rem', lineHeight: 1.25, letterSpacing: '-0.01em' },
          h3: { fontWeight: 600, fontSize: '1.7rem', lineHeight: 1.3 },
          h4: { fontWeight: 600, fontSize: '1.5rem', lineHeight: 1.35 },
          h5: { fontWeight: 600, fontSize: '1.25rem', lineHeight: 1.4 },
          h6: { fontWeight: 600, fontSize: '1.1rem', lineHeight: 1.4 },
          subtitle1: { fontWeight: 500, fontSize: '1rem', lineHeight: 1.5 },
          body1: { fontWeight: 400, fontSize: '0.95rem', lineHeight: 1.5 },
          body2: { fontWeight: 400, fontSize: '0.875rem', lineHeight: 1.57 },
          caption: { fontWeight: 400, fontSize: '0.75rem', lineHeight: 1.66 },
        },
        components: {
          MuiCssBaseline: {
            styleOverrides: {
              html: {
                scrollBehavior: 'smooth',
                colorScheme: mode,
              },
              body: {
                minHeight: '100vh',
                backgroundColor: tokens.VOID.base,
                color: tokens.TEXT.primary,
                transition: 'background-color 0.2s ease, color 0.2s ease',
              },
              '*::-webkit-scrollbar': {
                width: '6px',
                height: '6px',
              },
              '*::-webkit-scrollbar-track': {
                background: 'transparent',
              },
              '*::-webkit-scrollbar-thumb': {
                backgroundColor: mode === 'dark' ? 'rgba(255, 255, 255, 0.10)' : 'rgba(15, 23, 42, 0.18)',
                borderRadius: '10px',
                '&:hover': {
                  backgroundColor: mode === 'dark' ? 'rgba(255, 255, 255, 0.18)' : 'rgba(15, 23, 42, 0.28)',
                },
              },
            },
          },
          MuiPaper: {
            defaultProps: { elevation: 0 },
            styleOverrides: {
              root: {
                backgroundImage: 'none',
                backgroundColor: tokens.PANEL.background,
                borderRadius: RADIUS.panel,
                boxShadow: tokens.PANEL.boxShadow,
                border: tokens.PANEL.border,
              },
            },
          },
          MuiCard: {
            styleOverrides: {
              root: {
                backgroundColor: tokens.PANEL.background,
                borderRadius: RADIUS.panel,
                border: tokens.PANEL.border,
                boxShadow: tokens.PANEL.boxShadow,
              },
            },
          },
          MuiDrawer: {
            styleOverrides: {
              paper: {
                backgroundColor: tokens.SIDEBAR_GLASS.background,
                backdropFilter: tokens.SIDEBAR_GLASS.backdropFilter,
                WebkitBackdropFilter: tokens.SIDEBAR_GLASS.WebkitBackdropFilter,
                borderRight: tokens.SIDEBAR_GLASS.borderRight,
                boxShadow: tokens.SIDEBAR_GLASS.boxShadow,
                borderRadius: 0,
              },
            },
          },
          MuiAppBar: {
            styleOverrides: {
              root: {
                backgroundColor: tokens.TOP_BAR.background,
                backdropFilter: tokens.TOP_BAR.backdropFilter,
                WebkitBackdropFilter: tokens.TOP_BAR.WebkitBackdropFilter,
                borderBottom: tokens.TOP_BAR.borderBottom,
                boxShadow: tokens.TOP_BAR.boxShadow,
              },
            },
          },
          MuiDialog: {
            styleOverrides: {
              paper: {
                borderRadius: RADIUS.panel,
                backgroundColor: tokens.SIDEBAR_GLASS.background,
                backdropFilter: tokens.SIDEBAR_GLASS.backdropFilter,
                WebkitBackdropFilter: tokens.SIDEBAR_GLASS.WebkitBackdropFilter,
                boxShadow: tokens.SHADOWS.dialog,
                border: tokens.SIDEBAR_GLASS.border,
              },
            },
          },
          MuiButton: {
            styleOverrides: {
              root: {
                borderRadius: RADIUS.pill,
                transition: 'none',
                '&:active': { transform: 'scale(0.98)' },
                '&.MuiButton-containedError': {
                  background: 'rgba(255, 69, 58, 0.20)',
                  border: '1px solid rgba(255, 69, 58, 0.32)',
                  boxShadow: 'inset 0 1px 0 rgba(255, 255, 255, 0.15), 0 0 12px rgba(255, 69, 58, 0.18)',
                  color: COLORS.error,
                  '&:hover': {
                    background: 'rgba(255, 69, 58, 0.30)',
                  },
                },
                '&.MuiButton-outlinedError': {
                  background: 'rgba(255, 69, 58, 0.08)',
                  border: '1px solid rgba(255, 69, 58, 0.24)',
                  boxShadow: 'inset 0 1px 0 rgba(255, 255, 255, 0.08)',
                  color: COLORS.error,
                  '&:hover': {
                    background: 'rgba(255, 69, 58, 0.14)',
                    boxShadow: 'inset 0 1px 0 rgba(255, 255, 255, 0.12)',
                  },
                },
              },
              contained: {
                background: tokens.GLASS_PILL.active.background,
                backdropFilter: tokens.GLASS_PILL.active.backdropFilter,
                WebkitBackdropFilter: tokens.GLASS_PILL.active.WebkitBackdropFilter,
                border: tokens.GLASS_PILL.active.border,
                boxShadow: tokens.GLASS_PILL.active.boxShadow,
                color: tokens.GLASS_PILL.active.color,
                '&:hover': {
                  background: mode === 'dark' ? 'rgba(92, 157, 255, 0.30)' : 'rgba(92, 157, 255, 0.24)',
                },
              },
              outlined: {
                background: tokens.GLASS_PILL.inactive.background,
                backdropFilter: tokens.GLASS_PILL.inactive.backdropFilter,
                WebkitBackdropFilter: tokens.GLASS_PILL.inactive.WebkitBackdropFilter,
                border: tokens.GLASS_PILL.inactive.border,
                boxShadow: tokens.GLASS_PILL.inactive.boxShadow,
                color: tokens.GLASS_PILL.inactive.color,
                '&:hover': {
                  background: tokens.GLASS_PILL.hover.background,
                  boxShadow: tokens.GLASS_PILL.hover.boxShadow,
                },
              },
            },
          },
          MuiMenu: {
            styleOverrides: {
              paper: {
                borderRadius: RADIUS.card,
                padding: '6px',
                backgroundColor: tokens.SIDEBAR_GLASS.background,
                backdropFilter: tokens.SIDEBAR_GLASS.backdropFilter,
                WebkitBackdropFilter: tokens.SIDEBAR_GLASS.WebkitBackdropFilter,
                border: tokens.SIDEBAR_GLASS.border,
                boxShadow: tokens.SHADOWS.deep,
              },
              list: { padding: '4px' },
            },
          },
          MuiMenuItem: {
            styleOverrides: {
              root: {
                borderRadius: RADIUS.small,
                margin: '2px 0',
                color: tokens.TEXT.primary,
                '&.Mui-selected': {
                  background: tokens.GLASS_PILL.active.background,
                  color: tokens.GLASS_PILL.active.color,
                  '&:hover': {
                    background: mode === 'dark' ? 'rgba(92, 157, 255, 0.30)' : 'rgba(92, 157, 255, 0.24)',
                  },
                },
                '&:hover': {
                  background: mode === 'dark' ? 'rgba(255, 255, 255, 0.06)' : 'rgba(15, 23, 42, 0.04)',
                },
              },
            },
          },
          MuiTableCell: {
            styleOverrides: {
              root: {
                borderBottom: tokens.TEXT.divider,
                padding: '14px 16px',
              },
              head: {
                fontWeight: 600,
                color: tokens.TEXT.secondary,
                backgroundColor: 'transparent',
                borderBottom: mode === 'dark' ? '1px solid rgba(255, 255, 255, 0.08)' : '1px solid rgba(15, 23, 42, 0.08)',
              },
            },
          },
          MuiOutlinedInput: {
            styleOverrides: {
              root: {
                borderRadius: RADIUS.control,
                backgroundColor: tokens.INPUT.background,
                border: tokens.INPUT.border,
                boxShadow: tokens.INPUT.boxShadow,
                color: tokens.INPUT.color,
                '& fieldset': {
                  borderColor: 'transparent',
                },
                '&:hover': {
                  backgroundColor: tokens.INPUT_HOVER.background,
                  borderColor: tokens.INPUT_HOVER.borderColor,
                },
                '&:hover fieldset': {
                  borderColor: 'transparent',
                },
                '&.Mui-focused': {
                  backgroundColor: tokens.INPUT_FOCUS.background,
                  borderColor: tokens.INPUT_FOCUS.borderColor,
                  boxShadow: tokens.INPUT_FOCUS.boxShadow,
                },
                '&.Mui-focused fieldset': {
                  borderWidth: '0px',
                  borderColor: 'transparent',
                },
                '&.Mui-disabled': {
                  backgroundColor: mode === 'dark' ? '#1a1a1a' : '#eef2f7',
                },
              },
            },
          },
          MuiSwitch: {
            styleOverrides: {
              root: { padding: 8 },
              track: {
                borderRadius: 11,
                backgroundColor: mode === 'dark' ? 'rgba(255, 255, 255, 0.15)' : 'rgba(15, 23, 42, 0.14)',
                opacity: 1,
              },
              thumb: { boxShadow: 'none' },
            },
          },
          MuiChip: {
            styleOverrides: {
              root: {
                height: 24,
                borderRadius: RADIUS.small,
                backgroundColor: tokens.PANEL_NESTED.background,
                border: tokens.PANEL_NESTED.border,
                color: tokens.TEXT.secondary,
                fontSize: '0.75rem',
                fontWeight: 500,
              },
            },
          },
          MuiAlert: {
            styleOverrides: {
              root: {
                borderRadius: RADIUS.card,
                backgroundColor: tokens.PANEL.background,
                border: tokens.PANEL.border,
                boxShadow: tokens.PANEL.boxShadow,
                color: tokens.TEXT.primary,
              },
            },
          },
        },
      }),
    [mode, tokens]
  )

  return (
    <MuiThemeProvider theme={muiTheme}>
      <MotionConfig transition={{ type: 'spring', stiffness: 300, damping: 30 }}>
        <CssBaseline />
        {children}
      </MotionConfig>
    </MuiThemeProvider>
  )
}
