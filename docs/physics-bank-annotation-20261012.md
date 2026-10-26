# 初中物理题库与 Luna 候选标注（2026-10-12）

后续全量审核已应用本地：当前2,201道可练候选、651道隔离，细题型待审0；63份首批修订草稿保留。本页数量为10月12日历史批次，最新结论见[10月14日全量审核](physics-full-review-20261014.md)。

本次处理 2,852 道明确标为初中物理的来源题：CJEval 2,828 道、C-Eval middle_school_physics 公开答案 dev/val 24 道。全部保留来源 ID、参考答案、解析、原知识点、难度、固定版本及来源文件 SHA-256。学生页面仍聚焦数学；本批物理内容先供管理员后台筛选、审题及后续物理学习入口使用。

## 来源与许可

- [CJEval](https://github.com/SmileWHC/CJEval)，固定提交 `590fb8f34239f642324b806b68374c303fe643bf`，发布方限定学术研究使用，禁止商用。train/valid/test 物理文件均含参考答案。
- [C-Eval](https://huggingface.co/datasets/ceval/ceval-exam)，固定版本 `85ae5586dbc20cac29d0bef4df66c6569b04c1a0`；数据 CC BY-NC-SA 4.0，与代码 MIT 区别。只使用初中物理 dev 5 道、val 19 道，不导入无公开答案的 test。原 Parquet 保留，CSV 为逐字段核对的转换结果，哈希记录在私有缓存 DOWNLOAD.json；运行应用不需要 PyArrow。
- CMMLU 没有明确初中物理子集，本次没有用高中物理替代。网络资源不是人教版全册覆盖证明。

原始缓存及全量候选存放在被 Git 忽略的 `data/sources/`、`data/annotations/physics-20261012/`。仓库仅保留规则、生成器、少量来源绑定的标注样例和复核记录，不发布完整来源题集、学生数据或教材。

## 实际结果与可信度

| 项目 | 数量 |
| --- | ---: |
| 来源题及批次处理条目 | 2,852 |
| 保留结构化候选 | 2,824 |
| 剔除并隔离 | 28 |
| 保留候选中 Luna 逐题细化 `item_read` | 79 |
| 保留候选中规则辅助 `rule_assisted` | 2,745 |
| 精细题型待审 `fine_type_pending` | 2,746 |
| 当前通过材料及精细题型基础门槛的题 | 78 |

78 是后端材料与标签门槛统计，**不是人工核验通过数，也不是学生端已开放题量**。所有保留标注仍是 `candidate/source_only`，满分及得分点分值未知，不生成正式数字成绩，不进入人工审核更新包。年级、学期均未知，不猜填八上、九上，也不自动匹配教材范围。规则批处理不能冒称 2,852 道全部逐题模型审定。

剔除题包括：明确答案/解析数值冲突、物理状态条件矛盾、缺少必要图示、无有效参考答案、结构化选项失效，以及一条题干包含未解析对象和答案字段的记录。保留历史快照和具体原因，避免破坏旧作答。基础题和高难题均保留；未知册次不单独构成剔除理由。

三名实际 `gpt-6-luna` 子代理分别处理 1,456、1,372、24 道，再交叉核对逐题样例。交叉复核发现的待审项写入 `cross_audit_pending`；候选题型、主知识标签、逐问答案和细则仍需维护者复核。未调用个人 MiMo/DeepSeek API，也未让子代理读取学生数据库或密钥。

## 物理标注要求

共同字段遵循[完整标注规范](question-annotation.md)。重点记录具体任务与方法（例如“串联电路用欧姆定律求电流”）、主/辅/前置知识、单位和量纲、公式适用条件、实验中可观察证据。压强区分压力与受力面积；热量计算区分热传递与物态变化；电路区分连接条件与额定/实际状态；光学区分实虚像、物距和镜片条件。未知单位、容差、分值保持空值。

实验/作图暂用 application、composite 或 short_answer 表示作答形式，在细题型和 rubric 中写实验操作、读数、控制变量、图线或光路依据；没有必要题图时不能推断。不能把整题来源答案复制给每个小问。公式、单位和理想化条件须从具体题目确认。

## 重放与入库

先准备上述固定版本缓存及其 DOWNLOAD.json。重新导出不得覆盖已有输入分片；样例哈希及 C-Eval 顺序改变时拒绝重用旧标注。

```bash
.venv/bin/python scripts/annotate_physics_bank.py export --directory data/annotations/physics-20261012
.venv/bin/python scripts/luna_physics_shard_0.py
.venv/bin/python scripts/luna_physics_shard_1.py
.venv/bin/python scripts/luna_physics_shard_2.py
.venv/bin/python scripts/reconcile_physics_annotations.py
.venv/bin/python -m app.manage backup
.venv/bin/python -m app.manage import-physics-bank
.venv/bin/python -m app.manage import-physics-annotations --annotations data/annotations/physics-20261012/output-*.jsonl
.venv/bin/python -m app.manage import-physics-annotations --annotations data/annotations/physics-20261012/output-*.jsonl --apply
```

来源入库在同一事务内进行；候选导入全量校验、流式写入、整个批次原子提交。重复贴标与再次导入来源均不新增快照、不放开隔离题或粗泛题型。物理导入不能给数学题贴标，已有人工审核题不能被覆盖。

数据库副本验证覆盖 38 个学生/维护业务表以及数学题目、标签和关联的内容摘要，合计 41 项保持不变；重复导入 2,852 条均 unchanged，来源重导入新增 0，SQLite 完整性及外键检查通过。三端同步只更新代码与内容，账号、作答、上传材料及运行密钥各自保留。
