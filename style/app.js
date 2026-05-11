const manifestPath = "./daily_report/manifest.json";

const state = {
  reports: [],
  activeDate: null,
};

const fallbackManifest = {
  reports: [
    {
      date: "2026-05-02",
      title: "2026-05-02 学习笔记日报",
      summary:
        "围绕 Project Workspace、Construction Workspace 和流程式步骤容器完成工作台分层与入口收口。",
      path: "./daily_report/2026-05/2026-05-02-learning-report.html",
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

  const params = new URLSearchParams(location.search);
  const archiveMode = params.get("archive") === "1";
  const requestedDate = params.get("date");
  const requestedReport = state.reports.find((report) => report.date === requestedDate);

  if (!state.reports.length) {
    renderEmptySite();
    return;
  }

  if (!archiveMode) {
    redirectToReport(requestedReport || state.reports[0]);
    return;
  }

  const activeReport = requestedReport || state.reports[0];
  renderArchive(activeReport.date);
  renderArchiveIntro(activeReport);

  els.latestButton.addEventListener("click", () => redirectToReport(state.reports[0]));
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

function renderArchive(activeDate) {
  els.archiveCount.textContent = state.reports.length
    ? `${state.reports.length} 篇日报`
    : "暂无日报";

  if (!state.reports.length) {
    els.archiveTree.innerHTML = '<p class="muted">还没有可展示的学习日报。</p>';
    return;
  }

  const groups = groupReports(state.reports);
  const latest = state.reports[0];
  const currentMonth = activeDate.slice(0, 7);

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
                <button class="day-link" type="button" data-date="${escapeAttribute(report.date)}" data-path="${escapeAttribute(report.path)}">
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
    button.classList.toggle("is-active", button.dataset.date === activeDate);
    button.addEventListener("click", () => {
      redirectToReport({
        date: button.dataset.date,
        path: button.dataset.path,
      });
    });
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

function redirectToReport(report) {
  if (!report?.path) {
    return;
  }
  location.replace(report.path);
}

function renderArchiveIntro(report) {
  state.activeDate = report.date;
  els.title.textContent = report.title;
  els.summary.textContent = report.summary;
  els.weekday.textContent = formatDate(report.date);
  els.content.innerHTML = `
    <div class="archive-guide">
      <h2>学习日报归档</h2>
      <p>这里保留历史日报入口。访问首页时会自动打开最新日报，点击左侧日期可直接跳转到对应的 HTML 日报页面。</p>
      <a class="primary-link" href="${escapeAttribute(report.path)}">打开当前选中的日报</a>
    </div>
  `;
}

function renderEmptySite() {
  els.title.textContent = "学习簿等第一篇日报";
  els.summary.textContent = "后续自动化任务生成 HTML 学习日报后，首页会默认跳转到最新一天的内容。";
  els.weekday.textContent = "暂无归档";
  els.content.innerHTML = `
    <div class="empty-state">
      <div>
        <h2>暂无学习日报</h2>
        <p>请让每日自动化任务生成 <code>daily_report/manifest.json</code> 和对应 HTML 日报文件。</p>
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

function escapeAttribute(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}
