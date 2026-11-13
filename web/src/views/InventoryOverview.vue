<script setup>
import { ref, onMounted, onBeforeUnmount, nextTick, watch } from 'vue'
import * as echarts from 'echarts'
import { inventoryFlowStats, inventoryShareStats, inventoryLedgerMeta } from '../api'

const loading = ref(false)
const errorMsg = ref('')
const stats = ref(null)      // flow-stats 数据
const share = ref(null)      // share-stats 数据
const ledgerMeta = ref(null) // 台账更新日期

// 月份切换：最新（默认当前真实月）+ 1~12 月
const current = ref('latest')
const monthOptions = [
  { key: 'latest', label: '最新' },
  ...Array.from({ length: 12 }, (_, i) => ({ key: String(i + 1), label: `${i + 1}月` })),
]

let barChart = null
let ringProdChart = null
let ringSeriesChart = null
let trendChart = null

// 品类/系列颜色（与设计图一致的红橙黄绿蓝紫）
const CAT_COLORS = ['#ff5b7f', '#ff9f43', '#ffd166', '#2ee6a8', '#4db8ff', '#a06bff']

async function load(month = null) {
  loading.value = true
  errorMsg.value = ''
  try {
    const [r1, r2] = await Promise.all([inventoryFlowStats(month), inventoryShareStats(month)])
    stats.value = r1.data?.data
    share.value = r2.data?.data
  } catch (e) {
    errorMsg.value = e?.response?.data?.message || '加载失败'
  } finally {
    loading.value = false
  }
  // 台账更新日期：次要信息，失败静默不阻断数据渲染
  inventoryLedgerMeta()
    .then(r => { ledgerMeta.value = r.data?.data })
    .catch(() => {})
}

function switchMonth(key) {
  current.value = key
  load(key === 'latest' ? null : Number(key))
}

function fmt(v) {
  return Number(v ?? 0).toLocaleString('zh-CN')
}

function renderCharts() {
  if (!stats.value) return
  renderTrend()
  renderBar()
  renderRingProd()
  renderRingSeries()
}

function renderTrend() {
  const el = document.getElementById('flow-trend')
  if (!el) return
  if (trendChart) trendChart.dispose()
  trendChart = echarts.init(el)
  const ms = stats.value.monthly || []
  trendChart.setOption({
    backgroundColor: 'transparent',
    tooltip: { trigger: 'axis' },
    legend: {
      data: ['入库', '出库', '结存'], textStyle: { color: '#8aa0c8' },
      top: 0, right: 10,
    },
    grid: { left: 55, right: 20, top: 50, bottom: 30 },
    xAxis: {
      type: 'category', data: ms.map(m => `${m.month}月`),
      axisLine: { lineStyle: { color: 'rgba(120,150,210,.35)' } },
      axisLabel: { color: '#cfe0ff', fontSize: 12 },
    },
    yAxis: {
      type: 'value',
      axisLine: { show: false }, axisLabel: { color: '#8aa0c8' },
      splitLine: { lineStyle: { color: 'rgba(120,150,210,.15)' } },
    },
    series: [
      { name: '入库', type: 'line', smooth: true, symbol: 'circle', symbolSize: 6, data: ms.map(m => m.in), itemStyle: { color: '#2ee6a8' }, lineStyle: { width: 2 } },
      { name: '出库', type: 'line', smooth: true, symbol: 'circle', symbolSize: 6, data: ms.map(m => m.out), itemStyle: { color: '#ff5b7f' }, lineStyle: { width: 2 } },
      { name: '结存', type: 'line', smooth: true, symbol: 'circle', symbolSize: 6, data: ms.map(m => m.stock), itemStyle: { color: '#ffd166' }, lineStyle: { width: 2 } },
    ],
  })
}

function renderBar() {
  const el = document.getElementById('flow-bar')
  if (!el) return
  if (barChart) barChart.dispose()
  barChart = echarts.init(el)
  const ps = stats.value.products
  barChart.setOption({
    backgroundColor: 'transparent',
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    legend: {
      data: ['入库', '出库', '结存'], textStyle: { color: '#8aa0c8' },
      top: 0, right: 10,
    },
    grid: { left: 50, right: 20, top: 50, bottom: 30 },
    xAxis: {
      type: 'category', data: ps.map(p => p.name),
      axisLine: { lineStyle: { color: 'rgba(120,150,210,.35)' } },
      axisLabel: { color: '#cfe0ff', fontSize: 13 },
    },
    yAxis: {
      type: 'value',
      axisLine: { show: false }, axisLabel: { color: '#8aa0c8' },
      splitLine: { lineStyle: { color: 'rgba(120,150,210,.15)' } },
    },
    series: [
      { name: '入库', type: 'bar', barWidth: 14, data: ps.map(p => p.in), itemStyle: { color: '#2ee6a8' }, label: { show: true, position: 'top', color: '#cfe0ff', fontSize: 11 } },
      { name: '出库', type: 'bar', barWidth: 14, data: ps.map(p => p.out), itemStyle: { color: '#ff5b7f' }, label: { show: true, position: 'top', color: '#cfe0ff', fontSize: 11 } },
      { name: '结存', type: 'bar', barWidth: 14, data: ps.map(p => p.stock), itemStyle: { color: '#ffd166' }, label: { show: true, position: 'top', color: '#cfe0ff', fontSize: 11 } },
    ],
  })
}

function renderRingProd() {
  const el = document.getElementById('ring-prod-in')
  if (!el) return
  if (ringProdChart) ringProdChart.dispose()
  ringProdChart = echarts.init(el)
  const data = (share.value?.in?.products || []).map((x, i) => ({
    name: x.name, value: x.value, itemStyle: { color: CAT_COLORS[i % CAT_COLORS.length] },
  }))
  ringProdChart.setOption(ringOption(data, '入库占比'))
}

function renderRingSeries() {
  const el = document.getElementById('ring-series-in')
  if (!el) return
  if (ringSeriesChart) ringSeriesChart.dispose()
  ringSeriesChart = echarts.init(el)
  const data = (share.value?.in?.series || []).map((x, i) => ({
    name: x.name, value: x.value, itemStyle: { color: ['#ff5b7f', '#ffd166'][i % 2] },
  }))
  ringSeriesChart.setOption(ringOption(data, '两大系列入库占比'))
}

function ringOption(data, title) {
  return {
    backgroundColor: 'transparent',
    title: {
      text: title, left: 'center', top: 8,
      textStyle: { color: '#dbe6ff', fontSize: 15, fontWeight: 600 },
    },
    tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
    legend: {
      bottom: 0, textStyle: { color: '#8aa0c8', fontSize: 12 },
      itemWidth: 12, itemHeight: 12,
    },
    series: [{
      type: 'pie', radius: ['45%', '68%'], center: ['50%', '52%'],
      avoidLabelOverlap: true,
      itemStyle: { borderColor: '#0a1230', borderWidth: 2 },
      label: { color: '#cfe0ff', fontSize: 12, formatter: '{b} {d}% ({c})' },
      labelLine: { lineStyle: { color: 'rgba(140,160,200,.4)' } },
      data,
    }],
  }
}

let resizeHandler = null

// 数据就绪后渲染（对齐 Planning 的成功模式：watch + nextTick）
watch([stats, share], async () => {
  if (!stats.value || !share.value) return
  await nextTick()
  requestAnimationFrame(() => renderCharts())
})

onMounted(() => {
  load()
  resizeHandler = () => {
    [barChart, ringProdChart, ringSeriesChart, trendChart].forEach(c => c && c.resize())
  }
  window.addEventListener('resize', resizeHandler)
})
onBeforeUnmount(() => {
  [barChart, ringProdChart, ringSeriesChart, trendChart].forEach(c => c && c.dispose())
  if (resizeHandler) window.removeEventListener('resize', resizeHandler)
})
</script>

<template>
  <div class="big-screen">
    <div class="top">
      <div class="title">成品总览</div>
      <div class="badge" v-if="stats">2026年{{ stats.month }}月</div>
      <div class="update-hint" v-if="ledgerMeta?.mtime">数据更新：{{ ledgerMeta.mtime }}</div>
    </div>

    <div class="months">
      <button
        v-for="m in monthOptions"
        :key="m.key"
        class="mbtn"
        :class="{ active: m.key === current }"
        @click="switchMonth(m.key)"
      >{{ m.label }}</button>
    </div>

    <div v-if="loading" class="loading">数据加载中…</div>
    <div v-else-if="errorMsg" class="error">{{ errorMsg }}</div>

    <template v-else-if="stats">
      <!-- 3 KPI -->
      <div class="kpis">
        <div class="kpi">
          <div class="lbl">{{ stats.month }}月总入库数</div>
          <div class="val">{{ fmt(stats.total.in) }}</div>
        </div>
        <div class="kpi">
          <div class="lbl">{{ stats.month }}月总出库数</div>
          <div class="val">{{ fmt(stats.total.out) }}</div>
        </div>
        <div class="kpi">
          <div class="lbl">{{ stats.month }}月库存总数</div>
          <div class="val">{{ fmt(stats.total.stock) }}</div>
        </div>
      </div>

      <!-- 历史趋势折线图 -->
      <div class="panel" style="margin-bottom: 16px;">
        <div class="p-title">近 12 个月入库 / 出库 / 结存趋势</div>
        <div class="trend-box" id="flow-trend"></div>
      </div>

      <!-- 中部柱状图 -->
      <div class="panel">
        <div class="p-title">分品类 入库 / 出库 / 结存</div>
        <div class="bar-box" id="flow-bar"></div>
      </div>

      <!-- 底部两个环形图 -->
      <div class="rings">
        <div class="panel">
          <div class="ring-box" id="ring-prod-in"></div>
        </div>
        <div class="panel">
          <div class="ring-box" id="ring-series-in"></div>
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
.months { display: flex; flex-wrap: wrap; gap: 8px; margin: 16px 0 4px; }
.mbtn {
  background: rgba(20, 40, 90, .5); border: 1px solid rgba(70, 120, 220, .28);
  color: #8aa0c8; padding: 6px 14px; border-radius: 8px; cursor: pointer;
  font-size: 13px; transition: .2s;
}
.mbtn:hover { color: #fff; border-color: #3f9bff; }
.mbtn.active {
  background: linear-gradient(135deg, #2b6cff, #3f9bff); color: #fff;
  border-color: transparent; box-shadow: 0 0 14px rgba(59, 130, 255, .6);
}
.loading, .error { padding: 60px 0; text-align: center; color: #8aa0c8; font-size: 14px; }
.error { color: #ff5b7f; }

.kpis { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; margin: 22px 0; }
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
.kpi .val {
  font-size: 36px; font-weight: 800; margin-top: 6px;
  font-family: "DIN Alternate", "Bahnschrift", sans-serif;
}

.panel {
  background: rgba(16, 32, 72, .55); border: 1px solid rgba(70, 120, 220, .28);
  border-radius: 14px; padding: 16px; backdrop-filter: blur(4px);
}
.p-title { font-size: 16px; font-weight: 600; color: #dbe6ff; margin-bottom: 8px; }
.trend-box { height: 300px; width: 100%; }
.bar-box { height: 360px; width: 100%; }
.rings { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-top: 16px; }
.ring-box { height: 340px; width: 100%; }
</style>
