/** 家长可读的自动学情报告；真实统计图表与有依据的 AI 分析分开呈现。 */
export function createReportUI(ui) {
  const { S, el, btn, select, api, error, render } = ui;
  let data = null,
    period = "week",
    analyzing = false,
    analysisError = "",
    version = 0;
  let analyzingVersion = -1;
  function reset() {
    data = null;
    analyzing = false;
    analysisError = "";
    version++;
  }
  async function open(next = period) {
    period = next;
    const own = ++version;
    const result = await api("/reports?" + new URLSearchParams({ period }));
    if (own !== version) return;
    data = result;
    S.mode = "report";
    analysisError = "";
    render();
    if (data.analysis_source !== "ai") void analyze(own);
  }
  async function analyze(own = version) {
    if (analyzing && analyzingVersion === own) return;
    analyzingVersion = own;
    analyzing = true;
    render();
    try {
      const result = await api("/reports/analyze", { period });
      if (own === version) data = result;
    } catch (e) {
      if (own === version) analysisError = e.message;
    } finally {
      if (own === version) {
        analyzing = false;
        if (S.mode === "report") render();
      }
    }
  }
  function stat(label, value, description) {
    return el(
      "div",
      { class: "report-stat" },
      el("p", {}, label),
      el("strong", {}, value),
      el("small", {}, description),
    );
  }
  function chapters() {
    return el(
      "section",
      { class: "card report-chapters" },
      el(
        "div",
        { class: "section-heading" },
        el("h2", {}, "每一章，学到了哪里"),
        el(
          "p",
          { class: "subtle" },
          "截至当前的题型分布；未评估代表缺少证据。",
        ),
      ),
      el(
        "div",
        { class: "chart-legend" },
        [
          ["stable", "表现稳定"],
          ["weak", "需要补强"],
          ["learning", "学习中 / 证据不足"],
          ["unknown", "未评估"],
        ].map(([key, text]) =>
          el("span", {}, el("i", { class: "dot " + key }), text),
        ),
      ),
      data.chapters.map((c) =>
        el(
          "div",
          { class: "chapter-bar-row" },
          el(
            "div",
            { class: "chapter-label" },
            el("span", {}, c.name),
            el("small", {}, `${c.total}种题型`),
          ),
          el(
            "div",
            {
              class: "stacked-bar",
              role: "img",
              "aria-label": `${c.name}：稳定${c.stable}，需补强${c.weak}，学习中${c.learning}，未评估${c.unknown}`,
            },
            ["stable", "weak", "learning", "unknown"].map((key) =>
              c[key]
                ? el(
                    "span",
                    {
                      class: key,
                      style: `width:${(c[key] / Math.max(1, c.total)) * 100}%`,
                      title: String(c[key]),
                    },
                    c[key] >= 3 ? c[key] : "",
                  )
                : null,
            ),
          ),
          c.total === 0
            ? el("p", { class: "tiny" }, "该章节尚未形成细分题型记录。")
            : null,
        ),
      ),
    );
  }
  function trend() {
    const values = data.trend.slice(-14),
      max = Math.max(
        1,
        ...values.map((v) => v.independent + v.assisted + v.other),
      );
    return el(
      "section",
      { class: "card report-trend" },
      el("h2", {}, "练习的脚步"),
      el(
        "p",
        { class: "subtle" },
        "按有作答记录的日期展示，区分独立完成与辅助作答。",
      ),
      values.length
        ? el(
            "div",
            { class: "trend-chart", role: "img", "aria-label": "每日练习次数" },
            values.map((v) =>
              el(
                "div",
                { class: "trend-column" },
                el(
                  "span",
                  { class: "trend-count" },
                  v.independent + v.assisted + v.other,
                ),
                el(
                  "div",
                  {
                    class: "trend-stack",
                    style: `height:${Math.max(8, ((v.independent + v.assisted + v.other) / max) * 110)}px`,
                  },
                  v.independent
                    ? el("span", {
                        class: "stable",
                        style: `flex:${v.independent}`,
                      })
                    : null,
                  v.assisted
                    ? el("span", { class: "weak", style: `flex:${v.assisted}` })
                    : null,
                  v.other
                    ? el("span", {
                        class: "learning",
                        style: `flex:${v.other}`,
                      })
                    : null,
                ),
                el("small", {}, v.day.slice(5)),
              ),
            ),
          )
        : el(
            "p",
            { class: "empty" },
            "还没有这一时间段的题库作答。提问和导入也会记录，继续学习后再看变化。",
          ),
    );
  }
  function page() {
    if (!data) return el("p", { class: "empty" }, "正在整理学情…");
    const a = data.analysis;
    const names = new Map(data.types.map((t) => [t.id, t.name]));
    return el(
      "section",
      { class: "report-page" },
      el(
        "div",
        { class: "report-heading" },
        el(
          "div",
          {},
          el("p", { class: "eyebrow" }, "给家长的一份学习观察"),
          el("h1", {}, "学习报告"),
          el(
            "p",
            { class: "subtle" },
            `${data.student.nickname} · ${data.stage === "senior" ? data.book_title : `${data.student.grade}年级${data.subject === "physics" && data.student.grade === 9 ? (data.student.term === 1 ? "全一册·前半进度" : "全一册·后半进度") : (data.student.term === 1 ? "上册" : "下册")}${data.subject_name || "数学"}`} · ${data.period_label}`,
          ),
        ),
        el(
          "div",
          { class: "report-controls" },
          select(
            "报告时间",
            [
              ["week", "最近7天"],
              ["month", "最近30天"],
              ["all", "累计记录"],
            ],
            period,
            (v) => open(v).catch((e) => error(e.message)),
          ),
          el(
            "a",
            {
              class: "button-link",
              href: "/api/v1/reports/pdf?" + new URLSearchParams({ period }),
              download: "知域-learning-report.pdf",
            },
            "导出 PDF",
          ),
        ),
      ),
      el(
        "div",
        { class: "report-stats" },
        stat("题库作答", data.summary.attempts, "保存的练习次数"),
        stat("独立练习", data.summary.independent, "不同题目的有效证据"),
        stat("主动提问", data.summary.questions, "提问与讨论"),
        stat("导入题目", data.summary.imported, "已核对的已有练习"),
      ),
      chapters(),
      trend(),
      data.review_queue?.length
        ? el(
            "section",
            { class: "card" },
            el("h2", {}, "值得再检查一下"),
            el(
              "p",
              { class: "subtle" },
              "这些题型距上次独立验证较久。建议用新题复测，不表示已经不会。",
            ),
            data.review_queue.map((t) => el("p", {}, t.name)),
          )
        : null,
      el(
        "section",
        { class: "card report-analysis" },
        el(
          "div",
          { class: "kicker" },
          el("h2", {}, "AI 学情分析"),
          el(
            "span",
            { class: "badge" },
            analyzing
              ? "正在生成"
              : data.analysis_source === "ai"
                ? "已结合学习证据"
                : "先看记录摘要",
          ),
        ),
        el("p", { class: "analysis-lead" }, a.summary),
        analyzing
          ? el(
              "p",
              { class: "subtle", role: "status" },
              "正在结合练习与提问记录分析，图表已可查看。",
            )
          : null,
        analysisError
          ? el(
              "div",
              { class: "analysis-error" },
              el(
                "p",
                { class: "subtle" },
                analysisError + "；下方保留记录摘要。",
              ),
              btn("重试 AI分析", () => analyze(), "quiet"),
            )
          : null,
        a.strengths?.length
          ? el(
              "div",
              { class: "report-findings" },
              el("h3", {}, "值得看到的进展"),
              a.strengths.map((t) => el("p", {}, t)),
            )
          : null,
        a.focus?.map((f) =>
          el(
            "article",
            { class: "focus-card" },
            el("h3", {}, names.get(f.type_id) || "重点关注"),
            el("p", {}, f.finding),
            el(
              "details",
              {},
              el("summary", {}, "查看判断依据"),
              f.evidence_ids.map((id) => {
                const e = data.evidence.find((e) => e.id === id);
                return el("p", { class: "subtle" }, e?.quote || e?.stem || id);
              }),
            ),
          ),
        ),
        el(
          "div",
          { class: "report-actions-grid" },
          el(
            "section",
            {},
            el("h3", {}, "家长可以这样支持"),
            el(
              "ol",
              {},
              a.parent_actions.map((t) => el("li", {}, t)),
            ),
          ),
          el(
            "section",
            {},
            el("h3", {}, "接下来怎么学"),
            el(
              "ol",
              {},
              a.next_steps.map((t) => el("li", {}, t)),
            ),
          ),
        ),
        el("p", { class: "report-boundary" }, a.uncertainty),
      ),
      el(
        "section",
        { class: "card" },
        el("h2", {}, "题型观察"),
        data.types.length
          ? data.types.map((t) =>
              el(
                "div",
                { class: "type-row" },
                el(
                  "div",
                  {},
                  el("h3", {}, t.name),
                  el(
                    "p",
                    {},
                    `${t.independent_count}道有效独立练习 · ${t.observation_count || 0}条学习线索`,
                  ),
                ),
                el(
                  "span",
                  { class: "badge" },
                  t.current_status || t.learning_status || t.status,
                ),
              ),
            )
          : el(
              "p",
              { class: "empty" },
              "尚未形成题型观察，先从一次提问或练习开始。",
            ),
      ),
      el(
        "p",
        { class: "report-footnote" },
        `更新于 ${new Date(data.generated_at).toLocaleString("zh-CN")} · 报告依据真实记录生成，不提供能力百分比。`,
      ),
    );
  }
  return { page, open, reset };
}
