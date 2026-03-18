# ============================================================
#  小红书 AI 平台 — 一键启动脚本
#  启动 server.py (本地代理) + Cloudflare Tunnel
# ============================================================
param(
    [int]$Port = 3000,
    [string]$TunnelDomain = '',   # 留空=Quick Tunnel，填写=使用 Named Tunnel 域名
    [switch]$SkipTunnel           # 只启动 server.py，不启动 Tunnel
)

$ErrorActionPreference = 'Stop'
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

# ---- 终端颜色辅助 ----
function Write-Section($msg)  { Write-Host "`n━━━ $msg ━━━" -ForegroundColor Cyan }
function Write-Ok($msg)       { Write-Host "  ✅ $msg" -ForegroundColor Green }
function Write-Warn($msg)     { Write-Host "  ⚠️  $msg" -ForegroundColor Yellow }
function Write-Err($msg)      { Write-Host "  ❌ $msg" -ForegroundColor Red }
function Write-Info($msg)     { Write-Host "  ℹ️  $msg" -ForegroundColor Gray }

Write-Host @"

╔══════════════════════════════════════════════╗
║   小红书 AI 平台 — 本地 Tunnel 启动器 🚀     ║
╚══════════════════════════════════════════════╝
"@ -ForegroundColor Magenta

# ============ 1. 检测依赖 ============
Write-Section "检测环境"

# Python
$PythonExe = $null
foreach ($p in @(
    "$env:USERPROFILE\miniconda3\python.exe",
    "$env:USERPROFILE\anaconda3\python.exe",
    "python"
)) {
    try {
        $ver = & $p -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>$null
        if ($LASTEXITCODE -eq 0 -and $ver) { $PythonExe = $p; break }
    } catch {}
}
if (-not $PythonExe) { Write-Err "找不到 Python，请安装 Miniconda/Python"; exit 1 }
Write-Ok "Python: $PythonExe ($ver)"

# Cloudflared
$CfExe = $null
foreach ($p in @(
    "$env:USERPROFILE\cloudflared.exe",
    "cloudflared"
)) {
    try {
        $cfv = & $p version 2>&1 | Select-String -Pattern '\d+\.\d+\.\d+' | ForEach-Object { $_.Matches[0].Value }
        if ($cfv) { $CfExe = $p; break }
    } catch {}
}
if (-not $CfExe -and -not $SkipTunnel) {
    Write-Warn "cloudflared 未安装，正在自动下载..."
    $cfUrl = "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe"
    $cfDst = "$env:USERPROFILE\cloudflared.exe"
    Invoke-WebRequest -Uri $cfUrl -OutFile $cfDst -UseBasicParsing
    $CfExe = $cfDst
    $cfv = & $CfExe version 2>&1 | Select-String -Pattern '\d+\.\d+\.\d+' | ForEach-Object { $_.Matches[0].Value }
}
if ($CfExe) { Write-Ok "cloudflared: $CfExe (v$cfv)" }

# ============ 2. 检测梯子/代理 ============
Write-Section "检测网络代理"

$ProxyUrl = $null
# 检查系统代理设置
$SysProxy = (Get-ItemProperty 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Internet Settings' -ErrorAction SilentlyContinue)
if ($SysProxy.ProxyEnable -and $SysProxy.ProxyServer) {
    $raw = $SysProxy.ProxyServer
    if ($raw -notmatch '^https?://') { $raw = "http://$raw" }
    $ProxyUrl = $raw
}
# 检查常见代理端口（Clash/V2Ray/SSR）
if (-not $ProxyUrl) {
    foreach ($testPort in @(7890, 10808, 1080, 10809, 8080)) {
        try {
            $tcp = New-Object Net.Sockets.TcpClient
            $tcp.SendTimeout = 1000; $tcp.ReceiveTimeout = 1000
            $tcp.Connect('127.0.0.1', $testPort)
            $tcp.Close()
            $ProxyUrl = "http://127.0.0.1:$testPort"
            break
        } catch {}
    }
}
if ($ProxyUrl) {
    Write-Ok "检测到代理: $ProxyUrl"
    $env:HTTPS_PROXY = $ProxyUrl
    $env:HTTP_PROXY = $ProxyUrl
} else {
    Write-Warn "未检测到代理，Gemini API 请求将直连（需翻墙环境）"
}

# ============ 3. 加载 API Key ============
Write-Section "加载 API Key"

$KeyFile = Join-Path $ScriptDir "api_key.txt"
if (-not $env:GEMINI_API_KEY) {
    if (Test-Path $KeyFile) {
        $env:GEMINI_API_KEY = (Get-Content $KeyFile -Raw).Trim()
        Write-Ok "从 api_key.txt 加载 Key: $($env:GEMINI_API_KEY.Substring(0,10))..."
    } else {
        Write-Err "未找到 API Key！请设置 GEMINI_API_KEY 环境变量 或创建 api_key.txt"
        exit 1
    }
} else {
    Write-Ok "使用环境变量 Key: $($env:GEMINI_API_KEY.Substring(0,10))..."
}

# ============ 4. 启动 server.py ============
Write-Section "启动本地服务器"

$ServerLog = Join-Path $ScriptDir "_server.log"
$ServerProc = Start-Process -FilePath $PythonExe -ArgumentList "server.py" `
    -WorkingDirectory $ScriptDir -PassThru -RedirectStandardError $ServerLog `
    -WindowStyle Hidden
Write-Info "server.py PID: $($ServerProc.Id)"

# 等待服务器启动
$ready = $false
for ($i = 0; $i -lt 15; $i++) {
    Start-Sleep -Milliseconds 500
    try {
        $oldProxy = $env:HTTPS_PROXY; $env:HTTPS_PROXY = ""
        $r = Invoke-WebRequest -Uri "http://localhost:$Port/api/version" -UseBasicParsing -TimeoutSec 2
        $env:HTTPS_PROXY = $oldProxy
        if ($r.StatusCode -eq 200) { $ready = $true; break }
    } catch { $env:HTTPS_PROXY = $oldProxy }
}
if ($ready) {
    Write-Ok "本地服务器已启动 → http://localhost:$Port"
} else {
    Write-Err "服务器启动超时，请检查 $_server.log"
    Get-Content $ServerLog -Tail 5 -ErrorAction SilentlyContinue | Write-Host
    exit 1
}

# ============ 5. 启动 Cloudflare Tunnel ============
$TunnelUrl = "http://localhost:$Port"  # 默认本地访问

if (-not $SkipTunnel) {
    Write-Section "启动 Cloudflare Tunnel"
    
    $CfLog = Join-Path $env:TEMP "cloudflared_log.txt"
    
    if ($TunnelDomain) {
        # Named Tunnel 模式 — 固定域名
        Write-Info "Named Tunnel 模式: $TunnelDomain"
        # 检查是否已登录 Cloudflare
        $cfCert = "$env:USERPROFILE\.cloudflared\cert.pem"
        if (-not (Test-Path $cfCert)) {
            Write-Warn "首次使用 Named Tunnel，需要登录 Cloudflare 账号"
            Write-Info "浏览器将打开 Cloudflare 授权页面..."
            & $CfExe tunnel login
            if (-not (Test-Path $cfCert)) {
                Write-Err "Cloudflare 登录失败"; exit 1
            }
            Write-Ok "Cloudflare 登录成功"
        }
        # 检查/创建 Tunnel
        $TunnelName = "xhs-local"
        $tunnelList = & $CfExe tunnel list --output json 2>$null | ConvertFrom-Json
        $existing = $tunnelList | Where-Object { $_.name -eq $TunnelName -and -not $_.deleted_at }
        if (-not $existing) {
            Write-Info "创建 Named Tunnel: $TunnelName"
            & $CfExe tunnel create $TunnelName
        } else {
            Write-Info "使用已有 Tunnel: $TunnelName (ID: $($existing.id))"
        }
        # 配置 DNS 路由
        Write-Info "配置 DNS: $TunnelDomain → $TunnelName"
        & $CfExe tunnel route dns $TunnelName $TunnelDomain 2>$null
        # 写入配置
        $cfConfig = "$env:USERPROFILE\.cloudflared\config.yml"
        @"
tunnel: $TunnelName
credentials-file: $env:USERPROFILE\.cloudflared\$($existing.id ?? $TunnelName).json
ingress:
  - hostname: $TunnelDomain
    service: http://localhost:$Port
  - service: http_status:404
"@ | Set-Content $cfConfig
        $TunnelUrl = "https://$TunnelDomain"
        $CfProc = Start-Process -FilePath $CfExe -ArgumentList "tunnel run $TunnelName" `
            -PassThru -RedirectStandardError $CfLog -WindowStyle Hidden
    } else {
        # Quick Tunnel 模式 — 随机 URL
        Write-Info "Quick Tunnel 模式（随机 URL，每次重启会变）"
        $CfArgs = "tunnel --url http://localhost:$Port"
        $CfProc = Start-Process -FilePath $CfExe -ArgumentList $CfArgs `
            -PassThru -RedirectStandardError $CfLog -WindowStyle Hidden
    }
    Write-Info "cloudflared PID: $($CfProc.Id)"

    # 等待 Tunnel URL 出现
    if (-not $TunnelDomain) {
        Write-Info "等待 Tunnel 分配 URL（约 5-15 秒）..."
        $TunnelUrl = $null
        for ($i = 0; $i -lt 30; $i++) {
            Start-Sleep -Seconds 1
            if (Test-Path $CfLog) {
                $content = Get-Content $CfLog -Raw -ErrorAction SilentlyContinue
                if ($content -match '(https://[a-z0-9-]+\.trycloudflare\.com)') {
                    $TunnelUrl = $Matches[1]
                    break
                }
            }
        }
        if (-not $TunnelUrl) {
            Write-Err "Tunnel URL 获取超时，请检查 $CfLog"
            Get-Content $CfLog -Tail 5 -ErrorAction SilentlyContinue | Write-Host
        }
    }
    
    if ($TunnelUrl) {
        Write-Ok "Tunnel 已启动 → $TunnelUrl"
        
        # 自动更新前端代码中的 Tunnel URL
        $IndexFile = Join-Path $ScriptDir "public\index.html"
        $htmlContent = Get-Content $IndexFile -Raw
        $oldPattern = "const CF_TUNNEL_BACKEND = '[^']*';"
        $newValue = "const CF_TUNNEL_BACKEND = '$TunnelUrl';"
        if ($htmlContent -match $oldPattern) {
            $currentUrl = [regex]::Match($htmlContent, "const CF_TUNNEL_BACKEND = '([^']*)'").Groups[1].Value
            if ($currentUrl -ne $TunnelUrl) {
                $htmlContent = $htmlContent -replace $oldPattern, $newValue
                Set-Content -Path $IndexFile -Value $htmlContent -NoNewline
                Write-Ok "已更新 public/index.html 中的 Tunnel URL"
                Write-Warn "请记得 git commit & push 以更新 GitHub Pages"
            } else {
                Write-Info "Tunnel URL 未变化，无需更新"
            }
        }
    }
}

# ============ 汇总 ============
Write-Host @"

╔══════════════════════════════════════════════════╗
║            🎉 启动成功！                          ║
╠══════════════════════════════════════════════════╣
║  本地服务器: http://localhost:$Port                  ║
║  Tunnel URL: $($TunnelUrl.PadRight(36))║
║  代理/梯子:  $($ProxyUrl ?? '无（直连）')                      ║
╠══════════════════════════════════════════════════╣
║  Ctrl+C 停止所有服务                              ║
╚══════════════════════════════════════════════════╝

"@ -ForegroundColor Green

# 前端地址
Write-Host "  📱 用户访问地址:" -ForegroundColor White
Write-Host "     GitHub Pages: https://lincsd.github.io/xhs-emotion-platform/" -ForegroundColor Cyan
Write-Host "     Tunnel 直连:  $TunnelUrl" -ForegroundColor Cyan
Write-Host ""

# ============ 等待退出 ============
try {
    Write-Host "按 Ctrl+C 停止服务..." -ForegroundColor DarkGray
    # 保持运行，监控子进程
    while ($true) {
        Start-Sleep -Seconds 5
        # 检查 server.py 是否存活
        if ($ServerProc.HasExited) {
            Write-Err "server.py 已退出 (ExitCode: $($ServerProc.ExitCode))"
            Write-Info "最近日志:"
            Get-Content $ServerLog -Tail 10 -ErrorAction SilentlyContinue | Write-Host
            break
        }
        # 检查 cloudflared 是否存活
        if (-not $SkipTunnel -and $CfProc -and $CfProc.HasExited) {
            Write-Err "cloudflared 已退出 (ExitCode: $($CfProc.ExitCode))"
            break
        }
    }
} finally {
    Write-Section "清理进程"
    if (-not $ServerProc.HasExited) {
        Stop-Process -Id $ServerProc.Id -Force -ErrorAction SilentlyContinue
        Write-Ok "server.py 已停止"
    }
    if ($CfProc -and -not $CfProc.HasExited) {
        Stop-Process -Id $CfProc.Id -Force -ErrorAction SilentlyContinue
        # cloudflared 可能有子进程
        Get-Process -Name cloudflared -ErrorAction SilentlyContinue | Stop-Process -Force
        Write-Ok "cloudflared 已停止"
    }
    Write-Host "`n👋 已退出" -ForegroundColor DarkGray
}
