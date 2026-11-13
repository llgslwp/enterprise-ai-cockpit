<script setup>
import { ref, onMounted, computed } from 'vue'
import { inventoryMaterialGap, inventoryLedgerMeta } from '../api'

const loading = ref(false)
const errorMsg = ref('')
const alerts = ref([])
const ledgerMeta = ref(null)

const totalGap = computed(() =>
  alerts.value.reduce((s, a) => s + (Number(a.gap) || 0), 0)
)

async function load() {
  loading.value = true
  errorMsg.value = ''
  try {
    const r = await inventoryMaterialGap()
    alerts.value = r.data?.data?.alerts || []
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

function fmt(v) {
  return Number(v ?? 0).toLocaleString('zh-CN')
}

onMounted(load)
</script>

<template>
  <div class="big-screen">
    <div class="top">
      <div class="title">原料预警</div>
      <div class="badge">原料预警 · 低于安全库存</div>
      <div class="update-hint" v-if="ledgerMeta?.mtime">数据更新：{{ ledgerMeta.mtime }}</div>
    </div>

    <div v-if="loading" class="loading">数据加载中…</div>
    <div v-else-if="errorMsg" class="error">{{ errorMsg }}</div>

    <template v-else>
      <!-- KPI -->
      <div class="kpis">
        <div class="kpi">
          <div class="lbl">预警原料数</div>
          <div class="val warn">{{ alerts.length }}</div>
          <div class="sub">低于安全库存的货品</div>
        </div>
        <div class="kpi">
          <div class="lbl">总缺口</div>
          <div class="val warn">{{ fmt(totalGap) }}</div>
          <div class="sub">安全库存 − 当前存量 之和</div>
        </div>
      </div>

      <!-- 预警明细 -->
      <div class="panel">
        <div class="p-title">低于安全库存的货品明细</div>
        <p v-if="alerts.length === 0" class="empty">
          暂无低于安全库存的货品。<br>
          请在 <span class="path">data/raw/原料库存底线配置表.xlsx</span> 中填写各货品的「安全库存」值后，此处自动生效。
        </p>
        <table v-else class="tbl">
          <thead>
            <tr>
              <th>货品名称</th><th>规格</th>
              <th class="num">现有存量</th><th class="num">安全库存</th><th class="num">缺口</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(a, i) in alerts" :key="i">
              <td>{{ a.name }}</td>
              <td>{{ a.spec }}</td>
              <td class="num low">{{ fmt(a.stock) }}</td>
              <td class="num">{{ fmt(a.threshold) }}</td>
              <td class="num gap">{{ fmt(a.gap) }}</td>
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
.loading, .error { padding: 60px 0; text-align: center; color: #8aa0c8; font-size: 14px; }
.error { color: #ff5b7f; }

.kpis { display: grid; grid-template-columns: repeat(2, 1fr); gap: 16px; margin: 22px 0; max-width: 640px; }
.kpi {
  background: rgba(16, 32, 72, .55); border: 1px solid rgba(70, 120, 220, .28);
  border-radius: 14px; padding: 18px 20px; position: relative; overflow: hidden;
  backdrop-filter: blur(4px);
}
.kpi::before {
  content: ""; position: absolute; left: 0; top: 0; bottom: 0; width: 4px;
  background: linear-gradient(180deg, #ff5b7f, #ffd166);
}
.kpi .lbl { font-size: 14px; color: #8aa0c8; }
.kpi .val {
  font-size: 36px; font-weight: 800; margin-top: 6px;
  font-family: "DIN Alternate", "Bahnschrift", sans-serif;
}
.kpi .val.warn { color: #d32f2f; }
.kpi .sub { font-size: 12px; color: #8aa0c8; margin-top: 4px; }

.panel {
  background: rgba(16, 32, 72, .55); border: 1px solid rgba(70, 120, 220, .28);
  border-radius: 14px; padding: 18px; backdrop-filter: blur(4px);
}
.p-title { font-size: 16px; font-weight: 600; color: #dbe6ff; margin-bottom: 14px; }
.empty { color: #8aa0c8; font-size: 14px; line-height: 1.9; }
.empty .path { color: #ffd166; font-weight: 600; }

.tbl { width: 100%; border-collapse: collapse; font-size: 16px; }
.tbl th, .tbl td {
  padding: 10px 12px; text-align: left;
  border-bottom: 1px solid rgba(120, 150, 210, .2);
}
.tbl th { color: #8aa0c8; font-weight: 600; font-size: 15px; }
.tbl td { color: #dbe6ff; }
.num { text-align: right; font-variant-numeric: tabular-nums; }
.tbl td.low { color: #ffd166; font-weight: 700; }
.tbl td.gap { color: #d32f2f; font-weight: 700; }
</style>
