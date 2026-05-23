import axios from './axios'
import { createEventStream } from './utils/stream'

interface ApiResponse<T> {
  code: number
  msg: string
  data: T
}

export interface DashboardOverview {
  total_messages: number
  active_sessions: number
  unique_users: number
  total_tool_chain_runs: number
  success_calls: number
  failed_calls: number
  success_rate: number
}

export interface TrendDataPoint extends Record<string, number | string> {
  timestamp: string
}

export interface DistributionItem {
  label: string
  value: number
  percentage: number
}

export interface RankingItem {
  id: string
  name: string
  value: number
  avatar?: string
}

export interface RealTimeDataPoint {
  timestamp: string
  recent_messages: number
  recent_tool_chain_runs: number
  recent_success_calls: number
  recent_failed_calls: number
  recent_avg_exec_time: number
}

export interface DistributionsResponse {
  stop_type: DistributionItem[]
  message_type: DistributionItem[]
}

export interface LatestMessage {
  id: number
  sender_name: string
  content: string
  create_time: string
  chat_key: string
}

export const dashboardApi = {
  getOverview: async (params: { time_range: string; window_minutes?: number }): Promise<DashboardOverview> => {
    const response = await axios.get<ApiResponse<DashboardOverview>>('/dashboard/overview', { params })
    return response.data.data
  },

  getTrends: async (params: {
    metrics: string
    time_range: string
    interval: string
  }): Promise<TrendDataPoint[]> => {
    const response = await axios.get<ApiResponse<TrendDataPoint[]>>('/dashboard/trends', { params })
    return response.data.data
  },

  getActiveRanking: async (params: {
    ranking_type: string
    time_range: string
    limit?: number
    window_minutes?: number
  }): Promise<RankingItem[]> => {
    const response = await axios.get<ApiResponse<RankingItem[]>>('/dashboard/ranking', { params })
    return response.data.data
  },

  getDistributions: async (params: {
    time_range: string
  }): Promise<DistributionsResponse> => {
    const response = await axios.get<ApiResponse<DistributionsResponse>>('/dashboard/distributions', { params })
    return response.data.data
  },

  getLatestMessage: async (): Promise<LatestMessage | null> => {
    const response = await axios.get<ApiResponse<LatestMessage | null>>('/dashboard/latest-message')
    return response.data.data
  },

  createStatsStream: (
    onMessage: (data: string) => void,
    params: { granularity?: number; window_minutes?: number } = {}
  ) => {
    const searchParams = new URLSearchParams()
    if (params.window_minutes) {
      searchParams.set('window_minutes', String(params.window_minutes))
    } else if (params.granularity) {
      searchParams.set('granularity', String(params.granularity))
    }
    const queryString = searchParams.toString()

    return createEventStream({
      endpoint: `/dashboard/stats/stream${queryString ? `?${queryString}` : ''}`,
      onMessage,
      onError: error => console.error('Dashboard data stream error:', error),
    })
  }
}
