#!/bin/bash
# Chrome をリモートデバッグポート付きで起動するスクリプト
# x_opinion エージェントが chrome-devtools-mcp 経由でブラウザを操作するために必要

PORT=9222

# 既にデバッグポートが開いているか確認
if curl -s "http://127.0.0.1:${PORT}/json/version" > /dev/null 2>&1; then
    echo "✓ Chrome リモートデバッグは既にポート ${PORT} で起動中です"
    curl -s "http://127.0.0.1:${PORT}/json/version" | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'  Browser: {d.get(\"Browser\",\"?\")}')"
    exit 0
fi

DATA_DIR="${HOME}/.config/chrome-debug-profile"

echo "Chrome をリモートデバッグモードで起動します (port=${PORT})..."
echo "  data-dir: ${DATA_DIR}"
echo ""

google-chrome --remote-debugging-port=${PORT} --user-data-dir="${DATA_DIR}" &
CHROME_PID=$!

# 起動確認
for i in $(seq 1 10); do
    sleep 1
    if curl -s "http://127.0.0.1:${PORT}/json/version" > /dev/null 2>&1; then
        echo "✓ Chrome リモートデバッグ起動完了 (PID=${CHROME_PID}, port=${PORT})"
        exit 0
    fi
done

echo "✗ Chrome の起動に失敗しました"
exit 1
