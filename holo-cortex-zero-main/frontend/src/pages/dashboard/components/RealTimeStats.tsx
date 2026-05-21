import React, { useMemo } from 'react'
import {
  Box,
  Typography,
  useTheme,
  useMediaQuery,
  Theme,
  FormControl,
  InputLabel,
  Select,
  SelectChangeEvent,
  MenuItem,
} from '@mui/material'
import {
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
  Area,
  ComposedChart,
} from 'recharts'
import {
  formatTimestampByGranularity,
  formatTimestampToDateTime,
} from '../../../utils/time'
import { RealTimeDataPoint } from '../../../services/api/dashboard'
import { metricColors } from '../../../theme/glass'
import { useTranslation } from 'react-i18next'

interface RealTimeStatsProps {
  title: string
  data: RealTimeDataPoint[]
  granularity: number
  onGranularityChange: (granularity: number) => void
  titleClickable?: boolean
  titleActive?: boolean
  onTitleClick?: () => void
}

interface CustomTooltipProps {
  active?: boolean
  payload?: Array<{
    name: string
    value: number
    color: string
    dataKey: string
  }>
  label?: string | number
  theme: Theme
}

const CustomTooltip: React.FC<CustomTooltipProps> = ({ active, payload, label, theme }) => {
  if (active && payload && payload.length) {
    return (
      <Box
        className="p-3 rounded-md shadow-lg"
        sx={{
          bgcolor: theme.palette.background.paper,
          border: `1px solid ${theme.palette.divider}`,
          borderRadius: '8px',
          boxShadow: theme.palette.mode === 'dark'
            ? '0 8px 24px rgba(0, 0, 0, 0.36)'
            : '0 12px 28px rgba(15, 23, 42, 0.12)',
        }}
      >
        <Typography variant="subtitle2" className="mb-1" color="text.primary">
          {label && formatTimestampToDateTime(label.toString())}
        </Typography>
        {payload.map((entry, index) => (
          <Box key={`item-${index}`} className="flex items-center gap-2 my-1">
            <Box
              component="span"
              className="w-3 h-3 rounded-full"
              sx={{ backgroundColor: entry.color }}
            />
            <Typography variant="body2" color="text.primary" className="font-medium">
              {entry.name}: {entry.dataKey === 'success_rate' ? `${entry.value}%` : entry.value}
            </Typography>
          </Box>
        ))}
      </Box>
    )
  }
  return null
}

const getGranularityOptions = (t: (key: string) => string) => [
  { value: 60, label: t('granularity.1hour') },
  { value: 60 * 24, label: t('granularity.1day') },
  { value: 60 * 24 * 7, label: t('granularity.1week') },
  { value: 60 * 24 * 30, label: t('granularity.1month') },
  { value: 60 * 24 * 30 * 4, label: t('granularity.4months') },
]

const getMetrics = (t: (key: string) => string) => [
  {
    id: 'tool_chain_runs',
    name: t('metrics.toolChainRuns'),
    color: metricColors.tool_chain_runs,
  },
  {
    id: 'success_calls',
    name: t('metrics.successCalls'),
    color: metricColors.success_calls,
  },
  {
    id: 'failed_calls',
    name: t('metrics.failedCalls'),
    color: metricColors.failed_calls,
  },
]

const CHART_HEIGHT = {
  MOBILE: 250,
  DESKTOP: 350,
}

const scrollbar = {
  WIDTH: '6px',
  HEIGHT: '6px',
  TRACK: 'rgba(255, 255, 255, 0.04)',
  THUMB: 'rgba(92, 157, 255, 0.22)',
  THUMB_HOVER: 'rgba(92, 157, 255, 0.3)',
}

export const RealTimeStats: React.FC<RealTimeStatsProps> = ({
  title,
  data,
  granularity,
  onGranularityChange,
  titleClickable = false,
  titleActive = false,
  onTitleClick,
}) => {
  const theme = useTheme()
  const isMobile = useMediaQuery(theme.breakpoints.down('sm'))
  const { t } = useTranslation('dashboard')

  const metricsConfig = useMemo(() => getMetrics(t), [t])
  const granularityOptions = useMemo(() => getGranularityOptions(t), [t])
  const chartAxisColor = theme.palette.text.secondary
  const chartGridColor = theme.palette.mode === 'dark' ? 'rgba(255, 255, 255, 0.04)' : 'rgba(15, 23, 42, 0.08)'
  const formatXAxisTick = useMemo(
    () => (timestamp: string | number) => formatTimestampByGranularity(timestamp, granularity),
    [granularity]
  )

  const handleGranularityChange = (event: SelectChangeEvent<number>) => {
    onGranularityChange(Number(event.target.value))
  }

  const formattedData = useMemo(() => {
    return data.map(point => {
      const success = point.recent_success_calls || 0
      const failed = point.recent_failed_calls || 0

      return {
        timestamp: point.timestamp,
        tool_chain_runs: point.recent_tool_chain_runs || 0,
        success_calls: success,
        failed_calls: failed,
      }
    })
  }, [data])

  return (
    <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      <Box
        sx={{
          display: 'flex',
          alignItems: isMobile ? 'flex-start' : 'center',
          justifyContent: 'space-between',
          flexDirection: isMobile ? 'column' : 'row',
          mb: isMobile ? 2 : 1.5,
          gap: isMobile ? 1 : 0,
        }}
      >
        <Typography
          variant="h6"
          color="text.primary"
          onClick={onTitleClick}
          sx={
            titleClickable
              ? {
                  cursor: 'pointer',
                  px: 1.5,
                  py: 0.75,
                  borderRadius: '10px',
                  border: titleActive
                    ? '1px solid rgba(92, 157, 255, 0.28)'
                    : `1px solid ${theme.palette.divider}`,
                  background: titleActive
                    ? 'rgba(92, 157, 255, 0.14)'
                    : theme.palette.action.hover,
                  userSelect: 'none',
                  '&:hover': {
                    background: titleActive
                      ? 'rgba(92, 157, 255, 0.18)'
                      : theme.palette.action.selected,
                  },
                }
              : undefined
          }
        >
          {title}
        </Typography>
          <FormControl
            size="small"
            sx={{
              minWidth: isMobile ? '100%' : 140,
              '& .MuiOutlinedInput-root': {
                '& fieldset': {
                  borderColor: 'rgba(92, 157, 255, 0.3)',
                },
                '&:hover fieldset': {
                  borderColor: '#5c9dff',
                },
                '&.Mui-focused fieldset': {
                  borderColor: '#5c9dff',
                },
              },
            }}
          >
            <InputLabel id="granularity-select-label">{t('granularity.label')}</InputLabel>
            <Select<number>
              labelId="granularity-select-label"
              value={granularity}
              label={t('granularity.label')}
              onChange={handleGranularityChange}
            >
              {granularityOptions.map(option => (
                <MenuItem key={option.value} value={option.value}>
                  {option.label}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
        </Box>

        {formattedData.length === 0 ? (
          <Box
            className="flex justify-center items-center"
            sx={{ flex: 1, minHeight: 0 }}
          >
            <Typography variant="body2" color="text.secondary">
              {t('charts.noRealtimeData')}
            </Typography>
          </Box>
        ) : (
          <Box
            sx={{
              flex: 1,
              minHeight: 0,
              width: '100%',
              '&::-webkit-scrollbar': {
                width: scrollbar.WIDTH,
                height: scrollbar.HEIGHT,
              },
              '&::-webkit-scrollbar-track': {
                background: scrollbar.TRACK,
                borderRadius: '8px',
              },
              '&::-webkit-scrollbar-thumb': {
                background: scrollbar.THUMB,
                borderRadius: '8px',
                '&:hover': {
                  background: scrollbar.THUMB_HOVER,
                },
              },
            }}
          >
            <ResponsiveContainer width="100%" height="100%">
              <ComposedChart data={formattedData}>
                <CartesianGrid strokeDasharray="3 3" stroke={chartGridColor} />
                <XAxis
                  dataKey="timestamp"
                  tickFormatter={formatXAxisTick}
                  stroke={chartAxisColor}
                  tick={{ fontSize: isMobile ? 10 : 12, fill: chartAxisColor }}
                  minTickGap={24}
                />
                <YAxis stroke={chartAxisColor} tick={{ fontSize: isMobile ? 10 : 12, fill: chartAxisColor }} />
                <Tooltip content={<CustomTooltip theme={theme as Theme} />} />
                <Legend />
                {metricsConfig.map(metric => (
                  <Area
                    key={metric.id}
                    type="monotone"
                    dataKey={metric.id}
                    name={metric.name}
                    stroke={metric.color}
                    fill="rgba(92, 157, 255, 0.18)"
                    strokeWidth={2}
                  />
                ))}
              </ComposedChart>
            </ResponsiveContainer>
          </Box>
        )}
    </Box>
  )
}
