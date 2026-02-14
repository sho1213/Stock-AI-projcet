#!/bin/bash
# ============================================================
# GPU付きセルフホストランナー セットアップスクリプト
#
# GPUマシン上でこのスクリプトを実行して、GitHub Actions
# セルフホストランナーの環境を構築します。
#
# 前提条件:
#   - Ubuntu 22.04+ (推奨)
#   - NVIDIA GPUドライバがインストール済み
#   - nvidia-smi が動作すること
#
# 使い方:
#   chmod +x setup_runner.sh
#   ./setup_runner.sh
# ============================================================

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

info()  { echo -e "${GREEN}[INFO]${NC} $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*" >&2; }

# ── 1. GPU ドライバ確認 ──────────────────────────────────

echo ""
echo "========================================"
echo "  セルフホストランナー セットアップ"
echo "========================================"
echo ""

info "GPU ドライバを確認中..."
if ! command -v nvidia-smi &>/dev/null; then
    error "nvidia-smi が見つかりません。"
    echo "  NVIDIAドライバをインストールしてください:"
    echo "    sudo apt install -y nvidia-driver-535"
    echo "  インストール後、再起動してからこのスクリプトを再実行してください。"
    exit 1
fi

echo ""
nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader
echo ""
info "GPU ドライバ: OK"

# ── 2. システム依存パッケージ ─────────────────────────────

info "システムパッケージをインストール中..."
sudo apt-get update -qq
sudo apt-get install -y -qq python3 python3-pip python3-venv ffmpeg curl

info "ffmpeg: $(ffmpeg -version 2>&1 | head -1)"
info "Python: $(python3 --version)"

# ── 3. CUDA ツールキット (faster-whisper 用) ─────────────

info "CUDA ランタイムを確認中..."
if ! dpkg -l 2>/dev/null | grep -q cuda-toolkit; then
    warn "CUDA ツールキットが見つかりません。"
    echo ""
    echo "  faster-whisper は cuBLAS / cuDNN を必要とします。"
    echo "  以下のいずれかでインストールしてください:"
    echo ""
    echo "  方法1) pip 経由 (推奨・簡単):"
    echo "    pip install nvidia-cublas-cu12 nvidia-cudnn-cu12"
    echo ""
    echo "  方法2) apt 経由:"
    echo "    sudo apt install -y nvidia-cuda-toolkit"
    echo ""
    echo "  ※ pip 経由なら Python venv 内で自動的に利用されます。"
    echo ""
fi

# ── 4. Python 仮想環境 ───────────────────────────────────

VENV_DIR="$HOME/meeting-notes-venv"
info "Python 仮想環境を作成中: ${VENV_DIR}"
python3 -m venv "${VENV_DIR}" --system-site-packages 2>/dev/null || \
    python3 -m venv "${VENV_DIR}"

source "${VENV_DIR}/bin/activate"

pip install --upgrade pip -q
pip install faster-whisper -q
pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib python-dotenv -q

# CUDA ライブラリ (pip 経由)
pip install nvidia-cublas-cu12 nvidia-cudnn-cu12 -q 2>/dev/null || \
    warn "nvidia-cublas/cudnn の pip インストールに失敗。システム CUDA を使用します。"

info "Python パッケージ: OK"

# ── 5. Whisper GPU 動作確認 ──────────────────────────────

info "Whisper の GPU 動作を確認中..."
python3 -c "
from faster_whisper import WhisperModel
import torch
print(f'  CUDA available: {torch.cuda.is_available()}')
if torch.cuda.is_available():
    print(f'  GPU: {torch.cuda.get_device_name(0)}')
    print(f'  VRAM: {torch.cuda.get_device_properties(0).total_mem / 1024**3:.1f} GB')
print('  Whisper import: OK')
" 2>/dev/null || warn "GPU 確認をスキップ (実行時に確認されます)"

# ── 6. GitHub Actions Runner のセットアップ案内 ──────────

echo ""
echo "========================================"
echo "  GitHub Actions Runner セットアップ"
echo "========================================"
echo ""
echo "以下の手順でランナーを登録してください:"
echo ""
echo "1. GitHubリポジトリの Settings > Actions > Runners > New self-hosted runner"
echo ""
echo "2. 表示されるコマンドを実行してランナーをダウンロード・設定:"
echo "   mkdir -p ~/actions-runner && cd ~/actions-runner"
echo "   curl -o actions-runner-linux-x64.tar.gz -L <表示されるURL>"
echo "   tar xzf actions-runner-linux-x64.tar.gz"
echo ""
echo "3. ランナーを設定 (ラベルに 'gpu' を追加):"
echo "   ./config.sh --url https://github.com/<owner>/<repo> --token <TOKEN> --labels gpu"
echo ""
echo "4. サービスとして登録 (再起動後も自動起動):"
echo "   sudo ./svc.sh install"
echo "   sudo ./svc.sh start"
echo ""
echo "========================================"
echo ""
info "セットアップ完了!"
echo ""
echo "  次のステップ:"
echo "    1. 上記の手順で GitHub Actions Runner を登録"
echo "    2. リポジトリの Settings > Secrets に Google 認証情報を設定"
echo "    3. Actions タブから手動実行 (dry-run) でテスト"
echo ""
