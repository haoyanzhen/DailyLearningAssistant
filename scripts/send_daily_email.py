#!/usr/bin/env python3
"""每日拾光学习簿 — 邮件推送脚本。

读取 config.json 配置，从 daily_report/manifest.json 获取当日学习报告，
构造一封亲切的问候邮件并通过 SMTP 发送到目标邮箱列表。

用法:
    python3 scripts/send_daily_email.py          # 发送当日报告
    python3 scripts/send_daily_email.py --dry-run  # 仅打印，不发送
    python3 scripts/send_daily_email.py --date 2026-05-14  # 指定日期
"""

import argparse
import json
import smtplib
import sys
from datetime import datetime, date
from email.header import Header
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
from orchestrator.llm import LLMRetryPolicy, call_chat_completion, require_llm_config
from orchestrator.manifest import load_daily_manifest, select_report


def load_config():
    config_path = PROJECT_ROOT / "config.json"
    if not config_path.exists():
        print(f"[错误] 配置文件不存在: {config_path}")
        print("请复制 config.example.json 为 config.json 并填入真实配置。")
        sys.exit(1)
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_manifest():
    manifest_path = PROJECT_ROOT / "daily_report" / "manifest.json"
    if not manifest_path.exists():
        print(f"[跳过] manifest.json 不存在: {manifest_path}")
        return []
    return load_daily_manifest(manifest_path, root=PROJECT_ROOT, allow_empty=True)["reports"]


def find_latest_available_report(reports, target_date):
    """查找不晚于目标日期的最新可用日报。"""
    report, _ = select_report(reports, target_date, allow_latest_fallback=True)
    return report


def get_configured_recipients(config):
    """读取收件人 ID 配置。"""
    email_cfg = config.get("email", {})
    recipients = email_cfg.get("recipients")
    if not isinstance(recipients, dict):
        print("[错误] 邮件收件人配置无效，请设置 email.recipients 为收件人 ID 到邮箱和昵称的映射。")
        sys.exit(1)
    normalized = {}
    for recipient_id, item in recipients.items():
        if not isinstance(recipient_id, str) or not recipient_id.strip() or not isinstance(item, dict):
            continue
        email = item.get("email")
        target_name = item.get("target_name")
        if isinstance(email, str) and email.strip() and isinstance(target_name, str) and target_name.strip():
            normalized[recipient_id.strip()] = {
                "id": recipient_id.strip(),
                "email": email.strip(),
                "target_name": target_name.strip(),
            }
    if not normalized:
        print("[错误] 邮件收件人为空，请在 config.json 中设置 email.recipients。")
        sys.exit(1)
    return normalized


def get_target_recipient_ids(config):
    email_cfg = config.get("email", {})
    ids = email_cfg.get("target_recipient_ids")
    if not isinstance(ids, list) or not ids:
        print("[错误] 请设置 email.target_recipient_ids 为收件人 ID 列表。")
        sys.exit(1)
    return [item.strip() for item in ids if isinstance(item, str) and item.strip()]


def get_target_recipients(config):
    recipients = get_configured_recipients(config)
    target_ids = get_target_recipient_ids(config)
    missing = [recipient_id for recipient_id in target_ids if recipient_id not in recipients]
    if missing:
        print(f"[错误] email.target_recipient_ids 包含未定义 ID: {', '.join(missing)}")
        sys.exit(1)
    return [recipients[recipient_id] for recipient_id in target_ids]


def get_target_emails(config):
    """读取目标邮箱列表。"""
    return [recipient["email"] for recipient in get_target_recipients(config)]


def get_recipient_name(config, email):
    """Return the configured display nickname for an email address."""
    for recipient in get_configured_recipients(config).values():
        if recipient["email"] == email:
            return recipient["target_name"]
    return email.split("@", 1)[0]


def get_failure_recipient(config):
    email_cfg = config.get("email", {})
    recipient_id = email_cfg.get("failure_recipient_id")
    recipients = get_configured_recipients(config)
    if not isinstance(recipient_id, str) or recipient_id not in recipients:
        print("[错误] 请设置 email.failure_recipient_id，并确保它存在于 email.recipients。")
        sys.exit(1)
    return recipients[recipient_id]


def get_failure_email(config):
    return get_failure_recipient(config)["email"]


def generate_email_content(report, config, send_date, recipient_name=None):
    """调用 LLM 生成邮件问候和点评，失败返回 None 以触发回退。"""
    recipient_name = recipient_name or "你"
    weekday_names = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
    send_dt = datetime.strptime(send_date, "%Y-%m-%d")
    weekday = weekday_names[send_dt.weekday()]
    report_date = report.get("date", send_date)
    title = report.get("title", f"{report_date} 学习笔记日报")
    summary = report.get("summary", "今日学习内容已就绪。")
    prompt = f"""你是“每日学习助手”，和收件人既是熟悉的朋友，也是一起持续学习的同行者。你读过今天的学习日报，从中挑一处值得留意的细节，像朋友间发消息一样写一段简短留言。语气亲切、具体、自然，句子有长有短，偶尔带一点轻松的观察，表达真诚而松弛。

邮件发送日期：{send_date} {weekday}
今日学习日报：
- 日期：{report_date}
- 标题：{title}
- 摘要：{summary}
- 收件人称呼：{recipient_name}

写作时以标题和摘要明确提供的信息为依据；信息有限时，用概括而轻松的表达。问候里自然使用收件人称呼一次。点评只挑一个具体细节，顺着它说清楚今天内容之间的联系或值得留意之处；合适时再用一个贴近日常的比喻。

请写两部分内容：greeting 为 1–2 句自然问候；commentary 为 2–3 句轻量点评。两部分合计以 120–220 字为宜，上限 600 字。保持留言像熟人之间的短消息，让具体观察带出亲近感。

请按以下 JSON 结构提供最终内容，两个字段都填写完整的自然语言文本：
{{
  "greeting": "问候语",
  "commentary": "学习点评"
}}
最终回复请呈现完整 JSON 对象。"""

    try:
        llm = require_llm_config(config)
        text = call_chat_completion(
            llm,
            [{"role": "user", "content": prompt}],
            timeout=600,
            retry_policy=LLMRetryPolicy(attempts=1, initial_delay=0),
            temperature=0.9,
        )
    except Exception as e:
        print(f"[警告] LLM 调用失败: {e}")
        return None

    try:
        # 清理可能的 markdown 代码块标记
        text = text.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:]) if len(lines) > 1 else text
        if text.endswith("```"):
            text = text[: text.rfind("```")].strip()
        content = json.loads(text)
        print(f"[LLM] 已生成动态问候和点评")
        return content
    except (KeyError, IndexError, json.JSONDecodeError) as e:
        print(f"[警告] LLM 响应解析失败: {e}")
        return None


def build_email_html(report, config, send_date, llm_content=None, recipient_name=None):
    site_base = config["site"]["base_url"].rstrip("/")
    sender_name = config["email"]["sender_name"]
    recipient_name = recipient_name or "你"

    if report:
        report_url = f"{site_base}/{report['path'].lstrip('./')}"
        report_date = report.get("date", send_date)
        title = report.get("title", f"{report_date} 学习笔记日报")
        summary = report.get("summary", "今日学习内容已就绪，点击链接查看详情。")

        content_block = f"""
        <div style="background:#f0f7ff; border-radius:12px; padding:24px; margin:20px 0;">
            <h2 style="margin:0 0 8px 0; color:#2563eb;">
                <a href="{report_url}" style="color:#2563eb; text-decoration:none;">{title}</a>
            </h2>
            <p style="color:#4b5563; font-size:15px; line-height:1.6; margin:8px 0 0 0;">{summary}</p>
            <a href="{report_url}" style="display:inline-block; margin-top:16px; padding:10px 24px; background:#2563eb; color:#fff; border-radius:8px; text-decoration:none; font-size:14px;">查看完整日报</a>
        </div>
        """
    else:
        content_block = f"""
        <div style="background:#fefce8; border-radius:12px; padding:24px; margin:20px 0;">
            <p style="color:#92400e; font-size:15px; line-height:1.6; margin:0;">
                今日学习报告尚未生成，请稍后查看。<br>
                先去探索新知识吧，报告会在每日自动汇总后更新。
            </p>
        </div>
        """

    weekday_names = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
    weekday = weekday_names[datetime.strptime(send_date, "%Y-%m-%d").weekday()]

    if llm_content:
        greeting_html = f'<p style="color:#374151; font-size:16px; line-height:1.8;">{llm_content["greeting"]}</p>'
        commentary_html = f"""    <tr>
        <td style="padding:4px 24px 0;">
            <p style="color:#4b5563; font-size:15px; line-height:1.8; font-style:italic;">{llm_content["commentary"]}</p>
        </td>
    </tr>"""
    else:
        greeting_html = f"""<p style="color:#374151; font-size:16px; line-height:1.8;">
                {recipient_name}，早上好！<br>
                这份学习日报已经整理好了，可以按自己的节奏慢慢看。
            </p>"""
        commentary_html = ""

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="utf-8"></head>
<body style="margin:0; padding:0; background:#f3f4f6; font-family:-apple-system, 'PingFang SC', 'Microsoft YaHei', sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="max-width:600px; margin:0 auto;">
    <tr>
        <td style="padding:32px 24px 0;">
            <h1 style="color:#1f2937; font-size:22px; margin:0;">{sender_name}</h1>
            <p style="color:#6b7280; font-size:13px; margin:4px 0 0 0;">{send_date} {weekday}</p>
        </td>
    </tr>
    <tr>
        <td style="padding:8px 24px 0;">
            {greeting_html}
        </td>
    </tr>
    <tr>
        <td style="padding:0 24px;">
            {content_block}
        </td>
    </tr>
    {commentary_html}
    <tr>
        <td style="padding:16px 24px 32px;">
            <p style="color:#9ca3af; font-size:13px; line-height:1.6;">
                每日拾光学习簿 · 自动推送<br>
                每天进步一点点，时间会给你答案 🌱
            </p>
        </td>
    </tr>
</table>
</body>
</html>"""


def build_email_plain(report, config, send_date, llm_content=None, recipient_name=None):
    site_base = config["site"]["base_url"].rstrip("/")
    sender_name = config["email"]["sender_name"]
    recipient_name = recipient_name or "你"

    if report:
        report_url = f"{site_base}/{report['path'].lstrip('./')}"
        report_date = report.get("date", send_date)
        title = report.get("title", f"{report_date} 学习笔记日报")
        summary = report.get("summary", "今日学习内容已就绪。")
        content_line = f"本次报告：{title}\n摘要：{summary}\n查看完整日报：{report_url}"
    else:
        content_line = "今日学习报告尚未生成，请稍后查看。"

    greeting = (llm_content or {}).get("greeting", f"{recipient_name}，早上好！这份学习日报已经整理好了，可以按自己的节奏慢慢看。")
    commentary = (llm_content or {}).get("commentary", "")

    lines = [
        f"{sender_name}",
        f"{send_date}",
        "",
        greeting,
        "",
        content_line,
    ]
    if commentary:
        lines.append("")
        lines.append(f"点评：{commentary}")
    lines.append("")
    lines.append("每日拾光学习簿 · 自动推送")
    lines.append("每天进步一点点，时间会给你答案")
    return "\n".join(lines)


def send_email(html_content, plain_content, config, report=None, target_emails=None):
    email_cfg = config["email"]
    target_emails = target_emails or get_target_emails(config)
    msg = MIMEMultipart("alternative")
    subject_date = (report or {}).get("date", date.today().isoformat())
    subject = f"每日拾光学习簿 — {subject_date} 学习日报"
    msg["Subject"] = Header(subject, "utf-8")
    msg["From"] = formataddr((email_cfg["sender_name"], email_cfg["sender_email"]))
    msg["To"] = ", ".join(formataddr(("", email)) for email in target_emails)
    msg.attach(MIMEText(plain_content, "plain", "utf-8"))
    msg.attach(MIMEText(html_content, "html", "utf-8"))

    try:
        port = email_cfg["smtp_port"]
        if port == 465:
            server = smtplib.SMTP_SSL(email_cfg["smtp_server"], port, timeout=30)
        else:
            server = smtplib.SMTP(email_cfg["smtp_server"], port, timeout=30)
            server.starttls()
        with server:
            server.login(email_cfg["sender_email"], email_cfg["sender_password"])
            server.send_message(msg)
        print(f"[成功] 邮件已发送至 {', '.join(target_emails)}")
    except smtplib.SMTPAuthenticationError:
        print("[错误] SMTP 认证失败，请检查 sender_email 和 sender_password。")
        print("  Gmail 用户需使用应用专用密码: https://myaccount.google.com/apppasswords")
        sys.exit(1)
    except Exception as e:
        print(f"[错误] 邮件发送失败: {e}")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="每日拾光学习簿邮件推送")
    parser.add_argument("--dry-run", action="store_true", help="仅预览邮件内容，不实际发送")
    parser.add_argument("--no-llm", action="store_true", help="跳过 LLM 生成，使用静态问候内容")
    parser.add_argument("--date", type=str, default=date.today().isoformat(),
                        help="指定日期 (YYYY-MM-DD)，默认当天")
    args = parser.parse_args()

    send_date = args.date
    config = load_config()
    target_emails = get_target_emails(config)
    reports = load_manifest()
    report = find_latest_available_report(reports, send_date)

    llm_content = None
    preview_recipient = target_emails[0]
    preview_recipient_name = get_recipient_name(config, preview_recipient)
    if report and not args.no_llm:
        llm_content = generate_email_content(report, config, send_date, preview_recipient_name)

    html = build_email_html(report, config, send_date, llm_content=llm_content, recipient_name=preview_recipient_name)
    plain = build_email_plain(report, config, send_date, llm_content=llm_content, recipient_name=preview_recipient_name)

    if args.dry_run:
        print("=" * 60)
        print("[预览模式] HTML 邮件内容如下（不会实际发送）：")
        print("=" * 60)
        print(html)
        print("=" * 60)
        print("[预览模式] 纯文本邮件内容如下：")
        print("=" * 60)
        print(plain)
        print("=" * 60)
        print(f"收件人数量: {len(target_emails)}")
        if report:
            site_base = config["site"]["base_url"].rstrip("/")
            report_url = f"{site_base}/{report['path'].lstrip('./')}"
            print(f"发送日期: {send_date}")
            print(f"日报日期: {report.get('date', '(未知)')}")
            print(f"报告链接: {report_url}")
        else:
            print(f"{send_date} 及之前暂无可用学习报告。")
        return

    if report is None:
        print(f"[跳过] {send_date} 及之前暂无可用学习报告，不发送邮件。")
        return

    for target_email in target_emails:
        recipient_name = get_recipient_name(config, target_email)
        llm_content = None
        if report and not args.no_llm:
            llm_content = generate_email_content(report, config, send_date, recipient_name)
        html = build_email_html(report, config, send_date, llm_content=llm_content, recipient_name=recipient_name)
        plain = build_email_plain(report, config, send_date, llm_content=llm_content, recipient_name=recipient_name)
        send_email(html, plain, config, report=report, target_emails=[target_email])


if __name__ == "__main__":
    main()
