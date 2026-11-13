import http from './http'

// 后端 API 封装。所有接口以 FastAPI OpenAPI 为唯一契约。

// 登录
export function login(username, password) {
  return http.post('/auth/login', { username, password })
}

export function logout() {
  return http.post('/auth/logout')
}

// 当前登录用户信息（含角色）
export function whoami() {
  return http.get('/auth/me')
}

// 文件上传（保管员 / 生产副总）
export function uploadFile(formData) {
  return http.post('/files/upload', formData)
}

// 文件状态（哪些源文件已上传、缺失）
export function listFiles() {
  return http.get('/files')
}

// 知识库问答（同步）：返回 { answer, sources, rewritten, domain }
export function knowledgeChat(message, history = []) {
  return http.post('/knowledge/chat', { message, history })
}

// 知识库全部知识域（用于前端展示）
export function knowledgeDomains() {
  return http.get('/knowledge/domains')
}

// 知识库问答（流式 SSE）：callbacks = { onToken(text), onMeta(meta), onPhase(name), onError(msg) }
export async function knowledgeChatStream(message, history = [], callbacks = {}) {
  const resp = await fetch('/api/knowledge/chat/stream', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, history }),
    credentials: 'same-origin',
  })
  if (!resp.ok || !resp.body) {
    throw new Error(`请求失败 HTTP ${resp.status}`)
  }
  const reader = resp.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split('\n')
    buffer = lines.pop() ?? ''
    for (const line of lines) {
      const trimmed = line.trim()
      if (!trimmed.startsWith('data:')) continue
      const payload = trimmed.slice(5).trim()
      if (payload === '[DONE]') return
      try {
        const evt = JSON.parse(payload)
        if (evt.type === 'token') callbacks.onToken?.(evt.text)
        else if (evt.type === 'meta') callbacks.onMeta?.(evt)
        else if (evt.type === 'phase') callbacks.onPhase?.(evt.name)
        else if (evt.type === 'error') callbacks.onError?.(evt.message)
      } catch {
        /* 忽略无法解析的行 */
      }
    }
  }
}

// 生产计划管理大屏（production-planning）
export function productionDashboard(month = null) {
  return http.get('/production/dashboard', { params: month ? { month } : {} })
}
export function productionGapStat() {
  return http.get('/production/gap-stat')
}
// 入库填报（成品台账当月入库写回生产计划 F 列，异常即暂停覆盖）
export function productionBackfill() {
  return http.post('/production/backfill')
}
// 排产统计（跑完整排产链路，覆盖 V2.0 基底原文件）
export function productionSchedule() {
  return http.post('/production/schedule')
}
// 6 源文件 + V2.0 基底最后更新日期（按钮旁常驻显示）
export function productionSourceFiles() {
  return http.get('/production/source-files')
}

// 库存管理（inventory-status）
export function inventorySummary() {
  return http.get('/inventory/summary')
}
export function inventorySearch(keyword) {
  return http.get('/inventory/search', { params: { keyword } })
}
export function inventoryAlerts() {
  return http.get('/inventory/alerts')
}
// 原料预警：毛坯库「现有存量」低于安全库存
export function inventoryMaterialGap() {
  return http.get('/inventory/material-gap')
}
// 库存月度流水（入库/出库/结存，6品类+两大系列+明细）
export function inventoryFlowStats(month = null) {
  return http.get('/inventory/flow-stats', { params: month ? { month } : {} })
}
// 库存占比分析（入库/出库/结存 × 各品种/两大系列）
export function inventoryShareStats(month = null) {
  return http.get('/inventory/share-stats', { params: month ? { month } : {} })
}
// 重点关注规格明细（仅清单勾选的规格，本月入出库结存）
export function inventoryFocusStats(month = null) {
  return http.get('/inventory/focus-stats', { params: month ? { month } : {} })
}
// 台账（成品入出库 v8.1）文件信息：文件名 + 最后更新日期
export function inventoryLedgerMeta() {
  return http.get('/inventory/ledger-meta')
}
// 质量看板：车间抽检（KPI/趋势/问题TOP/严重预警）
export function qualityInspection(month = null) {
  return http.get('/quality/inspection', { params: month ? { month } : {} })
}
// 质量看板：原料来料检验（结果分布/供应商/TOP/预警）
export function qualityMaterialInspection(month = null) {
  return http.get('/quality/material-inspection', { params: month ? { month } : {} })
}
// 质量管理工具：控制图（p 图）
export function qualitySpc(month = null) {
  return http.get('/quality/spc', { params: month ? { month } : {} })
}
// 质量管理工具：8D 闭环卡片
export function quality8d(month = null) {
  return http.get('/quality/8d', { params: month ? { month } : {} })
}
// 质量管理工具：写回 8D 卡 D5–D8
export function quality8dUpdate(cardId, fields) {
  return http.post('/quality/8d/update', { card_id: cardId, fields })
}
// 质量管理工具：重置 8D 卡
export function quality8dReset(cardId) {
  return http.post('/quality/8d/reset', { card_id: cardId })
}

// 知识管理（knowledge-management）：文件上传/版本/启停
export function knowledgeUpload(formData) {
  return http.post('/knowledge/manage/upload', formData)
}
export function knowledgeList() {
  return http.get('/knowledge/manage/list')
}
export function knowledgeVersions(id) {
  return http.get(`/knowledge/manage/${id}/versions`)
}
export function knowledgeDownload(id, version = null) {
  const params = version ? { version } : {}
  return http.get(`/knowledge/manage/${id}/download`, { params, responseType: 'blob' })
}
export function knowledgeAddVersion(id, formData) {
  return http.post(`/knowledge/manage/${id}/version`, formData)
}
export function knowledgeRollback(id, version) {
  return http.post(`/knowledge/manage/${id}/rollback`, { version })
}
export function knowledgeToggle(id) {
  return http.post(`/knowledge/manage/${id}/toggle`)
}

// 智能辅助决策（agent-core 多工具调用）：同步对话，返回 { answer, tool_calls }
export function agentChat(question) {
  return http.post('/agent/chat', { question }, { timeout: 60000 })
}
