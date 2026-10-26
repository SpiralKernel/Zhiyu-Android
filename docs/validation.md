# 验证与维护

## 自动测试

从项目根目录运行：

```bash
PYTHONPATH=. uv run pytest -q
```

2026-10-21清理前基线：**571 passed、1 skipped**。清理后完整运行570通过、1跳过，剩余1项静态测试仍指向旧入口；更新为当前 `student.js` 后该项单独复测通过。测试使用临时数据库，覆盖账号与邀请码、学生隔离、题库判分、AI约束与训练、记忆、导入、报告、受控标注和内容更新。运行结果验证程序行为，不代表真实模型的识图、解题或判分准确率。

## 当前前端验收

```bash
PYTHONPATH=. uv run python scripts/browser_paper.py
PYTHONPATH=. uv run python scripts/browser_admin.py
```

前者覆盖做题入口、题图、文字与照片作答、AI评阅、亮暗主题、字号和手机布局；后者覆盖后台登录、搜索题目与标注、文件上传、本地模型审核和自动入库。2026-10-21清理后两项浏览器验收均通过，页面脚本错误0。两者使用本机Chrome、临时数据库及模拟模型，不调用付费API，不修改真实学生记录。

`scripts/browser_student.py`提供完整学生答疑、导入、报告与训练流程；`scripts/browser_senior.py`验证实际高中题库。学生验收截图默认写入 `output/evals/student-ui/`；纸感界面与后台截图分别写入 `output/evals/paper-ui/`、`output/evals/admin-paper/`。这些是生成物，不提交Git。

前端语法检查：

```bash
for file in web/js/*.js; do node --check "$file"; done
```

旧多面板前端、对应的四个浏览器脚本和旧截图已清理，不再列作当前验收依据。

## 题库核查

```bash
uv run python scripts/check_math_full_review.py data/annotations/math-full-20261016
uv run python scripts/check_physics_full_review.py data/annotations/physics-full-20261014
```

检查来源、题号、规范化审核哈希、双轮覆盖与争议；不写学生数据库。结构校验不能替代数学复算。实际数量以私有检查点为准，不能用历史批次自报数量替代。

## 真实模型验证

`scripts/check_personal_ai.py`、`check_deepseek.py`、`check_vision.py`、`check_written.py`、`eval_teaching.py --live`等会调用配置的真实服务，消耗模型用量；按需运行。默认离线评估和浏览器验收使用模拟服务。识图示例生成于 `output/evals/vision-test-sample.png`。

## 清理后的不变量

账号、学习记录、上传图片、题库与教材保留；正式初审、复核、裁定及模型身份绑定逐文件哈希保持不变；534个保留文件哈希校验通过，现用数据库的逻辑摘要与清理前在线快照一致。旧临时数据库、重复整批副本、旧前端和历史截图已删除。

私有明细与校验结果位于 `data/maintenance/cleanup-20261021.json`。恢复备份见[目录说明](project-structure.md)；备份不可随意覆盖当前数据库，恢复前应先停止服务并确认代码与数据库版本兼容。
