import { createWritingUI } from './writing.js';
import { createAppSettings } from './app-settings.js';
import { icon, initAppearance } from "./appearance.js";
import { createTeacherUI } from "./teacher.js";
import { createImportUI } from "./imports.js";
import { createReportUI } from "./report.js";
/* 学生页面仅依赖 study 与 auth API；凭证由 HttpOnly 会话 Cookie 保存。 */
(() => {
  "use strict";
  const appearance = initAppearance();
  let activeDialog = null, renderPending = false;
  const root = document.querySelector("#root"),
    notice = document.querySelector("#notice");
  const S = {
    student: null,
    home: null,
    mode: "bank",
    authMode: "login",
    aiPanel: null,
    work: null,
    training: null,
    result: null,
    unit: "",
    written: false,
    choice: false,
    challenge: true,
    aiType: "",
    messages: [],
    draft: "",
    files: [],
    answer: "",
    partAnswers: {},
    choices: [],
    review: null,
    epoch: 0,
    busy: false,
  };
  const ui = {
    S,
    el,
    btn,
    field,
    select,
    api,
    action,
    error,
    refresh,
    render,
    math,
    dialog,
  };
  const appSettings=createAppSettings(ui,appearance);
  const writingUI=createWritingUI(ui);
  const teacherUI = createTeacherUI(ui);
  const importUI = createImportUI(ui, teacherUI);
  const reportUI = createReportUI(ui);
  let noticeTimer;
  function el(tag, attrs = {}, ...children) {
    const n = document.createElement(tag);
    for (const [key, val] of Object.entries(attrs)) {
      if (val === null || val === undefined || val === false) continue;
      if (key.startsWith("on"))
        n.addEventListener(key.slice(2).toLowerCase(), val);
      else if (key === "class") n.className = val;
      else if (key in n) n[key] = val;
      else n.setAttribute(key, val);
    }
    for (const c of children.flat(Infinity)) {
      if (c !== null && c !== undefined && c !== false)
        n.append(c instanceof Node ? c : document.createTextNode(String(c)));
    }
    return n;
  }
  function error(message) {
    notice.textContent = message;
    notice.hidden = false;
    clearTimeout(noticeTimer);
    noticeTimer = setTimeout(() => (notice.hidden = true), 7000);
  }
  async function api(path, body, method) {
    const epoch = S.epoch;
    const options = {
      method: method || (body ? "POST" : "GET"),
      credentials: "same-origin",
      headers: {},
    };
    if (body instanceof FormData) options.body = body;
    else if (body) {
      options.headers["Content-Type"] = "application/json";
      options.body = JSON.stringify(body);
    }
    const res = await fetch("/api/v1" + path, options);
    const value = await res.json();
    if (epoch !== S.epoch) throw new Error("学习账号已切换，请重新操作。");
    if (!res.ok) {
      if (res.status === 401 && S.student) {
        reset();
        render();
      }
      throw new Error(
        typeof value.detail === "string"
          ? value.detail
          : "输入有误，请检查后重试。",
      );
    }
    return value;
  }
  async function action(fn) {
    if (S.busy) return;
    S.busy = true;
    notice.hidden = true;
    root.querySelectorAll("button").forEach((b) => (b.disabled = true));
    try {
      await fn();
    } catch (e) {
      error(e.message);
    } finally {
      S.busy = false;
      root.querySelectorAll("button").forEach((b) => (b.disabled = false));
    }
  }
  function btn(text, fn, cls = "") {
    return el(
      "button",
      { type: "button", class: cls, onClick: () => action(fn) },
      text,
    );
  }
  function field(text, input) {
    return el("label", { class: "field" }, el("span", {}, text), input);
  }
  function select(label, options, value, onChange) {
    const n = el(
      "select",
      { "aria-label": label, onChange: (e) => onChange(e.target.value) },
      options.map(([v, t]) => el("option", { value: v }, t)),
    );
    n.value = value;
    return n;
  }
  function brand() {
    return el(
      "div",
      { class: "brand" },
      icon("brand"),
      "知域",
    );
  }
  function math(n) {
    if (window.renderMathInElement)
      window.renderMathInElement(n, {
        delimiters: [
          { left: "$$", right: "$$", display: true },
          { left: "\\[", right: "\\]", display: true },
          { left: "$", right: "$", display: false },
          { left: "\\(", right: "\\)", display: false },
        ],
        throwOnError: false,
        trust: false,
      });
  }
  function reset() {
    S.epoch++;
    teacherUI.reset();
    writingUI.reset();
    importUI.reset();
    reportUI.reset();
    S.aiPanel = null;
    Object.assign(S, {
      student: null,
      home: null,
      work: null,
      training: null,
      result: null,
      messages: [],
      files: [],
      draft: "",
      answer: "",
      partAnswers: {},
      choices: [],
      review: null,
      aiType: "",
      mode: "bank",
      unit: "",
      written: false,
      choice: false,
    });
    notice.hidden = true;
  }
  async function load() {
    const session = await api("/auth/session");
    S.student = session.student;
    S.mobile = session.mobile === true;
    S.availableBooks = session.available_books || [];
    S.registrationEnabled = session.registration_enabled !== false;
    S.inviteRequired = session.registration_requires_invite === true;
    S.authMode = session.needs_setup && S.registrationEnabled ? "register" : "login";
    S.needsSetup = session.needs_setup;
    if (S.student) {
      const preferences=await appSettings.load();
      const book=S.student.stage==='senior'?S.student.book_id:`${S.student.subject||'math'}-${S.student.grade}-${S.student.term}`;
      const practice=preferences.profile.practice?.[book];
      if(practice)Object.assign(S,{written:practice.format==='written',choice:practice.format==='choice',unit:practice.unit,challenge:practice.challenge});
      S.home = await api("/study/home");
      S.training = (await api("/study/training-plans")).plan;
    }
    render();
    if (S.student && !S.work && S.mode === "bank") {
      try { await start(); } catch(e) { S.startError = e.message; render(); }
    }
  }
  function stageFields(grade = 7, term = 1, subject = "math", level = "junior", bookId = "") {
    grade = grade || 7; term = term || 1;
    const remembered = { [subject]: {grade, term} };
    const rememberedBooks = { [subject]: bookId };
    let current = subject;
    const g = select("年级", [], grade, () => {});
    const t = select("学期", [], term, () => {});
    const book = select("高中教材册次", [], bookId, () => {});
    const juniorFields = el("div", {class:"split-fields"}, field("学习年级",g), field("册次 / 进度",t));
    const seniorFields = field("教材册次",book);
    const levelSelect = select("学段", [["junior","初中"],["senior","高中"]], level, () => refill());
    const refill = () => {
      juniorFields.hidden = levelSelect.value !== "junior";
      seniorFields.hidden = levelSelect.value !== "senior";
      const books = (S.availableBooks || []).filter(b => b.subject === current);
      book.replaceChildren(...books.map(b => el("option", {value:b.id}, b.title)));
      if (books.some(b => b.id === rememberedBooks[current])) book.value = rememberedBooks[current];
      const saved = remembered[current] || {grade: current === "physics" ? 8 : 7, term: 1};
      g.replaceChildren(...(current === "physics" ? [[8,"八年级"],[9,"九年级"]] : [[7,"七年级"],[8,"八年级"],[9,"九年级"]]).map(([v,n]) => el("option", {value:v}, n)));
      g.value = saved.grade;
      const terms = () => {
        const all = current === "physics" && Number(g.value) === 9;
        t.replaceChildren(el("option", {value:1}, all ? "全一册 · 前半进度" : "上册"), el("option", {value:2}, all ? "全一册 · 后半进度" : "下册"));
        t.value = saved.term;
      };
      g.onchange = terms; terms();
    };
    const sub = select("科目", [["math","数学"],["physics","物理"]], current, () => {
      remembered[current] = {grade:Number(g.value),term:Number(t.value)};
      rememberedBooks[current] = book.value;
      current = sub.value; refill();
    });
    refill();
    return {
      node: el("div", {}, field("学段",levelSelect), field("科目", sub), juniorFields, seniorFields),
      get: () => levelSelect.value === "senior"
        ? {subject:current,stage:"senior",book_id:book.value}
        : {subject:current,stage:"junior",grade:Number(g.value),term:Number(t.value)},
    };
  }
  function subjectName() { return S.student?.subject === "physics" ? "物理" : "数学"; }
  function stageName() {
    if (S.student.stage === "senior") return S.student.book_title || "高中";
    if (S.student.subject === "physics" && S.student.grade === 9) return `九年级全一册 · ${S.student.term === 1 ? "前半" : "后半"}进度`;
    return `${S.student.grade}年级${S.student.term === 1 ? "上" : "下"}册`;
  }
  function login() {
    const register = S.authMode === "register";
    const name = el("input", {
      name: "username",
      autocomplete: "username",
      minLength: 2,
      maxLength: 40,
      required: true,
      placeholder: "输入用户名",
    });
    const password = el("input", {
      name: "password",
      type: "password",
      autocomplete: register ? "new-password" : "current-password",
      minLength: 8,
      maxLength: 128,
      required: true,
      placeholder: "至少 8 位",
    });
    const nickname = el("input", {
      name: "nickname",
      autocomplete: "nickname",
      maxLength: 30,
      placeholder: "你希望怎样被称呼？",
    });
    const invite = el("input", {type: "text", required: S.inviteRequired, maxlength: 128, autocomplete: "off", placeholder: "输入一次性邀请码"});
    const stage = stageFields();
    const form = el(
      "form",
      {
        onSubmit: (e) => {
          e.preventDefault();
          action(async () => {
            const body = { username: name.value, password: password.value };
            if (register)
              Object.assign(body, stage.get(), {
                nickname: nickname.value.trim() || "学习者",
                invitation_code: invite.value.trim(),
              });
            await api(register ? "/auth/register" : "/auth/login", body);
            password.value = "";
            await load();
            if(register)await appSettings.connections(true);
          });
        },
      },
      field("用户名", name),
      field("密码", password),
      register ? field("称呼", nickname) : null,
      register && S.inviteRequired ? field("邀请码（仅可使用一次）", invite) : null,
      register ? stage.node : null,
      register && S.needsSetup && !S.mobile
        ? el(
            "p",
            { class: "tiny" },
            "这是本机第一个账号，会继承之前的答题记录。",
          )
        : null,
      el(
        "button",
        { type: "submit", class: "primary full" },
        register ? "创建账号" : "登录",
      ),
    );
    return el(
      "main",
      { class: "login-shell" },
      el(
        "section",
        { class: "welcome" },
        brand(),
        el("h1", {}, "一题，一步。"),
      ),
      el(
        "section",
        { class: "card login-card" },
        el("h2", {}, register ? "创建账号" : "欢迎回来"),

        el(
          "div",
          { class: "login-tabs" },
          btn(
            "登录",
            () => {
              S.authMode = "login";
              render();
            },
            !register ? "badge" : "quiet",
          ),
          S.registrationEnabled ? btn(
            "新建学生",
            () => {
              S.authMode = "register";
              render();
            },
            register ? "badge" : "quiet",
          ) : null,
        ),
        form,
      ),
    );
  }
  async function refresh() {
    S.home = await api("/study/home");
    if (S.training) S.training = await api(`/study/training-plans/${S.training.id}`);
  }
  async function continueTraining() {
    const value = await api(`/study/training-plans/${S.training.id}/next`, {});
    Object.assign(S, {training:value.plan, work:value.work, mode:value.work?"bank":"state", result:null,
      answer:"", partAnswers:{}, choices:[], files:[], review:null});
    await refresh(); render();
    document.querySelector("#work")?.scrollIntoView({block:"start",behavior:"smooth"});
  }
  function trainingCard() {
    const p = S.training;
    return el("section", {class:"card training-card"},
      el("h2", {}, p ? (p.mode === "training" ? "针对加练与独立复测" : "独立诊断 / 复习") : "下一步，练什么？"),
      p ? el("p", {}, `${p.name} · 难度 ${p.difficulty} · ${p.answered} / ${p.total} 题`) : null,
      el("p", {class:"subtle"}, p ? p.reason : "根据独立答题证据安排练习；证据不足时，先做几道核验新题。"),
      p?.ai_reason ? el("p", {class:"tiny"}, `AI计划建议：${p.ai_reason}`) : null,
      p ? el("p", {class:"tiny"}, p.note) : null,
      p?.status === "completed" ? el("p", {}, `本轮已完成。独立复测 / 诊断 ${p.retest_correct} / ${p.retest_answered} 题答对，其中 ${p.independent_retests} 题计入有效独立证据。请结合下方题型状态查看，不以一轮成绩宣布掌握。`) : null,
      el("div", {class:"actions"},
        !p || p.status !== "active" ? btn("安排下一轮", async()=>{
          S.training = await api("/study/training-plans", {}); render();
        }, "primary") : btn(p.answered ? "恢复本轮练习" : `开始${p.training_count ? ` ${p.training_count} 道加练 + ${p.retest_count} 道复测` : ` ${p.retest_count} 道独立新题`}`, continueTraining, "primary"),
        p?.status === "active" ? btn("结束本轮", async()=>{
          await api(`/study/training-plans/${p.id}/cancel`, {});
          if (S.work?.training_plan_id === p.id) {S.work=null; S.result=null;}
          S.training=null; await refresh(); render();
        }, "quiet") : null));
  }
  async function start(typeId = null) {
    const w = await api("/study/next", {
      unit_id: typeId ? null : S.unit || null,
      type_id: typeId,
      written: typeId ? false : S.written,
      choice: typeId ? false : S.choice,
      allow_challenge: S.challenge,
    });
    Object.assign(S, {
      mode: "bank",
      work: w,
      result: null,
      answer: "",
      partAnswers: {},
      choices: [],
      files: [],
      review: w.review?.status === "review" ? w.review : null,
    });
    render();
    document
      .querySelector("#work")
      ?.scrollIntoView({ block: "start", behavior: "smooth" });
  }
  function iconButton(name, label, fn, cls = "") {
    const button = btn(icon(name), fn, `icon-button ${cls}`);
    button.setAttribute("aria-label", label); button.title = label;
    return button;
  }
  function dialog(title, content, cls = "") {
    activeDialog?.();
    const previous = document.activeElement;
    const siblings=[...root.children].map(node=>({node,inert:node.inert}));
    siblings.forEach(({node})=>node.inert=true);
    const shade = el("div", {class:"dialog-shade"});
    const close = () => { shade.remove(); siblings.forEach(({node,inert})=>node.inert=inert); document.removeEventListener("keydown",key); activeDialog=null; previous?.isConnected && previous.focus(); if(renderPending){renderPending=false;render();document.querySelector("#settings-button")?.focus();} };
    const card = el("section", {class:`card dialog-card ${cls}`,role:"dialog","aria-modal":"true","aria-label":title},
      el("div", {class:"kicker"},el("h2", {},title),iconButton("close","关闭",close)), content);
    const key = e => {
      if(e.key === "Escape") { e.preventDefault(); close(); }
      if(e.key !== "Tab") return;
      const items=[...card.querySelectorAll("button,select,input,textarea,a[href],[tabindex='0']")].filter(n=>!n.disabled && n.getClientRects().length);
      const first=items[0],last=items.at(-1);
      if(e.shiftKey && document.activeElement===first){e.preventDefault();last?.focus();}
      else if(!e.shiftKey && document.activeElement===last){e.preventDefault();first?.focus();}
    };
    shade.addEventListener("click",e=>{if(e.target===shade)close();});
    document.addEventListener("keydown",key);shade.append(card);root.append(shade);activeDialog=close;
    card.querySelector("button")?.focus();return close;
  }
  function settings(view = "practice") {
    const draft={unit:S.unit,format:S.written?"written":S.choice?"choice":"numeric",challenge:S.challenge};
    const stage = stageFields(S.student.grade,S.student.term,S.student.subject || "math",S.student.stage || "junior",S.student.book_id || "");
    const body=el("div",{class:"settings-body"});
    const pages={practice:"练习设置",account:"账号",ai:"AI 连接",appearance:"外观",updates:"题库更新"};
    if(view === "practice") {
      const chapter=select("练习章节",[["","全部章节"],...S.home.book.units.map(u=>[u.id,u.name])],draft.unit,v=>draft.unit=v);
      stage.node.addEventListener("change",()=>{
        chapter.disabled=Object.entries(stage.get()).some(([k,v])=>S.student[k]!==v);
        if(chapter.disabled){chapter.value="";draft.unit="";}
      });
      body.append(stage.node,field("章节",chapter),
        field("作答方式",select("作答方式",[["numeric","基础练习"],["choice","选择题"],["written","文字 / 拍照题"]],draft.format,v=>draft.format=v)),
        el("label",{class:"check"},el("input",{type:"checkbox",checked:draft.challenge,onChange:e=>draft.challenge=e.target.checked}),"包含挑战题"),
        btn("开始练习",async()=>{
          const next=stage.get();
          const changed=Object.entries(next).some(([k,v])=>S.student[k]!==v);
          if(changed){
            await api("/auth/stage",next);await api("/settings/practice",{...draft,unit:""},"PUT");close();reset();
            Object.assign(S,{written:draft.format==="written",choice:draft.format==="choice",challenge:draft.challenge});
            await load();
          } else {
            await api('/settings/practice',draft,'PUT');
            Object.assign(S,{unit:draft.unit,written:draft.format==="written",choice:draft.format==="choice",challenge:draft.challenge});
            close();await start();
          }
        },"primary full"));
    } else if(view === "appearance") {
      body.append(appSettings.appearancePanel());
    } else if(view === "ai") {
      appSettings.connections();return;
    } else if(view === "account") {
      body.append(appSettings.accountPanel(()=>{close();settings("account");}),
        btn("退出登录",async()=>{await api("/auth/logout",{});close();reset();await load();},"quiet full"));
    } else {
      const info=el("p",{class:"subtle"},"学习记录会保留。"),actions=el("div",{});
      body.append(info,btn("检查更新",async()=>{
        const value=await api("/content/check");info.textContent=value.message;
        actions.replaceChildren();
        if(value.available)actions.append(btn("下载并更新",async()=>{const r=await api("/content/update",{});await refresh();info.textContent=r.updated?`已更新至 ${r.version}`:"已是最新版本";actions.replaceChildren();},"primary full"));
      },"full"),actions);
    }
    const close=dialog(pages[view],body);
  }
  function bankPage() {
    if(S.work) return workspace();
    return el("section",{class:"practice-empty"},icon("book"),el("h1",{},S.startError?"暂时没有合适的题目":"准备好下一题"),
      S.startError?el("p",{class:"subtle"},S.startError):null,
      btn("开始练习",()=>start(),"primary"),btn("练习设置",()=>settings(),"quiet"));
  }
  function workspace() {
    const w = S.work,
      q = w.question;
    const node = el(
      "section",
      { class: "card question-paper", id: "work" },
      el(
        "div",
        { class: "kicker" },
        el(
          "span",
          { class: "badge" },
          q.difficulty === 3 ? "挑战" : "练习",
        ),
        el(
          "span",
          { class: "subtle" },
          w.type_name || "",
        ),
      ),
      el("div", { class: "question-stem" }, q.diagram?.kind === "square_grid" ? q.stem.split("图形位置：")[0] : q.stem),
    );
    if (w.training_plan_id) node.prepend(el("p", {class:"training-phase"},
      `第 ${w.position} 题 · ${w.training_phase === "training" ? "加练" : "独立复测"}`));
    for (const [index, asset] of (q.assets || []).entries()) {
      const src = typeof asset === "string" ? asset : asset?.url || asset?.src;
      if (!src) continue;
      let url; try { url=new URL(src,location.origin); } catch {continue;}
      if(!["http:","https:"].includes(url.protocol)) continue;
      const image=el("img",{src:url.href,alt:`题目附图 ${index+1}`,class:"question-asset",decoding:"async"});
      const figure=el("figure",{class:"question-figure"},image);
      const expand=iconButton("expand","放大题图",()=>dialog("题目附图",el("div",{class:"image-scroll",tabIndex:0},el("img",{src:url.href,alt:`题目附图 ${index+1}`})),"image-dialog"),"figure-expand");
      image.addEventListener("click",()=>expand.click());
      image.addEventListener("error",()=>{image.hidden=true;expand.hidden=true;figure.append(el("span",{class:"subtle"},"题图加载失败"),btn("重试",()=>{image.hidden=false;expand.hidden=false;image.src=url.href;figure.querySelectorAll("span,button:not(.figure-expand)").forEach(n=>n.remove());},"quiet"));});
      figure.append(expand);node.append(figure);
    }

    if (q.diagram?.kind === "square_grid") {
      const cells = q.diagram.cells;
      const size = 48;
      const width = (Math.max(...cells.map((c) => c.x)) + 1) * size + 8;
      const height = (Math.max(...cells.map((c) => c.y)) + 1) * size + 8;
      const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
      svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
      svg.setAttribute("role", "img");
      svg.setAttribute("aria-label", "正方体展开图，面的位置也列在题干中");
      svg.classList.add("question-diagram");
      for (const cell of cells) {
        const rect = document.createElementNS(svg.namespaceURI, "rect");
        for (const [key, value] of Object.entries({ x: cell.x * size + 4, y: cell.y * size + 4, width: size, height: size, fill: "#F5E2DA", stroke: "#3B3838" }))
          rect.setAttribute(key, String(value));
        const label = document.createElementNS(svg.namespaceURI, "text");
        label.setAttribute("x", String(cell.x * size + size / 2 + 4));
        label.setAttribute("y", String(cell.y * size + size / 2 + 4));
        label.setAttribute("text-anchor", "middle");
        label.setAttribute("dominant-baseline", "central");
        label.setAttribute("fill", "#3B3838");
        label.textContent = cell.label;
        svg.append(rect, label);
      }
      const expand=iconButton("expand","放大题图",()=>{
        const copy=svg.cloneNode(true);copy.classList.remove("question-diagram");copy.style.width=`${Math.max(width,360)}px`;copy.style.height="auto";
        dialog("题目附图",el("div",{class:"image-scroll",tabIndex:0},copy),"image-dialog");
      },"figure-expand");
      svg.addEventListener("click",()=>expand.click());
      node.append(el("figure",{class:"question-figure diagram-figure"},svg,expand));
      const positions = q.stem.split("图形位置：")[1];
      if (positions) node.append(el("details", { class: "tiny" }, el("summary", {}, "查看图形位置说明"), el("p", {}, positions)));
    }
    node.append(
      btn(
        [icon("chat"), "问 AI"],
        () => teacherUI.open({ source: w.source, attempt_id: w.attempt_id }),
        "ask-teacher-button",
      ),
    );
    if(!S.result)node.append(writingUI.paper(w,async file=>{
      const form=new FormData();
      const parts=q.annotation?.parts||[];
      const answer=[parts.filter(p=>S.partAnswers[p.id]?.trim()).map(p=>`${p.id}：${S.partAnswers[p.id]}`).join("\n\n"),S.answer].filter(Boolean).join("\n\n");
      if(answer.length>12000)throw new Error("整题解答合计最多 12000 字");
      if(S.files.length>3)throw new Error("答题纸与照片合计最多四张，请减少照片");
      form.append("answer",answer);S.files.forEach(image=>form.append("files",image));form.append("files",file);
      S.review=await api(`/bank/attempts/${w.attempt_id}/assess`,form);render();
      requestAnimationFrame(()=>document.querySelector(".review")?.scrollIntoView({behavior:"smooth",block:"start"}));
    }));
    if (S.result) {
      const r = S.result;
      const reference = q.answer_mode === "choice"
        ? (q.options || []).filter((o) => String(r.answer).includes(o.key))
            .map((o) => `${o.key}. ${o.text}`).join("；") || r.answer
        : r.answer;
      node.append(
        el(
          "div",
          { class: `result ${r.correct ? "" : "wrong"}` },
          el(
            "h3",
            {},
            r.verdict === "uncertain"
              ? "这次暂不判断正误"
              : r.verdict === "partial"
                ? "部分正确，看看还差哪一步"
                : r.correct
                  ? "这道题答对了。"
                  : "这道题值得再看一步。",
          ),
          el("p", {}, `参考答案：${reference}`),
          gradingPanel(r.explanation),
          r.annotation?.parts?.length > 1 ? el("div", {class:"question-parts"}, r.annotation.parts.map((p,i)=>
            el("details", {}, el("summary", {}, `第 ${i+1} 问参考解答`), el("p", {}, p.reference_answer || "逐问答案待核对，请结合整题解析。"),
              el("ol", {}, (p.solution_steps || []).map(s=>el("li", {}, s)))))) : null,
          el(
            "ol",
            {},
            (r.steps || []).map((t) => el("li", {}, t)),
          ),
          r.error ? el("p", { class: "subtle" }, r.error.feedback) : null,
          el(
            "p",
            { class: "tiny" },
            w.training_plan_id ? (r.evidence_weight > 0 && !r.assisted ? "独立复测记录已保存，题型状态按已有规则更新。" : "学习记录已保存；加练、求助或重复作答不增加独立证据。") : w.source === "verified" && r.evidence_weight > 0 && !r.assisted
              ? "已保存独立作答记录。"
              : w.source === "bank"
                ? "已保存作答记录。来源答案或 AI 评阅经核验前，不计入可靠题量。"
                : "记录已保存；重复或辅助作答不增加独立题量。",
          ),
          el(
            "div",
            { class: "actions" },
            btn(w.training_plan_id ? (S.training?.status === "completed" ? "查看本轮结果" : "继续本轮") : "下一题", w.training_plan_id ? continueTraining : () => start(), "primary"),
            btn(
              "继续问 AI",
              () =>
                teacherUI.open({ source: w.source, attempt_id: w.attempt_id }),
              "quiet",
            ),
          ),
        ),
      );
      return node;
    }
    if (["numeric", "expression", "scientific", "decimal"].includes(q.answer_mode)) {
      const input = el("input", {
        "aria-label": "你的答案",
        value: S.answer,
        maxLength: 64,
        required: true,
        autocomplete: "off",
        placeholder: { expression: "填写代数式，例如 3x+2", scientific: "例如 3.2×10^5 或 3.2e5", decimal: "保留题目要求的小数位数" }[q.answer_mode] || "输入答案",
        onInput: (e) => (S.answer = e.target.value),
      });
      node.append(
        el(
          "form",
          {
            class: "answer-line",
            onSubmit: (e) => {
              e.preventDefault();
              action(async () => {
                S.result = await api(`/attempts/${w.attempt_id}/answer`, {
                  answer: S.answer,
                });
                await refresh();
                render();
              });
            },
          },
          field("你的答案", input),
          el("button", { type: "submit", class: "primary" }, "提交"),
        ),
      );
    } else if (q.answer_mode === "choice") {
      const multi = q.kind === "multiple_choice";
      node.append(
        el(
          "div",
          { class: "choices" },
          (q.options || []).map((o) =>
            el(
              "label",
              { class: "choice" },
              el("input", {
                type: multi ? "checkbox" : "radio",
                name: "option",
                value: o.key,
                checked: S.choices.includes(o.key),
                onChange: (e) => {
                  if (multi)
                    S.choices = e.target.checked
                      ? [...S.choices, o.key]
                      : S.choices.filter((v) => v !== o.key);
                  else S.choices = [o.key];
                },
              }),
              el("span", {}, `${o.key}. ${o.text}`),
            ),
          ),
        ),
        btn(
          "提交",
          async () => {
            if (!S.choices.length) throw new Error("请先选择答案。");
            S.result = await api(`/bank/attempts/${w.attempt_id}/answer`, {
              answer: S.choices.join(""),
            });
            await refresh();
            render();
          },
          "primary",
        ),
      );
    } else {
      const parts = q.annotation?.parts || [];
      const multipart = parts.length > 1;
      const fill = q.annotation?.response_format === "fill_blank";
      const input = el("textarea", {
        "aria-label": "完整解答",
        value: S.answer,
        maxLength: 12000,
        placeholder: fill ? "按空格顺序填写答案；有单位或精度要求时一并写明。" : multipart ? "补充整题说明，或上传包含全部小问的手写答案。" : "写下你的推理和步骤，或拍照上传手写答案。",
        onInput: (e) => (S.answer = e.target.value),
      });
      const entry=el("div",{class:"written-entry"});
      entry.append(
        multipart ? el("div", {class:"question-parts"}, parts.map((p,i)=>el("section", {class:"question-part"},
          el("h3", {}, `第 ${i+1} 问`), el("p", {class:"part-prompt"}, p.prompt), field(`第 ${i+1} 问解答`, el("textarea", {
            "aria-label":`第 ${i+1} 问解答`, value:S.partAnswers[p.id] || "", maxLength:12000,
            placeholder:"写下本问的答案与过程，也可以统一拍照上传。", onInput:e=>S.partAnswers[p.id]=e.target.value,
          }))))) : null,
        field(multipart ? "补充说明（可选）" : fill ? "填写答案" : "你的解答", input),
        photoInput("上传手写答案"),
        el(
          "p",
          { class: "tiny" },
          "AI 会先转写并评阅。请核对转写和正误后再保存；评阅不直接增加可靠题量。",
        ),
        btn(
          S.review ? "重新评阅" : "提交 AI 评阅",
          async () => {
            const form = new FormData();
            const answer = [multipart ? parts.filter(p=>S.partAnswers[p.id]?.trim()).map(p=>`${p.id}：${S.partAnswers[p.id]}`).join("\n\n") : "", S.answer].filter(Boolean).join("\n\n");
            if (answer.length > 12000) throw new Error("整题解答合计最多 12000 字，可以改用拍照上传。");
            form.append("answer", answer);
            S.files.forEach((f) => form.append("files", f));
            S.review = await api(`/bank/attempts/${w.attempt_id}/assess`, form);
            render();
          },
          "primary",
        ),
      );
      node.append(entry);
      if (S.review) node.append(reviewPanel());
    }
    return node;
  }
  function photoInput(label) {
    const input = el("input", {
      type: "file",
      accept: "image/png,image/jpeg,image/webp",
      multiple: true,
      "aria-label": label,
      onChange: (e) => {
        S.files = [...e.target.files];
        if (S.files.length > 4) {
          S.files = [];
          e.target.value = "";
          error("每次最多选择 4 张图片。");
        }
      },
    });
    input.className="visually-hidden";
    const status=el("span",{class:"file-note",role:"status"},S.files.length?`${S.files.length} 张图片`:"");
    input.addEventListener("change",()=>status.textContent=S.files.length?`${S.files.length} 张图片`:"");
    return el("div",{class:"answer-photo"},el("label",{class:"photo-button",title:label},icon("camera"),el("span",{},"上传答案"),input),status);

  }
  function reviewPanel() {
    const r = S.review,
      a = r.assessment;
    if (r.status !== "review" || !a)
      return el("p", { class: "subtle" }, r.error || "请重新提交评阅。");
    const transcribed = el("textarea", {
      "aria-label": "核对转写",
      value: a.transcribed_answer,
      maxLength: 12000,
    });
    const verdict = select(
      "你确认的结果",
      [
        ["", "请选择核对结果"],
        ["correct", "正确"],
        ["incorrect", "错误"],
        ["partial", "部分正确"],
        ["uncertain", "无法判断"],
      ],
      "",
      () => {},
    );
    const checked = el("input", { type: "checkbox" });
    return el(
      "section",
      { class: "review" },
      el("h3", {}, "核对 AI 评阅"),
      el("p", {}, a.reason),
      gradingPanel(a),
      field("核对转写", transcribed),
      field("你确认的结果", verdict),
      el("label", { class: "check" }, checked, "我已核对图片转写与评价"),
      btn(
        "确认并保存",
        async () => {
          if (!checked.checked || !verdict.value)
            throw new Error("请核对转写与评价，并选择核对结果。");
          S.result = await api(`/bank/attempts/${S.work.attempt_id}/confirm`, {
            review_id: r.id,
            reviewed: true,
            verdict: verdict.value,
            transcribed_answer: transcribed.value,
            count_evidence: false,
          });
          await refresh();
          render();
        },
        "primary",
      ),
    );
  }
  function gradingPanel(assessment) {
    const d = assessment?.grading_detail;
    if (!d) return null;
    const verdicts = {correct:"正确",incorrect:"需要修改",partial:"部分正确",uncertain:"待确认",met:"已呈现",not_met:"需要补充"};
    const partName = id => {const i=(S.work?.question.annotation?.parts || []).findIndex(p=>p.id===id);return i>=0?`第 ${i+1} 问`:"本问";};
    return el("div", {class:"grading-detail"},
      el("h3", {}, "逐问反馈"),
      d.part_feedback.map(f=>el("article", {}, el("strong", {}, `${partName(f.part_id)} · ${verdicts[f.verdict] || "待确认"}`),
        el("p", {}, f.reason), f.evidence_quote ? el("blockquote", {}, f.evidence_quote) : null)),
      d.criterion_feedback.length ? el("details", {}, el("summary", {}, "查看解题过程反馈"),
        d.criterion_feedback.map(f=>el("p", {}, `${partName(f.part_id)} · ${verdicts[f.verdict] || "待确认"}：${f.reason}`))) : null,
      el("p", {class:"tiny"}, d.score == null ? "当前提供文字反馈，分数待核对。" : `AI 建议得分：${d.score} / ${d.full_score}，请结合转写和过程核对。`));
  }
  function progress() {
    const groups = S.home.types;
    const policy = S.home.evaluation_policy || {};
    return el(
      "details",
      { class: "card progress" },
      el("summary", {}, "看看我的题型状态"),
      el(
        "p",
        { class: "subtle" },
        "每种题至少独立完成 5 道不同的有效练习，再结合最近表现判断。未评估不代表不会。",
      ),
      el("details", {class:"state-policy"}, el("summary", {}, "学情是怎么判断的？"),
        el("p", {}, `至少 ${policy.minimum_distinct || 5} 道不同的有效独立练习才判断题型表现；重点参考最近 ${policy.evidence_window || 8} 条，旧证据每 ${policy.half_life_days || 30} 天降低一半权重。`),
        el("p", {}, "问知识只记录兴趣，自述不会先待确认；具体错答经过复核后才记录困难。得到提示、照抄解答和 AI 评阅不增加独立掌握证据。"),
        el("p", {}, "长期未练会建议复测，历史记录仍保留。学情线索不准确时可以撤回。")),
      groups.length
        ? groups.map((t) =>
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
                  `${t.independent_count} 道有效独立练习${t.recorded > t.independent_count ? ` · 共记录 ${t.recorded} 次作答` : ""} · ${t.reason}`,
                ),
                t.independent_count || t.learning_notes?.length ? el("details", {class:"type-evidence"},
                  el("summary", {}, "查看判断依据"),
                  el("p", {}, `近${t.evidence_summary?.half_life_days || 30}天 ${t.evidence_summary?.recent_independent_count || 0} 道有效独立练习；本次参考最近 ${t.evidence_summary?.sample_count || 0} 条。`),
                  (t.learning_notes || []).map(note=>el("div", {class:"learning-note"},
                    el("p", {}, note.note), el("blockquote", {}, note.evidence_quote),
                    btn("撤回这条学情线索", async()=>{
                      await api(`/teacher/observations/${note.id}/dismiss`, {});
                      await refresh();render();
                    }, "note-dismiss")))) : null,
              ),
              el(
                "span",
                { class: `badge ${t.status === "需要补强" ? "warn" : ""}` },
                t.current_status || t.learning_status || t.status,
              ),
            ),
          )
        : el(
            "p",
            { class: "empty" },
            "先完成一些当前阶段的练习。来源题型会随作答记录加入，未核验题暂不作可靠判断。",
          ),
      el("p", { class: "tiny" }, S.home.note),
    );
  }
  function render() {
    // An asynchronous report refresh must not discard an open settings panel.
    if(activeDialog) {renderPending=true;return;}
    const menuWasOpen = !!root.querySelector(".app-menu[open]");
    root.replaceChildren();
    if (!S.student) {
      root.append(login());
      return;
    }
    const go = (mode) => {S.mode=mode;S.aiPanel=null;render();window.scrollTo({top:0});};
    const menu = el("details",{class:"app-menu",open:menuWasOpen});
    const trigger=el("summary",{id:"settings-button","aria-label":"打开菜单",title:"菜单"},icon("menu"));
    const item=(name,label,fn)=>btn([icon(name),el("span",{},label)],()=>{menu.open=false;return fn();},"menu-item");
    menu.append(trigger,el("nav",{class:"menu-list","aria-label":"学习菜单"},
      btn([appSettings.avatarImage(true),el("span",{class:"menu-person-copy"},el("strong",{},S.student.nickname),el("small",{},`${subjectName()} · ${stageName()}`))],()=>{menu.open=false;settings("account");},"menu-person"),
      item("book","做题",()=>go("bank")),S.student.is_admin?item("upload","添加题目",()=>location.assign("/admin#import")):null,item("settings","练习设置",()=>settings()),
      item("chat","问 AI",()=>go("ai")),item("chart","知识掌握",()=>{go("state");}),
      item("report","学习报告",()=>reportUI.open()),item("upload","习题导入",()=>{S.mode="ai";S.aiPanel="imports";render();}),
      item("history","提问记录",async()=>{go("ai");await teacherUI.showHistory();}),
      el("hr"),item("chat","AI 连接",()=>appSettings.connections()),item("sun","外观",()=>settings("appearance")),item("upload","题库更新",()=>settings("updates"))));
    const top=el("header",{class:"topbar"},
      btn([el("span",{class:"wordmark"},icon("brand"),"知域"),el("span",{class:"header-stage"},`${subjectName()} · ${stageName()}`)],()=>go("bank"),"home-link"),
      el("div",{class:"header-actions"},menu));
    const back = S.mode!=="bank" ? btn([icon("back"),"返回做题"],()=>go("bank"),"back-to-work quiet") : null;
    let page;
    if(S.mode==="report")page=reportUI.page();
    else if(S.mode==="state")page=el("section",{class:"state-page"},el("h1",{},"知识掌握"),trainingCard(),progress());
    else if(S.mode==="bank")page=bankPage();
    else if(S.aiPanel==="imports")page=importUI.page();
    else page=teacherUI.page();
    root.append(top,el("main",{class:`shell ${S.mode==="bank"?"exercise-shell":""}`},back,page));
    const panel = teacherUI.panel();
    if (panel) {
      [...root.children].forEach(n=>n.inert=true);
      root.append(panel);
    }
    math(root);
  }
  document.addEventListener("click",e=>{const m=root.querySelector(".app-menu[open]");if(m && !m.contains(e.target))m.open=false;});
  document.addEventListener("keydown",e=>{if(e.key==="Escape"){const m=root.querySelector(".app-menu[open]");if(m){m.open=false;m.querySelector("summary").focus();}}});
  window.addEventListener("pageshow", (event) => {
    if (event.persisted) location.reload();
  });
  load().catch((e) => {
    root.replaceChildren(
      el(
        "main",
        { class: "shell" },
        el("h1", {}, "暂时未能打开学习空间"),
        el("p", {}, e.message),
        btn("重新连接", load, "primary"),
      ),
    );
  });
})();
