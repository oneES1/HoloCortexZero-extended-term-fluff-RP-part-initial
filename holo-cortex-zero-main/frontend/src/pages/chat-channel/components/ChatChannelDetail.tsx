import {
  Box,
  Button,
  Card,
} from '@mui/material'
import MessageHistory from './detail-tabs/MessageHistory'

interface ChatChannelDetailProps {
  chatKey: string
  onBack?: () => void
}

export default function ChatChannelDetail({ chatKey, onBack }: ChatChannelDetailProps) {
  return (
    <Box sx={{ height: '100%', minHeight: 0, overflow: 'hidden', position: 'relative' }}>
      {onBack && (
        <Button
          onClick={onBack}
          size="small"
          sx={{ position: 'absolute', top: 8, left: 8, zIndex: 2, textTransform: 'none' }}
        >
          Back
        </Button>
      )}
      <Card sx={{ height: '100%', p: 0, overflow: 'hidden' }}>
        <MessageHistory chatKey={chatKey} />
      </Card>
    </Box>
  )
}
