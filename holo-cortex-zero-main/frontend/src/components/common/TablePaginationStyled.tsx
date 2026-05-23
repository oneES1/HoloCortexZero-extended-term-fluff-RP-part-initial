import React from 'react'
import {
  TablePagination,
  Button,
  Box,
  useMediaQuery,
  useTheme,
  SxProps,
  Theme,
} from '@mui/material'
import { useTranslation } from 'react-i18next'

interface TablePaginationStyledProps {
  count: number
  page: number
  rowsPerPage: number
  onPageChange: (event: React.MouseEvent<HTMLButtonElement> | null, newPage: number) => void
  onRowsPerPageChange?: (event: React.ChangeEvent<HTMLInputElement>) => void
  rowsPerPageOptions?: number[]
  component?: React.ElementType
  labelRowsPerPage?: string
  labelDisplayedRows?: (from: { from: number; to: number; count: number }) => string
  sx?: SxProps<Theme>
  loading?: boolean
  showFirstLastPageButtons?: boolean
}

const TablePaginationStyled: React.FC<TablePaginationStyledProps> = ({
  count,
  page,
  rowsPerPage,
  onPageChange,
  onRowsPerPageChange,
  rowsPerPageOptions = [10, 25, 50],
  component = 'div',
  labelRowsPerPage,
  labelDisplayedRows,
  sx,
  loading = false,
  showFirstLastPageButtons = true,
}) => {
  const theme = useTheme()
  const isSmall = useMediaQuery(theme.breakpoints.down('sm'))
  const { t } = useTranslation('common')

  function TablePaginationActions(props: {
    count: number
    page: number
    rowsPerPage: number
    onPageChange: (event: React.MouseEvent<HTMLButtonElement>, newPage: number) => void
    className?: string
  }) {
    const { count, page, rowsPerPage, onPageChange, className } = props
    const totalPages = Math.max(1, Math.ceil(count / rowsPerPage))

    const handleFirstPage = (event: React.MouseEvent<HTMLButtonElement>) => {
      onPageChange(event, 0)
    }

    const handleBack = (event: React.MouseEvent<HTMLButtonElement>) => {
      onPageChange(event, page - 1)
    }

    const handleNext = (event: React.MouseEvent<HTMLButtonElement>) => {
      onPageChange(event, page + 1)
    }

    const handleLastPage = (event: React.MouseEvent<HTMLButtonElement>) => {
      onPageChange(event, Math.max(0, totalPages - 1))
    }

    const pageButtonSx = {
      textTransform: 'none',
      minWidth: isSmall ? 48 : 64,
      px: isSmall ? 1.25 : 1.75,
    }

    return (
      <Box
        className={className}
        sx={{
          ml: 'auto',
          display: 'flex',
          gap: isSmall ? 1 : 1.25,
          flex: '0 0 auto',
          flexWrap: 'wrap',
          justifyContent: 'flex-end',
        }}
      >
        {showFirstLastPageButtons && (
          <Button
            onClick={handleFirstPage}
            disabled={page === 0 || loading}
            size="small"
            sx={pageButtonSx}
          >
            {t('common.pagination.firstPage')}
          </Button>
        )}

        <Button
          onClick={handleBack}
          disabled={page === 0 || loading}
          size="small"
          sx={pageButtonSx}
        >
          {t('common.pagination.previousPage')}
        </Button>

        <Button
          onClick={handleNext}
          disabled={page >= totalPages - 1 || loading}
          size="small"
          sx={pageButtonSx}
        >
          {t('common.pagination.nextPage')}
        </Button>

        {showFirstLastPageButtons && (
          <Button
            onClick={handleLastPage}
            disabled={page >= totalPages - 1 || loading}
            size="small"
            sx={pageButtonSx}
          >
            {t('common.pagination.lastPage')}
          </Button>
        )}
      </Box>
    )
  }

  return (
    <TablePagination
      component={component}
      count={count}
      rowsPerPage={rowsPerPage}
      page={page}
      onPageChange={onPageChange}
      onRowsPerPageChange={onRowsPerPageChange}
      rowsPerPageOptions={rowsPerPageOptions}
      labelRowsPerPage={
        labelRowsPerPage ||
        (isSmall ? t('common.pagination.labelRowsPerPageShort') : t('common.pagination.labelRowsPerPage'))
      }
      labelDisplayedRows={
        labelDisplayedRows ||
        (({ from, to, count }) => {
          const key = isSmall
            ? 'common.pagination.displayedRowsShort'
            : 'common.pagination.displayedRows'
          return t(key, { from, to, count })
        })
      }
      ActionsComponent={TablePaginationActions}
      disabled={loading}
      sx={{
        borderTop: '1px solid',
        borderColor: 'divider',
        flexShrink: 0,
        px: isSmall ? 1 : 2,
        py: isSmall ? 1 : 1.25,
        '.MuiToolbar-root': {
          minHeight: isSmall ? 48 : 56,
          px: '0 !important',
          gap: isSmall ? 1 : 1.5,
          flexWrap: 'wrap',
          justifyContent: 'flex-end',
        },
        '.MuiTablePagination-spacer': {
          display: 'none',
        },
        '.MuiTablePagination-actions': {
          ml: 'auto',
          display: 'flex',
          justifyContent: 'flex-end',
          flex: '0 0 auto',
        },
        '.MuiTablePagination-selectLabel': {
          marginBottom: 0,
          display: isSmall ? 'none' : 'block',
        },
        '.MuiTablePagination-displayedRows': {
          marginBottom: 0,
          fontSize: isSmall ? '0.75rem' : 'inherit',
        },
        ...sx,
      }}
    />
  )
}

export default TablePaginationStyled
