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
import urllib.error
import urllib.request
from datetime import datetime, date
from email.header import Header
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


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
    with open(manifest_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("reports", [])


def find_today_report(reports, target_date):
    for report in reports:
        if report.get("date") == target_date:
            return report
    return None


def get_target_emails(config):
    """读取目标邮箱列表，兼容旧版 target_email 单收件人配置。"""
    email_cfg = config.get("email", {})
    target_emails = email_cfg.get("target_emails")

    if target_emails is None and email_cfg.get("target_email"):
        target_emails = [email_cfg["target_email"]]
    elif isinstance(target_emails, str):
        target_emails = [target_emails]

    if not isinstance(target_emails, list):
        print("[错误] 邮件收件人配置无效，请设置 email.target_emails 为邮箱列表。")
        sys.exit(1)

    normalized = [email.strip() for email in target_emails if isinstance(email, str) and email.strip()]
    if not normalized:
        print("[错误] 邮件收件人为空，请在 config.json 中设置 email.target_emails。")
        sys.exit(1)

    return normalized


def generate_email_content(report, config, target_date):
    """调用 LLM 生成邮件问候和点评，失败返回 None 以触发回退。"""
    api_url = config["llm"]["api_url"]
    api_key = config["llm"]["api_key"]
    model = config["llm"]["model"]

    weekday_names = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
    weekday = weekday_names[datetime.strptime(target_date, "%Y-%m-%d").weekday()]
    title = report.get("title", f"{target_date} 学习笔记日报")
    summary = report.get("summary", "今日学习内容已就绪。")

    prompt = f"""你是收件人相识多年的伴侣，关系亲密、彼此深深了解，负责为"每日拾光学习簿"撰写每日邮件文案。你的口吻应如爱人之间的私信：温柔、宠溺、偶尔撒娇，称呼对方为"绪绪"或你们之间才懂的小昵称，语气中有牵挂、有默契，也有日常的碎碎念。

今日是 {target_date} {weekday}。今日学习报告信息：
- 标题：{title}
- 摘要：{summary}

请为今日邮件生成以下两部分内容，严格按 JSON 格式输出（不要包含 markdown 代码块标记）：

{{
  "greeting": "邮件开头的问候语，2-3句话。要求：以亲密伴侣的口吻问候，温暖宠溺，体现对对方学习成长的骄傲与陪伴感。风格需每日变化——可以回忆过去的点滴、分享当下的想念、吐槽日常小事、或温柔鼓励，避免重复套路。称呼用"绪绪"或亲昵的小名。",
  "commentary": "对今日学习内容的点评和延伸思考，2-3句话。要求：以伴侣视角结合摘要中的知识点，表达'虽然有些我不太懂，但你在努力的样子让我很心动'的感觉，让读者在学术之外感受到被你关注和爱着的温暖。"
}}"""

    body = json.dumps({
        "model": model,
        "max_tokens": 400,
        "temperature": 0.9,
        "messages": [
            {"role": "user", "content": prompt}
        ]
    }).encode("utf-8")

    req = urllib.request.Request(api_url, data=body, method="POST")
    req.add_header("Authorization", f"Bearer {api_key}")
    req.add_header("content-type", "application/json")

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read())
    except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError, OSError) as e:
        print(f"[警告] LLM 调用失败: {e}")
        return None

    try:
        text = result["choices"][0]["message"]["content"]
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


def build_email_html(report, config, target_date, llm_content=None):
    site_base = config["site"]["base_url"].rstrip("/")
    sender_name = config["email"]["sender_name"]

    if report:
        report_url = f"{site_base}/{report['path'].lstrip('./')}"
        title = report.get("title", f"{target_date} 学习笔记日报")
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
    weekday = weekday_names[datetime.strptime(target_date, "%Y-%m-%d").weekday()]

    if llm_content:
        greeting_html = f'<p style="color:#374151; font-size:16px; line-height:1.8;">{llm_content["greeting"]}</p>'
        commentary_html = f"""    <tr>
        <td style="padding:4px 24px 0;">
            <p style="color:#4b5563; font-size:15px; line-height:1.8; font-style:italic;">{llm_content["commentary"]}</p>
        </td>
    </tr>"""
    else:
        greeting_html = """<p style="color:#374151; font-size:16px; line-height:1.8;">
                绪绪，早上好！☀️<br>
                又是新的一天，看到你每天都在学习和成长，真的好为你骄傲。今天的日报已经准备好了，一起看看吧。
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
            <p style="color:#6b7280; font-size:13px; margin:4px 0 0 0;">{target_date} {weekday}</p>
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


def build_email_plain(report, config, target_date, llm_content=None):
    site_base = config["site"]["base_url"].rstrip("/")
    sender_name = config["email"]["sender_name"]

    if report:
        report_url = f"{site_base}/{report['path'].lstrip('./')}"
        title = report.get("title", f"{target_date} 学习笔记日报")
        summary = report.get("summary", "今日学习内容已就绪。")
        content_line = f"今日报告：{title}\n摘要：{summary}\n查看完整日报：{report_url}"
    else:
        content_line = "今日学习报告尚未生成，请稍后查看。"

    greeting = (llm_content or {}).get("greeting", "绪绪，早上好！又是新的一天，看到你每天都在学习和成长，真的好为你骄傲。今天的日报已经准备好了，一起看看吧。")
    commentary = (llm_content or {}).get("commentary", "")

    lines = [
        f"{sender_name}",
        f"{target_date}",
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


def send_email(html_content, plain_content, config, target_emails=None):
    email_cfg = config["email"]
    target_emails = target_emails or get_target_emails(config)
    msg = MIMEMultipart("alternative")
    subject = f"每日拾光学习簿 — {date.today().isoformat()} 学习日报"
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

    target_date = args.date
    config = load_config()
    target_emails = get_target_emails(config)
    reports = load_manifest()
    report = find_today_report(reports, target_date)

    llm_content = None
    if report and not args.no_llm:
        llm_content = generate_email_content(report, config, target_date)

    html = build_email_html(report, config, target_date, llm_content=llm_content)
    plain = build_email_plain(report, config, target_date, llm_content=llm_content)

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
            print(f"报告链接: {report_url}")
        else:
            print(f"{target_date} 暂无学习报告。")
        return

    if report is None:
        print(f"[跳过] {target_date} 暂无学习报告，不发送邮件。")
        return

    send_email(html, plain, config, target_emails=target_emails)


if __name__ == "__main__":
    main()
