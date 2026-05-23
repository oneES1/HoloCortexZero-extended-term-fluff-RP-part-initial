import React, { useState, useEffect } from 'react'
import {
  Box,
  Paper,
  TextField,
  InputAdornment,
  useMediaQuery,
  useTheme,
  TableContainer,
} from '@mui/material'
import SearchOutlined from '@mui/icons-material/SearchOutlined'
import UserTable from './components/UserTable'
import UserDetail from './components/UserDetail'
import { useUserData } from './hooks/useUserData'
import { useTranslation } from 'react-i18next'
import TablePaginationStyled from '../../components/common/TablePaginationStyled'

const UserManagerPage: React.FC = () => {
  const [searchTerm, setSearchTerm] = useState('')
  const [debouncedSearchTerm, setDebouncedSearchTerm] = useState('')
  const [selectedUserId, setSelectedUserId] = useState<number | null>(null)
  const [isDetailOpen, setIsDetailOpen] = useState(false)

  const theme = useTheme()
  const isMobile = useMediaQuery(theme.breakpoints.down('md'))
  const isSmall = useMediaQuery(theme.breakpoints.down('sm'))
  const { t } = useTranslation('user-manager')

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedSearchTerm(searchTerm), 300)
    return () => clearTimeout(timer)
  }, [searchTerm])

  const {
    users,
    total,
    isLoading,
    pagination,
    setPagination,
    deleteUser,
    banUser,
    setPreventTrigger,
  } = useUserData(debouncedSearchTerm)

  const handleViewDetail = (userId: number) => {
    setSelectedUserId(userId)
    setIsDetailOpen(true)
  }

  return (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'column',
        p: 2,
        height: 'calc(100vh - var(--hcz-page-offset, 64px))',
      }}
    >
      <Box
        sx={{
          display: 'flex',
          gap: 1,
          pl: 1,
          flexShrink: 0,
          flexDirection: 'row',
          alignItems: 'center',
        }}
      >
        <TextField
          placeholder={t('search.placeholder')}
          size="small"
          sx={{ flex: 1 }}
          value={searchTerm}
          onChange={e => setSearchTerm(e.target.value)}
          InputProps={{
            startAdornment: (
              <InputAdornment position="start">
                <SearchOutlined fontSize="small" sx={{ color: 'text.secondary' }} />
              </InputAdornment>
            ),
          }}
        />
      </Box>

      <Paper sx={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden', mt: 2 }}>
        <TableContainer sx={{ flex: 1, overflow: 'auto' }}>
          <UserTable
            users={users}
            loading={isLoading}
            onViewDetail={handleViewDetail}
            onDeleteUser={deleteUser}
            onBanUser={banUser}
            onSetPreventTrigger={setPreventTrigger}
            tableProps={{
              sx: {
                tableLayout: 'fixed',
                width: '100%',
                p: 0,
              },
            }}
          />
        </TableContainer>
        <TablePaginationStyled
          rowsPerPageOptions={isMobile ? [5, 10, 25] : [5, 10, 25, 50]}
          component="div"
          count={total}
          rowsPerPage={pagination.page_size}
          page={pagination.page - 1}
          onPageChange={(_, newPage) => setPagination({ ...pagination, page: newPage + 1 })}
          onRowsPerPageChange={event =>
            setPagination({ page: 1, page_size: parseInt(event.target.value, 10) })
          }
          loading={isLoading}
          showFirstLastPageButtons={true}
        />
      </Paper>

      <UserDetail
        userId={selectedUserId || 0}
        open={isDetailOpen}
        onClose={() => setIsDetailOpen(false)}
      />
    </Box>
  )
}

export default UserManagerPage
