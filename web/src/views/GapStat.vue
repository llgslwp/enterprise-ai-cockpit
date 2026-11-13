<script setup>
import { ref, onMounted, computed } from 'vue'
import { productionGapStat, productionSchedule, productionSourceFiles } from '../api'

const loading = ref(false)
const errorMsg = ref('')
const data = ref(null)           // 后端返回的完整数据
const currentSheet = ref('加力') // 当前选中的品类

// 排产统计
const scheduling = ref(false)      // 排产执行中
const scheduleMsg = ref('')        // 排产结果反馈（成功/失败）
const scheduleOk = ref(false)      // 排产是否成功
const sourceDates = ref(null)      // 6 源文件 + V2.0 基底日期

const productSheets = ref([])

// 颜色映射（Excel 填充色 → CSS）
const FILL_MAP = {
  FF00B0F0: '#00b0f0',   // 蓝底（成品计划）
  FF92D050: '#92d050',   // 绿底
  FFFFFF00: '#ffff00',   // 黄底
  FFFFC000: '#ffc000',   // 橙底
  FFFF0000: '#ff0000',   // 红底
  FFFFFFFF: '#ffffff',   // 白底
}

function fillToCss(rgb) {
  return FILL_MAP[rgb] || ''
}

async function load() {
  loading.value = true
  errorMsg.value = ''
  try {
    const r = await productionGapStat()
    const d = r.data?.data
    if (!d) {
      errorMsg.value = r.data?.message || '无数据'
      return
    }
    data.value = d
    productSheets.value = d.product_sheets || []
    if (!currentSheet.value || !productSheets.value.includes(currentSheet.value)) {
      currentSheet.value = productSheets.value[0] || ''
    }
  } catch (e) {
    errorMsg.value = e?.response?.data?.message || '加载失败'
  } finally {
    loading.value = false
  }
}

// 加载源文件日期（按钮旁常驻显示，不阻塞）
async function loadSourceDates() {
  try {
    const r = await productionSourceFiles()
    sourceDates.value = r.data?.data || null
  } catch (e) {
    sourceDates.value = null
  }
}

// 触发排产统计（无条件执行，覆盖 V2.0）
async function runSchedule() {
  if (scheduling.value) return
  scheduling.value = true
  scheduleMsg.value = ''
  scheduleOk.value = false
  try {
    const r = await productionSchedule()
    const d = r.data?.data
    if (r.data?.code === 0) {
      scheduleOk.value = true
      scheduleMsg.value = `排产完成：已覆盖 V2.0。归集 ${d?.fill_count ?? 0} 处，成品计划 ${d?.chengpin_fills ?? 0} 处。`
    } else {
      scheduleOk.value = false
      scheduleMsg.value = r.data?.message || '排产失败'
    }
  } catch (e) {
    scheduleOk.value = false
    scheduleMsg.value = e?.response?.data?.message || '排产执行失败'
  } finally {
    scheduling.value = false
    // 排产完刷新表格 + 刷新源文件日期
    await load()
    await loadSourceDates()
  }
}

const sourceDateList = computed(() => {
  if (!sourceDates.value) return []
  return Object.entries(sourceDates.value).map(([name, info]) => ({
    name,
    mtime: info?.mtime || '—',
  }))
})

const currentBlocks = computed(() => {
  if (!data.value) return []
  return data.value.products?.[currentSheet.value]?.blocks || []
})

// 判断某个单元格是否应显示为「正缺口」（粉红底红字）——用于「装配缺口」「机加工生产计划」两列
function isPositiveGap(v) {
  return typeof v === 'number' && v > 0
}

function fmt(v) {
  if (v === null || v === undefined) return ''
  if (typeof v === 'number') {
    return Number.isInteger(v) ? String(v) : v.toFixed(1)
  }
  return v
}

// 单元格背景色（含正缺口粉红底）；onlyGap=true 时「装配缺口」「机加工生产计划」列才标红
function cellBg(fillRgb, value, onlyGap) {
  if (onlyGap && isPositiveGap(value)) return '#fdecea'  // 粉红底（正缺口）
  return fillToCss(fillRgb)
}
// 单元格文字色（正缺口红字）
function cellColor(value, onlyGap) {
  return (onlyGap && isPositiveGap(value)) ? '#d32f2f' : ''
}

// 判断该行的配件名/规格是否需要黄/橙底
function nameStyle(row) {
  const bg = fillToCss(row.name_fill)
  return bg ? { background: bg } : {}
}
function specStyle(row) {
  const bg = fillToCss(row.spec_fill)
  return bg ? { background: bg } : {}
}

onMounted(() => {
  load()
  loadSourceDates()
})
</script>

<template>
  <div class="gap-stat">
    <div class="page-head">
      <h2>生产缺口统计</h2>
      <p class="muted">V2.0 排产结果直显：缺口数值由公式引擎精确计算，与 Excel 打开结果一致。</p>

      <!-- 排产统计操作区 -->
      <div class="schedule-bar">
        <button class="schedule-btn" :disabled="scheduling" @click="runSchedule">
          {{ scheduling ? '排产执行中…' : '排产统计' }}
        </button>
        <span v-if="scheduleMsg" class="schedule-result" :class="{ ok: scheduleOk }">{{ scheduleMsg }}</span>
      </div>

      <!-- 源文件最后更新日期（常驻显示） -->
      <div v-if="sourceDateList.length" class="source-dates">
        <span class="source-dates-title">源文件最后更新：</span>
        <span v-for="d in sourceDateList" :key="d.name" class="source-date-item">
          <span class="source-date-name">{{ d.name }}</span>
          <span class="source-date-time">{{ d.mtime }}</span>
        </span>
      </div>
    </div>

    <!-- 品类切换 -->
    <div class="tabs">
      <button
        v-for="s in productSheets"
        :key="s"
        class="tab"
        :class="{ active: s === currentSheet }"
        @click="currentSheet = s"
      >{{ s }}</button>
    </div>

    <div v-if="loading" class="loading">数据加载中（公式计算约需 2~3 秒）…</div>
    <div v-else-if="errorMsg" class="error">{{ errorMsg }}</div>

    <!-- 各规格块表格 -->
    <div v-else v-for="(block, bi) in currentBlocks" :key="bi" class="block">
      <table class="gap-table">
        <!-- 块头行：品类名 + 规格块 + 缺口列标题 -->
        <thead>
          <tr class="block-head">
            <th :rowspan="2" class="product-name">{{ currentSheet }}</th>
            <th :rowspan="2" class="group-spec">{{ block.block_label }}</th>
            <th :colspan="7" class="group-stage">工序库存</th>
            <th class="plan-title">{{ block.col_titles.J || '成品计划' }}</th>
            <th v-if="block.col_titles.K" class="plan-title">{{ block.col_titles.K }}</th>
            <th class="gap-title">半成品需求计划</th>
            <th class="gap-title">装配缺口</th>
            <th class="gap-title">机加工生产计划</th>
          </tr>
          <tr class="stage-head">
            <th>毛坯库</th><th>机加工</th><th>热处理</th><th>待处理</th>
            <th>外协</th><th>半成品</th><th>装配</th>
            <th class="plan-val" :style="{ background: fillToCss(block.headers?.plan1?.fill) }">{{ fmt(block.headers?.plan1?.value) }}</th>
            <th v-if="block.col_titles.K" class="plan-val" :style="{ background: fillToCss(block.headers?.plan2?.fill) }">{{ fmt(block.headers?.plan2?.value) }}</th>
            <th></th><th></th><th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(row, ri) in block.rows" :key="ri" :class="{ assembly: row.is_assembly }">
            <td class="name-cell" :style="nameStyle(row)">{{ row.name }}</td>
            <td class="spec-cell" :style="specStyle(row)">{{ row.spec }}</td>
            <!-- C~I 工序库存 -->
            <td class="num">{{ fmt(row.cells['3']) }}</td>
            <td class="num">{{ fmt(row.cells['4']) }}</td>
            <td class="num">{{ fmt(row.cells['5']) }}</td>
            <td class="num">{{ fmt(row.cells['6']) }}</td>
            <td class="num">{{ fmt(row.cells['7']) }}</td>
            <td class="num">{{ fmt(row.cells['8']) }}</td>
            <td class="num">{{ fmt(row.cells['9']) }}</td>
            <!-- 成品计划 -->
            <td class="num plan-num">{{ fmt(row.plan?.plan1) }}</td>
            <td v-if="block.col_titles.K" class="num plan-num">{{ fmt(row.plan?.plan2) }}</td>
            <!-- 缺口列：借用行显示「见XX」，否则显示计算值。只有「装配缺口」列正数才标红 -->
            <td class="num gap-num" :style="{ background: cellBg('', row.gap?.need, false), color: cellColor(row.gap?.need, false) }">
              {{ row.gap_text?.need || fmt(row.gap?.need) }}
            </td>
            <td class="num gap-num" :style="{ background: cellBg('', row.gap?.gap, true), color: cellColor(row.gap?.gap, true) }">
              {{ row.gap_text?.gap || fmt(row.gap?.gap) }}
            </td>
            <td class="num gap-num" :style="{ background: cellBg('', row.gap?.machine, true), color: cellColor(row.gap?.machine, true) }">
              {{ row.gap_text?.machine || fmt(row.gap?.machine) }}
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<style scoped>
h2 { font-size: 22px; font-weight: 600; margin: 0 0 6px; }
.muted { color: var(--color-text-secondary, #666); font-size: 14px; margin-bottom: 18px; }

/* 排产统计操作区 */
.schedule-bar {
  display: flex; align-items: center; gap: 14px; margin-bottom: 14px;
}
.schedule-btn {
  padding: 10px 26px; border: none; border-radius: 8px; cursor: pointer;
  background: #1a73e8; color: #fff; font-size: 15px; font-weight: 600;
}
.schedule-btn:disabled { background: #a0c4f0; cursor: not-allowed; }
.schedule-result { font-size: 14px; color: #d32f2f; }
.schedule-result.ok { color: #1e8e3e; }

/* 源文件最后更新日期（常驻） */
.source-dates {
  display: flex; flex-wrap: wrap; align-items: center; gap: 8px;
  margin-bottom: 18px; padding: 10px 14px; border: 1px solid var(--color-border-tertiary, #ddd);
  border-radius: 8px; background: var(--color-bg-secondary, #f7f8fa);
}
.source-dates-title { font-size: 13px; color: var(--color-text-secondary, #666); font-weight: 600; }
.source-date-item {
  display: inline-flex; align-items: center; gap: 6px; padding: 3px 10px;
  border-radius: 6px; background: #fff; border: 1px solid #e5e5e5;
}
.source-date-name { font-size: 12px; color: var(--color-text-secondary, #555); }
.source-date-time { font-size: 12px; color: var(--color-text-primary, #222); font-variant-numeric: tabular-nums; }


.tabs { display: flex; gap: 8px; margin-bottom: 20px; }
.tab {
  padding: 9px 22px; border: 1px solid var(--color-border-tertiary, #ddd);
  border-radius: 8px; background: transparent; cursor: pointer; font-size: 15px;
  color: var(--color-text-secondary, #555);
}
.tab.active {
  background: var(--color-text-primary, #222); color: #fff; border-color: transparent;
}

.loading, .error { padding: 40px 0; text-align: center; color: var(--color-text-secondary, #888); font-size: 15px; }
.error { color: #d32f2f; }

.block { margin-bottom: 24px; overflow-x: auto; }

.gap-table {
  border-collapse: collapse; font-size: 14px; min-width: 1100px;
  border: 1px solid #bbb; background: #fff;
}
.gap-table th, .gap-table td {
  border: 1px solid #999; padding: 6px 10px; text-align: center; white-space: nowrap;
}
.gap-table thead th {
  background: #e8e8e8; color: #000; font-weight: 600;
}
.product-name { background: #d9d9d9 !important; font-weight: 700; }
.group-spec { background: #f2f2f2 !important; font-weight: 600; }
.group-stage { background: #d9d9d9 !important; }
.plan-title { background: #cfe8f7 !important; font-weight: 600; }
.gap-title { background: #f5d0d0 !important; font-weight: 600; }

/* 表头成品计划蓝底值 */
.plan-val {
  color: #fff !important; font-weight: 700; font-size: 15px;
}

.name-cell, .spec-cell { text-align: left; padding-left: 8px; }
.num { font-variant-numeric: tabular-nums; }

/* 组合件行淡色 */
.assembly td { background: #f7f7f7; color: #888; }
.assembly .name-cell { color: #666; font-style: italic; }

.plan-num { font-weight: 600; }
</style>
