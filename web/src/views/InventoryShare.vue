<script setup>
import { ref, onMounted, onBeforeUnmount, nextTick, watch } from 'vue'
import * as echarts from 'echarts'
import { inventoryShareStats, inventoryLedgerMeta } from '../api'

const loading = ref(false)
const errorMsg = ref('')
const share = ref(null)
const ledgerMeta = ref(null)

const charts = []
const CAT_COLORS = ['#ff5b7f', '#ff9f43', '#ffd166', '#2ee6a8', '#4db8ff', '#a06bff']
const SERIES_COLORS = ['#ff5b7f', '#ffd166']

const DIM_LABEL = { in: '入库', out: '出库', stock: '结存' }

async function load() {
  loading.value = true
  errorMsg.value = ''
  try {
    const r = await inventoryShareStats()
    share.value = r.data?.data
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

function ringOption(data, colors, title) {
  return {
    backgroundColor: 'transparent',
    title: { text: title, left: 'center', top: 8, textStyle: { color: '#dbe6ff', fontSize: 15, fontWeight: 600 } },
    tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
    legend: { bottom: 0, textStyle: { color: '#8aa0c8', fontSize: 12 }, itemWidth: 12, itemHeight: 12 },
    series: [{
      type: 'pie', radius: ['42%', '66%'], center: ['50%', '52%'],
      avoidLabelOverlap: true,
      itemStyle: { borderColor: '#0a1230', borderWidth: 2 },
      label: { color: '#cfe0ff', fontSize: 11, formatter: '{b} {d}% ({c})' },
      labelLine: { lineStyle: { color: 'rgba(140,160,200,.4)' } },
      data: data.map((x, i) => ({ name: x.name, value: x.value, itemStyle: { color: colors[i % colors.length] } })),
    }],
  }
}

function renderCharts() {
  if (!share.value) return
  charts.forEach(c => c.dispose())
  charts.length = 0

  const dims = ['in', 'out', 'stock']
  // 第一行：各品种占比（3 张）
  dims.forEach((dim, i) => {
    const el = document.getElementById(`share-prod-${dim}`)
    if (!el) return
    const c = echarts.init(el)
    c.setOption(ringOption(share.value[dim].products, CAT_COLORS, `各品种${DIM_LABEL[dim]}占比`))
    charts.push(c)
  })
  // 第二行：两大系列占比（3 张）
  dims.forEach((dim, i) => {
    const el = document.getElementById(`share-series-${dim}`)
    if (!el) return
    const c = echarts.init(el)
    c.setOption(ringOption(share.value[dim].series, SERIES_COLORS, `两大系列${DIM_LABEL[dim]}占比`))
    charts.push(c)
  })
}

let resizeHandler = null

// 数据就绪后渲染（对齐 Planning 的成功模式）
watch(share, async () => {
  if (!share.value) return
  await nextTick()
  requestAnimationFrame(() => renderCharts())
})

onMounted(() => {
  load()
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
      <div class="title">成品占比</div>
      <div class="badge" v-if="share">2026年{{ share.month }}月</div>
      <div class="update-hint" v-if="ledgerMeta?.mtime">数据更新：{{ ledgerMeta.mtime }}</div>
    </div>

    <div v-if="loading" class="loading">数据加载中…</div>
    <div v-else-if="errorMsg" class="error">{{ errorMsg }}</div>

    <template v-else-if="share">
      <div class="sec-title"><span class="dot"></span>各品种占比</div>
      <div class="grid3">
        <div class="panel" v-for="d in ['in','out','stock']" :key="'p-'+d">
          <div class="ring-box" :id="'share-prod-' + d"></div>
        </div>
      </div>

      <div class="sec-title"><span class="dot"></span>两大系列占比（管钳 / 自由钳）</div>
      <div class="grid3">
        <div class="panel" v-for="d in ['in','out','stock']" :key="'s-'+d">
          <div class="ring-box" :id="'share-series-' + d"></div>
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
.loading, .error { padding: 60px 0; text-align: center; color: #8aa0c8; font-size: 14px; }
.error { color: #ff5b7f; }

.sec-title { display: flex; align-items: center; gap: 10px; margin: 24px 0 14px; font-size: 17px; font-weight: 700; }
.sec-title .dot {
  width: 8px; height: 8px; border-radius: 50%; background: #2b6cff;
  box-shadow: 0 0 10px #2b6cff;
}
.grid3 { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; }
.panel {
  background: rgba(16, 32, 72, .55); border: 1px solid rgba(70, 120, 220, .28);
  border-radius: 14px; padding: 8px; backdrop-filter: blur(4px);
}
.ring-box { height: 320px; width: 100%; }
</style>
