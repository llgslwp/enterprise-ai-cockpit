# 企业AI驾驶舱 - 一键启动脚本（自动探测路径版，换电脑免手改）
# 同时启动后端(FastAPI:8000) 和 前端(Vite:5173)，并自动打开浏览器

$ErrorActionPreference = "Stop"

# ---------- 0. 自动定位项目目录与 Python / Node ----------
# 项目目录 = 本脚本所在目录（复制到任何电脑、任何盘符都有效）
$ProjectDir = $PSScriptRoot

# 探测 Python：优先 WorkBuddy 内置（已知可靠）-> D:\Python313 -> 系统 python
# 关键：排除 WindowsApps 的 Store stub（假的 python.exe，会导致脚本中断）
# 且探测用 try/catch 包裹，避免 $ErrorActionPreference=Stop 因 stub 报错而中断整个脚本
$Python = $null
$candidates = @()
# 1) WorkBuddy 内置 python（通常带齐依赖，2 号机实际可用）
$wbPy = Get-ChildItem "$env:USERPROFILE\.workbuddy\binaries\python\versions\*\python.exe" -ErrorAction SilentlyContinue | Sort-Object Name -Descending
foreach ($wp in $wbPy) { $candidates += $wp.FullName }
# 2) 独立安装的 D:\Python313
if (Test-Path "D:\Python313\python.exe") { $candidates += "D:\Python313\python.exe" }
# 3) 系统 PATH 里的 python（排除 WindowsApps 的 Store stub）
$pyCmd = Get-Command python -ErrorAction SilentlyContinue
if ($pyCmd -and $pyCmd.Source -notlike "*WindowsApps*") { $candidates += $pyCmd.Source }
foreach ($cand in $candidates) {
    if (-not $cand) { continue }
    if ($cand -like "*WindowsApps*") { continue }  # 跳过 Store stub
    try {
        $null = & $cand -c "import fastapi" 2>$null
        if ($LASTEXITCODE -eq 0) { $Python = $cand; break }
    } catch {
        # stub 或不可用 python 报错时跳过，继续下一个候选
        continue
    }
}

# 探测 Node：优先系统 node -> WorkBuddy 内置 node.exe
$Node = $null
$nodeCmd = Get-Command node -ErrorAction SilentlyContinue
if ($nodeCmd) { $Node = $nodeCmd.Source }
if (-not $Node) {
    $wbNode = Get-ChildItem "$env:USERPROFILE\.workbuddy\binaries\node\versions\*\node.exe" -ErrorAction SilentlyContinue | Sort-Object Name -Descending | Select-Object -First 1
    if ($wbNode) { $Node = $wbNode.FullName }
}

if (-not $Python) {
    Write-Host "错误：未找到带依赖(fastapi)的 Python。请先运行: pip install -r requirements.txt" -ForegroundColor Red
    exit 1
}
if (-not $Node) {
    Write-Host "错误：未找到 Node.js。" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "==============================================" -ForegroundColor Cyan
Write-Host "        企业AI驾驶舱 - 正在启动" -ForegroundColor Cyan
Write-Host "==============================================" -ForegroundColor Cyan
Write-Host "  项目目录: $ProjectDir" -ForegroundColor DarkGray
Write-Host "  Python : $Python" -ForegroundColor DarkGray
Write-Host "  Node   : $Node" -ForegroundColor DarkGray
Write-Host ""

# ---------- 1. 启动后端 (FastAPI, 端口 8000) ----------
Write-Host "[1/3] 启动后端服务 (FastAPI :8000)..." -ForegroundColor Yellow

$existing = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
if ($existing) {
    Write-Host "      后端服务已在运行 (端口 8000)，跳过启动。" -ForegroundColor Green
} else {
    Start-Process -FilePath $Python -ArgumentList "main.py" -WorkingDirectory $ProjectDir -WindowStyle Minimized
    Write-Host "      后端已启动。" -ForegroundColor Green
}

# ---------- 2. 启动前端 (Vite, 端口 5173) ----------
Write-Host "[2/3] 启动前端服务 (Vite :5173)..." -ForegroundColor Yellow

$existing5173 = Get-NetTCPConnection -LocalPort 5173 -State Listen -ErrorAction SilentlyContinue
if ($existing5173) {
    Write-Host "      前端服务已在运行 (端口 5173)，跳过启动。" -ForegroundColor Green
} else {
    # 直接用 node 跑 vite 的 JS 入口，绕开 npm.cmd 的 .cmd 解释兼容问题
    $viteJs = Join-Path $ProjectDir "web\node_modules\vite\bin\vite.js"
    Start-Process -FilePath $Node -ArgumentList $viteJs -WorkingDirectory "$ProjectDir\web" -WindowStyle Minimized
    Write-Host "      前端已启动。" -ForegroundColor Green
}

# ---------- 3. 等待服务就绪并打开浏览器 ----------
# 关键：必须先等【后端 8000 端口真正 LISTEN】，再开浏览器。
# 后端首次加载依赖要 10~20 秒才绑端口；若只等前端 vite 就绪就开浏览器，
# 用户手快登录会撞上后端空窗期 → 连接被拒 → 误报「登录失败」。
Write-Host "[3/3] 等待后端就绪 (:8000)..." -ForegroundColor Yellow

$backendReady = $false
for ($i = 0; $i -lt 60; $i++) {
    $chk8000 = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
    if ($chk8000) { $backendReady = $true; break }
    Start-Sleep -Seconds 1
}

if ($backendReady) {
    Write-Host "      后端已就绪 (:8000)。" -ForegroundColor Green
} else {
    Write-Host "      警告：后端 60 秒仍未就绪，可能启动失败，请检查 main.py 报错。" -ForegroundColor Red
}

# 再等前端 vite 返回 200（编译完成）
Write-Host "      等待前端就绪 (:5173)..." -ForegroundColor Yellow
$url = "http://127.0.0.1:5173"
$frontendReady = $false
for ($i = 0; $i -lt 30; $i++) {
    try {
        $resp = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 2
        if ($resp.StatusCode -eq 200) { $frontendReady = $true; break }
    } catch {}
    Start-Sleep -Seconds 1
}

# 只有后端就绪了才打开浏览器；否则打开也是登录失败，宁可明确提示
if ($frontendReady -and $backendReady) {
    Start-Process $url
    Write-Host ""
    Write-Host "==============================================" -ForegroundColor Cyan
    Write-Host "  启动完成！浏览器已打开 $url" -ForegroundColor Green
    Write-Host "  （后端+前端均已就绪，可直接登录）" -ForegroundColor Green
    Write-Host "==============================================" -ForegroundColor Cyan
} elseif ($frontendReady) {
    Write-Host ""
    Write-Host "  前端已就绪，但后端仍在启动，请【等十几秒再登录】。" -ForegroundColor Magenta
    Start-Process $url
} else {
    Write-Host ""
    Write-Host "  前端可能仍在编译中，请稍后手动访问 $url" -ForegroundColor Magenta
}

Write-Host ""
Write-Host "提示：关闭本窗口不会停止服务；如需停止，请到任务管理器结束 python.exe 和 node.exe 进程。" -ForegroundColor DarkGray
Start-Sleep -Seconds 3
