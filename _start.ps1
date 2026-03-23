$content = Get-Content "D:\Users\Administrator\Desktop\ls\xhsqg\api_key.txt" -Raw
if ($content -match 'GEMINI_API_KEY=(.+)') {
    $env:GEMINI_API_KEY = $matches[1].Trim()
} else {
    $env:GEMINI_API_KEY = $content.Trim()
}
$env:PYTHONIOENCODING = "utf-8"
Write-Host "GEMINI_API_KEY length: $($env:GEMINI_API_KEY.Length)"
Set-Location "D:\Users\Administrator\Desktop\ls\xhsqg"
& "C:\Users\Administrator\AppData\Local\Programs\Python\Python313\python.exe" -u server.py
