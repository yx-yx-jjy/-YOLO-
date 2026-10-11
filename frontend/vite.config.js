import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import path from 'path'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src')
    }
  },
  server: {
    port: 5173,
    open: false,
    host: true,
    // Quick Tunnel uses a random *.trycloudflare.com hostname.
    // Restrict the allow-list to that suffix instead of accepting arbitrary hosts.
    allowedHosts: ['.trycloudflare.com'],
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        // 视频流是无限长连接。浏览器换掉 <img> 的 src（切点位 / 点重连）时会
        // abort 请求，但 dev proxy 默认不会把上游那条 socket 一起关掉，
        // 于是后端的 MJPEG 推流循环一直留着空转（实测曾累积 7 条，白占 GPU）。
        // 这里在客户端断开时显式销毁上游响应 / 请求。
        configure(proxy) {
          proxy.on('proxyRes', (proxyRes, req, res) => {
            const teardown = () => {
              if (proxyRes.complete) return // 正常读完的不动它
              try { proxyRes.destroy() } catch (e) { /* 已关闭 */ }
              try { req.destroy() } catch (e) { /* 已关闭 */ }
            }
            res.on('close', teardown)
            res.on('error', teardown)
          })
        }
      },
      '/artifacts': 'http://127.0.0.1:8000'
    }
  }
})
