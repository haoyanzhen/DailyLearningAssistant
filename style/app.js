const manifestPath = "./prework/manifest.json";

const state = {
  reports: [],
  activeDate: null,
};

const fallbackManifest = {
  reports: [
    {
      date: "2026-05-11",
      title: "日常学习推送助手起步记录",
      summary:
        "今天完成了每日学习静态主页的第一版搭建，明确了从仓库变更、概念提炼到学习日报展示的自动化链路。",
      path: "./prework/2026-05-11/learning_report.md",
    },
  ],
};

const els = {
  archiveTree: document.querySelector("#archive-tree"),
  archiveCount: document.querySelector("#archive-count"),
  latestButton: document.querySelector("#latest-button"),
  title: document.querySelector("#report-title"),
  summary: document.querySelector("#report-summary"),
  weekday: document.querySelector("#report-weekday"),
  content: document.querySelector("#report-content"),
};

document.addEventListener("DOMContentLoaded", init);

async function init() {
  const manifest = await loadManifest();
  state.reports = normalizeReports(manifest.reports);
  renderArchive();

  const requestedDate = new URLSearchParams(location.search).get("date");
  const initialReport =
    state.reports.find((report) => report.date === requestedDate) || state.reports[0];

  if (initialReport) {
    await selectReport(initialReport.date, { replaceUrl: Boolean(requestedDate) });
  } else {
    renderEmptySite();
  }

  els.latestButton.addEventListener("click", () => {
    if (state.reports[0]) {
      selectReport(state.reports[0].date);
    }
  });
}

async function loadManifest() {
  try {
    const response = await fetch(manifestPath, { cache: "no-store" });
    if (!response.ok) {
      throw new Error(`Manifest request failed: ${response.status}`);
    }
    return await response.json();
  } catch (error) {
    console.info("Using fallback learning report manifest.", error);
    return fallbackManifest;
  }
}

function normalizeReports(reports = []) {
  return reports
    .filter((report) => report.date && report.path)
    .map((report) => ({
      date: report.date,
      title: report.title || `${report.date} 学习日报`,
      summary: report.summary || "这一天的学习日报已经归档。",
      path: report.path,
    }))
    .sort((a, b) => b.date.localeCompare(a.date));
}

function renderArchive() {
  els.archiveCount.textContent = state.reports.length
    ? `${state.reports.length} 篇日报`
    : "暂无日报";

  if (!state.reports.length) {
    els.archiveTree.innerHTML = '<p class="muted">还没有可展示的学习日报。</p>';
    return;
  }

  const groups = groupReports(state.reports);
  const latest = state.reports[0];
  const currentMonth = latest.date.slice(0, 7);

  els.archiveTree.innerHTML = Object.entries(groups)
    .map(([year, months]) => {
      const yearOpen = Object.keys(months).some((month) => `${year}-${month}` === currentMonth);
      const monthHtml = Object.entries(months)
        .map(([month, reports]) => {
          const monthKey = `${year}-${month}`;
          const monthOpen = monthKey === currentMonth;
          const days = reports
            .map((report) => {
              const label = `${Number(report.date.slice(8, 10))}日`;
              const latestMark = report.date === latest.date ? "<span>最新</span>" : "<span></span>";
              return `
                <button class="day-link" type="button" data-date="${report.date}">
                  <span>${label}</span>
                  ${latestMark}
                </button>
              `;
            })
            .join("");
          return `
            <details ${monthOpen ? "open" : ""}>
              <summary>${Number(month)}月</summary>
              ${days}
            </details>
          `;
        })
        .join("");
      return `
        <details ${yearOpen ? "open" : ""}>
          <summary>${year}年</summary>
          ${monthHtml}
        </details>
      `;
    })
    .join("");

  els.archiveTree.querySelectorAll(".day-link").forEach((button) => {
    button.addEventListener("click", () => selectReport(button.dataset.date));
  });
}

function groupReports(reports) {
  return reports.reduce((acc, report) => {
    const [year, month] = report.date.split("-");
    acc[year] ||= {};
    acc[year][month] ||= [];
    acc[year][month].push(report);
    return acc;
  }, {});
}

async function selectReport(date, options = {}) {
  const report = state.reports.find((item) => item.date === date);
  if (!report) {
    return;
  }

  state.activeDate = report.date;
  els.title.textContent = report.title;
  els.summary.textContent = report.summary;
  els.weekday.textContent = formatDate(report.date);
  markActiveDay(report.date);
  renderLoading();

  if (!options.replaceUrl) {
    const url = new URL(location.href);
    url.searchParams.set("date", report.date);
    history.replaceState(null, "", url);
  }

  try {
    const response = await fetch(report.path, { cache: "no-store" });
    if (!response.ok) {
      throw new Error(`Report request failed: ${response.status}`);
    }
    const markdown = await response.text();
    els.content.innerHTML = markdownToHtml(markdown);
  } catch (error) {
    els.content.innerHTML = `
      <div class="empty-state">
        <div>
          <h2>日报还在路上</h2>
          <p>已经找到 ${report.date} 的归档入口，但暂时无法读取正文文件。</p>
        </div>
      </div>
    `;
    console.warn(error);
  }
}

function markActiveDay(date) {
  els.archiveTree.querySelectorAll(".day-link").forEach((button) => {
    button.classList.toggle("is-active", button.dataset.date === date);
  });
}

function renderLoading() {
  els.content.innerHTML = `
    <div class="loading-state">
      <span class="loader" aria-hidden="true"></span>
      <p>正在展开这一天的学习日报...</p>
    </div>
  `;
}

function renderEmptySite() {
  els.title.textContent = "学习簿等第一篇日报";
  els.summary.textContent = "后续自动化任务生成学习日报后，这里会默认显示最新一天的内容。";
  els.weekday.textContent = "暂无归档";
  els.content.innerHTML = `
    <div class="empty-state">
      <div>
        <h2>暂无学习日报</h2>
        <p>请让每日自动化任务生成 <code>prework/manifest.json</code> 和对应日报文件。</p>
      </div>
    </div>
  `;
}

function formatDate(dateText) {
  const date = new Date(`${dateText}T00:00:00+08:00`);
  return new Intl.DateTimeFormat("zh-CN", {
    year: "numeric",
    month: "long",
    day: "numeric",
    weekday: "long",
  }).format(date);
}

function markdownToHtml(markdown) {
  const lines = markdown.replace(/\r\n/g, "\n").split("\n");
  const html = [];
  let listType = null;
  let inCode = false;
  let codeLines = [];

  for (const rawLine of lines) {
    const line = rawLine.trimEnd();

    if (line.startsWith("```")) {
      if (inCode) {
        html.push(`<pre><code>${escapeHtml(codeLines.join("\n"))}</code></pre>`);
        codeLines = [];
        inCode = false;
      } else {
        closeList();
        inCode = true;
      }
      continue;
    }

    if (inCode) {
      codeLines.push(rawLine);
      continue;
    }

    if (!line.trim()) {
      closeList();
      continue;
    }

    if (line.startsWith("### ")) {
      closeList();
      html.push(`<h3>${inlineMarkdown(line.slice(4))}</h3>`);
    } else if (line.startsWith("## ")) {
      closeList();
      html.push(`<h2>${inlineMarkdown(line.slice(3))}</h2>`);
    } else if (line.startsWith("# ")) {
      closeList();
      html.push(`<h2>${inlineMarkdown(line.slice(2))}</h2>`);
    } else if (line.startsWith("> ")) {
      closeList();
      html.push(`<blockquote>${inlineMarkdown(line.slice(2))}</blockquote>`);
    } else if (/^[-*]\s+/.test(line)) {
      openList("ul");
      html.push(`<li>${inlineMarkdown(line.replace(/^[-*]\s+/, ""))}</li>`);
    } else if (/^\d+\.\s+/.test(line)) {
      openList("ol");
      html.push(`<li>${inlineMarkdown(line.replace(/^\d+\.\s+/, ""))}</li>`);
    } else {
      closeList();
      html.push(`<p>${inlineMarkdown(line)}</p>`);
    }
  }

  if (inCode) {
    html.push(`<pre><code>${escapeHtml(codeLines.join("\n"))}</code></pre>`);
  }
  closeList();
  return html.join("");

  function openList(type) {
    if (listType === type) {
      return;
    }
    closeList();
    listType = type;
    html.push(`<${type}>`);
  }

  function closeList() {
    if (!listType) {
      return;
    }
    html.push(`</${listType}>`);
    listType = null;
  }
}

function inlineMarkdown(text) {
  return escapeHtml(text)
    .replace(/`([^`]+)`/g, "<code>$1</code>")
    .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
}

function escapeHtml(value) {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}
