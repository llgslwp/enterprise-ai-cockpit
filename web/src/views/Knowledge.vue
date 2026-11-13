<script setup>
import { ref, nextTick, onMounted } from 'vue'
import { knowledgeChatStream, knowledgeDomains } from '../api'
import { renderMarkdown } from '../utils/markdown'

// 知识库问答页：流式输出 + 引用溯源展示 + 对话常驻（localStorage 持久化）
const STORAGE_KEY = 'kb_chat_history'

// 从 localStorage 恢复历史对话（仅保留可序列化的字段）
function loadHistory() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return []
    const arr = JSON.parse(raw)
    if (!Array.isArray(arr)) return []
    // 归一化：确保每条记录字段齐全，且过滤掉「空 assistant」（上次发送中断遗留的占位）
    return arr
      .filter((m) => m && (m.role === 'user' || m.role === 'assistant'))
      .filter((m) => !(m.role === 'assistant' && !m.content))
      .map((m) => ({
        role: m.role,
        content: m.content || '',
        sources: Array.isArray(m.sources) ? m.sources : [],
        domain: m.domain || '',
        rewritten: m.rewritten || '',
        phase: m.phase || '',
      }))
  } catch {
    return []
  }
}

function saveHistory() {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(messages.value))
  } catch {
    // 存储超限等异常静默忽略，不阻塞问答
  }
}

const messages = ref(loadHistory())
const input = ref('')
const sending = ref(false)
const listRef = ref(null)
const domains = ref([]) // 知识域列表（后端返回）

onMounted(async () => {
  // 常驻：进入页面即定位到最底端（最新记录）
  scrollBottom()
  try {
    const resp = await knowledgeDomains()
    // 后端约定 { code, message, data }，域列表在 resp.data.data.domains
    const list = resp?.data?.data?.domains
    if (Array.isArray(list) && list.length) {
      domains.value = list
    }
  } catch {
    // 域列表拉取失败不阻塞问答，副标题回退为静态文案
  }
})

function scrollBottom() {
  nextTick(() => {
    listRef.value?.scrollTo({ top: listRef.value.scrollHeight })
  })
}

function buildHistory() {
  // 把已有对话转成后端 history（含 user / assistant 文本）
  return messages.value
    .filter((m) => (m.role === 'user' || m.role === 'assistant') && m.content)
    .map((m) => ({ role: m.role, content: m.content }))
}

async function send() {
  const msg = input.value.trim()
  if (!msg || sending.value) return
  input.value = ''
  messages.value.push({ role: 'user', content: msg })
  const assistantMsg = { role: 'assistant', content: '', sources: [], domain: '', rewritten: '', phase: 'rewrite' }
  messages.value.push(assistantMsg)
  sending.value = true
  saveHistory()
  scrollBottom()
  try {
    const history = buildHistory().slice(0, -1) // 去掉刚推入的空 assistant
    await knowledgeChatStream(msg, history, {
      onToken: (text) => {
        assistantMsg.content += text
        saveHistory()
        scrollBottom()
      },
      onPhase: (name) => {
        assistantMsg.phase = name
        scrollBottom()
      },
      onMeta: (meta) => {
        assistantMsg.sources = meta.sources || []
        assistantMsg.domain = meta.domain
        assistantMsg.rewritten = meta.rewritten
        saveHistory()
        scrollBottom()
      },
      onError: (err) => {
        if (!assistantMsg.content) assistantMsg.content = err
        saveHistory()
        scrollBottom()
      },
    })
  } catch (e) {
    if (!assistantMsg.content) {
      assistantMsg.content = e.message || '请求失败，请检查后端服务。'
    }
  } finally {
    sending.value = false
    scrollBottom()
  }
}

// 清空对话记录（localStorage + 内存）
function clearChat() {
  if (!messages.value.length) return
  messages.value = []
  try {
    localStorage.removeItem(STORAGE_KEY)
  } catch {
    // 忽略
  }
}

// 根据阶段返回加载占位文案
function phaseText(m) {
  if (m.phase === 'rewrite') return '正在理解问题…'
  if (m.phase === 'retrieve') return '正在检索知识库…'
  if (m.phase === 'generate') return '正在生成回答…'
  return '正在处理…'
}

// 引用来源展开/收起状态（key 为消息索引）
const expandedSources = ref({})
function toggleSources(i) {
  expandedSources.value[i] = !expandedSources.value[i]
}
</script>

<template>
  <div class="kb">
    <header class="kb-head">
      <div class="kb-head-row">
        <div class="kb-head-title">
          <h2>企业知识库</h2>
          <p class="sub">基于 <span class="sub-domains">{{ domains.length ? domains.join(' · ') : '生产工艺 · 作业指导书 · 行业标准' }}</span> 的检索增强问答（RAG）</p>
          <div v-if="domains.length" class="domain-bar">
            <span v-for="d in domains" :key="d" class="domain-chip">{{ d }}</span>
          </div>
        </div>
        <button v-if="messages.length" class="clear-btn" @click="clearChat">清空对话记录</button>
      </div>
    </header>

    <div ref="listRef" class="kb-list">
      <p v-if="messages.length === 0" class="hint">
        问我任何工艺、作业、标准相关问题，例如：<br />
        「含钛重型管钳有哪些规格？」「伸缩型加力的成品计划怎么算？」
      </p>

      <div v-for="(m, i) in messages" :key="i" class="turn" :class="m.role">
        <div class="bubble" :class="{ loading: m.role === 'assistant' && !m.content }">
          <span v-if="m.role === 'assistant' && m.content" class="md" v-html="renderMarkdown(m.content)"></span>
          <span v-else>{{ m.content || (m.role === 'assistant' ? phaseText(m) : '…') }}</span>
        </div>

        <!-- 引用溯源：默认收起为【1】【2】…，点击展开 -->
        <div v-if="m.role === 'assistant' && m.sources && m.sources.length" class="sources">
          <button class="src-toggle" @click="toggleSources(i)">
            <span class="src-toggle-icon">{{ expandedSources[i] ? '▾' : '▸' }}</span>
            <span class="src-toggle-label">引用来源</span>
            <span class="src-toggle-idxs">{{ m.sources.map(s => `【${s.index}】`).join(' ') }}</span>
          </button>

          <div v-if="expandedSources[i]" class="src-list">
            <div v-for="s in m.sources" :key="s.index" class="src">
              <span class="src-idx">[{{ s.index }}]</span>
              <div class="src-body">
                <div class="src-meta">
                  <span class="tag">{{ s.domain }}</span>
                  <span class="path">{{ s.title }} / {{ s.title_path }}</span>
                </div>
                <div class="src-snippet">{{ s.snippet }}</div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <footer class="kb-input">
      <input
        v-model="input"
        type="text"
        placeholder="输入问题，回车发送…"
        :disabled="sending"
        @keyup.enter="send"
      />
      <button class="send" :disabled="sending || !input.trim()" @click="send">发送</button>
    </footer>
  </div>
</template>

<style scoped>
.kb {
  height: calc(100vh - 48px);
  display: flex;
  flex-direction: column;
  background: linear-gradient(180deg, #0a1230 0%, #050a1e 100%);
  border-radius: 12px;
  overflow: hidden;
  border: 1px solid #1b2650;
}
.kb-head {
  padding: 18px 22px;
  border-bottom: 1px solid #1b2650;
  background: rgba(255, 255, 255, 0.02);
}
.kb-head-row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}
.kb-head-title {
  flex: 1;
  min-width: 0;
}
.clear-btn {
  flex-shrink: 0;
  padding: 7px 14px;
  border: 1px solid #3a4a8c;
  border-radius: 8px;
  background: transparent;
  color: #9fb0e0;
  font-size: 12px;
  cursor: pointer;
  white-space: nowrap;
  transition: all 0.2s;
}
.clear-btn:hover {
  color: #ffd9d9;
  border-color: #b05555;
  background: rgba(176, 85, 85, 0.12);
}
.kb-head h2 {
  margin: 0 0 4px;
  font-size: 18px;
  color: #e8edff;
}
.sub {
  margin: 0;
  font-size: 12px;
  color: #7c88b8;
}
.sub-domains {
  color: #a9c3ff;
  font-weight: 600;
}
.domain-bar {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 8px;
}
.domain-chip {
  font-size: 11px;
  padding: 2px 10px;
  border-radius: 11px;
  background: #1d3a6e;
  color: #9fc0ff;
  border: 1px solid #2b4b8f;
}
.kb-list {
  flex: 1;
  overflow-y: auto;
  padding: 18px 22px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.hint {
  color: #7c88b8;
  font-size: 13px;
  text-align: center;
  margin-top: 60px;
  line-height: 1.8;
}
.turn {
  display: flex;
  flex-direction: column;
}
.turn.user {
  align-items: flex-end;
}
.turn.assistant {
  align-items: flex-start;
}
.bubble {
  max-width: 78%;
  padding: 11px 14px;
  border-radius: 10px;
  font-size: 14px;
  line-height: 1.7;
  word-break: break-word;
}
.turn.user .bubble {
  background: #2b4b9b;
  color: #eaf0ff;
  border-bottom-right-radius: 3px;
  white-space: pre-wrap;
}
.turn.assistant .bubble {
  background: #151d3d;
  color: #dce4ff;
  border: 1px solid #22306a;
  border-bottom-left-radius: 3px;
  white-space: normal;
}
.bubble.loading {
  animation: kbPulse 1.4s ease-in-out infinite;
  color: #9fb0e0;
}
@keyframes kbPulse {
  0%, 100% { opacity: 0.55; }
  50% { opacity: 1; }
}

/* —— Markdown 渲染样式（与智能辅助决策页一致的正规表格范式）—— */
.md :deep(p) {
  margin: 0 0 8px;
}
.md :deep(p:last-child) {
  margin-bottom: 0;
}
.md :deep(strong) {
  color: #fff;
  font-weight: 700;
}
.md :deep(h1),
.md :deep(h2),
.md :deep(h3),
.md :deep(h4) {
  margin: 4px 0 8px;
  font-weight: 700;
  color: #fff;
  line-height: 1.4;
}
.md :deep(h1) { font-size: 19px; }
.md :deep(h2) { font-size: 18px; }
.md :deep(h3) { font-size: 17px; }
.md :deep(h4) { font-size: 16px; }
.md :deep(ul),
.md :deep(ol) {
  margin: 0 0 8px;
  padding-left: 20px;
}
.md :deep(li) {
  margin: 2px 0;
}
.md :deep(code) {
  background: #0d1636;
  border: 1px solid #22306a;
  border-radius: 4px;
  padding: 1px 5px;
  font-size: 14px;
  color: #9fd0ff;
  font-family: 'Consolas', 'Menlo', monospace;
}
.md :deep(pre) {
  background: #0d1636;
  border: 1px solid #1c2755;
  border-radius: 6px;
  padding: 10px 12px;
  overflow-x: auto;
  margin: 0 0 8px;
}
.md :deep(pre code) {
  background: transparent;
  border: none;
  padding: 0;
  color: #aeb8dd;
}
.md :deep(blockquote) {
  margin: 0 0 8px;
  padding: 4px 12px;
  border-left: 3px solid #4f7cf0;
  background: rgba(79, 124, 240, 0.08);
  color: #a9b6e0;
}
.md :deep(hr) {
  border: none;
  border-top: 1px solid #22306a;
  margin: 10px 0;
}
.md :deep(table) {
  border-collapse: collapse;
  margin: 6px 0 10px;
  width: 100%;
  font-size: 15px;
}
.md :deep(th),
.md :deep(td) {
  border: 1px solid #2a3a78;
  padding: 6px 10px;
  text-align: left;
}
.md :deep(th) {
  background: #1b2650;
  color: #fff;
  font-weight: 600;
  white-space: nowrap;
}
.md :deep(td) {
  color: #dce4ff;
  font-variant-numeric: tabular-nums;
}
.md :deep(tr:nth-child(even) td) {
  background: rgba(255, 255, 255, 0.02);
}
.sources {
  margin-top: 10px;
  width: 90%;
  align-self: flex-start;
}
.src-toggle {
  display: flex;
  align-items: center;
  gap: 6px;
  background: transparent;
  border: none;
  padding: 4px 0;
  cursor: pointer;
  font-size: 12px;
  color: #8b96c4;
}
.src-toggle:hover .src-toggle-label {
  color: #a9c3ff;
}
.src-toggle-icon {
  font-size: 11px;
  color: #6f7db5;
  width: 12px;
  text-align: center;
}
.src-toggle-label {
  transition: color 0.2s;
}
.src-toggle-idxs {
  color: #4f7cf0;
  font-weight: 600;
}
.src-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-top: 8px;
}
.src {
  display: flex;
  gap: 8px;
  background: #0d1636;
  border: 1px solid #1c2755;
  border-radius: 8px;
  padding: 8px 10px;
}
.src-idx {
  font-weight: 700;
  color: #4f7cf0;
  font-size: 13px;
  flex-shrink: 0;
}
.src-body {
  flex: 1;
  min-width: 0;
}
.src-meta {
  display: flex;
  gap: 8px;
  align-items: center;
  margin-bottom: 3px;
  flex-wrap: wrap;
}
.tag {
  font-size: 11px;
  padding: 1px 7px;
  border-radius: 10px;
  background: #1d3a6e;
  color: #9fc0ff;
}
.path {
  font-size: 12px;
  color: #8b96c4;
}
.src-snippet {
  font-size: 12px;
  color: #aeb8dd;
  line-height: 1.5;
  overflow: hidden;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}
.kb-input {
  display: flex;
  gap: 10px;
  padding: 14px 18px;
  border-top: 1px solid #1b2650;
  background: rgba(255, 255, 255, 0.02);
}
.kb-input input {
  flex: 1;
  padding: 11px 14px;
  border: 1px solid #26346e;
  border-radius: 8px;
  background: #0d1636;
  color: #e8edff;
  font-size: 14px;
  outline: none;
}
.kb-input input:focus {
  border-color: #4f7cf0;
}
.kb-input input::placeholder {
  color: #5d6a9e;
}
.send {
  padding: 11px 22px;
  border: none;
  border-radius: 8px;
  background: #2b4b9b;
  color: #fff;
  font-size: 14px;
  cursor: pointer;
}
.send:hover {
  background: #3659b5;
}
.send:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>
