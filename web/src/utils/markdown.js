// 轻量 Markdown 渲染器（零依赖）
// 覆盖模型输出最常见的语法：标题 / 加粗 / 行内代码 / 表格 / 列表 / 代码块 / 分隔线 / 引用
// 安全：所有文本内容先做 HTML 转义，结构标签由本渲染器生成，防 XSS

function escapeHtml(s) {
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

// 行内元素：行内代码 → 加粗（顺序：先保护代码再处理加粗）
function inline(s) {
  let t = escapeHtml(s)
  // 行内代码 `code`
  t = t.replace(/`([^`]+)`/g, '<code>$1</code>')
  // 加粗 **bold**
  t = t.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
  // 斜体 *em*（单星，避免与加粗冲突，处理剩余的）
  t = t.replace(/(^|[^*])\*([^*\n]+)\*(?!\*)/g, '$1<em>$2</em>')
  return t
}

function isTableSep(line) {
  return /^\s*\|?[\s:|-]+\|?\s*$/.test(line) && line.includes('-')
}

function isTableRow(line) {
  return /^\s*\|.*\|\s*$/.test(line)
}

function parseTableRow(line) {
  return line
    .trim()
    .replace(/^\|/, '')
    .replace(/\|$/, '')
    .split('|')
    .map((c) => c.trim())
}

function renderTable(lines) {
  // lines[0] 表头，lines[1] 分隔符，lines[2..] 数据
  const header = parseTableRow(lines[0])
  const bodyRows = lines.slice(2)
  let html = '<table><thead><tr>'
  header.forEach((h) => {
    html += `<th>${inline(h)}</th>`
  })
  html += '</tr></thead><tbody>'
  bodyRows.forEach((row) => {
    const cells = parseTableRow(row)
    html += '<tr>'
    header.forEach((_, idx) => {
      html += `<td>${inline(cells[idx] || '')}</td>`
    })
    html += '</tr>'
  })
  html += '</tbody></table>'
  return html
}

function isListStart(line) {
  return /^\s*[-*+]\s+/.test(line) || /^\s*\d+[.)]\s+/.test(line)
}

function renderList(lines, ordered) {
  const tag = ordered ? 'ol' : 'ul'
  let html = `<${tag}>`
  lines.forEach((line) => {
    const content = line.replace(/^\s*[-*+]\s+/, '').replace(/^\s*\d+[.)]\s+/, '')
    html += `<li>${inline(content)}</li>`
  })
  html += `</${tag}>`
  return html
}

export function renderMarkdown(text) {
  if (!text) return ''
  const lines = String(text).replace(/\r\n/g, '\n').split('\n')
  const out = []
  let i = 0

  while (i < lines.length) {
    const line = lines[i]
    const trimmed = line.trim()

    // 代码块 ```
    if (trimmed.startsWith('```')) {
      const codeLines = []
      i++
      while (i < lines.length && !lines[i].trim().startsWith('```')) {
        codeLines.push(lines[i])
        i++
      }
      i++ // 跳过结尾 ```
      out.push(`<pre><code>${escapeHtml(codeLines.join('\n'))}</code></pre>`)
      continue
    }

    // 表格（连续的 | 行，第二行为分隔符）
    if (isTableRow(trimmed)) {
      const tableLines = [line]
      let j = i + 1
      // 收集连续表格行
      while (j < lines.length && isTableRow(lines[j].trim())) {
        tableLines.push(lines[j])
        j++
      }
      // 需满足：至少 2 行，且第二行是分隔符
      if (tableLines.length >= 2 && isTableSep(tableLines[1])) {
        out.push(renderTable(tableLines))
        i = j
        continue
      }
      // 不是规范表格，按普通段落处理第一行
      out.push(`<p>${inline(line)}</p>`)
      i++
      continue
    }

    // 标题
    const hMatch = trimmed.match(/^(#{1,4})\s+(.*)$/)
    if (hMatch) {
      const level = hMatch[1].length
      out.push(`<h${level}>${inline(hMatch[2])}</h${level}>`)
      i++
      continue
    }

    // 分隔线
    if (/^(-{3,}|\*{3,}|_{3,})$/.test(trimmed)) {
      out.push('<hr />')
      i++
      continue
    }

    // 引用
    if (trimmed.startsWith('>')) {
      const quoteLines = []
      while (i < lines.length && lines[i].trim().startsWith('>')) {
        quoteLines.push(lines[i].trim().replace(/^>\s?/, ''))
        i++
      }
      out.push(`<blockquote>${quoteLines.map(inline).join('<br />')}</blockquote>`)
      continue
    }

    // 列表（连续的列表项）
    if (isListStart(trimmed)) {
      const ordered = /^\s*\d+[.)]\s+/.test(trimmed)
      const listLines = [line]
      let j = i + 1
      while (j < lines.length && isListStart(lines[j].trim())) {
        // 同类型列表才合并（有序/无序不混排）
        const nextOrdered = /^\s*\d+[.)]\s+/.test(lines[j].trim())
        if (nextOrdered !== ordered) break
        listLines.push(lines[j])
        j++
      }
      out.push(renderList(listLines, ordered))
      i = j
      continue
    }

    // 空行
    if (trimmed === '') {
      i++
      continue
    }

    // 普通段落
    out.push(`<p>${inline(line)}</p>`)
    i++
  }

  return out.join('\n')
}
