import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react-swc'

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  // 加载环境变量
  const env = loadEnv(mode, '.', '')

  // 获取后端地址，默认为 http://127.0.0.1:20261
  const backendUrl = env.VITE_API_BASE_URL || 'http://127.0.0.1:20261'

  return {
    plugins: [react()],
    // 使用相对基址，避免构建产物绑死当前实例的静态挂载前缀。
    base: './',
    optimizeDeps: {
      include: ['@monaco-editor/react'], // 预构建Monaco Editor
    },
    server: {
      proxy: {
        // API 请求代理
        '/api': {
          target: backendUrl,
          changeOrigin: true,
        },
      },
    },
    build: {
      cssMinify: true, // CSS 压缩
      cssCodeSplit: true, // CSS 代码分割
      rollupOptions: {
        output: {
          manualChunks: {
            'react-vendor': ['react', 'react-dom'],
            'mui-vendor': ['@mui/material', '@mui/icons-material'],
            'monaco-editor': ['@monaco-editor/react'], // Monaco Editor 单独分chunk
          },
        },
      },
    },
    css: {
      postcss: './postcss.config.js', // 指定配置文件路径
      devSourcemap: true, // 开发时的 sourcemap
    },
  }
})
