$ErrorActionPreference = 'Continue'
Remove-Item Env:\HTTPS_PROXY -ErrorAction SilentlyContinue
Remove-Item Env:\HTTP_PROXY -ErrorAction SilentlyContinue
$out = @()
$base = "https://xhs.xiaohsai.com"

$out += "============================================"
$out += "  FRONTEND FULL TEST: Content + 3 Images"
$out += "  $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
$out += "============================================"
$out += ""

# --- Login ---
$out += "--- Step 1: Login ---"
$loginJson = '{"username":"lin","password":"950320"}'
$t0 = Get-Date
$token = $null
try {
    $lr = Invoke-WebRequest "$base/api/auth/login" -Method POST -Body ([System.Text.Encoding]::UTF8.GetBytes($loginJson)) -ContentType "application/json; charset=utf-8" -UseBasicParsing -TimeoutSec 15
    $loginMs = [int]((Get-Date)-$t0).TotalMilliseconds
    $loginData = $lr.Content | ConvertFrom-Json
    $token = $loginData.token
    $out += "  OK: ${loginMs}ms, user=$($loginData.user.username), credits=$($loginData.user.credits)"
} catch {
    $loginMs = [int]((Get-Date)-$t0).TotalMilliseconds
    $out += "  FAILED: ${loginMs}ms - $($_.Exception.Message)"
}
$out += ""

if (-not $token) {
    $out += "  >> Cannot continue without login"
    $out | Out-File "frontend_test_result.txt" -Encoding UTF8
    Write-Host "Test failed at login."
    return
}

$headers = @{ 'Authorization' = "Bearer $token" }

# --- Content Generation ---
$out += "--- Step 2: AI Content Generation (gemini-2.5-flash) ---"
$contentPromptText = "You are a popular Xiaohongshu emotional blogger with 500k followers. Generate a healing-themed post. Requirements: 1) Title under 20 chars with emoji 2) Body 150-300 chars with sections and emoji 3) 5 hashtags. Return JSON: {`"title`":`"...`",`"content`":`"...`",`"tags`":[`"...`"]}. Write in Chinese."
$genJson = '{"model":"gemini-2.5-flash","action":"generateContent","feature":"content-gen","payload":{"contents":[{"parts":[{"text":"' + $contentPromptText.Replace('"','\"') + '"}]}]}}'

$t0 = Get-Date
try {
    $gr = Invoke-WebRequest "$base/api/gemini-proxy" -Method POST -Body ([System.Text.Encoding]::UTF8.GetBytes($genJson)) -ContentType "application/json; charset=utf-8" -Headers $headers -UseBasicParsing -TimeoutSec 90
    $genMs = [int]((Get-Date)-$t0).TotalMilliseconds
    $genData = $gr.Content | ConvertFrom-Json
    $aiText = $genData.candidates[0].content.parts[0].text
    $preview = $aiText.Substring(0, [Math]::Min(500, $aiText.Length))
    $out += "  OK: ${genMs}ms"
    $out += "  AI Output (first 500 chars):"
    $out += "  $preview"
} catch {
    $genMs = [int]((Get-Date)-$t0).TotalMilliseconds
    $out += "  FAILED: ${genMs}ms - $($_.Exception.Message)"
}
$out += ""

# --- Image Generation x3 ---
$imgPrompt1 = "Generate a healing-style cover image for a Xiaohongshu emotional account: soft pink warm tones, artistic feel, clean layout, premium quality, no text overlay, dreamy pastel aesthetic"
$imgPrompt2 = "Generate a cozy lifestyle photo: warm sunlight on a windowsill, a cup of coffee and an open book, healing atmosphere, soft warm color tones, photographic style"
$imgPrompt3 = "Generate a dreamy spring illustration: cherry blossom tree lined path, pink petals floating in the air, watercolor painting style, warm and healing mood, soft pastel colors"

$imgPrompts = @($imgPrompt1, $imgPrompt2, $imgPrompt3)
$imgLabels = @("Cover Image", "Content Image 1 (Coffee+Book)", "Content Image 2 (Cherry Blossom)")

$totalImgMs = 0
$successCount = 0
$totalImgBytes = 0

for ($i = 0; $i -lt 3; $i++) {
    $imgNum = $i + 1
    $stepNum = $imgNum + 2
    $out += "--- Step ${stepNum}: Image ${imgNum}/3 - $($imgLabels[$i]) ---"

    $imgJson = '{"model":"gemini-2.5-flash-image","action":"generateContent","feature":"image-gen","payload":{"contents":[{"parts":[{"text":"' + $imgPrompts[$i] + '"}]}],"generationConfig":{"responseModalities":["TEXT","IMAGE"]}}}'

    $t0 = Get-Date
    try {
        $ir = Invoke-WebRequest "$base/api/gemini-proxy" -Method POST -Body ([System.Text.Encoding]::UTF8.GetBytes($imgJson)) -ContentType "application/json; charset=utf-8" -Headers $headers -UseBasicParsing -TimeoutSec 180
        $imgMs = [int]((Get-Date)-$t0).TotalMilliseconds
        $hasImage = $ir.Content.IndexOf('inlineData') -ge 0
        $imgSize = $ir.Content.Length
        $totalImgMs += $imgMs
        $totalImgBytes += $imgSize

        if ($hasImage) {
            $successCount++
            $mimeType = ''
            if ($ir.Content -match '"mimeType"\s*:\s*"([^"]+)"') { $mimeType = $Matches[1] }
            $sizeMB = [Math]::Round($imgSize/1024/1024, 2)
            $out += "  OK: ${imgMs}ms, ${sizeMB}MB, mimeType=$mimeType"
        } else {
            $preview = $ir.Content.Substring(0, [Math]::Min(200, $ir.Content.Length))
            $out += "  WARNING: ${imgMs}ms, no image data. Preview: $preview"
        }
    } catch {
        $imgMs = [int]((Get-Date)-$t0).TotalMilliseconds
        $totalImgMs += $imgMs
        $out += "  FAILED: ${imgMs}ms - $($_.Exception.Message)"
    }
    $out += ""
}

# --- Summary ---
$out += "============================================"
$out += "  SUMMARY"
$out += "============================================"
$out += "  Backend:     Tunnel (xhs.xiaohsai.com)"
$out += "  Login:       OK (${loginMs}ms)"
$out += "  Content Gen: ${genMs}ms"
$out += "  Image Gen:   ${successCount}/3 successful"
$out += "  Image Total: ${totalImgMs}ms (avg $([int]($totalImgMs/3))ms)"
$totalMB = [Math]::Round($totalImgBytes/1024/1024, 2)
$out += "  Image Data:  ${totalMB} MB total"
$out += "============================================"

$result = $out -join "`n"
$result | Out-File "frontend_test_result.txt" -Encoding UTF8
Write-Host $result
Write-Host ""
Write-Host "Results saved to frontend_test_result.txt"
