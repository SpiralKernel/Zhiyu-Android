/** 练习识图导入：上传、原页预览、逐题核对与进入 AI 讨论。 */
export function createImportUI(ui, teacher) {
  const { S, el, btn, field, select, api, action, error, refresh, render } = ui;
  let material = null,
    files = [],
    mode = "completed",
    items = [],
    history = [],
    timer = null,
    pageStart = 1,
    pageEnd = 0;
  function reset() {
    clearTimeout(timer);
    material = null;
    files = [];
    items = [];
    history = [];
    mode = "completed";
  }
  function assign(value) {
    material = value;
    items = value.items.map((t) => ({
      ...t,
      verdict:
        value.mode === "blank"
          ? "unanswered"
          : t.verdict && t.reviewed
            ? t.verdict
            : t.suggested_verdict,
      reviewed: !!t.reviewed,
    }));
  }
  function poll() {
    const id = material?.id;
    clearTimeout(timer);
    timer = setTimeout(async () => {
      if (material?.id !== id) return;
      try {
        const value = await api("/imports/" + id);
        if (material?.id !== id) return;
        if (value.status === "processing") {
          material = value;
          if (S.aiPanel === "imports") render();
          poll();
        } else {
          assign(value);
          await refresh();
          if (S.aiPanel === "imports") render();
        }
      } catch (e) {
        if (material?.id === id) error(e.message);
      }
    }, 1200);
  }
  async function upload() {
    if (!files.length) throw new Error("请选择练习图片或PDF。");
    const body = new FormData();
    files.forEach((f) => body.append("files", f));
    body.append("mode", mode);
    body.append("page_start", pageStart);
    body.append("page_end", pageEnd);
    assign(await api("/imports", body));
    files = [];
    render();
  }
  async function recognize() {
    await api("/imports/" + material.id + "/recognize", {});
    material.status = "processing";
    render();
    poll();
  }
  async function confirm() {
    if (items.some((t) => !t.reviewed))
      throw new Error("请逐题核对；看不清的题可以选择无法判断。");
    const body = {
      items: items.map((t) => ({
        id: t.id,
        stem: t.stem,
        diagram_description: t.diagram_description || "",
        student_answer: material.mode === "blank" ? "" : t.student_answer || "",
        reference_answer: t.reference_answer || "",
        knowledge_ids: t.knowledge_ids || [],
        goal_ids: t.goal_ids || [],
        question_type_id: t.question_type_id,
        verdict: material.mode === "blank" ? "unanswered" : t.verdict,
        reviewed: true,
        count_evidence: false,
        assisted: !!t.assisted,
      })),
    };
    assign(await api("/imports/" + material.id + "/confirm", body));
    await refresh();
    render();
  }
  async function restore(id) {
    assign(await api("/imports/" + id));
    if (material.status === "processing") poll();
    render();
  }
  function item(t, index) {
    const locked = material.status === "confirmed";
    const stem = el("textarea", {
      "aria-label": `第${index + 1}题题干`,
      value: t.stem,
      disabled: locked,
      maxLength: 5000,
      onInput: (e) => (t.stem = e.target.value),
    });
    const answer = el("textarea", {
      "aria-label": `第${index + 1}题学生答案`,
      value: t.student_answer || "",
      disabled: locked,
      maxLength: 3000,
      onInput: (e) => (t.student_answer = e.target.value),
    });
    const reference = el("textarea", {
      "aria-label": `第${index + 1}题参考答案`,
      value: t.reference_answer || "",
      disabled: locked,
      maxLength: 3000,
      onInput: (e) => (t.reference_answer = e.target.value),
    });
    const verdict = select(
      `第${index + 1}题评价`,
      [
        ["uncertain", "无法判断"],
        ["correct", "正确"],
        ["incorrect", "错误"],
        ["unanswered", "未作答"],
      ],
      t.verdict,
      (v) => (t.verdict = v),
    );
    verdict.disabled = locked;
    return el(
      "article",
      { class: "import-item" },
      el(
        "div",
        { class: "kicker" },
        el("h3", {}, t.label || `第${index + 1}题`),
        el("span", { class: "badge" }, t.question_type_name || "待分类"),
      ),
      field("核对题干", stem),
      t.diagram_description
        ? el("p", { class: "subtle" }, "图形说明：" + t.diagram_description)
        : null,
      material.mode === "completed" ? field("学生已有答案", answer) : null,
      el(
        "details",
        {},
        el("summary", {}, "参考答案与识别评价"),
        field("核对参考答案", reference),
        el("p", { class: "subtle" }, t.reason || "识别内容仍需核对。"),
      ),
      material.mode === "completed" ? field("核对评价", verdict) : null,
      !locked
        ? el(
            "label",
            { class: "check" },
            el("input", {
              type: "checkbox",
              checked: t.reviewed,
              onChange: (e) => (t.reviewed = e.target.checked),
            }),
            "我已核对这道题",
          )
        : null,
      btn(
        "就这题问 AI",
        () => teacher.discussImport(material.id, t.id, t.stem),
        "quiet",
      ),
    );
  }
  function page() {
    const file = el("input", {
      type: "file",
      accept: "image/png,image/jpeg,image/webp,application/pdf",
      multiple: true,
      "aria-label": "选择练习图片或PDF",
      onChange: (e) => (files = [...e.target.files]),
    });
    return el(
      "section",
      { class: "imports-page" },
      btn(
        "← 返回 知域",
        () => {
          S.aiPanel = null;
          render();
        },
        "quiet",
      ),
      el("p", { class: "eyebrow" }, "识图导入 · 把已有练习带进来"),
      el("h1", {}, "题目不用重新抄。"),
      el(
        "p",
        { class: "subtle" },
        "导入未做习题，或者核对已做试卷，逐题讨论和记录学习情况。",
      ),
      !material
        ? el(
            "section",
            { class: "card upload-card" },
            field(
              "练习类型",
              select(
                "练习类型",
                [
                  ["completed", "已做练习 / 试卷"],
                  ["blank", "未做习题"],
                ],
                mode,
                (v) => (mode = v),
              ),
            ),
            field("选择文件", file),
            el(
              "p",
              { class: "tiny" },
              "最多8张图片或8页PDF，单文件20MB，合计40MB。",
            ),
            el(
              "div",
              { class: "split-fields" },
              field(
                "PDF起始页",
                el("input", {
                  type: "number",
                  min: 1,
                  value: pageStart,
                  onInput: (e) => (pageStart = Number(e.target.value)),
                }),
              ),
              field(
                "PDF结束页（0表示自动）",
                el("input", {
                  type: "number",
                  min: 0,
                  value: pageEnd,
                  onInput: (e) => (pageEnd = Number(e.target.value)),
                }),
              ),
            ),
            btn("上传并预览", upload, "primary"),
          )
        : el(
            "section",
            {},
            el(
              "section",
              { class: "card" },
              el(
                "div",
                { class: "kicker" },
                el("h2", {}, material.title),
                btn(
                  "导入另一份",
                  () => {
                    clearTimeout(timer);
                    material = null;
                    items = [];
                    render();
                  },
                  "quiet",
                ),
              ),
              el(
                "details",
                {
                  class: "page-previews",
                  open: material.status === "uploaded",
                },
                el("summary", {}, `原页预览 · ${material.page_count}页`),
                material.pages.map((p) =>
                  el("img", {
                    src: p.url,
                    alt: p.label,
                    class: "import-preview",
                    loading: "lazy",
                  }),
                ),
              ),
              material.status === "uploaded" || material.status === "failed"
                ? el(
                    "div",
                    {},
                    material.error
                      ? el("p", { class: "inline-error" }, material.error)
                      : null,
                    el(
                      "p",
                      { class: "subtle" },
                      "确认页面清晰后发送给AI识别。",
                    ),
                    btn(
                      material.status === "failed" ? "重试识别" : "开始识图",
                      recognize,
                      "primary",
                    ),
                  )
                : null,
              material.status === "processing"
                ? el(
                    "div",
                    { class: "processing", role: "status" },
                    el("span", { class: "spinner", "aria-hidden": "true" }),
                    "正在识别题目与已有作答，完成后可逐题核对…",
                  )
                : null,
              material.status === "confirmed"
                ? el(
                    "p",
                    { class: "success-note" },
                    "已保存核对结果，学习线索已更新。",
                  )
                : null,
            ),
            items.length
              ? el(
                  "section",
                  {},
                  items.map(item),
                  material.status === "review"
                    ? el(
                        "section",
                        { class: "card" },
                        el(
                          "p",
                          { class: "subtle" },
                          "确认后保存学习线索。空题和无法判断的题不会当作答错。",
                        ),
                        btn("保存核对结果", confirm, "primary"),
                      )
                    : null,
                )
              : null,
          ),
      el(
        "details",
        {
          class: "card history-list",
          open: history.length > 0,
          onToggle: (e) => {
            if (e.target.open && !history.length)
              action(async () => {
                history = (await api("/imports")).items;
                render();
              });
          },
        },
        el("summary", {}, "之前导入的练习"),
        history.map((h) => btn(h.title, () => restore(h.id), "history-item")),
      ),
    );
  }
  return { page, reset };
}
