import axios from './axios'

export interface ToolTraceUsage {
  prompt_tokens: number
  completion_tokens: number
  total_tokens: number
  cached_tokens?: number
  raw_usage?: Record<string, unknown>
}

export interface ToolTraceChainRound {
  iteration: number
  model: string
  duration_ms: number
  finish_reason: string
  tool_call_count: number
  text_length: number
  usage: ToolTraceUsage
  reasoning_content?: string
}

export interface ToolTraceChainEvent {
  kind: 'llm' | 'assistant' | 'tool' | 'error'
  iteration: number
  model?: string
  duration_ms?: number
  finish_reason?: string
  tool_call_count?: number
  text_length?: number
  usage?: ToolTraceUsage
  reasoning_content?: string
  text?: string
  tool_name?: string
  call_id?: string
  arguments?: Record<string, unknown>
  result_preview?: string
  is_error?: boolean
  message?: string
}

export interface ToolTraceChainData {
  schema: string
  success: boolean
  stop_type: number
  error_message: string
  context_id: string
  trigger_chat_key: string
  active_dialog_id: string
  trigger_message_text: string
  permission_level: string
  started_at_ms: number
  total_iterations: number
  total_duration_ms: number
  llm_duration_ms: number
  tool_duration_ms: number
  models: string[]
  llm_rounds: ToolTraceChainRound[]
  events: ToolTraceChainEvent[]
  token_input?: number
  token_output?: number
  token_consumption?: number
}

export interface ToolTraceLog {
  id: number
  context_id: string
  chat_key: string
  active_dialog_id: string
  permission_level: string
  trigger_user_id: string
  trigger_user_name: string
  trigger_message_text: string
  summary_text: string
  success: boolean
  create_time: string
  stop_type: number
  llm_duration_ms: number
  tool_duration_ms: number
  total_duration_ms: number
  total_iterations: number
  use_model: string
  token_input: number
  token_output: number
  token_total: number
  trace_data: ToolTraceChainData
}

export enum ExecStopType {
  NORMAL = 0,
  ERROR = 1,
  TIMEOUT = 2,
  AGENT = 8,
  MANUAL = 9,
  SECURITY = 10,
  MULTIMODAL_AGENT = 11,
}

export interface ToolTraceStats {
  total: number
  success: number
  failed: number
  success_rate: number
  agent_count: number
}

export const toolTracesApi = {
  getLogs: async (params: {
    page: number
    page_size: number
    chat_key?: string
    success?: boolean
  }) => {
    const response = await axios.get<{
      data: { total: number; items: ToolTraceLog[] }
    }>('/tool-traces/logs', { params })
    return response.data.data
  },

  getLogContent: async (trace_id: number) => {
    const response = await axios.get<ToolTraceChainData>('/tool-traces/log-content', {
      params: { trace_id },
    })
    return response.data
  },

  getStats: async (recent = 500) => {
    const response = await axios.get<{ data: ToolTraceStats }>('/tool-traces/stats', {
      params: { recent },
    })
    return response.data.data
  },
}
