/** 知域页面与题目内的即时提问面板。 */
export function createTeacherUI(ui) {
  const { S, el, btn, field, api, action, error, refresh, render, math } = ui;
  const starters=['从哪一步开始？','把问题展开看看。','哪里还没想明白？','一起找找思路。','今天想弄懂什么？'];
  const shared=['帮我把题意拆成几个条件','先给一个提示，不要直接给答案','我应该从哪里入手？','这一步为什么成立？','能换一种方法解释吗？','举一个容易混淆的反例','如何检查我的答案？','这类题最容易错在哪里？','帮我区分已知条件和所求','能用图示解释这个概念吗？','我想先自己想，请问我一个引导问题','这道题有哪些隐含条件？','帮我检查推理有没有跳步','能给我一个更简单的例子吗？','这个方法适用于哪些情况？','请用一个生活中的例子解释'];
  const subjectPrompts={math:['等式两边为什么可以做相同的运算？','怎样判断一个反例是否有效？','代数解法和几何思路怎么联系？','怎样检查计算中的符号错误？','文字条件怎么转成数学关系？','答案需要讨论不同情况吗？'],physics:['怎样选取研究对象？','这个公式有哪些适用条件？','如何检查单位是否一致？','图像的斜率表示什么？','实验中哪些变量需要控制？','怎样判断测量误差来自哪里？']};
  const sample=items=>[...items].map(v=>({v,k:Math.random()})).sort((a,b)=>a.k-b.k).slice(0,3).map(x=>x.v);
  function suggestions(target,prefix){
    target.prompts??=sample([...shared,...(subjectPrompts[S.student.subject]||subjectPrompts.math)]);
    return el('div',{class:'quick-prompts'},target.prompts.map(t=>btn(t,()=>{target.draft=t;render();document.querySelector('#'+prefix+'-teacher-text')?.focus();},'quiet')));
  }
  const empty = () => ({
    threadId: null,
    messages: [],
    draft: "",
    files: [],
    context: {},
    requestId: null,
    title:starters[Math.floor(Math.random()*starters.length)],
  });
  let main = empty(),
    drawer = null,
    history = [];
  function reset() {
    main = empty();
    drawer = null;
    history = [];
  }
  async function open(context) {
    if (!drawer || drawer.context.attempt_id !== context.attempt_id)
      drawer = { ...empty(), context };
    drawer.open = true;
    render();
    document.querySelector("#drawer-teacher-text")?.focus();
  }
  function close() {
    if (drawer) drawer.open = false;
    const y = scrollY;
    render();
    requestAnimationFrame(() => scrollTo({ top: y }));
  }
  async function newChat() {
    main = empty();
    render();
    document.querySelector("#main-teacher-text")?.focus();
  }
  async function loadHistory() {
    history = (await api("/teacher/threads")).items;
    render();
  }
  async function restore(id) {
    const value = await api("/teacher/threads/" + id);
    main = {
      ...empty(),
      threadId: id,
      messages: value.items,
      context: value.context,
    };
    render();
  }
  function entry(label, description, mark, fn) {
    return el(
      "button",
      { type: "button", class: "teacher-entry", onClick: () => action(fn) },
      el("span", { class: "entry-mark", "aria-hidden": "true" }, mark),
      el("span", {}, el("strong", {}, label), el("small", {}, description)),
      el("span", { "aria-hidden": "true" }, "↗"),
    );
  }
  function imageConfirmation(item, target) {
    const response = item.response;
    if (!response.images?.length || !response.transcribed_answer) return null;
    if (response.image_confirmation)
      return el("small", {}, "图片作答已核对，后续讨论会参考核对后的内容。");
    item.imageQuestion ??= response.recognized_question || "";
    item.imageAnswer ??= response.transcribed_answer;
    return el(
      "details",
      { class: "recognized-question" },
      el("summary", {}, "核对图片中的作答"),
      el(
        "p",
        {},
        "先核对题干和你的作答，确认后再用于学情判断。看不清的内容可以修改。",
      ),
      el("textarea", {
        "aria-label": "核对图片题干",
        value: item.imageQuestion,
        maxLength: 5000,
        onInput: (e) => {
          item.imageQuestion = e.target.value;
          item.imageRequestId = null;
        },
      }),
      el("textarea", {
        "aria-label": "核对图片作答",
        value: item.imageAnswer,
        maxLength: 12000,
        onInput: (e) => {
          item.imageAnswer = e.target.value;
          item.imageRequestId = null;
        },
      }),
      btn("确认作答并分析", async () => {
        if (!item.imageQuestion.trim() || !item.imageAnswer.trim())
          throw new Error("请补全并核对图片题干和作答。");
        item.imageRequestId ||= crypto.randomUUID();
        const value = await api(
          `/teacher/threads/${target.threadId}/messages/${response.message_id}/confirm-image`,
          {
            reviewed: true,
            recognized_question: item.imageQuestion,
            student_answer: item.imageAnswer,
            request_id: item.imageRequestId,
          },
        );
        response.image_confirmation = { message_id: value.message_id };
        if (
          !target.messages.some(
            (m) => m.response.message_id === value.message_id,
          )
        )
          target.messages.push({
            message: "请检查我核对后的图片作答。",
            response: value,
          });
        await refresh();
        render();
      }),
    );
  }
  function messages(target) {
    return el(
      "div",
      { class: "teacher-messages", "aria-live": "polite" },
      target.messages.length
        ? target.messages.map((item) =>
            el(
              "article",
              { class: "dialogue-pair" },
              el(
                "div",
                { class: "message user" },
                el("div", { class: "author" }, "我"),
                el("div", {}, item.message),
                (item.response.images || []).map((im) =>
                  el("img", {
                    src: im.url,
                    alt: "本次提问的题目图片",
                    class: "chat-photo",
                    loading: "lazy",
                  }),
                ),
              ),
              el(
                "div",
                { class: "message" },
                el("div", { class: "author" }, "知域"),
                item.response.recognized_question
                  ? el(
                      "details",
                      { class: "recognized-question" },
                      el("summary", {}, "识别到的题目"),
                      el("p", {}, item.response.recognized_question),
                    )
                  : null,
                el("div", { class: "reply" }, item.response.reply),
                imageConfirmation(item, target),
                item.response.check_question
                  ? el(
                      "div",
                      { class: "check-question" },
                      item.response.check_question,
                    )
                  : null,
                (item.response.observations || []).map((note) =>
                  el(
                    "div",
                    { class: "learning-note" },
                    el(
                      "span",
                      {},
                      ({
                        resolved: "已改善的历史记录",
                        expired: "历史线索，待重新确认",
                        superseded: "已由后续记录替代",
                        legacy_unverified: "历史线索，尚待核实",
                        invalid_time: "历史线索，尚待核实",
                      }[note.memory_status] || "已记录") +
                        " · " +
                        note.note,
                    ),
                    note.dismissed
                      ? el("small", {}, "已撤回")
                      : btn(
                          "记录不准确",
                          async () => {
                            await api(
                              "/teacher/observations/" + note.id + "/dismiss",
                              {},
                            );
                            note.dismissed = true;
                            await refresh();
                            render();
                          },
                          "note-dismiss",
                        ),
                  ),
                ),
                item.response.state_update?.rejected?.length
                  ? el(
                      "small",
                      {},
                      item.response.boundary?.blocked
                        ? "本轮没有更新学情，可以继续提问知识或题目。"
                        : item.response.state_update.review_unavailable
                        ? "学情复核暂未完成，本次讲解已保存，相关学习状态暂未更新。"
                        : "部分学习判断的依据还不足，暂未记录；可以继续解释你的思路。",
                    )
                  : null,
              ),
            ),
          )
        : el(
            "div",
            { class: "teacher-empty" },
            el("span", { "aria-hidden": "true" }, "✦"),
            el("p", {}, target.title),
            target===main?suggestions(target,"main"):null,
          ),
    );
  }
  async function send(target) {
    const message =
      target.draft.trim() ||
      (target.files.length ? "请帮我理解这道图片题。" : "");
    if (!message) throw new Error("写下你的问题，或上传题目照片。");
    target.requestId ||= crypto.randomUUID();
    const body = {
      message,
      thread_id: target.threadId,
      request_id: target.requestId,
      ...target.context,
      student_draft: target.context.attempt_id ? S.answer : "",
    };
    target.pending = true;
    render();
    let response;
    try {
      if (target.files.length) {
        const data = new FormData();
        for (const [k, v] of Object.entries(body))
          if (v !== null && v !== undefined) data.append(k, v);
        target.files.forEach((f) => data.append("files", f));
        response = await api("/teacher/photo", data);
      } else response = await api("/teacher/chat", body);
    } finally {
      target.pending = false;
      render();
    }
    target.threadId = response.thread_id;
    target.messages.push({ message, response });
    target.draft = "";
    target.files = [];
    target.requestId = null;
    await refresh();
    render();
    document
      .querySelector(
        target === main ? "#main-teacher-text" : "#drawer-teacher-text",
      )
      ?.focus();
  }
  function composer(target, prefix) {
    const text = el("textarea", {
      id: prefix + "-teacher-text",
      "aria-label": prefix === "main" ? "向 AI 提问" : "就这道题向 AI 提问",
      value: target.draft,
      maxLength: 1600,
      placeholder: target.prompts?.[0] || shared[Math.floor(Math.random()*shared.length)],
      onInput: (e) => {
        target.draft = e.target.value;
        target.requestId = null;
      },
    });
    const file = el("input", {
      id: prefix + "-teacher-photo",
      type: "file",
      accept: "image/png,image/jpeg,image/webp",
      multiple: true,
      class: "visually-hidden",
      "aria-label": prefix === "main" ? "拍照问题目" : "为这道题添加图片",
      onChange: (e) => {
        const files = [...e.target.files];
        if (files.length > 4) {
          e.target.value = "";
          error("每次最多4张图片。");
          return;
        }
        target.files = files;
        target.requestId = null;
        render();
        document.querySelector("#" + prefix + "-teacher-text")?.focus();
      },
    });
    return el(
      "form",
      {
        class: "teacher-composer",
        onSubmit: (e) => {
          e.preventDefault();
          action(() => send(target));
        },
      },
      text,
      target.pending
        ? el(
            "p",
            { class: "thinking-note", role: "status" },
            "知域正在思考，请稍候…",
          )
        : null,
      file,
      target.files.length
        ? el(
            "div",
            { class: "attachments" },
            el("span", {}, `已选择 ${target.files.length} 张图片`),
            btn(
              "移除图片",
              () => {
                target.files = [];
                render();
              },
              "quiet",
            ),
          )
        : null,
      el(
        "div",
        { class: "composer-toolbar" },
        el(
          "label",
          { class: "photo-trigger", htmlFor: prefix + "-teacher-photo" },
          "＋ 图片",
        ),

        el("button", { type: "submit", class: "primary" }, "发送问题"),
      ),
    );
  }
  function page() {
    return el(
      "section",
      { class: "teacher-page" },
      el(
        "div",
        { class: "teacher-hero" },
        el("p", { class: "eyebrow" }, "知域 · 随时提问，慢慢理解"),
        el("h1", {}, "问 AI"),
        el(
          "p",
          { class: "subtle" },
          `${S.student.nickname}，问知识、拍题目，或者一起看懂卡住的那一步。`,
        ),
      ),
      el(
        "div",
        { class: "teacher-entries" },
        entry("问知识", "把概念讲明白", "知", () =>
          document.querySelector("#main-teacher-text")?.focus(),
        ),
        entry("拍照问题", "读懂题意和思路", "题", () =>
          document.querySelector("#main-teacher-photo")?.click(),
        ),
        entry("导入练习", "已有习题与已做试卷", "练", () => {
          S.aiPanel = "imports";
          render();
        }),
      ),
      el(
        "section",
        { class: "card teacher-chat" },
        el(
          "div",
          { class: "kicker" },
          el(
            "h2",
            {},
            main.context.source ? "围绕这道题" : "",
          ),
          btn("新提问", newChat, "quiet"),
        ),
        main.context.source
          ? el("p", { class: "tiny" }, "这段讨论关联一份已识别的练习。")
          : null,
        messages(main),
        composer(main, "main"),
      ),
      el(
        "details",
        {
          class: "card history-list",
          open: history.length > 0,
          onToggle: (e) => {
            if (e.target.open && !history.length) action(loadHistory);
          },
        },
        el("summary", {}, "最近的提问"),
        history.map((h) => btn(h.title, () => restore(h.id), "history-item")),
      ),
    );
  }
  function panel() {
    if (!drawer?.open) return null;
    const node = el(
      "div",
      { class: "teacher-drawer-shade" },
      el(
        "section",
        {
          class: "teacher-drawer",
          role: "dialog",
          "aria-modal": "true",
          "aria-label": "这道题的讨论",
        },
        el(
          "div",
          { class: "kicker" },
          el(
            "div",
            {},
            el("p", { class: "eyebrow" }, "题目内即时提问"),
            el("h2", {}, drawer.title),
          ),
          btn("关闭问答", close, "quiet"),
        ),
        el("p", { class: "subtle" }, "当前题目和你已写的解答会作为讨论上下文。"),
        suggestions(drawer,"drawer"),
        messages(drawer),
        composer(drawer, "drawer"),
      ),
    );
    node.addEventListener("click", (e) => {
      if (e.target === node) close();
    });
    node.addEventListener("keydown", (e) => {
      if (e.key === "Escape") close();
      if (e.key === "Tab") {
        const items = [
          ...node.querySelectorAll("button,textarea,input"),
        ].filter((n) => !n.disabled && n.offsetParent !== null);
        if (e.shiftKey && document.activeElement === items[0]) {
          e.preventDefault();
          items.at(-1)?.focus();
        } else if (!e.shiftKey && document.activeElement === items.at(-1)) {
          e.preventDefault();
          items[0]?.focus();
        }
      }
    });
    return node;
  }
  function discussImport(importId, itemId, stem) {
    main = {
      ...empty(),
      context: { source: "import", import_id: importId, item_id: itemId },
      draft: "请帮我理解这道题：" + stem.slice(0, 300),
    };
    S.aiPanel = null;
    S.mode = "ai";
    render();
  }
  async function showHistory() {
    await loadHistory();
    document.querySelector(".history-list")?.scrollIntoView({block:"start",behavior:"smooth"});
  }
  return { page, panel, open, reset, discussImport, close, showHistory };
}
