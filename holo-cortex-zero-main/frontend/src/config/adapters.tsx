import i18next from './i18n'
import { ReactElement } from 'react'

import AdapterConfigPage from '../pages/adapter/AdapterConfigPage'
import OneBotV11NapCatPage from '../pages/adapter/onebot_v11/napcat'
import OneBotV11LogsPage from '../pages/adapter/onebot_v11/logs'

interface AdapterTabConfig {
  label: string
  value: string
  icon: ReactElement
  path: string
  component: ReactElement
}

// 适配器视觉配置
interface AdapterVisualConfig {
  displayName: string // 显示名称
  navIcon: ReactElement // 导航图标
}

interface AdapterConfig {
  key: string
  visual: AdapterVisualConfig
  tabs: AdapterTabConfig[]
}

// 适配器配置映射
const ADAPTER_CONFIGS: Record<string, AdapterConfig> = {
  // OneBot V11 适配器配置
  onebot_v11: {
    key: 'onebot_v11',
    visual: {
      displayName: 'names.onebot_v11',
      navIcon: <></>,
    },
    tabs: [
      {
        label: 'tabs.config',
        value: 'config',
        icon: <></>,
        path: 'config',
        component: <AdapterConfigPage />,
      },
      {
        label: 'tabs.napcat',
        value: 'napcat',
        icon: <></>,
        path: 'napcat',
        component: <OneBotV11NapCatPage />,
      },
      {
        label: 'tabs.logs',
        value: 'logs',
        icon: <></>,
        path: 'logs',
        component: <OneBotV11LogsPage />,
      },
    ],
  },

  telegram: {
    key: 'telegram',
    visual: {
      displayName: 'names.telegram',
      navIcon: <></>,
    },
    tabs: [
      {
        label: 'tabs.config',
        value: 'config',
        icon: <></>,
        path: 'config',
        component: <AdapterConfigPage />,
      },
    ],
  },

  matrix: {
    key: 'matrix',
    visual: {
      displayName: 'names.matrix',
      navIcon: <></>,
    },
    tabs: [
      {
        label: 'tabs.config',
        value: 'config',
        icon: <></>,
        path: 'config',
        component: <AdapterConfigPage />,
      },
    ],
  },
}

/**
 * 获取适配器的选项卡配置
 * @param adapterKey 适配器key
 * @returns 适配器选项卡配置
 */
export const getAdapterConfig = (adapterKey: string): AdapterConfig | undefined => {
  return ADAPTER_CONFIGS[adapterKey]
}

/**
 * 获取适配器选项卡的完整路径
 * @param adapterKey 适配器key
 * @param tabPath 选项卡路径
 * @returns 完整路径
 */
export const getAdapterTabPath = (adapterKey: string, tabPath: string): string => {
  const basePath = `/adapters/${adapterKey}`
  return tabPath ? `${basePath}/${tabPath}` : basePath
}

/**
 * 获取所有适配器的导航配置
 * @returns 导航配置数组
 */
export const getAdapterNavigationConfigs = () => {
  return Object.values(ADAPTER_CONFIGS)
    .map(config => ({
      path: getAdapterTabPath(config.key, config.tabs[0]?.path ?? ''),
      text: i18next.t(config.visual.displayName, { ns: 'adapter' }),
      icon: config.visual.navIcon,
      parent: 'adapters',
    }))
}
