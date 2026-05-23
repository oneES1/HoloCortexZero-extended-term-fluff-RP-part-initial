import React, { useCallback, useMemo, useRef, useState } from 'react'
import {
  Box,
  Typography,
  TextField,
  InputAdornment,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Stack,
  Divider,
  SelectChangeEvent,
  useTheme,
  useMediaQuery,
  Drawer,
  Fab,
  Card,
} from '@mui/material'
import { useInfiniteQuery } from '@tanstack/react-query'
import { chatChannelApi } from '../../services/api/chat-channel'
import ChatChannelList from './components/ChatChannelList'
import ChatChannelDetail from './components/ChatChannelDetail'
import { useTranslation } from 'react-i18next'

const CHANNEL_PAGE_SIZE = 25

export default function ChatChannelPage() {
  const [search, setSearch] = useState('')
  const [chatType, setChatType] = useState<string>('')
  const [isActive, setIsActive] = useState<string>('')
  const [selectedChatKey, setSelectedChatKey] = useState<string | null>(null)
  const [drawerOpen, setDrawerOpen] = useState(false)
  const listScrollRef = useRef<HTMLDivElement>(null)

  const theme = useTheme()
  const isMobile = useMediaQuery(theme.breakpoints.down('md'))
  const isSmall = useMediaQuery(theme.breakpoints.down('sm'))
  const { t } = useTranslation('chat-channel')

  const channelQueryKey = useMemo(
    () => ['chat-channels', search, chatType, isActive, CHANNEL_PAGE_SIZE],
    [search, chatType, isActive]
  )

  const {
    data: channelPages,
    fetchNextPage,
    hasNextPage,
    isFetchingNextPage,
    isLoading,
  } = useInfiniteQuery({
    queryKey: channelQueryKey,
    initialPageParam: 1,
    queryFn: ({ pageParam }) =>
      chatChannelApi.getList({
        page: pageParam,
        page_size: CHANNEL_PAGE_SIZE,
        search: search || undefined,
        chat_type: chatType || undefined,
        is_active: isActive === '' ? undefined : isActive === 'true',
      }),
    getNextPageParam: (lastPage, allPages) => {
      const loaded = allPages.reduce((sum, pageData) => sum + pageData.items.length, 0)
      return loaded < lastPage.total ? allPages.length + 1 : undefined
    },
  })

  const channels = channelPages?.pages.flatMap(pageData => pageData.items) ?? []
  const totalChannels = channelPages?.pages[0]?.total ?? 0

  const handleSearch = (event: React.ChangeEvent<HTMLInputElement>) => {
    setSearch(event.target.value)
    listScrollRef.current?.scrollTo({ top: 0 })
  }

  const handleClearSearch = () => {
    setSearch('')
    listScrollRef.current?.scrollTo({ top: 0 })
  }

  const handleChatTypeChange = (event: SelectChangeEvent) => {
    setChatType(event.target.value)
    listScrollRef.current?.scrollTo({ top: 0 })
  }

  const handleActiveChange = (event: SelectChangeEvent) => {
    setIsActive(event.target.value)
    listScrollRef.current?.scrollTo({ top: 0 })
  }

  const handleSelectChannel = (chatKey: string) => {
    setSelectedChatKey(chatKey)
    if (isMobile) {
      setDrawerOpen(false)
    }
  }

  const handleBackToList = () => {
    setSelectedChatKey(null)
  }

  const handleListScroll = useCallback(() => {
    const container = listScrollRef.current
    if (!container || !hasNextPage || isFetchingNextPage) return
    const remaining = container.scrollHeight - container.scrollTop - container.clientHeight
    if (remaining < 120) {
      fetchNextPage()
    }
  }, [fetchNextPage, hasNextPage, isFetchingNextPage])

  const renderChannelList = () => (
    <Box
      sx={{
        height: '100%',
        minHeight: 0,
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden',
      }}
    >
      <Box sx={{ p: 2, flexShrink: 0 }}>
        <Stack spacing={1.5}>
          <TextField
            fullWidth
            size={isSmall ? 'small' : 'medium'}
            placeholder={t('search.placeholder')}
            value={search}
            onChange={handleSearch}
            InputProps={{
              endAdornment: search && (
                <InputAdornment position="end">
                  <Typography
                    component="span"
                    onClick={handleClearSearch}
                    sx={{
                      cursor: 'pointer',
                      fontSize: '0.75rem',
                      color: 'text.secondary',
                      '&:hover': { color: 'text.primary' },
                      userSelect: 'none',
                    }}
                  >
                    Clear
                  </Typography>
                </InputAdornment>
              ),
            }}
          />

          <Stack direction={isSmall ? 'column' : 'row'} spacing={1}>
            <FormControl size="small" fullWidth>
              <InputLabel>{t('filters.type')}</InputLabel>
              <Select value={chatType} label={t('filters.type')} onChange={handleChatTypeChange}>
                <MenuItem value="">{t('filters.all')}</MenuItem>
                <MenuItem value="group">{t('filters.group')}</MenuItem>
                <MenuItem value="private">{t('filters.private')}</MenuItem>
              </Select>
            </FormControl>
            <FormControl size="small" fullWidth>
              <InputLabel>{t('filters.status')}</InputLabel>
              <Select value={isActive} label={t('filters.status')} onChange={handleActiveChange}>
                <MenuItem value="">{t('filters.all')}</MenuItem>
                <MenuItem value="true">{t('filters.active')}</MenuItem>
                <MenuItem value="false">{t('filters.inactive')}</MenuItem>
              </Select>
            </FormControl>
          </Stack>
        </Stack>
      </Box>

      <Divider />

      <Box
        ref={listScrollRef}
        onScroll={handleListScroll}
        sx={{
          flex: 1,
          minHeight: 0,
          overflowY: 'auto',
          WebkitOverflowScrolling: 'touch',
        }}
      >
        <ChatChannelList
          channels={channels}
          selectedChatKey={selectedChatKey}
          onSelectChannel={handleSelectChannel}
          isLoading={isLoading}
          isFetchingNextPage={isFetchingNextPage}
          hasNextPage={!!hasNextPage}
          total={totalChannels}
          search={search}
          chatType={chatType}
          isActive={isActive}
        />
      </Box>
    </Box>
  )

  const renderChannelDetail = () =>
    selectedChatKey ? (
      <ChatChannelDetail chatKey={selectedChatKey} onBack={isMobile ? handleBackToList : undefined} />
    ) : (
      <Card
        sx={{
          height: '100%',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          flexDirection: 'column',
        }}
      >
        <Typography
          variant="h2"
          sx={{ letterSpacing: '0.18em', color: 'text.secondary', opacity: 0.72 }}
        >
          HCZ
        </Typography>
      </Card>
    )

  return (
    <Box
      sx={{
        height: '100%',
        minHeight: 0,
        display: 'grid',
        gridTemplateColumns: isMobile ? '1fr' : '360px minmax(0, 1fr)',
        gridTemplateRows: 'minmax(0, 1fr)',
        alignItems: 'stretch',
        gap: 2,
        overflow: 'hidden',
        p: 2,
      }}
    >
      {isMobile ? (
        <>
          <Box sx={{ height: '100%', minHeight: 0, overflow: 'hidden' }}>{renderChannelDetail()}</Box>

          <Drawer
            anchor="left"
            open={drawerOpen}
            onClose={() => setDrawerOpen(false)}
            PaperProps={{
              sx: {
                width: isSmall ? '85%' : '320px',
                maxWidth: '100%',
                backgroundColor: 'transparent',
                backdropFilter: 'blur(20px)',
                borderRight: `1px solid rgba(255, 255, 255, 0.06)`,
              },
            }}
          >
            {renderChannelList()}
          </Drawer>

          <Fab
            color="primary"
            size={isSmall ? 'medium' : 'large'}
            onClick={() => setDrawerOpen(true)}
            sx={{
              position: 'fixed',
              bottom: 16,
              right: 16,
              zIndex: 1099,
            }}
          >
            List
          </Fab>
        </>
      ) : (
        <>
          <Card
            sx={{
              height: '100%',
              minHeight: 0,
              overflow: 'hidden',
              display: 'flex',
              flexDirection: 'column',
            }}
          >
            {renderChannelList()}
          </Card>

          <Box sx={{ minWidth: 0, height: '100%', minHeight: 0, overflow: 'hidden' }}>{renderChannelDetail()}</Box>
        </>
      )}
    </Box>
  )
}
