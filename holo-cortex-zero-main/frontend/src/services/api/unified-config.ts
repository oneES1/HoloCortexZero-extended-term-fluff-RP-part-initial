import axios from './axios'
import { ConfigItem, ModelGroupConfig, ModelTypeOption } from '../../components/common/ConfigTable'

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === 'object' && value !== null && !Array.isArray(value)

const normalizeModelGroups = (value: unknown): Record<string, ModelGroupConfig> => {
  if (!value) return {}

  if (Array.isArray(value)) {
    return value.reduce<Record<string, ModelGroupConfig>>((groups, item) => {
      if (!isRecord(item)) return groups

      const rawName = item.group_name ?? item.groupName ?? item.name ?? item.key
      const name = typeof rawName === 'string' ? rawName.trim() : ''
      if (!name) return groups

      if (isRecord(item.config)) {
        groups[name] = item.config as ModelGroupConfig
        return groups
      }

      const {
        group_name: _groupName,
        groupName: _camelGroupName,
        name: _name,
        key: _key,
        config: _config,
        ...rest
      } = item

      groups[name] = rest as ModelGroupConfig
      return groups
    }, {})
  }

  if (!isRecord(value)) return {}

  const nestedGroups = value.MODEL_GROUPS ?? value.model_groups ?? value.groups ?? value.items
  if (nestedGroups && nestedGroups !== value) {
    return normalizeModelGroups(nestedGroups)
  }

  return Object.fromEntries(
    Object.entries(value).filter(([, group]) => isRecord(group))
  ) as Record<string, ModelGroupConfig>
}

export interface BatchUpdateConfigRequest {
  configs: Record<string, string>
}

export interface ConfigInfo {
  config_key: string
  config_class: string
  config_file_path?: string
  config_type: string
  field_count: number
}

export interface GetConfigListOptions {
  includeHidden?: boolean
}

export interface ModelGroupConnectivityResult {
  ok: boolean
  suspected?: boolean
  group_name: string
  model: string
  model_type: string
  protocol: string
  latency_ms: number
  uses_proxy: boolean
  error?: string
  details?: Record<string, unknown>
}

export interface UpdateModelGroupResult {
  connectivity?: ModelGroupConnectivityResult
}

export const unifiedConfigApi = {
  // 获取所有配置键
  getConfigKeys: async (): Promise<string[]> => {
    const response = await axios.get<{ data: string[] }>('/config/keys')
    return response.data.data
  },

  // 获取配置基本信息
  getConfigInfo: async (configKey: string): Promise<ConfigInfo> => {
    const response = await axios.get<{ data: ConfigInfo }>(`/config/info/${configKey}`)
    return response.data.data
  },

  // 获取指定配置的配置列表
  getConfigList: async (configKey: string, options: GetConfigListOptions = {}): Promise<ConfigItem[]> => {
    const response = await axios.get<{ data: ConfigItem[] }>(`/config/list/${configKey}`, {
      params: { include_hidden: options.includeHidden ?? false },
    })
    return response.data.data
  },

  // 获取指定配置的配置项
  getConfigItem: async (configKey: string, itemKey: string): Promise<ConfigItem> => {
    const response = await axios.get<{ data: ConfigItem }>(`/config/get/${configKey}/${itemKey}`)
    return response.data.data
  },

  // 设置指定配置的配置项值
  setConfigValue: async (configKey: string, itemKey: string, value: string): Promise<void> => {
    await axios.post(`/config/set/${configKey}/${itemKey}`, null, {
      params: { value },
    })
  },

  // 批量更新指定配置
  batchUpdateConfig: async (configKey: string, configs: Record<string, string>): Promise<void> => {
    await axios.post(`/config/batch/${configKey}`, { configs })
  },

  // 保存指定配置
  saveConfig: async (configKey: string): Promise<void> => {
    await axios.post(`/config/save/${configKey}`)
  },

  // 重载指定配置
  reloadConfig: async (configKey: string): Promise<void> => {
    await axios.post(`/config/reload/${configKey}`)
  },

  // 获取模型组列表
  getModelGroups: async (): Promise<Record<string, ModelGroupConfig>> => {
    const response = await axios.get<{ data: unknown }>(
      '/config/model-groups'
    )
    return normalizeModelGroups(response.data.data)
  },

  // 获取模型类型列表
  getModelTypes: async (): Promise<ModelTypeOption[]> => {
    const response = await axios.get<{ data: ModelTypeOption[] }>('/config/model-types')
    return response.data.data
  },

  // 模型组管理
  updateModelGroup: async (groupName: string, config: ModelGroupConfig): Promise<UpdateModelGroupResult> => {
    const response = await axios.post<{ data: UpdateModelGroupResult }>(
      `/config/model-groups/${groupName}`,
      config
    )
    return response.data.data || {}
  },

  testModelGroupConnectivity: async (
    config: ModelGroupConfig,
    groupName?: string
  ): Promise<ModelGroupConnectivityResult> => {
    const response = await axios.post<{ data: ModelGroupConnectivityResult }>(
      '/config/model-groups/test',
      config,
      { params: { group_name: groupName || '' } }
    )
    return response.data.data
  },

  deleteModelGroup: async (groupName: string): Promise<void> => {
    await axios.delete(`/config/model-groups/${groupName}`)
  },
}

// 创建配置服务适配器，用于适配ConfigTable组件的接口
export const createConfigService = (configKey: string) => ({
  getConfigList: (key: string = configKey, options?: GetConfigListOptions) => unifiedConfigApi.getConfigList(key, options),
  getModelGroups: unifiedConfigApi.getModelGroups,
  getModelTypes: unifiedConfigApi.getModelTypes,
  batchUpdateConfig: (key: string, configs: Record<string, string>) =>
    unifiedConfigApi.batchUpdateConfig(key || configKey, configs),
  saveConfig: (key: string = configKey) => unifiedConfigApi.saveConfig(key),
  reloadConfig: (key: string = configKey) => unifiedConfigApi.reloadConfig(key),
})

export default unifiedConfigApi
