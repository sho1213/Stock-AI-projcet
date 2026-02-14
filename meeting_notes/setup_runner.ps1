# ============================================================
# GPU付きセルフホストランナー セットアップスクリプト (Windows)
#
# PowerShell を「管理者として実行」してください。
#
# 使い方:
#   powershell -ExecutionPolicy Bypass -File setup_runner.ps1
# ============================================================

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  セルフホストランナー セットアップ"       -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# ── 1. GPU ドライバ確認 ──────────────────────────────────

Write-Host "[1/5] GPU ドライバを確認中..." -ForegroundColor Green
try {
    $smi = & nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader 2>&1
    Write-Host "  GPU: $smi" -ForegroundColor White
} catch {
    Write-Host "[ERROR] nvidia-smi が見つかりません。" -ForegroundColor Red
    Write-Host "  NVIDIAドライバをインストールしてください。" -ForegroundColor Yellow
    Write-Host "  https://www.nvidia.com/drivers" -ForegroundColor Yellow
    exit 1
}

# ── 2. Python 確認 ───────────────────────────────────────

Write-Host "[2/5] Python を確認中..." -ForegroundColor Green
try {
    $pyVer = & python --version 2>&1
    Write-Host "  $pyVer" -ForegroundColor White
} catch {
    Write-Host "[ERROR] Python が見つかりません。" -ForegroundColor Red
    Write-Host "  https://www.python.org/downloads/ からインストールしてください。" -ForegroundColor Yellow
    Write-Host "  インストール時に 'Add Python to PATH' にチェックを入れてください。" -ForegroundColor Yellow
    exit 1
}

# ── 3. ffmpeg 確認 ───────────────────────────────────────

Write-Host "[3/5] ffmpeg を確認中..." -ForegroundColor Green
$ffmpegPath = Get-Command ffmpeg -ErrorAction SilentlyContinue
if ($ffmpegPath) {
    Write-Host "  ffmpeg: OK" -ForegroundColor White
} else {
    Write-Host "  [WARN] ffmpeg が見つかりません。" -ForegroundColor Yellow
    Write-Host "  動画のMP3変換ができないため、処理が遅くなります。" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "  インストール方法:" -ForegroundColor Yellow
    Write-Host "    winget install Gyan.FFmpeg" -ForegroundColor White
    Write-Host "  または https://ffmpeg.org/download.html からダウンロード" -ForegroundColor Yellow
    Write-Host ""
}

# ── 4. Python パッケージ ─────────────────────────────────

Write-Host "[4/5] Python パッケージをインストール中..." -ForegroundColor Green

python -m pip install --upgrade pip
python -m pip install faster-whisper
python -m pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib python-dotenv

# CUDA ライブラリ
Write-Host "  CUDA ライブラリをインストール中..." -ForegroundColor White
python -m pip install nvidia-cublas-cu12 nvidia-cudnn-cu12 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "  [WARN] nvidia-cublas/cudnn の pip インストールに失敗。" -ForegroundColor Yellow
    Write-Host "  システム CUDA が使用されます。" -ForegroundColor Yellow
}

Write-Host "  パッケージ: OK" -ForegroundColor White

# ── 5. GPU 動作テスト ────────────────────────────────────

Write-Host "[5/5] Whisper の GPU 動作を確認中..." -ForegroundColor Green
python -c @"
try:
    import torch
    print(f'  CUDA available: {torch.cuda.is_available()}')
    if torch.cuda.is_available():
        print(f'  GPU: {torch.cuda.get_device_name(0)}')
        vram = torch.cuda.get_device_properties(0).total_mem / 1024**3
        print(f'  VRAM: {vram:.1f} GB')
except ImportError:
    print('  (torch not installed - skipping GPU check)')
print('  faster-whisper import: ', end='')
from faster_whisper import WhisperModel
print('OK')
"@

# ── 完了 ─────────────────────────────────────────────────

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  環境構築完了!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "次のステップ: GitHub Actions Runner を登録してください。" -ForegroundColor Yellow
Write-Host ""
Write-Host "  1. https://github.com/<owner>/<repo>/settings/actions/runners/new" -ForegroundColor White
Write-Host "     でランナーの追加画面を開く" -ForegroundColor White
Write-Host ""
Write-Host "  2. OS に 'Windows' を選び、表示されるコマンドを実行" -ForegroundColor White
Write-Host ""
Write-Host "  3. configure 時にラベルを聞かれたら 'gpu' を追加" -ForegroundColor White
Write-Host ""
Write-Host "  4. 'Run as service' でサービスとして登録" -ForegroundColor White
Write-Host ""
