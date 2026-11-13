<script setup>
import { ref, onMounted, onBeforeUnmount, nextTick, watch } from 'vue'
import * as echarts from 'echarts'
import { productionDashboard, productionBackfill } from '../api'

// 月份按钮：最新 + 各历史月
const monthOptions = ref([])   // [{ key:'latest', label:'最新' }, { key:'8', label:'2026-08' }, ...]
const current = ref('latest')
const dashboard = ref(null)    // 当前展示的数据（latest 或 某月）
const loading = ref(false)

// 入库填报
const backfilling = ref(false)
const backfillResult = ref(null)   // { type:'success'|'error', text, exceptions }

async function doBackfill() {
  if (backfilling.value) return
  backfilling.value = true
  backfillResult.value = null
  try {
    const r = await productionBackfill()
    const d = r.data?.data ?? r.data
    if (d && d.committed) {
      backfillResult.value = {
        type: 'success',
        text: `入库填报完成，已覆盖最新生产计划文件。入库 ${d.inbound_records} 条，成功写入 ${d.matched} 行。`,
      }
    } else if (d && d.exception_count > 0) {
      backfillResult.value = {
        type: 'error',
        text: `发现 ${d.exception_count} 条异常，已暂停覆盖。`,
        exceptions: d.exceptions,
      }
    } else {
      backfillResult.value = { type: 'error', text: r.data?.message || '入库填报失败' }
    }
  } catch (e) {
    backfillResult.value = { type: 'error', text: e.response?.data?.message || '入库填报失败：系统异常' }
  } finally {
    backfilling.value = false
    load()   // 覆盖后刷新大屏数据
  }
}

const charts = []              // 已创建的 echarts 实例

const GREEN = '#2ee6a8'
const RED = '#ff5b7f'
const GOLD = '#ffd166'         // 超 100% 标注色

const PROD_LABEL = { 加力钳: '加力钳', 美式: '美重', 含钛: '含钛', 内管钳: '内管钳', 钻杆钳: '钻杆钳', 套管钳: '套管钳' }
const DIM_LABEL = { 历史: '历史', 当月库存: '当月库存', 当月订单: '当月订单', 世达: '世达' }

function pct(d) {
  return d.plan ? (d.done / d.plan) * 100 : 0
}

async function load() {
  loading.value = true
  try {
    const r = await productionDashboard()
    const d = r.data?.data
    if (!d) return
    dashboard.value = d
    // 构建月份按钮：最新 + months 里的月份（升序）
    const ms = Object.keys(d.months || {}).map(Number).sort((a, b) => a - b)
    monthOptions.value = [
      { key: 'latest', label: '最新' },
      ...ms.map(m => ({ key: String(m), label: `2026-${String(m).padStart(2, '0')}` })),
    ]
  } finally {
    loading.value = false
  }
}

function currentData() {
  if (!dashboard.value) return null
  return current.value === 'latest'
    ? dashboard.value.latest
    : dashboard.value.months?.[current.value]
}

function switchMonth(key) {
  current.value = key
}

function ringOption(d) {
  const rate = pct(d)
  const over = rate >= 100
  const done = Math.min(d.done, d.plan)          // 完成段最多画到 100%
  const undone = Math.max(0, d.plan - d.done)    // 未完成段
  const color = over ? GOLD : GREEN
  const label = rate >= 100 ? rate.toFixed(0) + '%' : rate.toFixed(1) + '%'
  return {
    series: [{
      type: 'pie',
      radius: ['62%', '84%'],
      center: ['50%', '50%'],
      startAngle: 90,
      clockwise: true,
      silent: true,
      label: { show: false },
      labelLine: { show: false },
      data: [
        { value: done, name: '完成', itemStyle: { color } },
        { value: undone, name: '未完成', itemStyle: { color: RED } },
      ],
    }],
    graphic: [{
      type: 'text',
      left: 'center',
      top: '37%',
      style: {
        text: label,
        fill: '#fff',
        fontSize: 26,
        fontWeight: 700,
        fontFamily: 'Bahnschrift, DIN Alternate, sans-serif',
      },
    }],
  }
}

function renderCharts(d) {
  // 销毁旧实例
  charts.forEach(c => c.dispose())
  charts.length = 0

  d.products.forEach(p => {
    const el = document.getElementById(`ring-p-${p.key}`)
    if (!el) return
    const c = echarts.init(el)
    c.setOption(ringOption(p))
    charts.push(c)
  })
  d.dimensions.forEach(x => {
    const el = document.getElementById(`ring-d-${x.key}`)
    if (!el) return
    const c = echarts.init(el)
    c.setOption(ringOption(x))
    charts.push(c)
  })
}

function fmt(v) {
  return Number(v ?? 0).toLocaleString('zh-CN')
}

let resizeHandler = null
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

// 数据加载完成 或 月份切换后，重渲染图表
watch(currentData, async (d) => {
  if (!d) return
  await nextTick()
  renderCharts(d)
})

</script>

<template>
  <div class="big-screen">
    <div class="top">
      <div class="title">生产计划管理</div>
      <div class="badge" v-if="currentData()">
        2026年{{ current === 'latest' ? '11' : current }}月总生产计划
      </div>
      <button
        class="backfill-btn"
        :disabled="backfilling"
        @click="doBackfill"
      >{{ backfilling ? '填报中…' : '入库填报' }}</button>
      <div class="months">
        <button
          v-for="m in monthOptions"
          :key="m.key"
          class="mbtn"
          :class="{ active: m.key === current }"
          @click="switchMonth(m.key)"
        >{{ m.label }}</button>
      </div>
    </div>

    <!-- 入库填报结果 -->
    <div v-if="backfillResult" class="backfill-result" :class="backfillResult.type">
      <div class="br-title">
        {{ backfillResult.type === 'success' ? '入库填报成功' : '入库填报异常' }}
      </div>
      <div class="br-text">{{ backfillResult.text }}</div>
      <div v-if="backfillResult.exceptions?.length" class="br-exceptions">
        <div class="br-ex-title">异常明细（未覆盖文件）：</div>
        <div v-for="(e, i) in backfillResult.exceptions" :key="i" class="br-ex-item">
          · 批号 {{ e.batch }} 颜色 {{ e.color }} 入库 {{ e.inbound }}：{{ e.reason }}（{{ e.sheet }} {{ e.date }}）
        </div>
      </div>
    </div>

    <div v-if="loading" class="loading">数据加载中…</div>

    <template v-else-if="currentData()">
      <!-- KPI 指标卡 -->
      <div class="kpis">
        <div class="kpi">
          <div class="lbl">总体完成率</div>
          <div class="val">{{ currentData().overall.rate }}%</div>
          <div class="sub">计划 <b>{{ fmt(currentData().overall.plan) }}</b> · 完成 <b>{{ fmt(currentData().overall.done) }}</b></div>
        </div>
        <div class="kpi" v-for="x in currentData().dimensions" :key="'kpi-' + x.key">
          <div class="lbl">{{ DIM_LABEL[x.key] || x.key }}完成率</div>
          <div class="val">{{ x.rate }}%</div>
          <div class="sub">{{ fmt(x.plan) }} / {{ fmt(x.done) }}</div>
        </div>
      </div>

      <!-- 6 品类 -->
      <div class="sec-title">
        <span class="dot"></span>6 大品种大类（各自独立）
        <div class="legend-inline">
          <span><i style="background: var(--green)"></i>已完成</span>
          <span><i style="background: var(--red)"></i>未完成</span>
        </div>
      </div>
      <div class="grid6">
        <div class="ring-card" v-for="p in currentData().products" :key="'p-' + p.key">
          <div class="rname">{{ PROD_LABEL[p.key] || p.key }}</div>
          <div class="ring-box" :id="'ring-p-' + p.key"></div>
          <div class="rfoot">计划 <b>{{ fmt(p.plan) }}</b> · 完成 <b>{{ fmt(p.done) }}</b></div>
        </div>
      </div>

      <!-- 4 维度 -->
      <div class="sec-title">
        <span class="dot"></span>历史 / 当月库存 / 当月订单（各自独立）
      </div>
      <div class="grid4">
        <div class="ring-card" v-for="x in currentData().dimensions" :key="'d-' + x.key">
          <div class="rname">{{ DIM_LABEL[x.key] || x.key }}</div>
          <div class="ring-box" :id="'ring-d-' + x.key"></div>
          <div class="rfoot">计划 <b>{{ fmt(x.plan) }}</b> · 完成 <b>{{ fmt(x.done) }}</b></div>
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
:root {
  --green: #2ee6a8;
  --red: #ff5b7f;
}
.big-screen {
  --green: #2ee6a8;
  --red: #ff5b7f;
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
.months { margin-left: auto; display: flex; gap: 10px; }
.backfill-btn {
  margin-left: 14px;
  padding: 8px 18px;
  border: 1px solid rgba(46, 230, 168, .5);
  border-radius: 8px;
  background: linear-gradient(135deg, #1d9e75, #2ee6a8);
  color: #04120a;
  font-size: 14px;
  font-weight: 700;
  cursor: pointer;
  transition: .2s;
}
.backfill-btn:hover { box-shadow: 0 0 14px rgba(46, 230, 168, .6); }
.backfill-btn:disabled { opacity: .5; cursor: not-allowed; }
.backfill-result {
  margin-top: 18px;
  padding: 16px 18px;
  border-radius: 12px;
  font-size: 13px;
  line-height: 1.6;
}
.backfill-result.success {
  background: rgba(16, 80, 50, .5);
  border: 1px solid rgba(46, 230, 168, .45);
}
.backfill-result.error {
  background: rgba(90, 20, 30, .5);
  border: 1px solid rgba(255, 91, 127, .45);
}
.br-title { font-size: 15px; font-weight: 700; margin-bottom: 6px; }
.backfill-result.success .br-title { color: #2ee6a8; }
.backfill-result.error .br-title { color: #ff5b7f; }
.br-text { color: #e8f0ff; }
.br-exceptions { margin-top: 10px; }
.br-ex-title { color: #ffb3c0; font-weight: 600; margin-bottom: 4px; }
.br-ex-item { color: #d8e2f5; padding-left: 6px; }
.mbtn {
  background: rgba(20, 40, 90, .5); border: 1px solid rgba(70, 120, 220, .28);
  color: #8aa0c8; padding: 7px 18px; border-radius: 8px; cursor: pointer;
  font-size: 14px; transition: .2s;
}
.mbtn:hover { color: #fff; border-color: #3f9bff; }
.mbtn.active {
  background: linear-gradient(135deg, #2b6cff, #3f9bff); color: #fff;
  border-color: transparent; box-shadow: 0 0 14px rgba(59, 130, 255, .6);
}

.loading { padding: 60px 0; text-align: center; color: #8aa0c8; font-size: 14px; }

.kpis { display: grid; grid-template-columns: repeat(5, 1fr); gap: 16px; margin: 22px 0; }
.kpi {
  background: rgba(16, 32, 72, .55); border: 1px solid rgba(70, 120, 220, .28);
  border-radius: 14px; padding: 16px 18px; position: relative; overflow: hidden;
  backdrop-filter: blur(4px);
}
.kpi::before {
  content: ""; position: absolute; left: 0; top: 0; bottom: 0; width: 4px;
  background: linear-gradient(180deg, #2b6cff, #2ee6a8);
}
.kpi .lbl { font-size: 13px; color: #8aa0c8; }
.kpi .val {
  font-size: 34px; font-weight: 800; margin: 6px 0 2px;
  font-family: "DIN Alternate", "Bahnschrift", sans-serif;
}
.kpi .sub { font-size: 12px; color: #8aa0c8; }
.kpi .sub b { color: #cfdfff; font-weight: 600; }

.sec-title { display: flex; align-items: center; gap: 10px; margin: 24px 0 14px; font-size: 17px; font-weight: 700; }
.sec-title .dot {
  width: 8px; height: 8px; border-radius: 50%; background: #2b6cff;
  box-shadow: 0 0 10px #2b6cff;
}
.legend-inline { display: flex; gap: 16px; margin-left: 14px; font-size: 13px; color: #8aa0c8; }
.legend-inline i { display: inline-block; width: 10px; height: 10px; border-radius: 50%; margin-right: 5px; }

.grid6 { display: grid; grid-template-columns: repeat(6, 1fr); gap: 16px; }
.grid4 { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; }
.ring-card {
  background: rgba(16, 32, 72, .55); border: 1px solid rgba(70, 120, 220, .28);
  border-radius: 14px; padding: 10px 8px; text-align: center;
  backdrop-filter: blur(4px);
}
.ring-card .rname { font-size: 14px; font-weight: 600; margin-bottom: 4px; color: #dbe6ff; }
.ring-box { height: 150px; }
.ring-card .rfoot { font-size: 12px; color: #8aa0c8; }
.ring-card .rfoot b { color: #cfdfff; }
</style>
