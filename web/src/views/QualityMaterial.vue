<script setup>
import { ref, onMounted, onBeforeUnmount, nextTick, watch, computed } from 'vue'
import * as echarts from 'echarts'
import { qualityMaterialInspection } from '../api'

const loading = ref(false)
const errorMsg = ref('')
const material = ref(null)  // 原料检验数据
const curMonth = ref(null)  // 当前选中月份（数字或 'latest'）

const charts = []
const CAT_COLORS = ['#ff5b7f', '#ff9f43', '#ffd166', '#2ee6a8', '#4db8ff', '#a06bff', '#c084fc', '#34d399']

async function load() {
  loading.value = true
  errorMsg.value = ''
  try {
    const month = curMonth.value && curMonth.value !== 'latest' ? curMonth.value : null
    const r = await qualityMaterialInspection(month)
    material.value = r.data?.data
  } catch (e) {
    errorMsg.value = e?.response?.data?.message || '加载失败'
  } finally {
    loading.value = false
  }
}

// 可用月份
const monthOptions = computed(() => {
  const labels = (material.value?.months || []).map(m => `${m}月`)
  return ['最新', ...labels]
})

function fmt(v) {
  return Number(v ?? 0).toLocaleString('zh-CN')
}

function selectMonth(m) {
  curMonth.value = m === '最新' ? 'latest' : parseInt(m)
  load()
}

function renderCharts() {
  if (!material.value) return
  charts.forEach(c => c.dispose())
  charts.length = 0

  // 检验结果分布饼图
  const el = document.getElementById('chart-material-result')
  if (el) {
    const c = echarts.init(el)
    const data = (material.value.results || []).map((x, i) => ({
      name: x.name, value: x.count, itemStyle: { color: CAT_COLORS[i % CAT_COLORS.length] },
    }))
    c.setOption({
      backgroundColor: 'transparent',
      tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
      legend: { bottom: 0, textStyle: { color: '#8aa0c8', fontSize: 12 } },
      series: [{
        type: 'pie', radius: ['45%', '68%'], center: ['50%', '45%'],
        itemStyle: { borderColor: '#0a1230', borderWidth: 2 },
        label: { color: '#cfe0ff', fontSize: 11, formatter: '{b}\n{d}%' },
        labelLine: { lineStyle: { color: 'rgba(140,160,200,.4)' } },
        data,
      }],
    })
    charts.push(c)
  }

  // 物料 TOP 横向柱状
  const el2 = document.getElementById('chart-material-top')
  if (el2) {
    const c = echarts.init(el2)
    const data = (material.value.materials_top || []).slice().reverse()
    c.setOption({
      backgroundColor: 'transparent',
      tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
      grid: { left: 90, right: 40, top: 10, bottom: 20 },
      xAxis: { type: 'value', minInterval: 1, axisLine: { show: false }, axisLabel: { color: '#8aa0c8' }, splitLine: { lineStyle: { color: 'rgba(120,150,210,.15)' } } },
      yAxis: { type: 'category', data: data.map(d => d.name), axisLabel: { color: '#cfe0ff', fontSize: 11 } },
      series: [{ type: 'bar', data: data.map(d => d.count), barWidth: 12, itemStyle: { color: '#ff9f43' }, label: { show: true, position: 'right', color: '#cfe0ff', fontSize: 11 } }],
    })
    charts.push(c)
  }

  // 问题 TOP 横向柱状
  const el3 = document.getElementById('chart-material-issues')
  if (el3) {
    const c = echarts.init(el3)
    const data = (material.value.issues_top || []).slice().reverse()
    c.setOption({
      backgroundColor: 'transparent',
      tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
      grid: { left: 120, right: 40, top: 10, bottom: 20 },
      xAxis: { type: 'value', minInterval: 1, axisLine: { show: false }, axisLabel: { color: '#8aa0c8' }, splitLine: { lineStyle: { color: 'rgba(120,150,210,.15)' } } },
      yAxis: { type: 'category', data: data.map(d => d.name), axisLabel: { color: '#cfe0ff', fontSize: 11 } },
      series: [{ type: 'bar', data: data.map(d => d.count), barWidth: 12, itemStyle: { color: '#ff5b7f' }, label: { show: true, position: 'right', color: '#cfe0ff', fontSize: 11 } }],
    })
    charts.push(c)
  }
}

let resizeHandler = null

watch(material, async () => {
  if (!material.value) return
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
      <div class="title">原料检验</div>
      <div class="badge" v-if="material">数据源：本地 Excel（毛坯来料检验记录）</div>
      <div class="update-hint" v-if="material?.mtime">数据更新：{{ material.mtime }}</div>
    </div>

    <!-- 月份选择器 -->
    <div class="month-bar" v-if="material">
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

    <template v-else-if="material">
      <div class="material-head">
        <span class="badge" v-if="material.month">{{ material.month }}</span>
      </div>

      <div class="grid2">
        <div class="panel">
          <div class="p-title">检验结果分布</div>
          <div class="box-md" id="chart-material-result"></div>
        </div>
        <div class="panel">
          <div class="p-title">物料 TOP</div>
          <div class="box-md" id="chart-material-top"></div>
        </div>
      </div>

      <div class="grid2">
        <div class="panel">
          <div class="p-title">问题 TOP</div>
          <div class="box-md" id="chart-material-issues"></div>
        </div>
        <div class="panel">
          <div class="p-title">供应商表现</div>
          <table class="tbl">
            <thead>
              <tr><th>供应商</th><th class="num">批数</th><th class="num">来料数量</th><th class="num">让步</th><th class="num">不合格</th></tr>
            </thead>
            <tbody>
              <tr v-for="(s, i) in material.suppliers" :key="i">
                <td>{{ s.name }}</td>
                <td class="num">{{ s.batches }}</td>
                <td class="num">{{ fmt(s.qty) }}</td>
                <td class="num c-warn">{{ s.concession }}</td>
                <td class="num c-bad">{{ s.reject }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- 退货 + 让步预警 -->
      <div class="panel">
        <div class="p-title">退货 / 让步预警（{{ material.alerts.length }}）</div>
        <p v-if="material.alerts.length === 0" class="empty">暂无退货或让步接收。</p>
        <table v-else class="tbl">
          <thead>
            <tr><th>日期</th><th>供应商</th><th>物料</th><th>规格</th><th>检验结果</th><th>处置</th></tr>
          </thead>
          <tbody>
            <tr v-for="(a, i) in material.alerts" :key="i">
              <td>{{ a.date }}</td>
              <td>{{ a.supplier }}</td>
              <td>{{ a.material }}</td>
              <td>{{ a.spec }}</td>
              <td>{{ a.result }}</td>
              <td><span class="disp-badge">{{ a.disp }}</span></td>
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

.material-head { display: flex; align-items: center; gap: 14px; margin-bottom: 10px; }

.loading, .error { padding: 60px 0; text-align: center; color: #8aa0c8; font-size: 14px; }
.error { color: #ff5b7f; }

.panel {
  background: rgba(16, 32, 72, .55); border: 1px solid rgba(70, 120, 220, .28);
  border-radius: 14px; padding: 16px; backdrop-filter: blur(4px); margin-bottom: 16px;
}
.p-title { font-size: 16px; font-weight: 600; color: #dbe6ff; margin-bottom: 8px; }
.box-md { height: 260px; width: 100%; }
.grid2 { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 16px; }

.tbl { width: 100%; border-collapse: collapse; font-size: 13px; }
.tbl th, .tbl td { padding: 9px 10px; text-align: left; border-bottom: 1px solid rgba(120, 150, 210, .2); }
.tbl th { color: #8aa0c8; font-weight: 600; font-size: 12px; }
.tbl td { color: #dbe6ff; }
.tbl .num { text-align: right; font-variant-numeric: tabular-nums; }
.tbl td.c-warn { color: #ffd166; }
.tbl td.c-bad { color: #ff5b7f; }
.disp-badge {
  background: rgba(255, 91, 127, .2); color: #ff5b7f; font-size: 12px;
  padding: 2px 8px; border-radius: 6px;
}
.empty { color: #8aa0c8; font-size: 13px; }
</style>
