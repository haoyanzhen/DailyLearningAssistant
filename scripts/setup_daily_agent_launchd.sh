#!/bin/bash
# Prepare macOS launchd jobs for the local agent pipeline.
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
PIPELINE_PLIST_NAME="com.daily-learning.agent-pipeline"
EMAIL_PLIST_NAME="com.daily-learning.agent-email"
PIPELINE_PLIST_PATH="$HOME/Library/LaunchAgents/$PIPELINE_PLIST_NAME.plist"
EMAIL_PLIST_PATH="$HOME/Library/LaunchAgents/$EMAIL_PLIST_NAME.plist"
PIPELINE_RUNNER_PATH="$PROJECT_ROOT/scripts/run_daily_pipeline.sh"
EMAIL_RUNNER_PATH="$PROJECT_ROOT/scripts/run_daily_email.sh"
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
    local key fallback
    key="$1"
    fallback="$2"
    "$PYTHON_BIN" - "$CONFIG_FILE" "$key" "$fallback" <<'PY'
import json
import re
import sys

config_path = sys.argv[1]
key = sys.argv[2]
fallback = sys.argv[3]
with open(config_path, "r", encoding="utf-8") as f:
    config = json.load(f)
schedule = config.get("schedule") or {}
run_time = schedule.get(key) or schedule.get(fallback) or "22:00"
if not re.fullmatch(r"\d{2}:\d{2}", run_time):
    raise SystemExit(f"invalid schedule.{key}: {run_time}")
hour, minute = map(int, run_time.split(":"))
if not (0 <= hour <= 23 and 0 <= minute <= 59):
    raise SystemExit(f"invalid schedule.{key}: {run_time}")
print(f"{hour}:{minute}")
PY
}

render_plist() {
    local plist_name runner_path log_name time_key fallback_key time_value hour minute
    plist_name="$1"
    runner_path="$2"
    log_name="$3"
    time_key="$4"
    fallback_key="$5"
    time_value="$(schedule_time "$time_key" "$fallback_key")"
    hour="${time_value%%:*}"
    minute="${time_value##*:}"
    cat <<PLIST_EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>$plist_name</string>
    <key>ProgramArguments</key>
    <array>
        <string>$runner_path</string>
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
    <string>/tmp/$log_name.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/$log_name.err</string>
    <key>RunAtLoad</key>
    <false/>
</dict>
</plist>
PLIST_EOF
}

write_plist() {
    check_config
    mkdir -p "$(dirname "$PIPELINE_PLIST_PATH")"
    render_plist "$PIPELINE_PLIST_NAME" "$PIPELINE_RUNNER_PATH" "daily-learning-agent-pipeline" "html_run_time" "daily_run_time" > "$PIPELINE_PLIST_PATH"
    render_plist "$EMAIL_PLIST_NAME" "$EMAIL_RUNNER_PATH" "daily-learning-agent-email" "email_send_time" "daily_run_time" > "$EMAIL_PLIST_PATH"
    chmod 644 "$PIPELINE_PLIST_PATH" "$EMAIL_PLIST_PATH"
    echo -e "${GREEN}[完成] 已写入 plist，但未加载任务:${NC}"
    echo "  $PIPELINE_PLIST_PATH"
    echo "  $EMAIL_PLIST_PATH"
}

install_plist() {
    write_plist
    launchctl bootout "gui/$(id -u)/$PIPELINE_PLIST_NAME" 2>/dev/null || true
    launchctl bootout "gui/$(id -u)/$EMAIL_PLIST_NAME" 2>/dev/null || true
    launchctl bootstrap "gui/$(id -u)" "$PIPELINE_PLIST_PATH"
    launchctl bootstrap "gui/$(id -u)" "$EMAIL_PLIST_PATH"
    echo -e "${GREEN}[完成] 已安装 HTML 生成发布任务和邮件发送任务。${NC}"
}

uninstall_plist() {
    launchctl bootout "gui/$(id -u)/$PIPELINE_PLIST_NAME" 2>/dev/null || true
    launchctl bootout "gui/$(id -u)/$EMAIL_PLIST_NAME" 2>/dev/null || true
    rm -f "$PIPELINE_PLIST_PATH" "$EMAIL_PLIST_PATH"
    echo -e "${GREEN}[完成] 已卸载 HTML 生成发布任务和邮件发送任务。${NC}"
}

show_status() {
    echo "=== launchd DailyLearningAssistant 任务状态 ==="
    for item in "$PIPELINE_PLIST_NAME|$PIPELINE_PLIST_PATH" "$EMAIL_PLIST_NAME|$EMAIL_PLIST_PATH"; do
        local name path
        name="${item%%|*}"
        path="${item##*|}"
        echo "--- $name ---"
        echo "plist: $path"
        if [ -f "$path" ]; then
            echo "plist 文件: 存在"
            /usr/libexec/PlistBuddy -c 'Print :ProgramArguments' -c 'Print :StartCalendarInterval' "$path" 2>/dev/null || true
        else
            echo "plist 文件: 不存在"
        fi
        if launchctl print "gui/$(id -u)/$name" >/dev/null 2>&1; then
            echo "运行状态: 已加载"
        else
            echo "运行状态: 未加载"
        fi
    done
}

case "${1:---print}" in
    --print)
        check_config
        echo "# $PIPELINE_PLIST_PATH"
        render_plist "$PIPELINE_PLIST_NAME" "$PIPELINE_RUNNER_PATH" "daily-learning-agent-pipeline" "html_run_time" "daily_run_time"
        echo
        echo "# $EMAIL_PLIST_PATH"
        render_plist "$EMAIL_PLIST_NAME" "$EMAIL_RUNNER_PATH" "daily-learning-agent-email" "email_send_time" "daily_run_time"
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
