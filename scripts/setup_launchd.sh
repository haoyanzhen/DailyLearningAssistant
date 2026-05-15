#!/bin/bash
# 为每日邮件推送配置 macOS launchd 定时任务。
#
# 用法:
#   bash scripts/setup_launchd.sh          # 安装定时任务
#   bash scripts/setup_launchd.sh --uninstall  # 卸载定时任务
#   bash scripts/setup_launchd.sh --status     # 查看任务状态
#
# launchd 会在配置的时间点触发脚本，日志写入 /tmp/daily-learning-email.log

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CONFIG_FILE="$PROJECT_ROOT/config.json"
PLIST_NAME="com.daily-learning.email"
PLIST_PATH="$HOME/Library/LaunchAgents/$PLIST_NAME.plist"
SCRIPT_PATH="$PROJECT_ROOT/scripts/send_daily_email.py"
PYTHON_BIN="/usr/bin/python3"

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

install_plist() {
    check_config

    # 从 config.json 解析运行时间
    RUN_TIME=$(python3 -c "
import json
with open('$CONFIG_FILE') as f:
    c = json.load(f)
print(c['schedule']['daily_run_time'])
")
    HOUR=$(echo "$RUN_TIME" | cut -d: -f1 | sed 's/^0*//')
    MINUTE=$(echo "$RUN_TIME" | cut -d: -f2 | sed 's/^0*//')
    HOUR=${HOUR:-0}
    MINUTE=${MINUTE:-0}

    echo -e "${GREEN}配置信息:${NC}"
    echo "  项目路径: $PROJECT_ROOT"
    echo "  脚本路径: $SCRIPT_PATH"
    echo "  运行时间: $RUN_TIME (H=$HOUR, M=$MINUTE)"

    # 生成 plist
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
        <string>$PYTHON_BIN</string>
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
    <string>/tmp/daily-learning-email.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/daily-learning-email.err</string>
    <key>RunAtLoad</key>
    <false/>
</dict>
</plist>
PLIST_EOF

    echo "  plist 路径: $PLIST_PATH"

    # 卸载旧任务（如果存在）
    launchctl bootout "gui/$(id -u)/$PLIST_NAME" 2>/dev/null || true

    # 加载新任务
    launchctl bootstrap "gui/$(id -u)" "$PLIST_PATH"

    echo -e "${GREEN}[完成] 定时任务已安装，每日 $RUN_TIME 自动发送学习邮件。${NC}"
    echo ""
    echo "提示:"
    echo "  查看状态: bash scripts/setup_launchd.sh --status"
    echo "  手动测试: python3 $SCRIPT_PATH --dry-run"
    echo "  查看日志: tail -f /tmp/daily-learning-email.log"
    echo "  卸载任务: bash scripts/setup_launchd.sh --uninstall"
}

uninstall_plist() {
    if [ -f "$PLIST_PATH" ]; then
        launchctl bootout "gui/$(id -u)/$PLIST_NAME" 2>/dev/null || true
        rm -f "$PLIST_PATH"
        echo -e "${GREEN}[完成] 定时任务已卸载。${NC}"
    else
        echo -e "${YELLOW}[跳过] 未找到已安装的定时任务。${NC}"
    fi
}

show_status() {
    echo "=== launchd 任务状态 ==="
    if [ -f "$PLIST_PATH" ]; then
        echo "plist 文件: 存在 ($PLIST_PATH)"
    else
        echo "plist 文件: 不存在"
    fi

    if launchctl list | grep -q "$PLIST_NAME"; then
        echo "运行状态: 已加载"
        echo ""
        echo "最近日志:"
        tail -20 /tmp/daily-learning-email.log 2>/dev/null || echo "  (暂无日志)"
    else
        echo "运行状态: 未加载"
    fi
}

case "${1:-}" in
    --uninstall) uninstall_plist ;;
    --status) show_status ;;
    *) install_plist ;;
esac
