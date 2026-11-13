import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [vue()],
  server: {
    host: '127.0.0.1',
    port: 5173,
    watch: {
      // 用轮询替代系统文件通知，确保任何电脑（尤其 Windows D 盘 + 直跑 vite.js）
      // 都能可靠感知文件改动并热更新，避免「改了代码页面不生效」。
      usePolling: true,
      interval: 300,
    },
    proxy: {
      // 开发期将 /api 请求代理到 FastAPI 后端，避免跨域
      '/api': {
        target: 'http://127.0.0.1:8000',
        // 关键：不改写 Host 头，让后端看到浏览器真实的 Host（localhost / 127.0.0.1）
        // 这样签发的 session cookie 域与浏览器 origin 一致，登录态才能正确写入/回读。
        // 若 changeOrigin:true 会把 Host 改成 127.0.0.1，导致用 localhost 打开时 cookie 域不匹配、登录失败。
        changeOrigin: false,
      },
    },
  },
})
