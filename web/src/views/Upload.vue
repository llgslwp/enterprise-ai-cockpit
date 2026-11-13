<script setup>
import { ref, computed, onMounted } from 'vue'
import { uploadFile, listFiles } from '../api'

// 保管员端口：上传 ERP 导出的库存文件（替代微信传文件）。
const files = ref([])   // [{filename, upload_time}]
const uploading = ref(false)
const status = ref('')

async function refresh() {
  try {
    const resp = await listFiles()
    files.value = resp.data?.data ?? resp.data ?? []
  } catch {
    files.value = []
  }
}

// 今天日期（YYYY-MM-DD），用于划分「最新上传」
function todayStr() {
  const d = new Date()
  const mm = String(d.getMonth() + 1).padStart(2, '0')
  const dd = String(d.getDate()).padStart(2, '0')
  return `${d.getFullYear()}-${mm}-${dd}`
}

// 最新上传 = 当天上传的文件（后端已按时间倒序，最新在上）
const latestFiles = computed(() =>
  files.value.filter(f => (f.upload_time || '').startsWith(todayStr()))
)
// 历史上传 = 非当天上传的文件
const historyFiles = computed(() =>
  files.value.filter(f => !(f.upload_time || '').startsWith(todayStr()))
)

async function onFileChange(e) {
  const f = e.target.files[0]
  if (!f) return
  uploading.value = true
  status.value = ''
  const fd = new FormData()
  fd.append('file', f)
  try {
    await uploadFile(fd)
    status.value = `已上传：${f.name}`
    await refresh()
  } catch (err) {
    status.value = `上传失败：${err.response?.data?.detail || err.message}`
  } finally {
    uploading.value = false
    e.target.value = ''
  }
}

onMounted(refresh)
</script>

<template>
  <div>
    <h2>文件上传</h2>
    <p class="muted">保管员端口：上传 ERP 导出的库存 Excel 文件。</p>

    <label class="drop">
      <input type="file" accept=".xlsx,.xls" @change="onFileChange" />
      <span>{{ uploading ? '上传中…' : '点击选择或拖入 Excel 文件' }}</span>
    </label>
    <p v-if="status" class="status">{{ status }}</p>

    <!-- 最新上传 -->
    <h3>最新上传</h3>
    <ul class="list">
      <li v-for="f in latestFiles" :key="f.filename">
        <span class="name">{{ f.filename }}</span>
        <span class="time">{{ f.upload_time }}</span>
      </li>
      <li v-if="latestFiles.length === 0" class="empty">暂无今日上传文件</li>
    </ul>

    <!-- 历史上传 -->
    <h3>历史上传</h3>
    <ul class="list">
      <li v-for="f in historyFiles" :key="f.filename">
        <span class="name">{{ f.filename }}</span>
        <span class="time">{{ f.upload_time }}</span>
      </li>
      <li v-if="historyFiles.length === 0" class="empty">暂无历史文件</li>
    </ul>
  </div>
</template>

<style scoped>
h2 {
  font-size: 18px;
  font-weight: 600;
  margin: 0 0 8px;
}
.muted {
  color: var(--color-text-secondary, #666);
  font-size: 13px;
  margin-bottom: 20px;
}
.drop {
  display: block;
  padding: 32px;
  border: 2px dashed var(--color-border-secondary, #ccc);
  border-radius: 12px;
  text-align: center;
  cursor: pointer;
  color: var(--color-text-secondary, #555);
  font-size: 14px;
}
.drop input {
  display: none;
}
.status {
  font-size: 13px;
  color: var(--color-text-secondary, #555);
  margin-top: 10px;
}
h3 {
  font-size: 15px;
  font-weight: 600;
  margin: 24px 0 10px;
}
.list {
  list-style: none;
  padding: 0;
  margin: 0;
}
.list li {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  padding: 8px 12px;
  border: 1px solid var(--color-border-tertiary, #eee);
  border-radius: 8px;
  margin-bottom: 6px;
  font-size: 13px;
}
.list .name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.list .time {
  flex-shrink: 0;
  color: var(--color-text-tertiary, #999);
  font-size: 12px;
}
.empty {
  color: var(--color-text-tertiary, #999);
}
</style>
