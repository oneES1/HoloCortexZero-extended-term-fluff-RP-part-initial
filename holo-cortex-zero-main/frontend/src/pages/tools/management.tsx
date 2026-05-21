import { useMemo, useState } from 'react'
import { Alert, Box, Paper, Stack, Typography } from '@mui/material'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'

import ConfigTable from '../../components/common/ConfigTable'
import { createConfigService, unifiedConfigApi } from '../../services/api/unified-config'
import { ToolDetail, ToolItem, toolsApi } from '../../services/api/tools'

function formatJson(value: unknown) {
  try {
    return JSON.stringify(value, null, 2)
  } catch {
    return String(value ?? '')
  }
}

function ToolListItem({
  tool,
  selected,
  onSelect,
  t,
}: {
  tool: ToolItem
  selected: boolean
  onSelect: (tool: ToolItem) => void
  t: (key: string, options?: { defaultValue?: string }) => string
}) {
  return (
    <Box
      onClick={() => onSelect(tool)}
      sx={{
        px: 1.5,
        py: 1.25,
        borderRadius: 2,
        cursor: 'pointer',
        userSelect: 'none',
        transition: 'all 0.18s ease',
        bgcolor: selected ? 'action.selected' : 'transparent',
        border: '1px solid',
        borderColor: selected ? 'primary.main' : 'divider',
        '&:hover': {
          bgcolor: selected ? 'action.selected' : 'action.hover',
          borderColor: selected ? 'primary.main' : 'text.disabled',
        },
      }}
    >
      <Stack spacing={0.5}>
        <Typography variant="body2" sx={{ fontWeight: selected ? 700 : 600, lineHeight: 1.35 }}>
          {t(`toolNames.${tool.tool_id}`, { defaultValue: tool.display_name })}
        </Typography>
        <Typography variant="caption" color="text.secondary" sx={{ fontFamily: 'monospace' }}>
          {tool.tool_id}
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ lineHeight: 1.45 }}>
          {t(`toolDescriptions.${tool.tool_id}`, { defaultValue: tool.description }) || t('tools.noDescription')}
        </Typography>
      </Stack>
    </Box>
  )
}

function ToolParametersPanel({ toolDetail }: { toolDetail: ToolDetail | undefined }) {
  return (
    <Box
      sx={{
        flexShrink: 0,
        minWidth: 0,
        borderTop: '1px solid',
        borderColor: 'divider',
        pt: 1.5,
      }}
    >
      <Box
        component="pre"
        sx={{
          m: 0,
          whiteSpace: 'pre-wrap',
          wordBreak: 'break-word',
          fontSize: 12,
          lineHeight: 1.55,
          fontFamily:
            'ui-monospace, SFMono-Regular, SF Mono, Menlo, Monaco, Consolas, Liberation Mono, monospace',
        }}
      >
        {formatJson(toolDetail?.parameters_schema ?? {})}
      </Box>
    </Box>
  )
}

export default function ToolsManagementPage() {
  const queryClient = useQueryClient()
  const [selectedToolId, setSelectedToolId] = useState<string>('')
  const { t } = useTranslation('common')

  const { data: tools = [], isLoading } = useQuery({
    queryKey: ['tools'],
    queryFn: () => toolsApi.getTools(),
  })

  const selectedTool = useMemo(() => {
    if (!tools.length) return undefined
    return tools.find(item => item.tool_id === selectedToolId) || tools[0]
  }, [tools, selectedToolId])

  const { data: toolDetail, isLoading: detailLoading } = useQuery({
    queryKey: ['tool-detail', selectedTool?.tool_id],
    queryFn: () => toolsApi.getToolDetail(selectedTool?.tool_id || ''),
    enabled: Boolean(selectedTool?.tool_id),
  })

  const { data: toolConfigs = [], isLoading: configLoading, refetch: refetchConfig } = useQuery({
    queryKey: ['tool-config', selectedTool?.config_key],
    queryFn: () => unifiedConfigApi.getConfigList(selectedTool?.config_key || ''),
    enabled: Boolean(selectedTool?.config_key),
  })

  return (
    <Box
      sx={{
        height: '100%',
        minHeight: 0,
        display: 'grid',
        gridTemplateColumns: { xs: '1fr', md: '280px minmax(0, 1fr)' },
        gridTemplateRows: { xs: 'minmax(180px, 34%) minmax(0, 1fr)', md: 'minmax(0, 1fr)' },
        alignItems: 'stretch',
        gap: 1.5,
        overflow: 'hidden',
        p: 2,
      }}
    >
      <Paper
        elevation={0}
        sx={{
          display: 'flex',
          flexDirection: 'column',
          minHeight: 0,
          height: '100%',
          overflow: 'hidden',
          borderRadius: 3,
          border: '1px solid',
          borderColor: 'divider',
          bgcolor: 'background.paper',
        }}
      >
        <Box
          sx={{
            flex: 1,
            minHeight: 0,
            overflowY: 'auto',
            WebkitOverflowScrolling: 'touch',
            p: 1,
          }}
        >
          <Stack spacing={0.75}>
            {tools.map(tool => (
              <ToolListItem
                key={tool.tool_id}
                tool={tool}
                selected={tool.tool_id === selectedTool?.tool_id}
                onSelect={item => setSelectedToolId(item.tool_id)}
                t={t}
              />
            ))}
            {!isLoading && tools.length === 0 && (
              <Typography variant="body2" color="text.secondary" sx={{ px: 1, py: 1.5 }}>
                {t('tools.noTools')}
              </Typography>
            )}
          </Stack>
        </Box>
      </Paper>

      <Paper
        elevation={0}
        sx={{
          display: 'flex',
          flexDirection: 'column',
          minHeight: 0,
          height: '100%',
          overflow: 'hidden',
          borderRadius: 3,
          border: '1px solid',
          borderColor: 'divider',
          bgcolor: 'background.paper',
        }}
      >
        <Box
          sx={{
            height: '100%',
            minHeight: 0,
            overflowY: 'auto',
            overflowX: 'hidden',
            WebkitOverflowScrolling: 'touch',
            display: 'flex',
            flexDirection: 'column',
            gap: 1.5,
            p: 1,
          }}
        >
          <Box sx={{ minHeight: 0, flexShrink: 0 }}>
            {selectedTool ? (
              <ConfigTable
                configKey={selectedTool.config_key}
                configService={createConfigService(selectedTool.config_key)}
                configs={toolConfigs}
                loading={configLoading || detailLoading}
                onRefresh={() => {
                  queryClient.invalidateQueries({ queryKey: ['tools'] })
                  if (selectedTool.tool_id) {
                    queryClient.invalidateQueries({ queryKey: ['tool-detail', selectedTool.tool_id] })
                  }
                  refetchConfig()
                }}
                showSearchBar={false}
                showToolbar={true}
                resetButtonColor="error"
                fillHeight={false}
                emptyMessage={t('tools.emptyConfig')}
              />
            ) : (
              <Alert severity="info">{t('tools.selectTool')}</Alert>
            )}
          </Box>

          <ToolParametersPanel toolDetail={toolDetail} />
        </Box>
      </Paper>
    </Box>
  )
}
