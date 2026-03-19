$body = '{"model":"gemini-2.5-flash","action":"generateContent","payload":{"contents":[{"parts":[{"text":"say hello in 3 words"}]}]}}'
$bytes = [System.Text.Encoding]::UTF8.GetBytes($body)

Write-Host "Testing Gemini API proxy..."
try {
    $req = [System.Net.HttpWebRequest]::Create("https://xhs.xiaohsai.com/api/gemini-proxy")
    $req.Method = "POST"
    $req.ContentType = "application/json"
    $req.Timeout = 60000
    $req.Proxy = [System.Net.GlobalProxySelection]::GetEmptyWebProxy()
    $stream = $req.GetRequestStream()
    $stream.Write($bytes, 0, $bytes.Length)
    $stream.Close()

    $resp = $req.GetResponse()
    $sr = New-Object System.IO.StreamReader($resp.GetResponseStream())
    $result = $sr.ReadToEnd()
    $sr.Close()
    $resp.Close()
    Write-Host "SUCCESS (HTTP $($resp.StatusCode)):"
    Write-Host $result.Substring(0, [Math]::Min(500, $result.Length))
} catch [System.Net.WebException] {
    $errResp = $_.Exception.Response
    if ($errResp) {
        $sr = New-Object System.IO.StreamReader($errResp.GetResponseStream())
        $errBody = $sr.ReadToEnd()
        $sr.Close()
        Write-Host "HTTP ERROR $([int]$errResp.StatusCode):"
        Write-Host $errBody.Substring(0, [Math]::Min(500, $errBody.Length))
    } else {
        Write-Host "NETWORK ERROR: $($_.Exception.Message)"
    }
} catch {
    Write-Host "UNEXPECTED ERROR: $_"
}
