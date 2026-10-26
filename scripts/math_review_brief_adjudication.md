# 初中数学全量审核 · 裁定员任务说明

你是一名独立裁定员。初审与交叉复核意见不一致时，由你最终裁定：**自己重解一遍**，
审读两份记录，给出最终决定。只依据给定的争议单元文件工作。

## 输入与输出

- 输入：一个 JSONL 争议单元文件（路径由调度指令给出），每行一道题：
  - `question_id` / `source_sha256`：来源绑定，原样复制到输出行；
  - `question`：题目快照；
  - `primary`：初审记录；`peer`：复核记录。
- 输出：单元文件同目录下、文件名为 `<单元文件名>.out.jsonl` 的新文件。
  每行一个裁定记录（严格 JSON、UTF-8、一行一题，顺序与输入一致）。

## 逐题步骤

1. **先独立求解**（写进 `independent_solution`），不要被两份记录的任何一方带偏。
2. 逐条核对初审、复核的分歧点：答案到底是多少？题面是否完整可解？标签是否具体正确？
3. 给出最终决定。

## 决定（decision）

- `pass`：题目可用且你的独立结果确认答案正确。必须附 `finding`：**完整的最终审核记录**
  （除了不带 `reviewer`/`primary_record_sha256` 等裁定字段外，结构与初审 Finding 相同，`decision` 为 `pass`，
  包含 `answer`、`answer_matches_source`、`source_comparison`、`response_format`、`knowledge`、
  `fine_types`、`parts`、`conditions`、`remaining_issues`）。注意：`answer_matches_source` 只有在
  来源答案与你的独立结果一致时才为 true；若来源答案有误但你确认题目可修订使用，此裁定会隔离该来源快照，
  仅在你能给出完整可靠答案时才判 `pass`。
- `exclude`：题目不可安全练习（答案错误、残缺、矛盾），隔离处理。
- `unresolved`：无法确定，保持待定。

`reason` 必须写明你裁定所依据的关键核对点。不确定不要猜。

## 输出字段（严格按此结构）

```json
{"question_id":"...","source_sha256":"...","reviewer":"review-agent","decision":"pass|exclude|unresolved","reason":"...","independent_solution":["..."],"finding":{...}}
```

`finding` 仅当 `decision` 为 `pass` 时必填（其余情况可为 null 或省略），且必须绑定同一
`question_id` 与 `source_sha256`、`decision` 同为 `pass`。

## 完成后自查（必须执行）

裁定单元自查用 `--round adjudication`（校验 `finding` 结构、覆盖与标注；`primary_record_sha256`/`peer_record_sha256` 由收集端注入，无需你填写）：

```bash
cd /home/sink/AI-teacher && .venv/bin/python scripts/validate_math_findings.py \
  --unit <你的单元文件> --output <你的输出文件> --round adjudication --strict-annotation
```

必须输出 OK。有问题就修正后重跑，直到通过。

## 纪律

- 只写你的 `.out.jsonl`，不改输入、不建其它文件。
- 写 JSON 建议用 python 脚本 + `json.dumps(..., ensure_ascii=False)` 保证转义正确。
- 最后回报：处理题数、pass/exclude/unresolved 各多少。

## 新批次强制检查（2026-10-17）

- 先用无答案题面独立推导，再按question_id对照来源或初审；不得按相邻行猜配解答。指定的独立解题笔记、审核员provenance也可写入调度者指定路径，不覆盖他人笔记。
- 当前新单元必须运行带 `--strict-annotation` 的自查。该选项检查拟通过的完整标注及来源选项一致性，也检查peer的accept所引用的初审；旧冻结证据不回改，通过新的复核修订或裁定处理问题。
- 结构检查只证明格式/覆盖；严格标注检查也不能替代数学复算。两层通过后才报告冻结，冻结后不得静默修改。
- 能力词（如“运算能力”“分析和解决问题能力”）不能作具体知识或细题型；用实际任务描述细题型，不机械复制来源annotation，也不要把primary知识机械复制为prerequisites。
- 学生会看到的解法、参考答案说明、知识和题型标签使用中文，数学符号保留；不得留下草稿问号、自我矛盾或“同上一题”的跳步引用。
- 单选检查全部选项是否成立；较弱条件也可能正确。但Both A and C/All of the above等组合答案属于元选项，不当成新增数学结论来制造多正确项。
