#!/bin/bash
# Configure a macOS launchd job that pushes local commits before the daily email.
#
# Usage:
#   bash scripts/setup_git_push_launchd.sh              # install task
#   bash scripts/setup_git_push_launchd.sh --uninstall  # remove task
#   bash scripts/setup_git_push_launchd.sh --status     # show status
#
# The scheduled time is derived from config.json:
#   schedule.daily_run_time - 30 minutes

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CONFIG_FILE="$PROJECT_ROOT/config.json"
PLIST_NAME="com.daily-learning.git-push"
PLIST_PATH="$HOME/Library/LaunchAgents/$PLIST_NAME.plist"
SCRIPT_PATH="$PROJECT_ROOT/scripts/auto_git_push.sh"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

check_config() {
    if [ ! -f "$CONFIG_FILE" ]; then
        echo -e "${RED}[错误] 配置文件不存在: $CONFIG_FILE${NC}"
        echo "请先复制并填写配置文件: cp config.example.json config.json"
        exit 1
    fi
}

derive_push_time() {
    python3 - "$CONFIG_FILE" <<'PY'
import json
import sys
from datetime import datetime, timedelta

config_path = sys.argv[1]
with open(config_path, "r", encoding="utf-8") as f:
    config = json.load(f)

run_time = config.get("schedule", {}).get("daily_run_time")
if not run_time:
    raise SystemExit("missing schedule.daily_run_time")

email_dt = datetime.strptime(run_time, "%H:%M")
push_dt = email_dt - timedelta(minutes=30)
print(push_dt.strftime("%H:%M"))
PY
}

install_plist() {
    check_config

    PUSH_TIME="$(derive_push_time)"
    HOUR="$(echo "$PUSH_TIME" | cut -d: -f1 | sed 's/^0*//')"
    MINUTE="$(echo "$PUSH_TIME" | cut -d: -f2 | sed 's/^0*//')"
    HOUR=${HOUR:-0}
    MINUTE=${MINUTE:-0}

    echo -e "${GREEN}配置信息:${NC}"
    echo "  项目路径: $PROJECT_ROOT"
    echo "  脚本路径: $SCRIPT_PATH"
    echo "  自动 git push 时间: $PUSH_TIME (H=$HOUR, M=$MINUTE)"
    echo "  规则: 比邮件推送时间提前 30 分钟"

    cat > "$PLIST_PATH" << PLIST_EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>$PLIST_NAME</string>
    <key>ProgramArguments</key>
    <array>
        <string>$SCRIPT_PATH</string>
    </array>
    <key>WorkingDirectory</key>
    <string>$PROJECT_ROOT</string>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>$HOUR</integer>
        <key>Minute</key>
        <integer>$MINUTE</integer>
    </dict>
    <key>StandardOutPath</key>
    <string>/tmp/daily-learning-git-push.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/daily-learning-git-push.err</string>
    <key>RunAtLoad</key>
    <false/>
</dict>
</plist>
PLIST_EOF

    launchctl bootout "gui/$(id -u)/$PLIST_NAME" 2>/dev/null || true
    launchctl bootstrap "gui/$(id -u)" "$PLIST_PATH"

    echo -e "${GREEN}[完成] 自动 git push 任务已安装，每日 $PUSH_TIME 执行。${NC}"
    echo ""
    echo "提示:"
    echo "  手动运行: $SCRIPT_PATH"
    echo "  查看状态: bash scripts/setup_git_push_launchd.sh --status"
    echo "  查看日志: tail -f /tmp/daily-learning-git-push.log"
    echo "  卸载任务: bash scripts/setup_git_push_launchd.sh --uninstall"
}

uninstall_plist() {
    if [ -f "$PLIST_PATH" ]; then
        launchctl bootout "gui/$(id -u)/$PLIST_NAME" 2>/dev/null || true
        rm -f "$PLIST_PATH"
        echo -e "${GREEN}[完成] 自动 git push 任务已卸载。${NC}"
    else
        echo -e "${YELLOW}[跳过] 未找到已安装的自动 git push 任务。${NC}"
    fi
}

show_status() {
    echo "=== launchd 自动 git push 任务状态 ==="
    if [ -f "$PLIST_PATH" ]; then
        echo "plist 文件: 存在 ($PLIST_PATH)"
        /usr/libexec/PlistBuddy -c 'Print :StartCalendarInterval' "$PLIST_PATH" 2>/dev/null || true
    else
        echo "plist 文件: 不存在"
    fi

    if launchctl list | grep -q "$PLIST_NAME"; then
        echo "运行状态: 已加载"
        echo ""
        echo "最近日志:"
        tail -20 /tmp/daily-learning-git-push.log 2>/dev/null || echo "  (暂无日志)"
    else
        echo "运行状态: 未加载"
    fi
}

case "${1:-}" in
    --uninstall) uninstall_plist ;;
    --status) show_status ;;
    *) install_plist ;;
esac
