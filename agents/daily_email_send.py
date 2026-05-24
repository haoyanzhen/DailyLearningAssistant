#!/usr/bin/env python3
"""Run the fifth local agent: generate and send the daily email."""

from __future__ import annotations

import argparse
import importlib.util
import imaplib
import json
import os
import smtplib
import sys
from datetime import datetime, timedelta
from email.header import decode_header
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
from orchestrator.llm import RetryPolicy, retry_call, retry_optional, wait_until
from orchestrator.manifest import load_daily_manifest, select_report
EMAIL_SCRIPT = PROJECT_ROOT / "scripts" / "send_daily_email.py"


def load_email_module():
    spec = importlib.util.spec_from_file_location("send_daily_email", EMAIL_SCRIPT)
    if not spec or not spec.loader:
        raise SystemExit(f"[错误] 无法加载邮件脚本: {EMAIL_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate and send daily learning report email.")
    parser.add_argument("--date", help="Target date in YYYY-MM-DD format. Defaults to today in configured timezone.")
    parser.add_argument("--config", default=str(PROJECT_ROOT / "config.json"), help="Config JSON path.")
    parser.add_argument("--input-root", default=str(PROJECT_ROOT), help="Root to read daily_report/manifest.json from.")
    parser.add_argument("--output-root", default=str(PROJECT_ROOT), help="Root to write email preview and status to.")
    parser.add_argument("--timezone", help="Timezone override, e.g. Asia/Shanghai.")
    parser.add_argument("--dry-run", action="store_true", help="Generate email content and status without sending.")
    parser.add_argument("--no-llm", action="store_true", help="Skip LLM copy generation and use static fallback text.")
    parser.add_argument("--timeout", type=int, default=180, help="Reserved for orchestrator compatibility.")
    parser.add_argument("--verify-inbox", action="store_true", help="After sending, verify the message via IMAP.")
    parser.add_argument("--verify-timeout", type=int, default=90, help="Seconds to wait for IMAP delivery verification.")
    parser.add_argument("--verify-interval", type=float, default=10.0, help="Seconds between IMAP verification attempts.")
    parser.add_argument(
        "--allow-latest-fallback",
        action="store_true",
        help="If exact date has no report, send the latest report not later than target date.",
    )
    parser.add_argument("--llm-retries", type=int, default=2, help="Maximum LLM content generation attempts.")
    parser.add_argument("--llm-retry-delay", type=float, default=2.0, help="Initial LLM retry delay in seconds.")
    parser.add_argument("--test-email", action="store_true", help="Prefix the subject with 'test: ' for email delivery tests.")
    parser.add_argument("--failure-notice", action="store_true", help="Send a notice that today's report was not generated.")
    parser.add_argument("--failure-reason", default="", help="Short failure reason for failure notice emails.")
    return parser.parse_args()


def load_config(path: Path) -> dict:
    if not path.exists():
        raise SystemExit(f"[错误] 配置文件不存在: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"[错误] 配置文件不是合法 JSON: {path} ({exc})")


def resolve_timezone(args: argparse.Namespace, config: dict) -> ZoneInfo:
    timezone_name = args.timezone or (config.get("schedule") or {}).get("timezone") or "Asia/Shanghai"
    try:
        return ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        raise SystemExit(f"[错误] 未识别的时区: {timezone_name}")


def resolve_target_date(args: argparse.Namespace, timezone: ZoneInfo) -> str:
    if args.date:
        try:
            datetime.strptime(args.date, "%Y-%m-%d")
        except ValueError:
            raise SystemExit("[错误] --date 必须使用 YYYY-MM-DD 格式。")
        return args.date
    return datetime.now(timezone).date().isoformat()


def relative_to_root(path: Path, root: Path = PROJECT_ROOT) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except ValueError:
        return str(path)


def load_status_file(path: Path, target_date: str) -> dict:
    if not path.exists():
        return {"date": target_date, "agents": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"date": target_date, "agents": {}}
    if not isinstance(data, dict):
        return {"date": target_date, "agents": {}}
    data.setdefault("date", target_date)
    data.setdefault("agents", {})
    if not isinstance(data["agents"], dict):
        data["agents"] = {}
    return data


def write_agent_status(status_path: Path, target_date: str, agent_status: dict, now_iso: str) -> None:
    status_data = load_status_file(status_path, target_date)
    status_data["date"] = target_date
    status_data["updated_at"] = now_iso
    status_data.setdefault("agents", {})
    status_data["agents"]["daily_email_send"] = agent_status

    status_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = status_path.with_suffix(".json.tmp")
    temp_path.write_text(json.dumps(status_data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp_path.replace(status_path)


def validate_report_file(input_root: Path, report: dict) -> Path:
    report_path = str(report.get("path") or "")
    if not report_path:
        raise ValueError("日报 manifest 条目缺少 path")
    local_path = input_root / report_path.lstrip("./")
    if not local_path.exists():
        raise FileNotFoundError(f"日报文件不存在: {local_path}")
    if not local_path.read_text(encoding="utf-8").strip():
        raise ValueError(f"日报文件为空: {local_path}")
    return local_path


def generate_llm_content(
    email_module,
    report: dict,
    config: dict,
    target_date: str,
    recipient_name: str,
    retries: int,
    retry_delay: float,
) -> tuple[dict | None, str | None]:
    return retry_optional(
        lambda: email_module.generate_email_content(report, config, target_date, recipient_name),
        RetryPolicy(attempts=retries, initial_delay=retry_delay, label="邮件文案 LLM 生成"),
    )


def write_email_previews(output_dir: Path, html: str, plain: str) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    html_path = output_dir / "email_preview.html"
    plain_path = output_dir / "email_preview.txt"
    html_path.write_text(html.rstrip() + "\n", encoding="utf-8")
    plain_path.write_text(plain.rstrip() + "\n", encoding="utf-8")
    return html_path, plain_path


def build_failure_email_html(report: dict | None, config: dict, target_date: str, failure_reason: str, recipient_name: str) -> str:
    site_base = config["site"]["base_url"].rstrip("/")
    sender_name = config["email"]["sender_name"]
    if report:
        report_url = f"{site_base}/{report['path'].lstrip('./')}"
        report_date = report.get("date", "上一有效日期")
        report_title = report.get("title", f"{report_date} 学习日报")
        link_block = f"""
        <div style="background:#f0f7ff; border-radius:12px; padding:20px; margin:18px 0;">
          <p style="margin:0 0 10px; color:#4b5563; font-size:15px; line-height:1.7;">今天先附上上一份可用日报：</p>
          <a href="{report_url}" style="color:#2563eb; font-weight:700; text-decoration:none;">{report_title}</a>
        </div>
        """
    else:
        link_block = """
        <div style="background:#fefce8; border-radius:12px; padding:20px; margin:18px 0;">
          <p style="margin:0; color:#92400e; font-size:15px; line-height:1.7;">暂时没有找到上一份可用日报链接。</p>
        </div>
        """
    reason = failure_reason or "流水线在生成或发布今日学习日报时遇到异常。"
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="utf-8"></head>
<body style="margin:0; padding:0; background:#f3f4f6; font-family:-apple-system, 'PingFang SC', 'Microsoft YaHei', sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="max-width:600px; margin:0 auto;">
  <tr><td style="padding:32px 24px 0;"><h1 style="color:#1f2937; font-size:22px; margin:0;">{sender_name}</h1><p style="color:#6b7280; font-size:13px; margin:4px 0 0 0;">{target_date}</p></td></tr>
  <tr><td style="padding:16px 24px 0;"><p style="color:#374151; font-size:16px; line-height:1.8;">{recipient_name}，今天的学习日报没有顺利生成。系统已经记录了失败信息，后续可以根据状态文件继续排查。</p></td></tr>
  <tr><td style="padding:0 24px;"><div style="background:#fff7ed; border-radius:12px; padding:20px; margin:18px 0;"><p style="margin:0; color:#9a3412; font-size:15px; line-height:1.7;"><strong>当前提示：</strong>{reason}</p></div>{link_block}</td></tr>
  <tr><td style="padding:16px 24px 32px;"><p style="color:#9ca3af; font-size:13px; line-height:1.6;">每日拾光学习簿 · 自动推送<br>今天先不强行生成新内容，避免把异常结果当作正式日报。</p></td></tr>
</table>
</body>
</html>"""


def build_failure_email_plain(report: dict | None, config: dict, target_date: str, failure_reason: str, recipient_name: str) -> str:
    site_base = config["site"]["base_url"].rstrip("/")
    lines = [
        config["email"]["sender_name"],
        target_date,
        "",
        f"{recipient_name}，今天的学习日报没有顺利生成。系统已经记录了失败信息，后续可以根据状态文件继续排查。",
        "",
        f"当前提示：{failure_reason or '流水线在生成或发布今日学习日报时遇到异常。'}",
    ]
    if report:
        report_url = f"{site_base}/{report['path'].lstrip('./')}"
        lines.extend(["", f"上一份可用日报：{report.get('title', report.get('date', '上一有效日报'))}", report_url])
    else:
        lines.extend(["", "暂时没有找到上一份可用日报链接。"])
    lines.extend(["", "每日拾光学习簿 · 自动推送", "今天先不强行生成新内容，避免把异常结果当作正式日报。"])
    return "\n".join(lines)


def build_subject(report: dict, target_date: str, test_email: bool) -> str:
    prefix = "test: " if test_email else ""
    return f"{prefix}每日拾光学习簿 — {report.get('date', target_date)} 学习日报"


def build_failure_subject(target_date: str, test_email: bool) -> str:
    prefix = "test: " if test_email else ""
    return f"{prefix}每日拾光学习簿 — {target_date} 日报未生成提醒"


def select_delivery_emails(email_module, config: dict, target_emails: list[str], failure_notice: bool) -> tuple[list[str], str]:
    if not failure_notice:
        return target_emails, "target_report"
    if hasattr(email_module, "get_failure_email"):
        return [email_module.get_failure_email(config)], "sender_failure_notice"
    sender_email = (config.get("email") or {}).get("sender_email")
    if not sender_email:
        raise ValueError("配置缺少 email.sender_email，无法发送故障提醒。")
    return [sender_email], "sender_failure_notice"


def recipient_name_for(email_module, config: dict, email: str) -> str:
    if hasattr(email_module, "get_recipient_name"):
        return email_module.get_recipient_name(config, email)
    recipients = (config.get("email") or {}).get("recipients") or {}
    if isinstance(recipients, dict):
        for recipient in recipients.values():
            if not isinstance(recipient, dict):
                continue
            if recipient.get("email") == email and isinstance(recipient.get("target_name"), str):
                return recipient["target_name"].strip()
    return email.split("@", 1)[0]


def build_recipient_payload(
    email_module,
    report: dict | None,
    config: dict,
    target_date: str,
    recipient_email: str,
    failure_notice: bool,
    failure_reason: str,
    no_llm: bool,
    retries: int,
    retry_delay: float,
) -> tuple[str, str, dict | None, str | None]:
    recipient_name = recipient_name_for(email_module, config, recipient_email)
    if failure_notice:
        html = build_failure_email_html(report, config, target_date, failure_reason, recipient_name)
        plain = build_failure_email_plain(report, config, target_date, failure_reason, recipient_name)
        return html, plain, None, None
    llm_content = None
    llm_error = None
    if report and not no_llm:
        llm_content, llm_error = generate_llm_content(
            email_module,
            report,
            config,
            target_date,
            recipient_name,
            retries,
            retry_delay,
        )
    html = email_module.build_email_html(report, config, target_date, llm_content=llm_content, recipient_name=recipient_name)
    plain = email_module.build_email_plain(report, config, target_date, llm_content=llm_content, recipient_name=recipient_name)
    return html, plain, llm_content, llm_error


def send_email(email_module, html: str, plain: str, config: dict, report: dict | None, target_emails: list[str], target_date: str, test_email: bool, retries: int, retry_delay: float, failure_notice: bool = False) -> None:
    email_cfg = config["email"]
    msg = email_module.MIMEMultipart("alternative")
    subject = build_failure_subject(target_date, test_email) if failure_notice else build_subject(report or {}, target_date, test_email)
    msg["Subject"] = email_module.Header(subject, "utf-8")
    msg["From"] = email_module.formataddr((email_cfg["sender_name"], email_cfg["sender_email"]))
    msg["To"] = ", ".join(email_module.formataddr(("", email)) for email in target_emails)
    msg.attach(email_module.MIMEText(plain, "plain", "utf-8"))
    msg.attach(email_module.MIMEText(html, "html", "utf-8"))

    def operation() -> None:
        port = int(email_cfg["smtp_port"])
        if port == 465:
            server = smtplib.SMTP_SSL(email_cfg["smtp_server"], port, timeout=30)
        else:
            server = smtplib.SMTP(email_cfg["smtp_server"], port, timeout=30)
            server.starttls()
        with server:
            server.login(email_cfg["sender_email"], email_cfg["sender_password"])
            server.send_message(msg)

    try:
        retry_call(operation, RetryPolicy(attempts=retries, initial_delay=retry_delay, label="SMTP 邮件发送"))
    except smtplib.SMTPAuthenticationError as exc:
        raise RuntimeError("SMTP 认证失败，请检查 sender_email 和 sender_password。") from exc
    except Exception as exc:
        raise RuntimeError(f"邮件发送失败: {exc}") from exc


def require_imap_config(config: dict) -> dict:
    email_cfg = config.get("email") or {}
    imap_user = email_cfg.get("imap_user") or email_cfg.get("sender_email")
    imap_password = email_cfg.get("imap_password") or email_cfg.get("sender_password")
    imap_cfg = {
        "imap_server": email_cfg.get("imap_server"),
        "imap_port": int(email_cfg.get("imap_port") or 993),
        "imap_user": imap_user,
        "imap_password": imap_password,
    }
    missing = [key for key, value in imap_cfg.items() if not value]
    if missing:
        raise ValueError(f"缺少 IMAP 配置项: {', '.join(missing)}")
    return imap_cfg


def decode_imap_bytes(value) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def decode_mime_header(value: str) -> str:
    parts = []
    for text, charset in decode_header(value):
        if isinstance(text, bytes):
            parts.append(text.decode(charset or "utf-8", errors="replace"))
        else:
            parts.append(text)
    return "".join(parts)


def extract_header_value(header_text: str, header_name: str) -> str:
    lines = header_text.replace("\r\n", "\n").split("\n")
    collected = []
    capture = False
    prefix = f"{header_name.lower()}:"
    for line in lines:
        if line.lower().startswith(prefix):
            capture = True
            collected.append(line.split(":", 1)[1].strip())
            continue
        if capture and (line.startswith(" ") or line.startswith("\t")):
            collected.append(line.strip())
            continue
        if capture:
            break
    return decode_mime_header(" ".join(collected)) if collected else ""


def verify_inbox_delivery(config: dict, report: dict, target_date: str, timeout: int, interval: float, test_email: bool, failure_notice: bool = False) -> dict:
    imap_cfg = require_imap_config(config)
    subject = build_failure_subject(target_date, test_email) if failure_notice else build_subject(report, target_date, test_email)
    attempts = {"count": 0}

    def operation() -> dict:
        attempts["count"] += 1
        with imaplib.IMAP4_SSL(imap_cfg["imap_server"], imap_cfg["imap_port"]) as mailbox:
            mailbox.login(imap_cfg["imap_user"], imap_cfg["imap_password"])
            if "ID" not in imaplib.Commands:
                imaplib.Commands["ID"] = ("AUTH", "SELECTED")
            mailbox._simple_command("ID", '("name" "DailyLearningAssistant" "version" "1.0" "vendor" "local")')
            status, _ = mailbox.select("INBOX", readonly=True)
            if status != "OK":
                raise RuntimeError("无法选择 INBOX")
            search_since = datetime.now().strftime("%d-%b-%Y")
            status, data = mailbox.search(None, "SINCE", search_since)
            if status != "OK":
                raise RuntimeError("IMAP 搜索失败")
            message_ids = (data[0] or b"").split()
            for message_id in reversed(message_ids[-30:]):
                status, fetched = mailbox.fetch(message_id, "(BODY.PEEK[HEADER.FIELDS (SUBJECT DATE FROM TO)])")
                if status != "OK":
                    continue
                header_text = "\n".join(
                    decode_imap_bytes(part[1])
                    for part in fetched
                    if isinstance(part, tuple) and len(part) > 1
                )
                decoded_subject = extract_header_value(header_text, "Subject")
                if subject in decoded_subject:
                    return {
                        "status": "found",
                        "attempts": attempts["count"],
                        "subject": subject,
                        "matched_subject": decoded_subject,
                        "message_id": decode_imap_bytes(message_id),
                    }
            raise RuntimeError(f"未在最近 {min(len(message_ids), 30)} 封邮件中找到目标标题")

    try:
        return wait_until(operation, timeout=timeout, interval=interval, label="IMAP 邮件验收")
    except RuntimeError as exc:
        return {"status": "not_found", "attempts": attempts["count"], "subject": subject, "error": str(exc)}


def main() -> int:
    args = parse_args()
    email_module = load_email_module()
    config_path = Path(args.config).expanduser().resolve()
    input_root = Path(os.path.expanduser(args.input_root)).resolve()
    output_root = Path(os.path.expanduser(args.output_root)).resolve()
    config = load_config(config_path)
    timezone = resolve_timezone(args, config)
    target_date = resolve_target_date(args, timezone)
    started_at = datetime.now(timezone).isoformat()
    year_month = target_date[:7]

    output_dir = output_root / "prework" / year_month / target_date
    output_dir.mkdir(parents=True, exist_ok=True)
    status_path = output_dir / "run_status.json"
    manifest_path = input_root / "daily_report" / "manifest.json"

    problems: list[str] = []
    report: dict | None = None
    report_file: Path | None = None
    selection_mode = "not_selected"
    target_emails: list[str] = []
    delivery_emails: list[str] = []
    recipient_scope = "not_selected"
    llm_content = None
    llm_status = "skipped"
    send_status = "skipped"
    inbox_verification = {
        "enabled": args.verify_inbox,
        "status": "skipped",
    }
    preview_html_path = output_dir / "email_preview.html"
    preview_txt_path = output_dir / "email_preview.txt"

    try:
        target_emails = email_module.get_target_emails(config)
        sender_email = (config.get("email") or {}).get("sender_email")
        delivery_emails, recipient_scope = select_delivery_emails(email_module, config, target_emails, args.failure_notice)
        test_email = args.test_email or args.dry_run or (not args.failure_notice and delivery_emails == [sender_email])
        reports = load_daily_manifest(manifest_path, root=input_root, allow_empty=False)["reports"]
        if args.failure_notice:
            previous_date = (datetime.strptime(target_date, "%Y-%m-%d").date() - timedelta(days=1)).isoformat()
            report, selection_mode = select_report(reports, previous_date, allow_latest_fallback=True)
            selection_mode = "previous_available_for_failure_notice"
        else:
            report, selection_mode = select_report(reports, target_date, args.allow_latest_fallback)
        if not report:
            raise FileNotFoundError(f"{target_date} 没有可发送的日报 manifest 条目")
        if report.get("date") == target_date:
            report_file = validate_report_file(input_root, report)

        if args.failure_notice:
            llm_status = "skipped_failure_notice"
        elif args.no_llm:
            llm_status = "skipped_by_option"
        else:
            preview_recipient = delivery_emails[0]
            html, plain, llm_content, llm_error = build_recipient_payload(
                email_module,
                report,
                config,
                target_date,
                preview_recipient,
                args.failure_notice,
                args.failure_reason,
                args.no_llm,
                args.llm_retries,
                args.llm_retry_delay,
            )
            llm_status = "success" if llm_content else "fallback_static"
            if llm_error and not llm_content:
                problems.append(f"LLM 邮件文案生成失败，已使用静态文案: {llm_error}")

        if args.failure_notice or args.no_llm:
            html, plain, llm_content, _ = build_recipient_payload(
                email_module,
                report,
                config,
                target_date,
                delivery_emails[0],
                args.failure_notice,
                args.failure_reason,
                args.no_llm,
                args.llm_retries,
                args.llm_retry_delay,
            )
        preview_html_path, preview_txt_path = write_email_previews(output_dir, html, plain)

        if args.dry_run:
            send_status = "dry_run"
            status = "success"
        else:
            llm_failures = 1 if (llm_status == "fallback_static" and llm_error) else 0
            for index, recipient_email in enumerate(delivery_emails):
                recipient_html = html
                recipient_plain = plain
                if index > 0:
                    recipient_html, recipient_plain, recipient_llm_content, recipient_llm_error = build_recipient_payload(
                        email_module,
                        report,
                        config,
                        target_date,
                        recipient_email,
                        args.failure_notice,
                        args.failure_reason,
                        args.no_llm,
                        args.llm_retries,
                        args.llm_retry_delay,
                    )
                    if not args.failure_notice and not args.no_llm:
                        if recipient_llm_content:
                            llm_content = llm_content or recipient_llm_content
                        elif recipient_llm_error:
                            llm_failures += 1
                send_email(
                    email_module,
                    recipient_html,
                    recipient_plain,
                    config,
                    report,
                    [recipient_email],
                    target_date,
                    test_email,
                    args.llm_retries,
                    args.llm_retry_delay,
                    args.failure_notice,
                )
            if not args.failure_notice and not args.no_llm and len(delivery_emails) > 1:
                llm_status = "success" if llm_failures == 0 else "fallback_static"
                if llm_failures:
                    problems.append(f"{llm_failures} 个收件人的 LLM 邮件文案生成失败，已使用静态文案。")
            send_status = "sent"
            if args.verify_inbox:
                inbox_verification = {
                    "enabled": True,
                    **verify_inbox_delivery(
                        config,
                        report,
                        target_date,
                        args.verify_timeout,
                        args.verify_interval,
                        test_email,
                        args.failure_notice,
                    ),
                }
                if inbox_verification.get("status") != "found":
                    raise RuntimeError(f"邮件已发送，但 IMAP 验收未找到目标邮件: {inbox_verification.get('error')}")
            status = "success"
    except Exception as exc:
        problems.append(str(exc))
        status = "failed"
        if send_status == "skipped":
            send_status = "failed"

    finished_at = datetime.now(timezone).isoformat()
    site_base = (config.get("site") or {}).get("base_url", "").rstrip("/")
    report_url = None
    if report and report.get("path") and site_base:
        report_url = f"{site_base}/{str(report['path']).lstrip('./')}"

    write_agent_status(
        status_path,
        target_date,
        {
            "status": status,
            "started_at": started_at,
            "finished_at": finished_at,
            "timezone": str(timezone),
            "dry_run": args.dry_run,
            "test_email": args.test_email
            or args.dry_run
            or (not args.failure_notice and delivery_emails == [(config.get("email") or {}).get("sender_email")]),
            "input_manifest_path": relative_to_root(manifest_path, input_root),
            "report_selection_mode": selection_mode,
            "report_date": report.get("date") if report else None,
            "report_title": report.get("title") if report else None,
            "report_path": relative_to_root(report_file, input_root) if report_file else None,
            "report_url": report_url,
            "email_preview_html_path": relative_to_root(preview_html_path, output_root),
            "email_preview_text_path": relative_to_root(preview_txt_path, output_root),
            "recipient_count": len(delivery_emails),
            "configured_target_recipient_count": len(target_emails),
            "recipient_scope": recipient_scope,
            "script": relative_to_root(EMAIL_SCRIPT),
            "llm": {
                "enabled": not args.no_llm,
                "status": llm_status,
                "used_dynamic_content": bool(llm_content),
            },
            "email": {
                "status": send_status,
                "smtp_server": (config.get("email") or {}).get("smtp_server"),
                "subject": (
                    build_failure_subject(target_date, args.test_email or args.dry_run)
                    if args.failure_notice
                    else build_subject(report, target_date, args.test_email or args.dry_run or delivery_emails == [(config.get("email") or {}).get("sender_email")])
                )
                if report
                else None,
                "failure_notice": args.failure_notice,
            },
            "inbox_verification": inbox_verification,
            "problems": problems,
        },
        finished_at,
    )

    if status != "success":
        print("[错误] 第 5 步邮件生成或发送失败。")
        for problem in problems:
            print(f"- {problem}")
        print(f"[状态] 已更新: {status_path}")
        return 1

    print(f"[完成] 邮件内容已生成: {preview_html_path}")
    print(f"[完成] 邮件纯文本已生成: {preview_txt_path}")
    if args.dry_run:
        print("[完成] dry-run 模式，未发送邮件。")
    else:
        print(f"[完成] 邮件已发送至 {len(delivery_emails)} 个收件人。")
    print(f"[状态] 已更新: {status_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
