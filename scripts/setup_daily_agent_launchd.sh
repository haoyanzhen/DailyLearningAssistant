#!/bin/bash
# Prepare a macOS launchd job for the full local agent pipeline.
#
# This script is deliberately non-invasive by default:
#   bash scripts/setup_daily_agent_launchd.sh --print    # preview plist
#   bash scripts/setup_daily_agent_launchd.sh --write    # write plist only
#   bash scripts/setup_daily_agent_launchd.sh --install  # write and load plist
#   bash scripts/setup_daily_agent_launchd.sh --status   # inspect current job
#   bash scripts/setup_daily_agent_launchd.sh --uninstall

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CONFIG_FILE="${DLA_CONFIG_FILE:-$PROJECT_ROOT/config.json}"
PLIST_NAME="com.daily-learning.agent-pipeline"
PLIST_PATH="$HOME/Library/LaunchAgents/$PLIST_NAME.plist"
RUNNER_PATH="$PROJECT_ROOT/scripts/run_daily_pipeline.sh"
PYTHON_BIN="${DLA_PYTHON_BIN:-$(command -v python3)}"

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
    "$PYTHON_BIN" "$PROJECT_ROOT/scripts/check_config.py" --config "$CONFIG_FILE" --strict >/dev/null
}

schedule_time() {
    "$PYTHON_BIN" - "$CONFIG_FILE" <<'PY'
import json
import re
import sys

config_path = sys.argv[1]
with open(config_path, "r", encoding="utf-8") as f:
    config = json.load(f)
run_time = (config.get("schedule") or {}).get("daily_run_time") or "22:00"
if not re.fullmatch(r"\d{2}:\d{2}", run_time):
    raise SystemExit(f"invalid schedule.daily_run_time: {run_time}")
hour, minute = map(int, run_time.split(":"))
if not (0 <= hour <= 23 and 0 <= minute <= 59):
    raise SystemExit(f"invalid schedule.daily_run_time: {run_time}")
print(f"{hour}:{minute}")
PY
}

render_plist() {
    local time_value hour minute
    time_value="$(schedule_time)"
    hour="${time_value%%:*}"
    minute="${time_value##*:}"
    cat <<PLIST_EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>$PLIST_NAME</string>
    <key>ProgramArguments</key>
    <array>
        <string>$RUNNER_PATH</string>
    </array>
    <key>WorkingDirectory</key>
    <string>$PROJECT_ROOT</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>DLA_CONFIG_FILE</key>
        <string>$CONFIG_FILE</string>
        <key>DLA_PYTHON_BIN</key>
        <string>$PYTHON_BIN</string>
    </dict>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>$hour</integer>
        <key>Minute</key>
        <integer>$minute</integer>
    </dict>
    <key>StandardOutPath</key>
    <string>/tmp/daily-learning-agent-pipeline.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/daily-learning-agent-pipeline.err</string>
    <key>RunAtLoad</key>
    <false/>
</dict>
</plist>
PLIST_EOF
}

write_plist() {
    check_config
    mkdir -p "$(dirname "$PLIST_PATH")"
    render_plist > "$PLIST_PATH"
    chmod 644 "$PLIST_PATH"
    echo -e "${GREEN}[完成] 已写入 plist，但未加载任务: $PLIST_PATH${NC}"
}

install_plist() {
    write_plist
    launchctl bootout "gui/$(id -u)/$PLIST_NAME" 2>/dev/null || true
    launchctl bootstrap "gui/$(id -u)" "$PLIST_PATH"
    echo -e "${GREEN}[完成] 已安装完整本地 Agent 流水线任务。${NC}"
}

uninstall_plist() {
    launchctl bootout "gui/$(id -u)/$PLIST_NAME" 2>/dev/null || true
    rm -f "$PLIST_PATH"
    echo -e "${GREEN}[完成] 已卸载完整本地 Agent 流水线任务。${NC}"
}

show_status() {
    echo "=== launchd 完整 Agent 流水线任务状态 ==="
    echo "plist: $PLIST_PATH"
    if [ -f "$PLIST_PATH" ]; then
        echo "plist 文件: 存在"
        /usr/libexec/PlistBuddy -c 'Print :StartCalendarInterval' "$PLIST_PATH" 2>/dev/null || true
    else
        echo "plist 文件: 不存在"
    fi
    if launchctl list | grep -q "$PLIST_NAME"; then
        echo "运行状态: 已加载"
    else
        echo "运行状态: 未加载"
    fi
}

case "${1:---print}" in
    --print)
        check_config
        render_plist
        ;;
    --write) write_plist ;;
    --install) install_plist ;;
    --uninstall) uninstall_plist ;;
    --status) show_status ;;
    *)
        echo "用法: bash scripts/setup_daily_agent_launchd.sh [--print|--write|--install|--status|--uninstall]"
        exit 2
        ;;
esac
