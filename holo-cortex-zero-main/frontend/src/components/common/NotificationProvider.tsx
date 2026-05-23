/**
 * 通知系统提供者
 * 整合notistack库和自定义通知组件
 */
import { ReactNode } from 'react'
import { SnackbarProvider } from 'notistack'
import HCZNotification from './HCZNotification'
import { notificationConfig } from './config/notificationConfig'

interface NotificationProviderProps {
  children: ReactNode
}

// 通知提供者组件
export default function NotificationProvider({ children }: NotificationProviderProps) {
  return (
    <SnackbarProvider
      maxSnack={notificationConfig.maxSnack}
      autoHideDuration={notificationConfig.autoHideDuration}
      anchorOrigin={notificationConfig.anchorOrigin}
      // 使用自定义组件
      Components={{
        success: HCZNotification,
        error: HCZNotification,
        warning: HCZNotification,
        info: HCZNotification,
        default: HCZNotification
      }}
      // 自定义类名
      classes={{
        containerRoot: 'hcz-notification-container'
      }}
    >
      {children}
    </SnackbarProvider>
  )
} 