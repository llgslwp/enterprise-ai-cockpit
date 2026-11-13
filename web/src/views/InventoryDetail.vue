<script setup>
import { ref, onMounted, computed } from 'vue'
import { inventoryFocusStats, inventoryLedgerMeta } from '../api'

const loading = ref(false)
const errorMsg = ref('')
const focus = ref(null)   // { month, count, products:[{name, items:[...]}], flat:[...] }
const ledgerMeta = ref(null)

const totalIn = computed(() => focus.value?.flat?.reduce((s, x) => s + (Number(x.in) || 0), 0) || 0)
const totalOut = computed(() => focus.value?.flat?.reduce((s, x) => s + (Number(x.out) || 0), 0) || 0)
const totalStock = computed(() => focus.value?.flat?.reduce((s, x) => s + (Number(x.stock) || 0), 0) || 0)

async function load() {
  loading.value = true
  errorMsg.value = ''
  try {
    const r = await inventoryFocusStats()
    focus.value = r.data?.data
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
      <div class="title">重点成品</div>
      <div class="badge" v-if="focus">2026年{{ focus.month }}月</div>
      <div class="badge hint" v-if="focus">重点规格 {{ focus.count }} 个</div>
      <div class="update-hint" v-if="ledgerMeta?.mtime">数据更新：{{ ledgerMeta.mtime }}</div>
    </div>

    <div v-if="loading" class="loading">数据加载中…</div>
    <div v-else-if="errorMsg" class="error">{{ errorMsg }}</div>

    <template v-else-if="focus">
      <!-- KPI 汇总 -->
      <div class="kpis">
        <div class="kpi">
          <div class="lbl">本月重点入库</div>
          <div class="val in">{{ fmt(totalIn) }}</div>
        </div>
        <div class="kpi">
          <div class="lbl">本月重点出库</div>
          <div class="val out">{{ fmt(totalOut) }}</div>
        </div>
        <div class="kpi">
          <div class="lbl">重点规格结存</div>
          <div class="val stock">{{ fmt(totalStock) }}</div>
        </div>
      </div>

      <!-- 空状态 -->
      <div v-if="focus.count === 0" class="empty">
        尚未勾选重点关注规格。<br>
        请在 <span class="path">data/raw/重点关注规格.xlsx</span> 的「是否重点」列填「是」勾选。
      </div>

      <!-- 明细表 -->
      <template v-else>
        <div class="panel" v-for="p in focus.products" :key="p.name">
          <div class="p-title"><span class="dot"></span>{{ p.name }}（{{ p.items.length }} 个规格）</div>
          <table class="tbl">
            <thead>
              <tr>
                <th>规格</th><th>特征</th>
                <th class="num">入库</th><th class="num">出库</th><th class="num">结存</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(it, i) in p.items" :key="i">
                <td>{{ it.spec }}</td>
                <td>{{ it.feature || '-' }}</td>
                <td class="num c-in">{{ fmt(it.in) }}</td>
                <td class="num c-out">{{ fmt(it.out) }}</td>
                <td class="num c-stock">{{ fmt(it.stock) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </template>
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
.badge.hint {
  background: linear-gradient(135deg, #ff9f43, #ff5b7f);
  box-shadow: 0 0 16px rgba(255, 120, 90, .55);
}
.update-hint { font-size: 13px; color: #8aa0c8; }
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
  font-size: 34px; font-weight: 800; margin-top: 6px;
  font-family: "DIN Alternate", "Bahnschrift", sans-serif;
}
.kpi .val.in { color: #2ee6a8; }
.kpi .val.out { color: #ff5b7f; }
.kpi .val.stock { color: #ffd166; }

.empty { padding: 50px 20px; text-align: center; color: #8aa0c8; font-size: 15px; line-height: 1.9; }
.empty .path { color: #ffd166; font-weight: 600; }

.panel {
  background: rgba(16, 32, 72, .55); border: 1px solid rgba(70, 120, 220, .28);
  border-radius: 14px; padding: 18px; backdrop-filter: blur(4px); margin-bottom: 16px;
}
.p-title { display: flex; align-items: center; gap: 10px; font-size: 16px; font-weight: 700; color: #dbe6ff; margin-bottom: 14px; }
.p-title .dot { width: 8px; height: 8px; border-radius: 50%; background: #2b6cff; box-shadow: 0 0 10px #2b6cff; }

.tbl { width: 100%; border-collapse: collapse; font-size: 14px; }
.tbl th, .tbl td {
  padding: 10px 12px; text-align: left;
  border-bottom: 1px solid rgba(120, 150, 210, .2);
}
.tbl th { color: #8aa0c8; font-weight: 600; font-size: 13px; }
.tbl td { color: #dbe6ff; font-size: 16px; }
.num { text-align: right; font-variant-numeric: tabular-nums; }
.tbl td.c-in { color: #2ee6a8; }
.tbl td.c-out { color: #ff5b7f; }
.tbl td.c-stock { color: #ffd166; font-weight: 700; }
</style>
