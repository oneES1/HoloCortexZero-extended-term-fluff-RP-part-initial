import type { ReactNode } from 'react'
import type { I18nDict } from '../../../services/api/types'

export interface FieldSchema {
  type: string
  title?: string
  description?: string
  default?: unknown
  required?: boolean
  is_secret?: boolean
  is_textarea?: boolean
  placeholder?: string
  is_complex?: boolean
  element_type?: string
  key_type?: string
  value_type?: string
  is_need_restart?: boolean
}

export interface ConfigItem {
  key: string
  value: string | number | boolean | Array<string | number | boolean> | Record<string, unknown>
  title: string
  description?: string
  placeholder?: string
  type: string
  is_complex?: boolean
  element_type?: string
  key_type?: string
  value_type?: string
  field_schema?: Record<string, FieldSchema>
  enum?: string[]
  is_secret?: boolean
  is_textarea?: boolean
  ref_model_groups?: boolean
  is_hidden?: boolean
  required?: boolean
  model_type?: string
  sub_item_name?: string
  is_need_restart?: boolean
  i18n_title?: I18nDict
  i18n_description?: I18nDict
  help_label?: string
  help_text?: string
  i18n_help_label?: I18nDict
  i18n_help_text?: I18nDict
}

export interface ModelGroupConfig {
  CHAT_MODEL: string
  USE_GLOBAL_PROXY?: boolean
  CHAT_PROXY: string
  BASE_URL: string
  API_KEY: string
  MODEL_TYPE?: string
  WIRE_API?: 'default' | 'chat' | 'responses' | 'gemini'
  CACHE_TRANSPORT_PROFILE?: 'default' | 'cache_control' | 'prompt_cache_key' | 'cache_prompt' | 'off'
  TEMPERATURE?: number | null
  TOP_P?: number | null
  TOP_K?: number | null
  MAX_OUTPUT_TOKENS?: number | null
  IMAGE_MAX_COUNT?: number | null
  REASONING_MODE?: '' | 'default' | 'off' | 'minimal' | 'low' | 'medium' | 'high'
  TEXT_VERBOSITY?: '' | 'default' | 'low' | 'medium' | 'high'
  REPLAY_REASONING_CONTENT?: boolean
  PRESENCE_PENALTY?: number | null
  FREQUENCY_PENALTY?: number | null
  EXTRA_BODY?: string | null
}

export interface ModelTypeOption {
  value: string
  label: string
  description?: string
  color?: string
  icon?: string
}

export interface ConfigService {
  getConfigList: (configKey: string, options?: { includeHidden?: boolean }) => Promise<ConfigItem[]>
  getModelGroups?: () => Promise<Record<string, ModelGroupConfig>>
  getModelTypes?: () => Promise<ModelTypeOption[]>
  batchUpdateConfig: (configKey: string, configs: Record<string, string>) => Promise<void>
  saveConfig: (configKey: string) => Promise<void>
  reloadConfig: (configKey: string) => Promise<void>
}

export interface ExpandedRowsState {
  [configKey: string]: boolean
}

export interface ConfigTableProps {
  configKey: string
  configService: ConfigService
  configs: ConfigItem[]
  loading?: boolean
  searchText?: string
  onSearchChange?: (text: string) => void
  onRefresh?: () => void
  showSearchBar?: boolean
  showToolbar?: boolean
  title?: string
  emptyMessage?: string
  infoBox?: ReactNode
  showHidden?: boolean
  resetButtonColor?: 'primary' | 'secondary' | 'error' | 'warning' | 'info' | 'success'
  fillHeight?: boolean
}
