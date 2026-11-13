<script setup>
import { ref, onMounted } from 'vue'
import {
  knowledgeUpload,
  knowledgeList,
  knowledgeVersions,
  knowledgeDownload,
  knowledgeAddVersion,
  knowledgeRollback,
  knowledgeToggle,
} from '../api'

const loading = ref(false)
const errorMsg = ref('')
const files = ref([])

// 上传区
const fileInput = ref(null)
const selectedFiles = ref([])
const uploadType = ref('工艺类')
const uploadVisibility = ref('全员')
const uploading = ref(false)
const uploadMsg = ref('')
const showHint = ref(false)

const TYPES = ['工艺类', '制度类', '知识类']
const VISIBILITIES = ['全员', '生产', '质量', '管理']

// 入库类型说明（hover 提示 + 智能建议依据）
const TYPE_HINTS = {
  '工艺类': {
    desc: '产品怎么造：生产工艺、作业指导书、操作规程、BOM、规格参数、钎焊/组装/加工工序等「怎么做产品」的内容。',
    examples: '如：加力钳生产工艺、钻杆钳组装作业指导、套管钳规格表',
    counter: '不是：考勤、薪酬、报销、管理制度、行业知识科普',
  },
  '制度类': {
    desc: '公司怎么管：考勤、请假、报销、薪酬、考核、岗位职责、离职、人事行政、管理制度、工作思路与制度规范等「管人管事」的内容。',
    examples: '如：考勤管理制度、质量管理体系建设思路、绩效考核办法',
    counter: '不是：产品加工步骤、钳把镀彩工艺、行业标准科普',
  },
  '知识类': {
    desc: '通用知识科普：行业标准、术语解释、技术背景、通用工艺知识、参考资料等「不特指本公司产品/制度」的通用内容。',
    examples: '如：管钳行业标准 QB/T、钎焊技术原理、材料性能资料',
    counter: '不是：本公司具体产品的工艺、本公司的管理制度',
  },
}

// 智能建议：按文件名关键词匹配（纯规则，不依赖后端/LLM）
const TYPE_KEYWORDS = {
  '制度类': ['制度', '管理', '考勤', '请假', '报销', '薪酬', '工资', '考核', '绩效', '岗位', '职责', '离职', '人事', '行政', '纪律', '规定', '办法', '流程规范', '工作思路', '守则', '奖惩', '福利', '社保', '通知'],
  '工艺类': ['工艺', '作业指导', '作业标准', '操作规程', '工序', '组装', '钎焊', '焊接', '镀', '加工', '热处理', 'BOM', '规格', '参数', '夹具', '模具', '喷砂', '抛丸'],
  '知识类': ['标准', 'GB', 'QB', '术语', '原理', '科普', '手册', '指南', '技术背景', '资料', '材料', '性能'],
}

// 建议结果
const suggestion = ref(null) // { type, reason, keywords }

// 判断优先级：强知识类信号（标准/GB/原理/手册等）> 制度类 > 工艺类
// 「钳/管钳/钻杆」等产品名太泛，不作为强工艺信号，避免把行业标准/科普误判为工艺
function suggestType(name) {
  const n = (name || '').toLowerCase()
  const score = { '制度类': 0, '工艺类': 0, '知识类': 0 }
  const hitKw = { '制度类': [], '工艺类': [], '知识类': [] }
  for (const [t, kws] of Object.entries(TYPE_KEYWORDS)) {
    for (const kw of kws) {
      if (n.includes(kw.toLowerCase())) {
        // 知识类的强信号词（标准/GB/原理/手册等）权重 x2，避免被「钳」等泛词盖过
        const w = t === '知识类' && ['标准', 'gb', 'qb', '原理', '术语', '手册', '指南', '科普'].includes(kw.toLowerCase()) ? 2 : 1
        score[t] += w
        if (hitKw[t].length < 4) hitKw[t].push(kw)
      }
    }
  }
  // 强知识类信号优先；否则取最高分，同分按 制度>工艺>知识 优先
  let best = '知识类'
  let bestScore = score['知识类']
  for (const t of ['制度类', '工艺类']) {
    if (score[t] >= bestScore) { best = t; bestScore = score[t] }
  }
  const keywords = hitKw[best]
  const reason = keywords.length
    ? `命中关键词：${keywords.join('、')}`
    : '未命中明显关键词，建议人工确认'
  return { type: best, score: bestScore, keywords, reason }
}

function onSuggest() {
  if (!selectedFiles.value.length) {
    suggestion.value = { type: null, reason: '请先选择文件' }
    return
  }
  // 对已选文件逐个建议，取最可信（关键词命中数最多）的那个
  let best = null
  for (const f of selectedFiles.value) {
    const s = suggestType(f.name)
    if (!best || s.score > best.score) best = s
  }
  if (best && best.score > 0) {
    uploadType.value = best.type
    suggestion.value = { type: best.type, reason: best.reason, applied: true }
  } else {
    suggestion.value = { type: best?.type || null, reason: best?.reason || '未命中关键词', applied: false }
  }
}

// 版本弹层
const verPanel = ref(null) // { id, name, versions, current_version }
const verLoading = ref(false)

// 新版本上传（隐藏 input）
const versionInput = ref(null)
const versionTargetId = ref(null)

async function load() {
  loading.value = true
  errorMsg.value = ''
  try {
    const r = await knowledgeList()
    files.value = r.data?.data?.items || []
  } catch (e) {
    errorMsg.value = e?.response?.data?.message || '加载失败'
  } finally {
    loading.value = false
  }
}

function trigger() {
  fileInput.value?.click()
}

function onPick(e) {
  const list = Array.from(e.target.files || [])
  if (list.length) {
    selectedFiles.value = [...selectedFiles.value, ...list]
    uploadMsg.value = ''
  }
  e.target.value = ''
}

function onDrop(e) {
  const list = Array.from(e.dataTransfer.files || [])
  const valid = list.filter(f => /\.(md|txt|docx|pdf)$/i.test(f.name))
  if (valid.length !== list.length) {
    uploadMsg.value = '已忽略不支持的文件类型（仅 MD / TXT / docx / PDF）'
  }
  if (valid.length) {
    selectedFiles.value = [...selectedFiles.value, ...valid]
  }
}

function removeSelected(i) {
  selectedFiles.value.splice(i, 1)
}

async function doUpload() {
  if (!selectedFiles.value.length) {
    uploadMsg.value = '请先选择文件'
    return
  }
  uploading.value = true
  uploadMsg.value = ''
  let ok = 0
  let fail = 0
  for (const f of selectedFiles.value) {
    const fd = new FormData()
    fd.append('file', f)
    fd.append('type', uploadType.value)
    fd.append('visibility', uploadVisibility.value)
    try {
      await knowledgeUpload(fd)
      ok++
    } catch (e) {
      fail++
    }
  }
  uploading.value = false
  selectedFiles.value = []
  uploadMsg.value = fail
    ? `上传完成：成功 ${ok} 个，失败 ${fail} 个`
    : `已上传 ${ok} 个文件`
  load()
}

function fmtSize(bytes) {
  if (bytes == null) return '-'
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / 1024 / 1024).toFixed(2) + ' MB'
}

async function onDownload(item) {
  try {
    const resp = await knowledgeDownload(item.id)
    const blob = resp.data
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = item.name
    document.body.appendChild(a)
    a.click()
    a.remove()
    URL.revokeObjectURL(url)
  } catch (e) {
    alert('下载失败')
  }
}

async function openVersions(item) {
  verLoading.value = true
  verPanel.value = { id: item.id, name: item.name, versions: [], current_version: item.current_version }
  try {
    const r = await knowledgeVersions(item.id)
    const d = r.data?.data
    verPanel.value = { ...verPanel.value, versions: d?.versions || [], current_version: d?.current_version }
  } catch (e) {
    alert('读取版本历史失败')
  } finally {
    verLoading.value = false
  }
}

function closeVersions() {
  verPanel.value = null
}

async function onDownloadVersion() {
  // 下载版本弹层中某个历史版本
  const ver = prompt('输入要下载的版本号', String(verPanel.value?.current_version))
  if (!ver) return
  const v = Number(ver)
  if (!v) return
  try {
    const resp = await knowledgeDownload(verPanel.value.id, v)
    const blob = resp.data
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = verPanel.value.name
    document.body.appendChild(a)
    a.click()
    a.remove()
    URL.revokeObjectURL(url)
  } catch (e) {
    alert('下载失败')
  }
}

async function onRollback(v) {
  if (!confirm(`确认回滚到 v${v.version} 吗？将复制该版本为新的当前版本。`)) return
  try {
    await knowledgeRollback(verPanel.value.id, v.version)
    alert('已回滚')
    closeVersions()
    load()
  } catch (e) {
    alert('回滚失败')
  }
}

function triggerVersion(item) {
  versionTargetId.value = item.id
  versionInput.value?.click()
}

async function onPickVersion(e) {
  const f = e.target.files?.[0]
  e.target.value = ''
  if (!f || !versionTargetId.value) return
  const fd = new FormData()
  fd.append('file', f)
  try {
    await knowledgeAddVersion(versionTargetId.value, fd)
    alert('新版本已上传')
    load()
  } catch (e) {
    alert('上传新版本失败')
  } finally {
    versionTargetId.value = null
  }
}

async function onToggle(item) {
  const action = item.status === 'enabled' ? '停用' : '启用'
  if (!confirm(`确认${action}「${item.name}」吗？`)) return
  try {
    await knowledgeToggle(item.id)
    load()
  } catch (e) {
    alert(`${action}失败`)
  }
}

onMounted(load)
</script>

<template>
  <div class="big-screen">
    <div class="top">
      <div class="title">知识管理</div>
      <div class="badge">文件入库 · 版本管理 · 启停</div>
    </div>

    <!-- 上传区 -->
    <div class="panel">
      <div class="p-title">上传新文件</div>
      <div class="upload-row">
        <div
          class="drop-zone"
          @click="trigger"
          @dragover.prevent
          @dragenter.prevent
          @drop.prevent="onDrop"
        >
          <div class="dz-icon">⇪</div>
          <p class="dz-main">拖入文件，或点击选择</p>
          <p class="dz-sub">支持 MD / TXT / docx / PDF</p>
          <input ref="fileInput" type="file" multiple accept=".md,.txt,.docx,.pdf" hidden @change="onPick" />
        </div>
        <div class="upload-fields">
          <div class="field">
            <label class="label-hint">
              入库类型
              <span class="hint-icon" @mouseenter="showHint = true" @mouseleave="showHint = false">?</span>
            </label>
            <select v-model="uploadType">
              <option v-for="t in TYPES" :key="t" :value="t">{{ t }}</option>
            </select>
            <button class="btn sm suggest" :disabled="!selectedFiles.length" @click="onSuggest" title="按文件名智能建议类型">智能建议</button>
          </div>
          <!-- 类型语义提示浮层 -->
          <div v-if="showHint" class="type-hint">
            <div class="th-title">入库类型怎么选？</div>
            <div v-for="t in TYPES" :key="t" class="th-item">
              <div class="th-type">{{ t }} <span class="th-ex">{{ TYPE_HINTS[t].examples }}</span></div>
              <div class="th-desc">{{ TYPE_HINTS[t].desc }}</div>
            </div>
            <div class="th-tip">💡 拿不准就用「智能建议」；标错类型会导致提问时被路由漏检。</div>
          </div>
          <!-- 当前类型的语义说明（随选择变化） -->
          <div class="type-desc">
            <span class="td-label">当前：</span>{{ TYPE_HINTS[uploadType].desc }}
          </div>
          <!-- 智能建议结果 -->
          <div v-if="suggestion" class="suggestion" :class="{ applied: suggestion.applied }">
            {{ suggestion.applied ? '✓ 已建议为「' + suggestion.type + '」' : '建议：' + suggestion.reason }}
          </div>
          <div class="field">
            <label>可见范围</label>
            <select v-model="uploadVisibility">
              <option v-for="v in VISIBILITIES" :key="v" :value="v">{{ v }}</option>
            </select>
          </div>
          <button class="btn primary" :disabled="uploading || !selectedFiles.length" @click="doUpload">
            {{ uploading ? '上传中…' : '上传' }}
          </button>
        </div>
      </div>
      <div v-if="selectedFiles.length" class="selected">
        <span class="sel-tag">已选 {{ selectedFiles.length }} 个：</span>
        <span v-for="(f, i) in selectedFiles" :key="i" class="sel-item">
          {{ f.name }} <span class="sel-x" @click="removeSelected(i)">×</span>
        </span>
      </div>
      <div v-if="uploadMsg" class="msg">{{ uploadMsg }}</div>
    </div>

    <!-- 文件列表 -->
    <div class="panel">
      <div class="p-title">文件列表（{{ files.length }}）</div>
      <div v-if="loading" class="loading">数据加载中…</div>
      <div v-else-if="errorMsg" class="error">{{ errorMsg }}</div>
      <p v-else-if="!files.length" class="empty">暂无文件，请在上方上传。</p>
      <table v-else class="tbl">
        <thead>
          <tr>
            <th>文件名</th><th>入库类型</th><th>可见范围</th>
            <th class="num">当前版本</th><th>状态</th><th>更新时间</th><th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="f in files" :key="f.id" :class="{ disabled: f.status !== 'enabled' }">
            <td class="fname">{{ f.name }}</td>
            <td><span class="chip">{{ f.type }}</span></td>
            <td>{{ f.visibility }}</td>
            <td class="num">v{{ f.current_version }}</td>
            <td>
              <span class="st" :class="f.status">{{ f.status === 'enabled' ? '启用' : '停用' }}</span>
            </td>
            <td>{{ f.updated_at }}</td>
            <td class="ops">
              <button class="btn sm" @click="onDownload(f)">下载</button>
              <button class="btn sm" @click="openVersions(f)">版本</button>
              <button class="btn sm" @click="triggerVersion(f)">新版本</button>
              <button class="btn sm warn" @click="onToggle(f)">
                {{ f.status === 'enabled' ? '停用' : '启用' }}
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <input ref="versionInput" type="file" accept=".md,.txt,.docx,.pdf" hidden @change="onPickVersion" />

    <!-- 版本历史弹层 -->
    <div v-if="verPanel" class="mask" @click.self="closeVersions">
      <div class="modal">
        <div class="m-head">
          <span class="m-title">版本历史 · {{ verPanel.name }}</span>
          <button class="m-close" @click="closeVersions">×</button>
        </div>
        <div v-if="verLoading" class="loading">读取中…</div>
        <table v-else class="tbl vtable">
          <thead>
            <tr><th>版本</th><th class="num">大小</th><th>上传时间</th><th>说明</th><th>操作</th></tr>
          </thead>
          <tbody>
            <tr v-for="v in verPanel.versions" :key="v.version" :class="{ cur: v.version === verPanel.current_version }">
              <td>v{{ v.version }}<span v-if="v.version === verPanel.current_version" class="cur-tag">当前</span></td>
              <td class="num">{{ fmtSize(v.size) }}</td>
              <td>{{ v.uploaded_at }}</td>
              <td>{{ v.remark || '-' }}</td>
              <td class="ops">
                <button class="btn sm" @click="onDownloadVersion">下载</button>
                <button
                  v-if="v.version !== verPanel.current_version"
                  class="btn sm warn"
                  @click="onRollback(v)"
                >回滚到此</button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<style scoped>
.big-screen {
  margin: -24px;
  padding: 22px 28px 30px;
  min-height: 100vh;
  background:
    radial-gradient(1200px 700px at 20% -10%, #12255c 0%, transparent 55%),
    radial-gradient(1000px 600px at 90% 110%, #0d1e4a 0%, transparent 50%),
    linear-gradient(160deg, #050a1e, #0a1230 55%, #060d24);
  color: #e8f0ff;
  font-family: "Microsoft YaHei", "PingFang SC", sans-serif;
}
.top { display: flex; align-items: center; gap: 18px; flex-wrap: wrap; margin-bottom: 22px; }
.title {
  font-size: 28px; font-weight: 700; letter-spacing: 2px;
  text-shadow: 0 0 18px rgba(80, 140, 255, .55);
}
.badge {
  background: linear-gradient(135deg, #2b6cff, #3f9bff); color: #fff;
  padding: 5px 14px; border-radius: 20px; font-size: 13px; font-weight: 600;
  box-shadow: 0 0 16px rgba(59, 130, 255, .55);
}
.panel {
  background: rgba(16, 32, 72, .55); border: 1px solid rgba(70, 120, 220, .28);
  border-radius: 14px; padding: 18px; backdrop-filter: blur(4px);
  margin-bottom: 18px;
}
.p-title { font-size: 16px; font-weight: 600; color: #dbe6ff; margin-bottom: 14px; }

/* 上传区 */
.upload-row { display: flex; gap: 18px; flex-wrap: wrap; align-items: stretch; }
.drop-zone {
  flex: 1; min-width: 280px;
  border: 2px dashed rgba(90, 140, 230, .45); border-radius: 12px;
  padding: 26px 20px; text-align: center; cursor: pointer;
  transition: border-color .2s, background .2s;
}
.drop-zone:hover { border-color: #4f7cf0; background: rgba(40, 80, 180, .15); }
.dz-icon { font-size: 30px; color: #5d7fe0; }
.dz-main { font-size: 16px; color: #dbe6ff; margin: 6px 0 4px; }
.dz-sub { font-size: 13px; color: #8aa0c8; }
.upload-fields { display: flex; flex-direction: column; gap: 10px; justify-content: center; min-width: 200px; }
.field { display: flex; align-items: center; gap: 10px; }
.field label { font-size: 13px; color: #8aa0c8; width: 60px; }
.label-hint { display: flex; align-items: center; gap: 4px; }
.hint-icon {
  display: inline-flex; align-items: center; justify-content: center;
  width: 15px; height: 15px; border-radius: 50%;
  background: #2b3a6e; color: #9fc0ff; font-size: 11px; font-weight: 700;
  cursor: help;
}
.hint-icon:hover { background: #3a4f8f; color: #fff; }
.field select {
  flex: 1; padding: 8px 10px; border: 1px solid #2b3a6e; border-radius: 8px;
  background: #0d1636; color: #e8f0ff; font-size: 14px; outline: none;
}
.btn.suggest { padding: 5px 10px; font-size: 12px; white-space: nowrap; color: #9fc0ff; }
.btn.suggest:hover { background: #1e3068; }

/* 类型语义提示浮层 */
.type-hint {
  position: relative; margin: 2px 0; padding: 12px 14px;
  background: #0d1636; border: 1px solid #2b4b8f; border-radius: 10px;
  font-size: 12px; line-height: 1.6; box-shadow: 0 6px 20px rgba(0,0,0,.35);
}
.th-title { font-size: 13px; font-weight: 700; color: #dbe6ff; margin-bottom: 8px; }
.th-item { padding: 6px 0; border-bottom: 1px dashed rgba(120,150,210,.2); }
.th-item:last-child { border-bottom: none; }
.th-type { font-weight: 600; color: #9fc0ff; }
.th-ex { color: #6f86b8; font-weight: 400; }
.th-desc { color: #b8c6e6; margin-top: 2px; }
.th-tip { margin-top: 8px; color: #ffd166; font-size: 12px; }

/* 当前类型说明 */
.type-desc {
  font-size: 12px; color: #6f86b8; line-height: 1.5; padding: 4px 2px;
}
.td-label { color: #8aa0c8; font-weight: 600; }

/* 智能建议结果 */
.suggestion {
  font-size: 12px; padding: 6px 10px; border-radius: 8px;
  background: #1d2a4d; color: #8aa0c8;
}
.suggestion.applied { background: rgba(76, 208, 125, .12); color: #4cd07d; border: 1px solid rgba(76,208,125,.3); }
.selected { margin-top: 12px; display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }
.sel-tag { font-size: 13px; color: #8aa0c8; }
.sel-item {
  font-size: 13px; background: #1d3a6e; color: #cfe0ff; border-radius: 8px; padding: 3px 10px;
}
.sel-x { color: #ff9db0; cursor: pointer; margin-left: 6px; font-weight: 700; }
.msg { margin-top: 10px; font-size: 13px; color: #ffd166; }
.loading, .error { padding: 40px 0; text-align: center; color: #8aa0c8; font-size: 14px; }
.error { color: #ff5b7f; }
.empty { color: #8aa0c8; font-size: 14px; padding: 20px 0; }

/* 表格 */
.tbl { width: 100%; border-collapse: collapse; font-size: 16px; }
.tbl th, .tbl td {
  padding: 10px 12px; text-align: left;
  border-bottom: 1px solid rgba(120, 150, 210, .2);
}
.tbl th { color: #8aa0c8; font-weight: 600; font-size: 15px; }
.tbl td { color: #dbe6ff; }
.tbl tr.disabled td { color: #5d6a90; opacity: .6; }
.num { text-align: right; font-variant-numeric: tabular-nums; }
.fname { font-weight: 600; color: #eaf0ff; }
.chip {
  font-size: 13px; padding: 2px 10px; border-radius: 10px;
  background: #1d3a6e; color: #9fc0ff; border: 1px solid #2b4b8f;
}
.st { font-size: 13px; font-weight: 600; }
.st.enabled { color: #4cd07d; }
.st.disabled { color: #ff9db0; }
.ops { white-space: nowrap; }

.btn {
  padding: 8px 16px; border: 1px solid #2b3a6e; border-radius: 8px;
  background: #16244d; color: #dbe6ff; font-size: 14px; cursor: pointer;
  transition: background .2s;
}
.btn:hover { background: #1e3068; }
.btn.primary { background: #2b4b9b; border-color: #3659b5; color: #fff; }
.btn.primary:hover { background: #3659b5; }
.btn.primary:disabled { opacity: .5; cursor: not-allowed; }
.btn.sm { padding: 5px 10px; font-size: 13px; }
.btn.warn { color: #ffb4c2; border-color: #5c2b3a; background: #2a1520; }
.btn.warn:hover { background: #3a1c2a; }

/* 版本弹层 */
.mask {
  position: fixed; inset: 0; background: rgba(0, 0, 0, .55);
  display: flex; align-items: center; justify-content: center; z-index: 50;
}
.modal {
  width: 760px; max-width: 92vw; max-height: 80vh; overflow: auto;
  background: linear-gradient(160deg, #0a1230, #060d24);
  border: 1px solid #2b3a6e; border-radius: 14px; padding: 20px;
}
.m-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 14px; }
.m-title { font-size: 16px; font-weight: 600; color: #dbe6ff; }
.m-close { background: transparent; border: none; color: #8aa0c8; font-size: 22px; cursor: pointer; }
.vtable { font-size: 14px; }
.vtable td { font-size: 14px; }
tr.cur td { background: rgba(43, 75, 155, .18); }
.cur-tag {
  font-size: 11px; margin-left: 6px; padding: 1px 7px; border-radius: 8px;
  background: #2b6cff; color: #fff;
}
</style>
