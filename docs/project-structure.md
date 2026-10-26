# 项目目录与维护入口

项目根目录：`/home/sink/AI-teacher`。

```text
AI-teacher/
├── app/                  后端业务与API
│   └── data/             随代码维护的题库、课程、标注与来源清单
├── web/
│   ├── index.html        学生入口
│   ├── admin.html        题库工作台入口
│   ├── js/               当前页面模块
│   ├── css/              student、study、bank样式
│   ├── assets/           应用图标
│   └── vendor/katex/     本地公式渲染
├── tests/                自动测试，使用临时数据库
├── scripts/              维护、题库核查与浏览器验收
├── docs/                 产品约定、数据规则、维护说明
├── deploy/               容器、反向代理与备份模板
├── data/                 私有运行数据，不提交Git
├── output/               可删除的截图、报告和测试产物，不提交Git
├── pyproject.toml        Python依赖与测试配置
├── uv.lock               依赖锁定
├── .env.example          配置模板
└── .env                  本机配置与密钥，不提交Git
```

## 前端

| 文件 | 职责 |
| --- | --- |
| `web/js/student.js` | 学生登录、题库练习、设置与页面壳 |
| `web/js/teacher.js` | AI答疑、照片提问与即时帮助 |
| `web/js/imports.js` | 学生导入已答试卷或习题 |
| `web/js/report.js` | 学情报告与PDF |
| `web/js/appearance.js` | 图标、亮暗主题与字号 |
| `web/js/admin.js` | 只读检索题目、答案及标注 |
| `web/js/bank-import.js` | 文件导入与AI审核入库任务 |

学生入口加载 `student.css`、`study.css`；后台加载 `study.css`、`bank.css`。页面模块通过ES模块显式导入。旧版多面板页面、手动标注编辑器及其浏览器脚本已删除。

## 后端

| 业务 | 主要模块 |
| --- | --- |
| 账号、阶段、邀请码 | `auth.py`、`identity.py`、`invites.py`、`preferences.py` |
| 当前练习与AI加练 | `study.py`、`training.py`、`learning.py` |
| 自由答疑与学习线索 | `teacher.py`、`observations.py`、`observation_guard.py` |
| 记忆衰减与家长报告 | `memory.py`、`reports.py`、`report_pdf.py` |
| AI边界与传输 | `ai_policy.py`、`ai_transport.py`、`config.py` |
| 题库、答案与逐问评阅 | `bank.py`、`bank_ai.py`、`answers.py`、`annotation_grading.py` |
| AI文件入库与本地标定 | `bank_ingest.py`、`local_calibration.py`、`calibration*.py` |
| 来源适配与完整标注 | `datasets.py`、`question_annotation.py`、`math_annotations.py` |
| 课程与教材要求 | `course_catalog.py`、`courses.py`、`curriculum.py` |
| 数学、物理及高中题库 | `math_*.py`、`physics_*.py`、`senior_*.py` |
| 原创核验题 | `questions.py`、`challenges.py`、`foundations.py`、`diagnostic_core.py` |
| 图片/PDF导入 | `materials.py` |
| 后台权限与题库更新包 | `admin.py`、`content.py` |
| 数据存储、迁移与维护命令 | `db.py`、`manage.py` |

未从后端删除仍被当前业务、数据迁移或测试引用的模块。全科课程和高中内容仍有运行时引用，不能仅因学生默认年级较低就删除。

## 私有数据

| 路径 | 内容与清理边界 |
| --- | --- |
| `data/ai-teacher.sqlite3` | 当前账号、题库、学习记录；保留 |
| `data/imports/`、`bank_answers/`、`teacher_images/` | 学生原始材料；保留 |
| `data/bank-ingest/` | 文件入库来源、模型任务与恢复检查点；保留 |
| `data/sources/` | 原始题集、教材PDF与提取文本；保留 |
| `data/annotations/` | 有效核查记录与恢复材料；保留正式输入、输出和身份绑定 |
| `data/backups/` | 保留清理前在线快照及最近一次历史备份 |
| `data/maintenance/` | 私有清理清单和校验结果 |
| `output/`、`tmp/`、缓存 | 可再生成的测试产物，结束测试后可删除 |

核查的临时SQLite库、重复 `validated-staging` / `canonical-before` 和旧备份已清理。有效初审、复核、裁定、来源指纹及模型身份绑定不变。部分旧文档的备份路径和临时目录仅为历史操作记录，已不再存在。

## 常用命令

```bash
uv sync
uv run uvicorn app.main:app --host 127.0.0.1 --port 8010
uv run pytest -q
PYTHONPATH=. uv run python scripts/browser_paper.py
PYTHONPATH=. uv run python scripts/browser_admin.py
uv run python -m app.manage backup
```

浏览器验收使用临时数据库与模拟AI；产物写入 `output/evals/`。完整验收、真实API测试边界见[验证说明](validation.md)。标注与入库见[本地AI标定](local-calibration.md)、[题目标注规范](question-annotation.md)、[题库维护](content-maintenance.md)。
