# Auto open URLs from txt files in current directory
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$currentDir = $PSScriptRoot
if (-not $currentDir) {
    $currentDir = (Get-Location).Path
}

$txtFiles = Get-ChildItem -Path $currentDir -Filter "*.txt" -File

if (-not $txtFiles -or $txtFiles.Count -eq 0) {
    Write-Host "【提示】在此資料夾中沒有找到任何 .txt 檔案！" -ForegroundColor Yellow
    Write-Host "請將包含網址的 .txt 檔案放入此資料夾中。"
    Write-Host ""
    Read-Host "請按 Enter 鍵關閉..."
    exit
}

$urlPattern = 'https?://[^\s"''<>]+'
$allUrls = [System.Collections.Generic.List[string]]::new()

foreach ($file in $txtFiles) {
    $fileContent = Get-Content -LiteralPath $file.FullName -Raw -Encoding UTF8 -ErrorAction SilentlyContinue
    if (-not $fileContent) {
        $fileContent = Get-Content -LiteralPath $file.FullName -Raw -Encoding Default -ErrorAction SilentlyContinue
    }
    if ($fileContent) {
        $matches = [regex]::Matches($fileContent, $urlPattern)
        foreach ($m in $matches) {
            $url = $m.Value.TrimEnd('.', ',', ';', ':', ')', ']', '}')
            if (-not [string]::IsNullOrWhiteSpace($url) -and -not $allUrls.Contains($url)) {
                $allUrls.Add($url)
            }
        }
    }
}

if ($allUrls.Count -eq 0) {
    Write-Host "【提示】已掃描 .txt 檔案，但未找到任何有效網址 (需包含 http:// 或 https://)。" -ForegroundColor Yellow
    Write-Host ""
    Read-Host "請按 Enter 鍵關閉..."
    exit
}

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host " 找到 $($allUrls.Count) 個網址：" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

foreach ($u in $allUrls) {
    Write-Host "  -> $u" -ForegroundColor Gray
}
Write-Host ""

if ($allUrls.Count -ge 10) {
    Write-Host "注意：網址數量較多 ($($allUrls.Count) 個)。" -ForegroundColor Yellow
    $confirm = Read-Host "確定要一次全部開啟嗎？(輸入 Y 繼續 / N 取消) [預設 Y]"
    if ($confirm -match '^[Nn]$') {
        Write-Host "已取消開啟。" -ForegroundColor Yellow
        Start-Sleep -Seconds 1
        exit
    }
}

Write-Host "正在使用預設瀏覽器開啟網頁..." -ForegroundColor Green
foreach ($u in $allUrls) {
    Start-Process $u
    Start-Sleep -Milliseconds 150
}

Write-Host "所有網頁已成功開啟！" -ForegroundColor Green
Write-Host ""
Read-Host "請按 Enter 鍵關閉視窗..."

