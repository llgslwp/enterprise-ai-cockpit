<script setup>
import { ref, onMounted, onBeforeUnmount, nextTick, watch, computed } from 'vue'
import * as echarts from 'echarts'
import { qualityInspection, qualitySpc, quality8d, quality8dUpdate, quality8dReset } from '../api'

const loading = ref(false)
const errorMsg = ref('')
const quality = ref(null)   // 看板（含 suggestions 四预警建议动作）
const spc = ref(null)       // 控制图数据
const eightd = ref(null)    // 8D 闭环数据
const curMonth = ref(null)

const charts = []

async function load() {
  loading.value = true
  errorMsg.value = ''
  try {
    const month = curMonth.value && curMonth.value !== 'latest' ? curMonth.value : null
    const [r, sr, er] = await Promise.all([
      qualityInspection(month),
      qualitySpc(month),
      quality8d(month),
    ])
    quality.value = r.data?.data
    spc.value = sr.data?.data
    eightd.value = er.data?.data
  } catch (e) {
    errorMsg.value = e?.response?.data?.message || '加载失败'
  } finally {
    loading.value = false
  }
}

const monthOptions = computed(() => {
  const labels = (quality.value?.trend || []).map(t => t.month)
  return ['最新', ...labels]
})

function fmt(v) {
  return Number(v ?? 0).toLocaleString('zh-CN')
}
function fmtRate(v) {
  return Number(v ?? 0).toFixed(1)
}

function selectMonth(m) {
  curMonth.value = m === '最新' ? 'latest' : parseInt(m)
  load()
}

// ============ 控制图渲染 ============
function renderSpc() {
  const el = document.getElementById('chart-spc')
  if (!el || !spc.value) return
  const c = echarts.init(el)
  const pts = spc.value.points || []
  const cl = spc.value.cl || 0
  const days = pts.map(p => p.day)
  const rates = pts.map(p => p.rate)
  const ucls = pts.map(p => p.ucl)
  const lcls = pts.map(p => p.lcl)

  c.setOption({
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'axis',
      formatter: ps => {
        const p = pts[ps[0].dataIndex]
        const warn = p.small_n ? '<br><span style="color:#ffd166">样本量小，破限统计意义弱</span>' : ''
        return `10月${p.day}日<br>不合格率 <b>${p.rate}%</b><br>抽检 ${p.checked} · 不合格 ${p.unqualified}${warn}`
      },
    },
    legend: { data: ['不合格率', 'UCL', 'LCL', '中心线 CL'], textStyle: { color: '#8aa0c8' }, top: 0 },
    grid: { left: 50, right: 20, top: 40, bottom: 30 },
    xAxis: {
      type: 'category', data: days,
      axisLine: { lineStyle: { color: 'rgba(120,150,210,.35)' } },
      axisLabel: { color: '#cfe0ff', fontSize: 11 },
    },
    yAxis: {
      type: 'value',
      axisLine: { show: false }, axisLabel: { color: '#8aa0c8', formatter: '{value}%' },
      splitLine: { lineStyle: { color: 'rgba(120,150,210,.15)' } },
    },
    series: [
      { // 不合格率折线（破限点标红）
        name: '不合格率', type: 'line', data: rates, symbol: 'circle', symbolSize: 6,
        lineStyle: { color: '#4db8ff', width: 2 },
        itemStyle: { color: p => (p.dataIndex >= 0 && pts[p.dataIndex].breach ? '#ff5b7f' : '#4db8ff') },
      },
      { // UCL
        name: 'UCL', type: 'line', data: ucls, symbol: 'none',
        lineStyle: { color: '#ff5b7f', width: 1.2, type: 'dashed' },
      },
      { // LCL
        name: 'LCL', type: 'line', data: lcls, symbol: 'none',
        lineStyle: { color: '#2ee6a8', width: 1.2, type: 'dashed' },
      },
      { // 中心线 CL
        name: '中心线 CL', type: 'line', data: pts.map(() => cl), symbol: 'none',
        lineStyle: { color: '#f5c518', width: 1.5, type: 'dotted' },
      },
    ],
  })
  charts.push(c)
}

function renderCharts() {
  if (!spc.value) return
  charts.forEach(c => c.dispose())
  charts.length = 0
  renderSpc()
}

let resizeHandler = null

watch(spc, async () => {
  if (!spc.value) return
  await nextTick()
  requestAnimationFrame(() => renderCharts())
})

// ============ 8D 卡编辑写回 ============
const editingCard = ref(null)   // 当前正在编辑的 8D 卡 id
const editForm = ref({})        // 编辑表单

function startEdit(card) {
  editingCard.value = card.id
  editForm.value = {
    d4_rootcause: card.d4_rootcause || '',
    d5_correct: card.d5_correct || '',
    d6_verify: card.d6_verify || '',
    d7_prevent: card.d7_prevent || '',
    d8_closed: card.d8_closed || false,
  }
}
function cancelEdit() {
  editingCard.value = null
  editForm.value = {}
}
async function saveCard(card) {
  try {
    const closed = !!editForm.value.d8_closed
    await quality8dUpdate(card.id, {
      d4_rootcause: editForm.value.d4_rootcause,
      d5_correct: editForm.value.d5_correct,
      d6_verify: editForm.value.d6_verify,
      d7_prevent: editForm.value.d7_prevent,
      d8_closed: closed,
      status: closed ? '已关闭' : '进行中',
    })
    editingCard.value = null
    await load()   // 重新拉取合并状态
  } catch (e) {
    errorMsg.value = e?.response?.data?.message || '保存失败'
  }
}
async function resetCard(card) {
  if (!confirm(`确定将「${card.problem}」重置为待执行？`)) return
  try {
    await quality8dReset(card.id)
    await load()
  } catch (e) {
    errorMsg.value = e?.response?.data?.message || '重置失败'
  }
}

const dSteps = [
  { k: 'd1', label: 'D1 组建团队', field: 'd1_team', editable: false },
  { k: 'd2', label: 'D2 描述问题', field: 'd2_desc', editable: false },
  { k: 'd3', label: 'D3 临时措施', field: 'd3_action', editable: false },
  { k: 'd4', label: 'D4 根因分析', field: 'd4_rootcause', editable: true },
  { k: 'd5', label: 'D5 纠正+验证', field: 'd5_correct', editable: true },
  { k: 'd6', label: 'D6 实施+确认', field: 'd6_verify', editable: true },
  { k: 'd7', label: 'D7 防再发', field: 'd7_prevent', editable: true },
  { k: 'd8', label: 'D8 关闭确认', field: 'd8_closed', editable: true },
]

function lvlClass(level) {
  return level === '高' ? 'lvl-high' : level === '备注' ? 'lvl-note' : 'lvl-mid'
}

onMounted(load)
onMounted(() => {
  resizeHandler = () => charts.forEach(c => c.resize())
  window.addEventListener('resize', resizeHandler)
})
onBeforeUnmount(() => {
  charts.forEach(c => c.dispose())
  charts.length = 0
  if (resizeHandler) window.removeEventListener('resize', resizeHandler)
})
</script>

<template>
  <div class="big-screen">
    <div class="top">
      <div class="title">质量管理工具</div>
      <div class="badge" v-if="quality">数据源：本地 Excel（车间抽检表）</div>
      <div class="update-hint" v-if="quality?.mtime">数据更新：{{ quality.mtime }}</div>
    </div>

    <!-- 月份选择器 -->
    <div class="month-bar" v-if="quality">
      <button
        v-for="m in monthOptions"
        :key="m"
        class="month-btn"
        :class="{ active: (m === '最新' && curMonth === 'latest') || (m !== '最新' && parseInt(m) === curMonth) }"
        @click="selectMonth(m)"
      >{{ m }}</button>
    </div>

    <div v-if="loading" class="loading">数据加载中…</div>
    <div v-else-if="errorMsg" class="error">{{ errorMsg }}</div>

    <template v-else-if="quality">
      <div v-if="quality.note" class="note">⚠ {{ quality.note }}</div>

      <!-- ============ 块一：控制图 ============ -->
      <div class="panel">
        <div class="p-title">控制图（p 图）· 每日不合格率</div>
        <div class="box-lg" id="chart-spc"></div>
        <div class="sub-hint">
          中心线 CL {{ spc?.cl }}% · 红点=破限（不合格率超出上控制限） · 橙点=样本量小（n&lt;30）
        </div>
      </div>

      <!-- ============ 块二：四预警建议动作 ============ -->
      <div class="panel">
        <div class="p-title">四预警 · 建议动作（{{ quality.suggestions?.length || 0 }}）</div>
        <p v-if="!quality.suggestions || quality.suggestions.length === 0" class="empty">暂无预警建议。</p>
        <table v-else class="tbl">
          <thead>
            <tr>
              <th>级别</th><th>预警</th><th>问题</th><th>责任部门</th><th>时限</th><th>措施</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(s, i) in quality.suggestions" :key="i">
              <td><span :class="['lvl', lvlClass(s.level)]">{{ s.level }}</span></td>
              <td><span class="alert-tag">{{ s.source_alert }}</span></td>
              <td class="left">{{ s.problem }}</td>
              <td>{{ s.dept }}</td>
              <td>{{ s.deadline }}</td>
              <td class="left">{{ s.action }}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- ============ 块三：8D 闭环 ============ -->
      <div class="panel">
        <div class="p-title">8D 问题解决闭环（{{ eightd?.cards?.length || 0 }}）</div>
        <p v-if="!eightd || !eightd.cards || eightd.cards.length === 0" class="empty">
          暂无「反复出现」问题，无需发起 8D。
        </p>
        <div v-else class="d8-list">
          <div v-for="card in eightd.cards" :key="card.id" class="d8-card">
            <div class="d8-head">
              <div class="d8-title">
                <span :class="['type-tag', card.type === 'cross_month' ? 'type-cross' : 'type-repeat']">
                  {{ card.type === 'cross_month' ? '跨月反复' : '人员反复' }}
                </span>
                <span class="d8-problem">{{ card.problem }}</span>
              </div>
              <span :class="['status', card.status === '已关闭' ? 'status-closed' : 'status-open']">{{ card.status }}</span>
            </div>

            <!-- 只读展示 D1-D3 -->
            <div class="d8-grid">
              <div v-for="st in dSteps.filter(x => !x.editable)" :key="st.k" class="d8-cell">
                <div class="d8-label">{{ st.label }}</div>
                <div class="d8-val">{{ card[st.field] || '—' }}</div>
              </div>
            </div>

            <!-- 可编辑 D4-D8 -->
            <div v-if="editingCard !== card.id" class="d8-grid">
              <div v-for="st in dSteps.filter(x => x.editable && x.field !== 'd8_closed')" :key="st.k" class="d8-cell">
                <div class="d8-label">{{ st.label }}</div>
                <div class="d8-val">{{ card[st.field] || '（未填写）' }}</div>
              </div>
              <div class="d8-cell">
                <div class="d8-label">D8 关闭确认</div>
                <div class="d8-val">{{ card.d8_closed ? '✅ 已关闭' : '○ 未关闭' }}</div>
              </div>
            </div>

            <!-- 编辑表单 -->
            <div v-else class="d8-edit">
              <div class="edit-row"><label>D4 根因分析（5M1E/5Why）</label>
                <textarea v-model="editForm.d4_rootcause" rows="2" placeholder="填写根因"></textarea></div>
              <div class="edit-row"><label>D5 纠正措施 + 验证</label>
                <textarea v-model="editForm.d5_correct" rows="2" placeholder="填写纠正措施与验证方式"></textarea></div>
              <div class="edit-row"><label>D6 实施 + 效果确认</label>
                <textarea v-model="editForm.d6_verify" rows="2" placeholder="填写实施情况与效果确认"></textarea></div>
              <div class="edit-row"><label>D7 防再发（横向铺开）</label>
                <textarea v-model="editForm.d7_prevent" rows="2" placeholder="填写防再发措施"></textarea></div>
              <div class="edit-row"><label class="chk">
                <input type="checkbox" v-model="editForm.d8_closed" /> D8 关闭（签字确认）
              </label></div>
              <div class="edit-actions">
                <button class="btn primary" @click="saveCard(card)">保存</button>
                <button class="btn" @click="cancelEdit()">取消</button>
              </div>
            </div>

            <!-- 操作按钮 -->
            <div class="d8-actions" v-if="editingCard !== card.id">
              <button class="btn primary" @click="startEdit(card)">编辑 D4–D8</button>
              <button class="btn ghost" @click="resetCard(card)">重置</button>
            </div>
          </div>
        </div>
      </div>
    </template>
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
.top { display: flex; align-items: center; gap: 18px; flex-wrap: wrap; }
.title {
  font-size: 28px; font-weight: 700; letter-spacing: 2px;
  text-shadow: 0 0 18px rgba(80, 140, 255, .55);
}
.badge {
  background: linear-gradient(135deg, #2b6cff, #3f9bff); color: #fff;
  padding: 5px 14px; border-radius: 20px; font-size: 13px; font-weight: 600;
  box-shadow: 0 0 16px rgba(59, 130, 255, .55);
}
.update-hint { font-size: 13px; color: #8aa0c8; }

.month-bar { display: flex; gap: 8px; flex-wrap: wrap; margin: 18px 0; }
.month-btn {
  padding: 8px 18px; border: 1px solid rgba(70, 120, 220, .4); border-radius: 8px;
  background: transparent; color: #cfe0ff; cursor: pointer; font-size: 14px;
}
.month-btn.active {
  background: linear-gradient(135deg, #2b6cff, #3f9bff); color: #fff; border-color: transparent;
}

.note {
  margin: 12px 0; padding: 10px 16px; border-radius: 8px;
  background: rgba(255, 157, 67, .15); color: #ffd166; font-size: 14px;
  border: 1px solid rgba(255, 157, 67, .35);
}

.loading, .error { padding: 60px 0; text-align: center; color: #8aa0c8; font-size: 14px; }
.error { color: #ff5b7f; }

.panel {
  background: rgba(16, 32, 72, .55); border: 1px solid rgba(70, 120, 220, .28);
  border-radius: 14px; padding: 16px; backdrop-filter: blur(4px); margin-bottom: 16px;
}
.p-title { font-size: 16px; font-weight: 600; color: #dbe6ff; margin-bottom: 8px; }
.box-lg { height: 380px; width: 100%; }
.sub-hint { font-size: 12px; color: #8aa0c8; margin-top: 6px; }

.tbl { width: 100%; border-collapse: collapse; font-size: 13px; }
.tbl th, .tbl td { padding: 9px 10px; text-align: left; border-bottom: 1px solid rgba(120, 150, 210, .2); }
.tbl th { color: #8aa0c8; font-weight: 600; font-size: 12px; }
.tbl td { color: #dbe6ff; }
.tbl .left { text-align: left; }

.lvl {
  font-size: 12px; padding: 2px 8px; border-radius: 6px; white-space: nowrap;
}
.lvl-high { background: rgba(255, 91, 127, .2); color: #ff5b7f; }
.lvl-mid { background: rgba(245, 197, 24, .18); color: #f5c518; }
.lvl-note { background: rgba(46, 230, 168, .18); color: #2ee6a8; }
.alert-tag {
  font-size: 12px; color: #8aa0c8; background: rgba(120, 150, 210, .15);
  padding: 2px 8px; border-radius: 6px; white-space: nowrap;
}

.empty { color: #8aa0c8; font-size: 13px; }

.d8-list { display: flex; flex-direction: column; gap: 16px; }
.d8-card {
  background: rgba(10, 20, 48, .5); border: 1px solid rgba(70, 120, 220, .3);
  border-radius: 12px; padding: 14px;
}
.d8-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px; }
.d8-title { display: flex; align-items: center; gap: 10px; flex: 1; }
.d8-problem { font-size: 15px; font-weight: 600; color: #e8f0ff; }
.type-tag { font-size: 12px; padding: 2px 8px; border-radius: 6px; white-space: nowrap; font-weight: 600; }
.type-repeat { background: rgba(77, 184, 255, .2); color: #4db8ff; }
.type-cross { background: rgba(255, 91, 127, .2); color: #ff5b7f; }
.status { font-size: 12px; padding: 3px 10px; border-radius: 6px; white-space: nowrap; }
.status-open { background: rgba(245, 197, 24, .2); color: #f5c518; }
.status-closed { background: rgba(46, 230, 168, .2); color: #2ee6a8; }

.d8-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; margin-bottom: 12px; }
.d8-cell {
  background: rgba(16, 32, 72, .4); border: 1px solid rgba(70, 120, 220, .2);
  border-radius: 8px; padding: 10px;
}
.d8-label { font-size: 12px; color: #8aa0c8; margin-bottom: 4px; font-weight: 600; }
.d8-val { font-size: 13px; color: #dbe6ff; line-height: 1.5; }

.d8-edit {
  background: rgba(10, 20, 48, .6); border: 1px solid rgba(70, 120, 220, .35);
  border-radius: 10px; padding: 14px; margin-bottom: 12px;
}
.edit-row { margin-bottom: 12px; }
.edit-row label { display: block; font-size: 13px; color: #cfe0ff; margin-bottom: 6px; }
.edit-row textarea {
  width: 100%; box-sizing: border-box; background: rgba(5, 10, 30, .6);
  border: 1px solid rgba(70, 120, 220, .35); border-radius: 6px;
  color: #e8f0ff; padding: 8px 10px; font-size: 13px; font-family: inherit; resize: vertical;
}
.edit-row label.chk { display: flex; align-items: center; gap: 8px; }
.edit-row input[type="checkbox"] { width: 16px; height: 16px; }

.d8-actions { display: flex; gap: 10px; }
.edit-actions { display: flex; gap: 10px; }
.btn {
  padding: 8px 16px; border: 1px solid rgba(70, 120, 220, .4); border-radius: 8px;
  background: transparent; color: #cfe0ff; cursor: pointer; font-size: 13px;
}
.btn.primary {
  background: linear-gradient(135deg, #2b6cff, #3f9bff); color: #fff; border-color: transparent;
}
.btn.ghost { border-color: rgba(255, 91, 127, .4); color: #ff5b7f; }
.btn:hover { opacity: .9; }
</style>
