#!/bin/bash
# 議事録自動生成の定期実行設定スクリプト
#
# 毎日午前6時（JST）に議事録生成スクリプトを自動実行するcronジョブを設定します。
# 実行時間を変更する場合は CRON_SCHEDULE 変数を編集してください。

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PYTHON_PATH="$(which python3)"
MAIN_SCRIPT="${SCRIPT_DIR}/main.py"
LOG_FILE="${SCRIPT_DIR}/cron_execution.log"

# cron スケジュール（デフォルト: 毎日午前6時）
# フォーマット: 分 時 日 月 曜日
CRON_SCHEDULE="0 6 * * *"

CRON_JOB="${CRON_SCHEDULE} cd ${SCRIPT_DIR} && ${PYTHON_PATH} ${MAIN_SCRIPT} >> ${LOG_FILE} 2>&1"

# 既存のcronジョブを確認
EXISTING=$(crontab -l 2>/dev/null | grep -F "${MAIN_SCRIPT}" || true)

if [ -n "${EXISTING}" ]; then
    echo "既存のcronジョブが見つかりました:"
    echo "  ${EXISTING}"
    echo ""
    read -p "上書きしますか？ (y/N): " CONFIRM
    if [ "${CONFIRM}" != "y" ] && [ "${CONFIRM}" != "Y" ]; then
        echo "キャンセルしました。"
        exit 0
    fi
    # 既存のジョブを削除
    crontab -l 2>/dev/null | grep -vF "${MAIN_SCRIPT}" | crontab -
fi

# cronジョブを追加
(crontab -l 2>/dev/null; echo "${CRON_JOB}") | crontab -

echo "cronジョブを設定しました:"
echo "  スケジュール: ${CRON_SCHEDULE} (毎日午前6時)"
echo "  実行コマンド: cd ${SCRIPT_DIR} && ${PYTHON_PATH} ${MAIN_SCRIPT}"
echo "  ログ出力先:   ${LOG_FILE}"
echo ""
echo "設定確認:"
crontab -l | grep -F "${MAIN_SCRIPT}"
