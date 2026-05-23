import {
  List,
  ListItem,
  ListItemButton,
  ListItemText,
  Typography,
  Skeleton,
  Stack,
  Box,
  Switch,
  Tooltip,
} from '@mui/material'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { ChatChannel } from '../../../services/api/chat-channel'
import { chatChannelApi } from '../../../services/api/chat-channel'
import { useTranslation } from 'react-i18next'

interface ChatChannelListProps {
  channels: ChatChannel[]
  selectedChatKey: string | null
  onSelectChannel: (chatKey: string) => void
  isLoading: boolean
  isFetchingNextPage: boolean
  hasNextPage: boolean
  total: number
  search: string
  chatType: string
  isActive: string
}

export default function ChatChannelList({
  channels,
  selectedChatKey,
  onSelectChannel,
  isLoading,
  isFetchingNextPage,
  hasNextPage,
  total,
  search,
  chatType,
  isActive,
}: ChatChannelListProps) {
  const { t } = useTranslation('chat-channel')
  const queryClient = useQueryClient()
  const { mutate: toggleActive, variables: pendingChatKey, isPending: isToggling } = useMutation({
    mutationFn: ({ chatKey, active }: { chatKey: string; active: boolean }) =>
      chatChannelApi.setActive(chatKey, active),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ['chat-channels', search, chatType, isActive],
      })
    },
  })

  if (isLoading) {
    return (
      <List>
        {[...Array(5)].map((_, index) => (
          <ListItem key={index} disablePadding divider>
            <ListItemButton>
              <ListItemText
                primary={<Skeleton width="60%" />}
                secondary={<Skeleton width="40%" />}
              />
            </ListItemButton>
          </ListItem>
        ))}
      </List>
    )
  }

  if (channels.length === 0) {
    return (
      <Box className="h-full flex items-center justify-center">
        <Typography color="textSecondary">{t('list.empty')}</Typography>
      </Box>
    )
  }

  return (
    <List disablePadding>
      <Box sx={{ px: 2, py: 1, borderBottom: '1px solid', borderColor: 'divider' }}>
        <Typography variant="caption" color="text.secondary">
          {t('list.loaded', { loaded: channels.length, total })}
        </Typography>
      </Box>
      {channels.map(channel => (
        <ListItem
          key={channel.chat_key}
          disablePadding
          divider
          secondaryAction={
            <Tooltip title={channel.is_active ? t('list.deactivate') : t('list.activate')}>
              <Switch
                edge="end"
                size="small"
                checked={channel.is_active}
                disabled={isToggling && pendingChatKey?.chatKey === channel.chat_key}
                onClick={event => event.stopPropagation()}
                onChange={event => {
                  event.stopPropagation()
                  toggleActive({ chatKey: channel.chat_key, active: event.target.checked })
                }}
                sx={{
                  '& .MuiSwitch-switchBase.Mui-checked': {
                    color: 'success.main',
                    '& + .MuiSwitch-track': {
                      backgroundColor: 'success.main',
                      opacity: 0.55,
                    },
                  },
                }}
              />
            </Tooltip>
          }
        >
          <ListItemButton
            selected={channel.chat_key === selectedChatKey}
            onClick={() => onSelectChannel(channel.chat_key)}
            sx={{
              minWidth: 0,
              py: 1.5,
              pl: 2,
              pr: 7,
            }}
          >
            <Box className="min-w-0 flex-1">
              <Stack direction="row" spacing={1} alignItems="center" className="min-w-0">
                <Typography variant="body2" className="font-medium truncate flex-1">
                  {channel.channel_name || channel.chat_key}
                </Typography>
              </Stack>
            </Box>
          </ListItemButton>
        </ListItem>
      ))}
      {(isFetchingNextPage || hasNextPage) && (
        <Box sx={{ py: 2, display: 'flex', justifyContent: 'center' }}>
          <Typography variant="caption" color="text.secondary">
            {isFetchingNextPage ? t('list.loadingMore') : t('list.scrollForMore')}
          </Typography>
        </Box>
      )}
    </List>
  )
}
