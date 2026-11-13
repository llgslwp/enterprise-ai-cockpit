import axios from 'axios'

// 统一 axios 实例：所有后端接口走 /api 前缀
// 携带凭证（Session Cookie），后端据此识别登录态
const http = axios.create({
  baseURL: '/api',
  withCredentials: true,
  timeout: 30000,
})

// 统一响应拦截：后端约定 { code, message, data } 结构
http.interceptors.response.use(
  (resp) => resp,
  (err) => {
    const status = err.response?.status
    if (status === 401 || status === 403) {
      // 未登录 / 无权限：引导回登录页
      if (window.location.pathname !== '/login') {
        window.location.href = '/login'
      }
    }
    return Promise.reject(err)
  },
)

export default http
