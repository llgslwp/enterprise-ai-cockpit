<script setup>
import { ref, onMounted } from 'vue'
import { inventorySummary, inventorySearch, inventoryAlerts } from '../api'

const summary = ref([])
const alerts = ref([])
const searchKeyword = ref('')
const searchResults = ref([])
const searched = ref(false)
const loading = ref(false)

async function loadSummary() {
  const r = await inventorySummary()
  summary.value = r.data?.data?.summary || []
}
async function loadAlerts() {
  const r = await inventoryAlerts()
  alerts.value = r.data?.data?.alerts || []
}
async function doSearch() {
  const kw = searchKeyword.value.trim()
  if (!kw) return
  loading.value = true
  searched.value = true
  try {
    const r = await inventorySearch(kw)
    searchResults.value = r.data?.data?.items || []
  } finally {
    loading.value = false
  }
}

function fmtStock(v) {
  return Number(v ?? 0).toLocaleString('zh-CN')
}

onMounted(() => {
  loadSummary()
  loadAlerts()
})
</script>

<template>
  <div class="inventory">
    <h2>库存管理</h2>
    <p class="muted">反映各类物资库存状态；成品结存低于安全库存时自动预警。</p>

    <!-- 汇总看板 -->
    <section class="card">
      <h3>库存汇总看板</h3>
      <div class="summary-grid">
        <div v-for="s in summary" :key="s.category" class="summary-item">
          <div class="summary-name">{{ s.category }}</div>
          <div class="summary-count" :class="{ missing: s.status === '缺失' }">
            {{ s.status === '缺失' ? '缺失' : s.item_count + ' 种' }}
          </div>
          <div class="summary-stock">总存量 {{ fmtStock(s.total_stock) }}</div>
        </div>
      </div>
    </section>

    <!-- 预警列表 -->
    <section class="card">
      <h3>
        库存预警
        <span class="badge" :class="{ warn: alerts.length > 0 }">{{ alerts.length }}</span>
      </h3>
      <p v-if="alerts.length === 0" class="empty">暂无低于安全库存的成品。</p>
      <table v-else class="tbl">
        <thead>
          <tr>
            <th>类别</th><th>规格</th><th>特征</th>
            <th class="num">当前库存</th><th class="num">安全库存</th><th class="num">缺口</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(a, i) in alerts" :key="i">
            <td>{{ a.category }}</td>
            <td>{{ a.spec }}</td>
            <td>{{ a.feature }}</td>
            <td class="num stock-low">{{ fmtStock(a.stock) }}</td>
            <td class="num">{{ fmtStock(a.threshold) }}</td>
            <td class="num gap">{{ fmtStock(a.gap) }}</td>
          </tr>
        </tbody>
      </table>
    </section>

    <!-- 明细查询 -->
    <section class="card">
      <h3>逐物资明细查询</h3>
      <div class="search-bar">
        <input
          v-model="searchKeyword"
          placeholder="输入货品名称或规格，如 Z108S、内管钳S61"
          @keyup.enter="doSearch"
        />
        <button @click="doSearch" :disabled="loading">查询</button>
      </div>
      <p v-if="searched && searchResults.length === 0" class="empty">无匹配记录。</p>
      <table v-if="searchResults.length > 0" class="tbl">
        <thead>
          <tr>
            <th>库别</th><th>货品名称</th><th>规格</th><th>特征</th>
            <th class="num">存量</th><th>批号/库位</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(it, i) in searchResults" :key="i">
            <td>{{ it.category }}</td>
            <td>{{ it.name }}</td>
            <td>{{ it.spec }}</td>
            <td>{{ it.feature || '-' }}</td>
            <td class="num">{{ fmtStock(it.stock) }}</td>
            <td class="muted-cell">{{ it.batch || it.location || '-' }}</td>
          </tr>
        </tbody>
      </table>
    </section>
  </div>
</template>

<style scoped>
h2 { font-size: 18px; font-weight: 600; margin: 0 0 6px; }
.muted { color: var(--color-text-secondary, #666); font-size: 13px; margin-bottom: 20px; }
.card {
  background: var(--color-background-primary, #fff);
  border: 1px solid var(--color-border-tertiary, #eee);
  border-radius: 12px;
  padding: 18px;
  margin-bottom: 18px;
}
.card h3 { font-size: 15px; font-weight: 600; margin: 0 0 14px; display: flex; align-items: center; gap: 8px; }
.badge {
  background: #e0e0e0; color: #555; font-size: 12px; border-radius: 10px;
  padding: 1px 9px; font-weight: 600;
}
.badge.warn { background: #fdecea; color: #d32f2f; }
.empty { color: var(--color-text-secondary, #999); font-size: 13px; margin: 0; }

.summary-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(160px, 1fr)); gap: 12px; }
.summary-item {
  border: 1px solid var(--color-border-tertiary, #eee); border-radius: 10px;
  padding: 14px; text-align: center;
}
.summary-name { font-size: 13px; color: var(--color-text-secondary, #666); margin-bottom: 6px; }
.summary-count { font-size: 20px; font-weight: 700; }
.summary-count.missing { color: #d32f2f; font-size: 15px; }
.summary-stock { font-size: 12px; color: var(--color-text-secondary, #999); margin-top: 4px; }

.search-bar { display: flex; gap: 8px; margin-bottom: 14px; }
.search-bar input {
  flex: 1; padding: 9px 12px; border: 1px solid var(--color-border-tertiary, #ddd);
  border-radius: 8px; font-size: 14px;
}
.search-bar button {
  padding: 9px 18px; border: none; border-radius: 8px; cursor: pointer;
  background: var(--color-text-primary, #222); color: #fff; font-size: 14px;
}
.search-bar button:disabled { opacity: 0.5; cursor: not-allowed; }

.tbl { width: 100%; border-collapse: collapse; font-size: 13px; }
.tbl th, .tbl td { padding: 8px 10px; text-align: left; border-bottom: 1px solid var(--color-border-tertiary, #f0f0f0); }
.tbl th { color: var(--color-text-secondary, #888); font-weight: 600; font-size: 12px; }
.num { text-align: right; font-variant-numeric: tabular-nums; }
.stock-low { color: #d32f2f; font-weight: 700; }
.gap { color: #d32f2f; }
.muted-cell { color: var(--color-text-secondary, #999); }
</style>
