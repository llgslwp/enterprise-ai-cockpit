<script setup>
import { ref, nextTick, watch, onMounted } from 'vue'
import { agentChat } from '../api'
import { renderMarkdown } from '../utils/markdown'

// 智能辅助决策页：多工具调用 Agent 对话（同步接口 + loading 进度反馈）
// 对话历史持久化到 localStorage，切模块 / 刷新页面 / 关浏览器重开都不丢失
const STORAGE_KEY = 'agent_chat_history'

function loadHistory() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    const arr = raw ? JSON.parse(raw) : []
    if (!Array.isArray(arr)) return []
    // 清理「发送中断」残留的占位消息（assistant 且无内容）
    return arr.filter((m) => !(m.role === 'assistant' && !m.content))
  } catch (e) {
    return []
  }
}

const messages = ref(loadHistory())
const input = ref('')
const sending = ref(false)
const listRef = ref(null)

// 工具调用轨迹展开状态（key 为消息索引）
const expandedTools = ref({})

// 对话历史自动保存（消息一变就写入 localStorage）
watch(
  messages,
  (val) => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(val))
    } catch (e) {
      // 容量超限等异常静默忽略，不影响对话
    }
  },
  { deep: true }
)

function clearChat() {
  messages.value = []
  expandedTools.value = {}
  try {
    localStorage.removeItem(STORAGE_KEY)
  } catch (e) {}
}

function scrollBottom() {
  nextTick(() => {
    listRef.value?.scrollTo({ top: listRef.value.scrollHeight })
  })
}

// 进入页面（含刷新/切模块回来）自动滚动到最底端，停在最新一条消息处
onMounted(scrollBottom)

function toggleTools(i) {
  expandedTools.value[i] = !expandedTools.value[i]
}

async function send() {
  const msg = input.value.trim()
  if (!msg || sending.value) return
  input.value = ''
  messages.value.push({ role: 'user', content: msg })
  messages.value.push({ role: 'assistant', content: '', tool_calls: [], error: false })
  // 必须通过数组索引改「响应式代理」对象，改局部变量不会触发 watch、localStorage 不会保存
  const idx = messages.value.length - 1
  sending.value = true
  scrollBottom()
  try {
    const resp = await agentChat(msg)
    const body = resp?.data
    if (body?.code === 0 && body?.data) {
      messages.value[idx].content = body.data.answer || '（无回答）'
      messages.value[idx].tool_calls = body.data.tool_calls || []
    } else {
      messages.value[idx].content = body?.message || '回答失败'
      messages.value[idx].error = true
    }
  } catch (e) {
    messages.value[idx].content = e.response?.data?.message || e.message || '请求失败，请检查后端服务。'
    messages.value[idx].error = true
  } finally {
    sending.value = false
    scrollBottom()
  }
}
</script>

<template>
  <div class="agent">
    <header class="agent-head">
      <div class="head-row">
        <h2>智能辅助决策</h2>
        <button v-if="messages.length" class="clear" title="清空本次对话历史" @click="clearChat">清空对话</button>
      </div>
      <p class="sub">基于多工具调用的智能问答（Agent）——模型动态选择工具查询真实数据，数字可逐值对账</p>
    </header>

    <div ref="listRef" class="agent-list">
      <p v-if="messages.length === 0" class="hint">
        问我生产经营数据，我会调用工具查询后如实回答，例如：<br />
        「11 月库存还剩多少？」「加力钳上个月入库多少？」
      </p>

      <div v-for="(m, i) in messages" :key="i" class="turn" :class="m.role">
        <div
          class="bubble"
          :class="{ loading: m.role === 'assistant' && !m.content, error: m.error }"
        >
          <span v-if="m.content" class="md" v-html="renderMarkdown(m.content)"></span>
          <span v-else>{{ m.role === 'assistant' ? '正在思考…' : '…' }}</span>
        </div>

        <!-- 工具调用轨迹：默认收起，点击展开对账 -->
        <div v-if="m.role === 'assistant' && m.tool_calls && m.tool_calls.length" class="tools">
          <button class="tools-toggle" @click="toggleTools(i)">
            <span class="tools-icon">{{ expandedTools[i] ? '▾' : '▸' }}</span>
            <span class="tools-label">工具调用</span>
            <span class="tools-count">{{ m.tool_calls.length }} 次</span>
          </button>

          <div v-if="expandedTools[i]" class="tools-list">
            <div v-for="(t, j) in m.tool_calls" :key="j" class="tool">
              <div class="tool-head">
                <span class="tool-name">{{ t.name }}</span>
              </div>
              <pre class="tool-content">{{ t.content }}</pre>
            </div>
          </div>
        </div>
      </div>
    </div>

    <footer class="agent-input">
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
.agent {
  height: calc(100vh - 48px);
  display: flex;
  flex-direction: column;
  background: linear-gradient(180deg, #0a1230 0%, #050a1e 100%);
  border-radius: 12px;
  overflow: hidden;
  border: 1px solid #1b2650;
}
.agent-head {
  padding: 18px 22px;
  border-bottom: 1px solid #1b2650;
  background: rgba(255, 255, 255, 0.02);
}
.head-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 4px;
}
.head-row h2 {
  margin: 0;
  font-size: 18px;
  color: #e8edff;
}
.clear {
  padding: 4px 12px;
  font-size: 12px;
  border: 1px solid #26346e;
  border-radius: 6px;
  background: transparent;
  color: #8b96c4;
  cursor: pointer;
  transition: color 0.15s, border-color 0.15s;
}
.clear:hover {
  color: #ffb3bd;
  border-color: #7a2b3c;
}
.sub {
  margin: 0;
  font-size: 12px;
  color: #7c88b8;
}
.agent-list {
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
  font-size: 16px;
  line-height: 1.7;
  word-break: break-word;
}
/* —— Markdown 渲染样式 —— */
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
.turn.user .bubble {
  background: #2b4b9b;
  color: #eaf0ff;
  border-bottom-right-radius: 3px;
}
.turn.assistant .bubble {
  background: #151d3d;
  color: #dce4ff;
  border: 1px solid #22306a;
  border-bottom-left-radius: 3px;
}
.bubble.loading {
  animation: agentPulse 1.4s ease-in-out infinite;
  color: #9fb0e0;
}
.bubble.error {
  border-color: #7a2b3c;
  color: #ffb3bd;
}
@keyframes agentPulse {
  0%, 100% { opacity: 0.55; }
  50% { opacity: 1; }
}
.tools {
  margin-top: 10px;
  width: 90%;
  align-self: flex-start;
}
.tools-toggle {
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
.tools-toggle:hover .tools-label {
  color: #a9c3ff;
}
.tools-icon {
  font-size: 11px;
  color: #6f7db5;
  width: 12px;
  text-align: center;
}
.tools-count {
  color: #4f7cf0;
  font-weight: 600;
}
.tools-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-top: 8px;
}
.tool {
  background: #0d1636;
  border: 1px solid #1c2755;
  border-radius: 8px;
  padding: 8px 10px;
}
.tool-head {
  margin-bottom: 4px;
}
.tool-name {
  font-size: 12px;
  font-weight: 600;
  color: #4f7cf0;
}
.tool-content {
  margin: 0;
  font-size: 12px;
  color: #aeb8dd;
  line-height: 1.5;
  white-space: pre-wrap;
  word-break: break-all;
  font-family: inherit;
}
.agent-input {
  display: flex;
  gap: 10px;
  padding: 14px 18px;
  border-top: 1px solid #1b2650;
  background: rgba(255, 255, 255, 0.02);
}
.agent-input input {
  flex: 1;
  padding: 11px 14px;
  border: 1px solid #26346e;
  border-radius: 8px;
  background: #0d1636;
  color: #e8edff;
  font-size: 14px;
  outline: none;
}
.agent-input input:focus {
  border-color: #4f7cf0;
}
.agent-input input::placeholder {
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
