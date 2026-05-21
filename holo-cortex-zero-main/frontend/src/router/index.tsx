import { lazy, ComponentType, Suspense } from 'react'
import { createHashRouter, Navigate } from 'react-router-dom'
import { CircularProgress, Box } from '@mui/material'
import MainLayoutNew from '../layouts/MainLayoutNew'
import AdapterLayout from '../layouts/AdapterLayout'
import LoginPage from '../pages/login'
import MonitorPage from '../pages/monitor'
import ManagePage from '../pages/manage'

// 创建一个包装器组件来处理懒加载和加载状态
const lazyLoad = (importFn: () => Promise<{ default: ComponentType }>) => {
  const LazyComponent = lazy(importFn)
  return (
    <Suspense 
      fallback={
        <Box 
          sx={{ 
            display: 'flex', 
            justifyContent: 'center', 
            alignItems: 'center', 
            height: '100%',
            minHeight: 200 
          }}
        >
          <CircularProgress />
        </Box>
      }
    >
      <LazyComponent />
    </Suspense>
  )
}

const router = createHashRouter([
  {
    path: '/login',
    element: <LoginPage />,
  },
  {
    path: '/',
    element: <MainLayoutNew />,
    children: [
      {
        index: true,
        element: <Navigate to="/monitor/dashboard" replace />,
      },
      {
        path: 'monitor',
        element: <MonitorPage />,
        children: [
          {
            index: true,
            element: <Navigate to="dashboard" replace />,
          },
          {
            path: 'dashboard',
            element: lazyLoad(() => import('../pages/dashboard')),
          },
          {
            path: 'logs',
            element: lazyLoad(() => import('../pages/logs')),
          },
          {
            path: 'traces',
            element: lazyLoad(() => import('../pages/tool-traces')),
          },
          {
            path: 'channels',
            element: lazyLoad(() => import('../pages/chat-channel')),
          },
        ],
      },
      {
        path: 'manage',
        element: <ManagePage />,
        children: [
          {
            index: true,
            element: <Navigate to="users" replace />,
          },
          {
            path: 'users',
            element: lazyLoad(() => import('../pages/user-manager')),
          },
          {
            path: 'prompts',
            element: lazyLoad(() => import('../pages/prompt-management')),
          },
          {
            path: 'tools',
            element: lazyLoad(() => import('../pages/tools/management')),
          },
        ],
      },
      {
        path: 'adapters',
        children: [
          {
            index: true,
            element: <Navigate to="onebot_v11/config" replace />,
          },
          {
            path: ':adapterKey',
            element: <AdapterLayout />,
            children: [
              {
                index: true,
                element: lazyLoad(() => import('../pages/adapter/AdapterTabPage')),
              },
              {
                path: '*',
                element: lazyLoad(() => import('../pages/adapter/AdapterTabPage')),
              },
            ],
          },
        ],
      },
      {
        path: 'settings',
        element: lazyLoad(() => import('../pages/settings')),
        children: [
          {
            index: true,
            element: <Navigate to="system" replace />,
          },
          {
            path: 'system',
            element: lazyLoad(() => import('../pages/settings/system')),
          },
          {
            path: 'model-groups',
            element: lazyLoad(() => import('../pages/settings/model_group')),
          },
        ],
      },
      {
        path: 'dashboard',
        element: <Navigate to="/monitor/dashboard" replace />,
      },
      {
        path: 'logs',
        element: <Navigate to="/monitor/logs" replace />,
      },
      {
        path: 'tool-traces',
        element: <Navigate to="/monitor/traces" replace />,
      },
      {
        path: 'chat-channel',
        element: <Navigate to="/monitor/channels" replace />,
      },
      {
        path: 'user-manager',
        element: <Navigate to="/manage/users" replace />,
      },
      {
        path: 'prompt-management',
        element: <Navigate to="/manage/prompts" replace />,
      },
      {
        path: 'tools',
        children: [
          {
            index: true,
            element: <Navigate to="/manage/tools" replace />,
          },
          {
            path: 'management',
            element: <Navigate to="/manage/tools" replace />,
          },
        ],
      },
    ],
  },
  {
    path: '*',
    element: <Navigate to="/" replace />,
  },
])

export default router
