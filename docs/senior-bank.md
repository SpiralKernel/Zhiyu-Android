# 高中数学与物理题库

范围：数学北师大必修、选择性必修全部4册，以及物理人教必修、选择性必修全部6册。本轮在原281道精选题之外补充基础题，按教材小节拆分基础能力，不再仅以“每章有5题”判断覆盖。目录纠正为50单元、100条项目目标。另18道待核、1道排除，保持隔离。仅在本地维护，尚未推送或部署。

2026-10-16本地已安装新增577题：数学276、物理301，覆盖288项基础细技能；高中可练题合计858道（数学395、物理463）。全部100条目标都有直接技能和复核通过的题，288项技能各至少2题。实际复核、浏览器、回归与备份信息见[验证记录](validation.md)。

## 教材与范围

10册原始PDF在私有 `data/sources/textbooks/senior-private/`，由用户已有本地文件归档。页数、SHA256、目录核对信息见[教材档案](senior-textbooks.md)。数学23个目录单元，物理27个；课程目标在 `app/data/senior_curriculum.json`，运行时并入 `course_catalog.py`。必修一的“数学建模活动（一）”此前漏登，本轮已按真实目录补正。文件名中的年份不能证明教材版次。

高中直接选择教材册次，不假定“必修一=高一上”等学校进度。账号增加独立的高中册次选择；原初中年级学期记录保留。题库、对话、导入和报告按当前学生、科目、学段及册次隔离。

## 网络题源

- [CMM-Math](https://huggingface.co/datasets/ecnu-icalk/cmm-math)：现有缓存中高中数学8521条，作为同步题候选；来源大类标签不直接当细题型。
- [GAOKAO-Bench](https://github.com/OpenLMLab/GAOKAO-Bench)：高考客观与主观题，保留来源原卷、参考答案和解析；部分公式/OCR有缺陷。
- [CMMLU](https://github.com/haonan-li/CMMLU)：仅高中数学、物理两个配置，保留dev/test文件与公开答案。
- [AGIEval](https://github.com/ruixiangcui/AGIEval)：v1.1的高中数学选择、填空及物理，保留固定版本。其物理选项可能将多个原判断合成一个选项，不能按旧版格式拆答案。
- [题桩](https://tizhuang.qcscience.cc/)：按物理6册27章定向取回54条补充候选，使用原有访客身份和配额；不轮换身份。原始HTML、检索条件、时间和响应哈希保留在私有缓存。

固定来源版本和23份文件的校验值保存在 `app/data/senior_source_manifests.json`。许可、原题归属和来源说明随来源保留；不将代码许可当作原试卷的独立授权证明。教材与题库来源相互独立，不要求习题来自北师大版。

## 标注与两轮核验

数学和物理由Luna分别逐题阅读、推导并标注，另一Luna单独复核。每条入选记录含原始规范化快照、来源指纹、细题型、主/辅助/前置知识、难度依据、答案、小问、解题步骤、评分依据和复核理由。来源答案相符只是必要条件；还须检查条件是否充分、题干/选项是否完整、单位和严格不等号边界是否正确。

题干粘入答案、公式转义损坏、缺必要图片、多解却标单选、舍入不一致等问题进入pending/excluded。保留私有原始来源便于追踪；这不代表把问题题目开放给学生。标注或题干变化后，旧复核哈希失效，必须重新核验。

`app/data/senior_math_luna.json`、`senior_physics_luna.json`是主审台账；`senior_peer_review.json`是独立复核。中间批次与可重放脚本保留供审计，累计台账是导入入口。`source_sha256`沿用项目来源指纹；独立复核还绑定完整规范化Annotation的SHA256。

新增基础题分别保存在 `senior_math_foundations.json`、`senior_physics_foundations.json`，独立复核为 `senior_foundations_peer_review.json`。`senior_*_foundation_skills.json`记录细技能、对应课程目标、具体要求和题号；每题的 `foundation_skill_ids`必须与清单双向对应，同科同册且知识目标一致。这批补题为明确标记的原创基础题（`dataset=local_senior_foundations`、`local://senior-foundations/…`），不冒充网络原题或教材摘录。网络精选原题仍保留原出处。

模型审核不冒充教师认证。即使两轮核验通过，`teacher_reviewed`仍为false；选择题可按来源答案反馈，学习报告不据此凑足可靠独立诊断题量。过程题依然需要核对AI转写与逐问评阅，书面题不认证实验操作技能。

## 完成检查

完成检查同时保留章节层和基础技能层：50个目录单元各至少5道不同、两轮核验通过的题；每册兼有选择题和主观题，并有不同难度。基础层要求全部100条目标各至少2项直接技能，每项至少2道不同、难度不超过2、独立复核有效的任务；前置技能不能代替本目标主体覆盖。同一题不能跨技能重复凑数，错误答案/标注指纹不符或缺失关联会阻断发布。清单由作者、独立复核者及主任务对照教材小节检查，不能仅凭ID齐全声称语义覆盖。

具体细项见自动生成的[基础题型清单](senior-foundations.md)。这里覆盖的是基础概念、公式、条件、单步或短步骤应用及纸面实验数据，不能代替复杂参数/综合证明、真实建模项目和实验操作，也不证明所有图形空间感知能力或实际学生掌握率。难度是模型估计，未经学生表现校准。

以 `scripts/audit_senior_bank.py --include-foundations` 的实际题目、来源/标注哈希和去重结果为准，不能依赖批次自报的coverage。基础缺口与验收记录在私有 `data/annotations/senior-foundations-20261016/`。审核台账不会因文件存在就自动入库；完成并复验后生成 `app/data/senior_release.json`。schema2发布清单以 `ready_for_import` 和10份内容文件SHA256冻结精选题、基础题、独立复核、教材目标、来源及技能矩阵；原schema1仍可读取。内容再变化，启动会拒绝旧清单。基础题变更后必须重新核验并带 `--include-foundations` 冻结，不能用旧章级审计代替。

验收包括来源指纹与归档校验、旧题快照保留、后台发布及更新包保持高中学段，以及注册、选册、答题、求助、导入与报告流程。逐册浏览器验收使用实际入选题和模拟评阅服务，验证流程而非真实模型判题准确率；全量题干/选项另经本地KaTeX渲染扫描。数据库升级前先备份并在副本核对历史记录；详细结果见[验证记录](validation.md)。

## 维护命令

```bash
cd /home/sink/AI-teacher
# 不联网核对固定公共来源；缺少缓存时明确失败。
.venv/bin/python scripts/fetch_senior_sources.py --source verify
# 清洁工作区按固定版本下载公共来源，不请求题桩配额。
.venv/bin/python scripts/fetch_senior_sources.py --source public
# 仅在有配额时，使用同一个既有访客凭证续取题桩章节补充。
.venv/bin/python scripts/fetch_senior_sources.py --source tizhuang
.venv/bin/python scripts/audit_senior_bank.py --include-foundations --require-complete
.venv/bin/python scripts/export_senior_foundations.py --check
# 修改主审后先让独立复核者更新绑定，再验收；浏览器需本机Chrome。
PYTHONPATH=. .venv/bin/python scripts/browser_senior.py --include-foundations
# 完成审核与回归后冻结本地导入组合；不会推送、部署。
.venv/bin/python scripts/release_senior_bank.py --include-foundations
# 默认仅备份副本验证；--apply先保留0600备份，再增量更新本地。
.venv/bin/python scripts/install_senior_release.py
.venv/bin/python scripts/install_senior_release.py --apply
```

`app/senior_bank.py`在任何写入前验证整批，生成不可变版本题号；已有题和退役题不由启动重复创建。schema13仅添加独立册次选择与细题型登记表，不把高中册次塞进初中年级字段。所有临时数据库、源文件与用户记录都在Git忽略范围内。
