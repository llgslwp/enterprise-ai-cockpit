<script setup>
import { ref, onMounted, onBeforeUnmount, nextTick, watch, computed } from 'vue'
import * as echarts from 'echarts'
import { qualityInspection } from '../api'

const loading = ref(false)
const errorMsg = ref('')
const quality = ref(null)   // 车间抽检（生产巡检）数据
const curMonth = ref(null)  // 当前选中月份（数字或 'latest'）

const charts = []

async function load() {
  loading.value = true
  errorMsg.value = ''
  try {
    const month = curMonth.value && curMonth.value !== 'latest' ? curMonth.value : null
    const r = await qualityInspection(month)
    quality.value = r.data?.data
  } catch (e) {
    errorMsg.value = e?.response?.data?.message || '加载失败'
  } finally {
    loading.value = false
  }
}

// 可用月份（从 trend 推导，含 'latest'）
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

function renderCharts() {
  if (!quality.value) return
  charts.forEach(c => c.dispose())
  charts.length = 0
  renderTrend()
  renderTop('by_problem', 'chart-problem')
  renderTop('by_part', 'chart-part')
  renderTop('by_section', 'chart-section')
  renderTop('by_name', 'chart-name')
}

function renderTrend() {
  const el = document.getElementById('chart-trend')
  if (!el) return
  const c = echarts.init(el)
  const data = quality.value.trend || []
  c.setOption({
    backgroundColor: 'transparent',
    tooltip: { trigger: 'axis', formatter: '{b}: {c}%' },
    grid: { left: 50, right: 20, top: 30, bottom: 30 },
    xAxis: {
      type: 'category', data: data.map(t => t.month),
      axisLine: { lineStyle: { color: 'rgba(120,150,210,.35)' } },
      axisLabel: { color: '#cfe0ff', fontSize: 12 },
    },
    yAxis: {
      type: 'value', min: 90, max: 100,
      axisLine: { show: false }, axisLabel: { color: '#8aa0c8', formatter: '{value}%' },
      splitLine: { lineStyle: { color: 'rgba(120,150,210,.15)' } },
    },
    series: [{
      type: 'line', data: data.map(t => t.rate), smooth: true,
      lineStyle: { color: '#2ee6a8', width: 3 },
      itemStyle: { color: '#2ee6a8' },
      areaStyle: { color: 'rgba(46,230,168,.12)' },
      label: { show: true, color: '#cfe0ff', fontSize: 11, formatter: '{c}%' },
    }],
  })
  charts.push(c)
}

function renderTop(key, id) {
  const el = document.getElementById(id)
  if (!el) return
  const c = echarts.init(el)
  const data = (quality.value.issue_top?.[key] || []).slice().reverse()
  c.setOption({
    backgroundColor: 'transparent',
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    grid: { left: 90, right: 40, top: 10, bottom: 20 },
    xAxis: {
      type: 'value', minInterval: 1,
      axisLine: { show: false }, axisLabel: { color: '#8aa0c8' },
      splitLine: { lineStyle: { color: 'rgba(120,150,210,.15)' } },
    },
    yAxis: {
      type: 'category', data: data.map(d => d.name),
      axisLine: { lineStyle: { color: 'rgba(120,150,210,.35)' } },
      axisLabel: { color: '#cfe0ff', fontSize: 11 },
    },
    series: [{
      type: 'bar', data: data.map(d => d.count), barWidth: 12,
      itemStyle: { color: '#4db8ff' },
      label: { show: true, position: 'right', color: '#cfe0ff', fontSize: 11 },
    }],
  })
  charts.push(c)
}

let resizeHandler = null

watch(quality, async () => {
  if (!quality.value) return
  await nextTick()
  requestAnimationFrame(() => renderCharts())
})

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
      <div class="title">生产巡检</div>
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
      <!-- 回退提示 -->
      <div v-if="quality.note" class="note">⚠ {{ quality.note }}</div>

      <!-- KPI 三卡 -->
      <div class="kpis">
        <div class="kpi">
          <div class="lbl">当月总合格率</div>
          <div class="val">{{ fmtRate(quality.overall.rate) }}%</div>
          <div class="sub">抽检 {{ fmt(quality.overall.checked) }} · 合格 {{ fmt(quality.overall.qualified) }}</div>
        </div>
        <div class="kpi">
          <div class="lbl">严重预警批次</div>
          <div class="val warn">{{ quality.alerts.length }}</div>
          <div class="sub">废/返工/让步</div>
        </div>
        <div class="kpi">
          <div class="lbl">热处理合格率</div>
          <div class="val">{{ fmtRate((quality.sections.find(s => s.name === '热处理') || {}).rate || 0) }}%</div>
          <div class="sub">关注重点</div>
        </div>
      </div>

      <!-- 趋势折线 -->
      <div class="panel">
        <div class="p-title">月度合格率趋势</div>
        <div class="box-lg" id="chart-trend"></div>
      </div>

      <!-- 问题 TOP 四维 -->
      <div class="grid2">
        <div class="panel">
          <div class="p-title">问题分布 TOP · 问题描述</div>
          <div class="box-md" id="chart-problem"></div>
        </div>
        <div class="panel">
          <div class="p-title">问题分布 TOP · 配件</div>
          <div class="box-md" id="chart-part"></div>
        </div>
        <div class="panel">
          <div class="p-title">问题分布 TOP · 工段</div>
          <div class="box-md" id="chart-section"></div>
        </div>
        <div class="panel">
          <div class="p-title">问题分布 TOP · 人名</div>
          <div class="box-md" id="chart-name"></div>
        </div>
      </div>

      <!-- 严重预警列表 -->
      <div class="panel">
        <div class="p-title">严重预警明细（{{ quality.alerts.length }}）</div>
        <p v-if="quality.alerts.length === 0" class="empty">暂无严重预警。</p>
        <table v-else class="tbl">
          <thead>
            <tr>
              <th>处置方式</th><th>日期</th><th>姓名</th><th>工段</th>
              <th>配件</th><th>规格</th><th>问题描述</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(a, i) in quality.alerts" :key="i">
              <td><span class="disp-badge">{{ a.disp }}</span></td>
              <td>{{ a.date }}</td>
              <td>{{ a.name }}</td>
              <td>{{ a.section }}</td>
              <td>{{ a.part }}</td>
              <td>{{ a.spec }}</td>
              <td class="left">{{ a.problem }}</td>
            </tr>
          </tbody>
        </table>
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

.kpis { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; margin: 20px 0; }
.kpi {
  background: rgba(16, 32, 72, .55); border: 1px solid rgba(70, 120, 220, .28);
  border-radius: 14px; padding: 18px 20px; position: relative; overflow: hidden;
  backdrop-filter: blur(4px);
}
.kpi::before {
  content: ""; position: absolute; left: 0; top: 0; bottom: 0; width: 4px;
  background: linear-gradient(180deg, #2b6cff, #2ee6a8);
}
.kpi .lbl { font-size: 14px; color: #8aa0c8; }
.kpi .val { font-size: 36px; font-weight: 800; margin-top: 6px; font-family: "DIN Alternate", "Bahnschrift", sans-serif; }
.kpi .val.warn { color: #ff5b7f; }
.kpi .sub { font-size: 12px; color: #8aa0c8; margin-top: 4px; }

.panel {
  background: rgba(16, 32, 72, .55); border: 1px solid rgba(70, 120, 220, .28);
  border-radius: 14px; padding: 16px; backdrop-filter: blur(4px); margin-bottom: 16px;
}
.p-title { font-size: 16px; font-weight: 600; color: #dbe6ff; margin-bottom: 8px; }
.box-lg { height: 360px; width: 100%; }
.box-md { height: 260px; width: 100%; }
.grid2 { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 16px; }

.tbl { width: 100%; border-collapse: collapse; font-size: 13px; }
.tbl th, .tbl td { padding: 9px 10px; text-align: left; border-bottom: 1px solid rgba(120, 150, 210, .2); }
.tbl th { color: #8aa0c8; font-weight: 600; font-size: 12px; }
.tbl td { color: #dbe6ff; }
.tbl .num { text-align: right; font-variant-numeric: tabular-nums; }
.tbl .left { text-align: left; }
.c-warn { color: #ffd166; }
.c-bad { color: #ff5b7f; }
.disp-badge {
  background: rgba(255, 91, 127, .2); color: #ff5b7f; font-size: 12px;
  padding: 2px 8px; border-radius: 6px;
}
.empty { color: #8aa0c8; font-size: 13px; }
</style>
