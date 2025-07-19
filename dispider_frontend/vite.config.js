import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import AutoImport from 'unplugin-auto-import/vite'
import Components from 'unplugin-vue-components/vite'
import { ElementPlusResolver } from 'unplugin-vue-components/resolvers'
// 导入处理路径所需的模块
import { URL, fileURLToPath } from 'node:url'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [
    vue(),
    AutoImport({
      resolvers: [ElementPlusResolver()],
    }),
    Components({
      resolvers: [ElementPlusResolver()],
    }),
  ],
  resolve: {
    alias: {
      // 使用 Vite 推荐的标准方式来配置别名，确保跨平台兼容性
      '@': fileURLToPath(new URL('./src', import.meta.url))
    }
  },
  // 保留之前的 CSS 预处理器配置
  css: {
    preprocessorOptions: {
      scss: {
        additionalData: `@import "@/styles/_variables.scss";`
      }
    }
  },
  // 配置服务器
  server: {
    host: '0.0.0.0',
    port: 5173,
    open: true,
    cors: true,
    strictPort: true,
    hmr: {
      protocol: 'ws'
    },
    allowedHosts: [
      'dispider.liiper.cn',
    ]
  }
})
