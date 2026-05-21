import axios from './axios'

export type ToolScopeMode = 'disabled' | 'normal_only' | 'advanced_only' | 'all'
export type ToolCapabilityClass = 'user_facing' | 'privileged'

export interface ToolItem {
  tool_id: string
  display_name: string
  description: string
  category: string
  capability_class: ToolCapabilityClass
  scope_mode: ToolScopeMode
  effective_normal_enabled: boolean
  effective_advanced_enabled: boolean
  config_key: string
  supports_multimodal_return: boolean
}

export interface ToolDetail extends ToolItem {
  parameters_schema: Record<string, unknown>
  hard_limit_notice?: string
  trace_behavior: {
    inject_context: boolean
    history_strategy: string
  }
  history_role_default: string
}

export const toolsApi = {
  getTools: async (): Promise<ToolItem[]> => {
    const response = await axios.get<{ data: ToolItem[] }>('/tools')
    return response.data.data
  },
  getToolDetail: async (toolId: string): Promise<ToolDetail> => {
    const response = await axios.get<{ data: ToolDetail }>(`/tools/${toolId}`)
    return response.data.data
  },
  updateToolScope: async (toolId: string, scopeMode: ToolScopeMode): Promise<void> => {
    await axios.post(`/tools/${toolId}/scope`, { scope_mode: scopeMode })
  },
}

export default toolsApi
