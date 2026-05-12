const manifestPath = "./daily_report/manifest.json";
const knowledgeManifestPath = "./knowledge_log/manifest.json";

const state = {
  reports: [],
  knowledgeMonths: [],
  activeDate: null,
  activeKnowledgeMonth: null,
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

const fallbackKnowledgeManifest = {
  months: [],
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
  const knowledgeManifest = await loadKnowledgeManifest();
  state.reports = normalizeReports(manifest.reports);
  state.knowledgeMonths = normalizeKnowledgeMonths(knowledgeManifest.months);

  const params = new URLSearchParams(location.search);
  const knowledgeMode = params.get("knowledge") === "1";
  const archiveMode = params.get("archive") === "1";
  const requestedDate = params.get("date");
  const requestedMonth = params.get("month");
  const requestedReport = state.reports.find((report) => report.date === requestedDate);
  const requestedKnowledgeMonth = state.knowledgeMonths.find((month) => month.key === requestedMonth);

  if (knowledgeMode) {
    renderKnowledgeArchive(requestedKnowledgeMonth?.key || state.knowledgeMonths[0]?.key);
    await renderKnowledgeMonth(requestedKnowledgeMonth || state.knowledgeMonths[0]);
    els.latestButton.addEventListener("click", () => {
      location.href = "./?archive=1";
    });
    return;
  }

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
  return loadJson(manifestPath, fallbackManifest, "Using fallback learning report manifest.");
}

async function loadKnowledgeManifest() {
  return loadJson(
    knowledgeManifestPath,
    fallbackKnowledgeManifest,
    "Using fallback knowledge log manifest.",
  );
}

async function loadJson(path, fallback, message) {
  try {
    const response = await fetch(path, { cache: "no-store" });
    if (!response.ok) {
      throw new Error(`Manifest request failed: ${response.status}`);
    }
    return await response.json();
  } catch (error) {
    console.info(message, error);
    return fallback;
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

function normalizeKnowledgeMonths(months = []) {
  return months
    .filter((month) => month.year && month.month && month.path)
    .map((month) => {
      const monthNumber = String(month.month).padStart(2, "0");
      const key = `${month.year}-${monthNumber}`;
      return {
        key,
        year: String(month.year),
        month: monthNumber,
        title: month.title || `${month.year}年${Number(monthNumber)}月教学记录`,
        path: month.path,
      };
    })
    .sort((a, b) => b.key.localeCompare(a.key));
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

function groupKnowledgeMonths(months) {
  return months.reduce((acc, month) => {
    acc[month.year] ||= [];
    acc[month.year].push(month);
    return acc;
  }, {});
}

function renderKnowledgeArchive(activeMonth) {
  els.archiveCount.textContent = state.knowledgeMonths.length
    ? `${state.knowledgeMonths.length} 个月度记录`
    : "暂无记录";
  els.latestButton.textContent = "查看日报归档";

  const panelTitle = document.querySelector(".panel-title strong");
  if (panelTitle) {
    panelTitle.textContent = "教学记录";
  }

  if (!state.knowledgeMonths.length) {
    els.archiveTree.innerHTML = '<p class="muted">还没有可展示的教学记录。</p>';
    return;
  }

  const groups = groupKnowledgeMonths(state.knowledgeMonths);
  els.archiveTree.innerHTML = Object.entries(groups)
    .map(([year, months]) => {
      const yearOpen = months.some((month) => month.key === activeMonth);
      const monthButtons = months
        .map((month) => `
          <button class="day-link month-link" type="button" data-month="${escapeAttribute(month.key)}" data-path="${escapeAttribute(month.path)}">
            <span>${Number(month.month)}月</span>
            <span>${month.key === state.knowledgeMonths[0].key ? "最新" : ""}</span>
          </button>
        `)
        .join("");
      return `
        <details ${yearOpen ? "open" : ""}>
          <summary>${year}年</summary>
          ${monthButtons}
        </details>
      `;
    })
    .join("");

  els.archiveTree.querySelectorAll(".month-link").forEach((button) => {
    button.classList.toggle("is-active", button.dataset.month === activeMonth);
    button.addEventListener("click", () => {
      const month = state.knowledgeMonths.find((item) => item.key === button.dataset.month);
      renderKnowledgeArchive(month.key);
      renderKnowledgeMonth(month);
      history.replaceState(null, "", `./?knowledge=1&month=${encodeURIComponent(month.key)}`);
    });
  });
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

async function renderKnowledgeMonth(month) {
  state.activeKnowledgeMonth = month?.key || null;
  els.weekday.textContent = "教学记录";

  if (!month) {
    els.title.textContent = "暂无教学记录";
    els.summary.textContent = "月度教学记录生成后，会在这里按年份和月份归档展示。";
    els.content.innerHTML = `
      <div class="empty-state">
        <div>
          <h2>暂无教学记录</h2>
          <p>请让每日自动化任务生成 <code>knowledge_log/manifest.json</code> 和对应月度记录文件。</p>
        </div>
      </div>
    `;
    return;
  }

  els.title.textContent = month.title;
  els.summary.textContent = "按月整理每日三个正式讲解概念，并为后续讲解留下参考线索。";
  els.content.innerHTML = `
    <div class="loading-state">
      <span class="loader" aria-hidden="true"></span>
      <p>正在读取${Number(month.month)}月教学记录...</p>
    </div>
  `;

  try {
    const response = await fetch(month.path, { cache: "no-store" });
    if (!response.ok) {
      throw new Error(`Knowledge log request failed: ${response.status}`);
    }
    const markdown = await response.text();
    const table = extractKnowledgeTable(markdown);
    if (!table) {
      throw new Error("No table found in knowledge log.");
    }
    els.content.innerHTML = `
      <div class="knowledge-log-view">
        <div class="knowledge-log-header">
          <h2>${escapeHtml(month.title)}</h2>
          <a class="primary-link" href="${escapeAttribute(month.path)}">打开原始记录</a>
        </div>
        <div class="knowledge-table-wrap">${table}</div>
      </div>
    `;
    resolveEmbeddedLinks(els.content.querySelector(".knowledge-table-wrap"), month.path);
  } catch (error) {
    console.info("Unable to render knowledge log.", error);
    els.content.innerHTML = `
      <div class="empty-state">
        <div>
          <h2>暂无教学记录</h2>
          <p>未能读取当前月份的教学记录文件。</p>
        </div>
      </div>
    `;
  }
}

function extractKnowledgeTable(markdown) {
  const match = markdown.match(/<table[\s\S]*?<\/table>/i);
  return match ? match[0] : "";
}

function resolveEmbeddedLinks(container, sourcePath) {
  const sourceUrl = new URL(sourcePath, location.href);
  container.querySelectorAll("a[href]").forEach((anchor) => {
    const href = anchor.getAttribute("href");
    if (!href || /^(https?:|mailto:|#)/i.test(href)) {
      return;
    }
    anchor.href = new URL(href, sourceUrl).href;
  });
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

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}
