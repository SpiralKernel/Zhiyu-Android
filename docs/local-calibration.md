# 本地AI习题标定

这条流程用于维护题库，不使用学生端MiMo/DeepSeek配置，不读取学生答卷或对话。管理员可提供新题或挑选已有来源题，让本机模型完成结构化标注和审核，再将通过项批量纳入练习。模型审核不冒充人工审核；本轮新增题的独立掌握证据权重为0。

## 从后台开始

后台 `/admin` 仅保留“题库”和“导入”，沿用学生端亮暗主题。不提供人工审题、草稿或审批入口。

- **题库**：按题干、题型和编号搜索，筛选科目、阶段、册次和难度；只读查看题目、答案、分问解析、知识点、细题型、难度依据、答案规则及评分标准。
- **导入**：选择教材册次、已安装的本地模型，上传文件后点击“交给 AI”。后台串行执行两轮盲解和核对，每题经过原有标定协议校验后自动入库。分歧、缺图、未知标签和校验失败题只保留原因，不要求人工审批。

服务端配置：

```dotenv
LOCAL_AUDIT_ENABLED=true
LOCAL_AUDIT_BASE_URL=http://127.0.0.1:11434
LOCAL_AUDIT_MODEL=qwen38-27b-audit:latest
LOCAL_AUDIT_VISION_MODEL=
```

默认关闭自动调用，启用后连接**当前应用服务所在电脑**的 Ollama。云端不会自动连接用户浏览器所在电脑的 localhost。模型仅从已安装列表选择，不会自动下载。文字模型不会冒充识图，图片题需要配置已安装的视觉模型。

支持 JSON、JSONL、UTF-8 TXT/Markdown，以及无扫描页和嵌入图片的文字版 PDF。每次最多 8 个文件、每文件 12MB、总计 24MB、100 道题；PDF 最多 50 页。JSON/JSONL 使用 `Source` 字段，支持 `answer` 作为 `reference_answer` 的别名；后台可下载示例。文本按从 1 开始的连续题号拆分，单题也可直接上传；题号前有公共题干时拒绝拆分，避免漏条件。独立行的“答案：”移入来源答案，防止泄露到盲解。扫描件、题图及复杂排版不会仅凭文字提取假定为完整题目，建议使用保留完整题图的结构化文件。

任务和检查点位于数据库同目录的 `bank-ingest/<任务ID>/`，权限为 0600。每题先保存结果，再校验和入库。任务可暂停、继续；服务重启后标记暂停，保留已入库内容，由用户继续。已有审核结果保持不可覆盖。长期任务不依赖浏览器一直打开。

原来的任务导出/结果导入 API 与下述 CLI 保留兼容，历史任务不删除，前端不再展示命令行中转步骤。

## 准备模型并运行

先按[Ollama Linux说明](https://docs.ollama.com/linux)准备Ollama；模型服务不随本项目安装。已有Ollama服务运行时无需重复启动；否则先运行`ollama serve`，另一个终端执行：

```bash
cd /home/sink/AI-teacher
ollama pull qwen3.5:9b
.venv/bin/python -m app.local_calibration run \
  --task /你的路径/calibration-任务ID.json \
  --output /你的路径/calibration-result.json \
  --model qwen3.5:9b
```

默认连接`http://127.0.0.1:11434`的原生Ollama API，串行处理，每题写一次结果，文件权限0600；同一命令再次运行恢复进度，不重复处理已有结果。失败题可加`--retry-failed`重试；建议在正式导入前完成重试。导入后不同审核结果不能覆盖旧记录，需另建任务保留历史。

图片题需要能看图的模型，例如准备好`qwen3-vl:8b`后增加`--vision-model qwen3-vl:8b`。没有视觉模型的图片题保留待处理；文字模型不会自动冒充识图。图片只保留题目所需区域，不要把答案/解析拍进去；文字题也将参考答案另填，避免破坏盲解隔离。涉及图形且没有实际附图的题不会猜图。命令行支持JSON/JSONL及JPEG/PNG/WebP题图数据。后台文字版PDF仅做保守提取，复杂版式和扫描件不自动拆题。

可用`--peer-model 另一个已安装模型`让第二轮使用不同模型。未设置时是同一模型的两次隔离调用，并非两个不同模型的独立能力认证。默认上下文16384、超时300秒；显存紧张可缩短题目、调整`--context-size 8192`或使用更小模型。未测量实际GPU吞吐及标定准确率，不根据模型名称承诺审核正确。

兼容其他本地OpenAI接口，例如LM Studio：

```bash
.venv/bin/python -m app.local_calibration run \
  --task /你的路径/task.json --output /你的路径/result.json \
  --backend openai --base-url http://127.0.0.1:1234/v1 \
  --model 服务实际提供的模型ID
```

默认拒绝非本机地址。明确使用自己局域网的模型服务时加`--allow-remote`；有认证时通过独立环境变量`LOCAL_AUDIT_API_KEY`提供凭据，或用`--api-key-env`指定变量名。worker不会加载学生老师的`.env`和API Key，也不会读取该配置来补齐模型凭据。模型地址不写入学生前端，结果不保存API Key。

## 纯命令行维护本地题库

先启动一次新版应用以完成数据库升级，然后：

```bash
# 从当前本地题库导出待标定题；不覆盖已有任务文件。
.venv/bin/python -m app.local_calibration export \
  --database data/ai-teacher.sqlite3 --book math-7-1 --limit 10 \
  --output data/calibration/task.json

# 或提供新题文件，示例见 docs/calibration-example.jsonl。
.venv/bin/python -m app.local_calibration export \
  --database data/ai-teacher.sqlite3 --book math-7-1 \
  --input docs/calibration-example.jsonl --output data/calibration/new-task.json

.venv/bin/python -m app.local_calibration run \
  --task data/calibration/task.json --output data/calibration/result.json --model qwen3.5:9b

# 先只导入结果，查看统计；--publish只纳入通过项。
.venv/bin/python -m app.local_calibration import \
  --database data/ai-teacher.sqlite3 --report data/calibration/result.json
.venv/bin/python -m app.local_calibration import \
  --database data/ai-teacher.sqlite3 --report data/calibration/result.json --publish
```

CLI拥有所指定数据库的本机维护权限；HTTP入口仍严格要求管理员登录。未传`--publish`时不加入练习；发布不需要伪造人工审核。原来已人工核对的题和程序核心题默认不会被批量标定替换。

## 题目输入

每项包括`id`（可省略自动生成）、`stem`、`kind`、`options`、`reference_answer`或`reference_answers`、`source_steps`、`source_label`、`source_url`、`images`。书册在任务层指定，模型不能自行换册。

- `kind`默认`auto`，允许从原文/题图识别选择题；明确指定时可用`single_choice`、`multiple_choice`、`reference`。不能凭空生成选项。
- `reference_answers`按`p1`、`p2`记录逐问来源答案；没有答案时留空。
- `images`为图片data URL，最多4张、单张约6MB，每个任务和结果包上限25MiB。
- 不清楚的来源、分值和条件不编造。本轮只生成明确的文字评分标准，不制造数值满分或得分点分配。

## 审核与标签规则

标定标签库位于`app/calibration_catalog.py`：知识主干来自现有教材目标；七上细题型来自`math_catalog.py`，其他初中数学采用维护的细题型清单，物理沿用规则核心题型，高中引用已冻结的基础技能清单。知识标签包括已学册次，当前细题型必须与本册主要知识目标一致；知识目标主干尚可继续细分，不把它当作已穷尽的最细知识图谱。

所有标签有稳定ID、类别、定义、适用范围及库版本。模型只选ID，后端验证；Ollama结构化输出也将标签ID限制为候选枚举。别名不产生新正式标签。无法覆盖时提交`proposed_tags`，保留定义、理由及代表题，整题待处理；模型不能自行注册正式标签。新增正式标签应先维护标签库并复核定义及去重，再重新导出任务。

每题三轮：

1. **初审盲解**：只看原题、题图和标签库，输出逐问答案、推导、标签、依据及评分标准，不看来源答案/解析。
2. **复审盲解**：新请求重新解答，不看初审、来源答案及解析。可使用同一或另一个本地模型。
3. **核对**：比较两次解答和来源答案，检查题干完整、答案与推导、标签、课程范围及评分标准。模型判断之外，还执行ID、引用、数值/选项、结构和内容哈希等程序校验。通用证明和任意符号题尚无数学形式化验证器。

未知标签、标签证据不在题干、答案/单位/难度不一致、缺图、虚构分值、待解决问题、模型格式错误或截断均不自动发布。两次一致不表示数学真理；采用AI审核来源及受限使用权限保留这一边界。

任务绑定题目快照、来源哈希、完整标签库及版本；结果还绑定各轮实际提示哈希、请求模型、服务返回的模型名、Ollama可提供的模型文件digest和运行参数。题目或标签库改变后重新导出，不复用陈旧审核。

发布为新的不可变题目快照，保留原始输入和审核记录。现有来源题经过标定后退出普通推荐，已有作答仍引用旧快照；同题去重不覆盖记录。整批中发现来源变更会回滚，重复导入/发布不重复写入。新题可进入题库更新包，客户端必须使用支持本轮协议的新版；更新后仍保留AI审核身份和0独立证据权重。

## 验收边界

自动测试和后台浏览器验收使用临时数据库、模拟模型及合成题；覆盖本地Ollama请求格式、源答案隔离、实际模型溯源、断点续跑、任务绑定、错误标签/答案拦截、多小问、原题变更回滚和更新包分发。尚未下载模型或运行真实本地模型准确率评测。正式批量使用前，先用一小批已知对错、含易错陷阱和缺图题的题目检验漏判和误判。

## 简化工作台（2026-10-17）

默认进入“AI审核”。不再提供人工编辑、逐题审批和人工通过勾选。题库页仅用于查看题目、答案及完整标注；历史草稿、修订和旧接口保留兼容，不删除历史数据。HTTP结果导入默认在同一事务内自动纳入通过项，重复导入不会重复入库；分歧、缺图、标签不合规及新标签建议自动留置。诊断工具可显式传 `?auto_publish=false`，CLI仍可用 `--publish` 选择导入即入库。

Ollama官方Qwen3.8目前列出27B；9B使用 `qwen3.5:9b`。本机已安装Ollama后可执行：

```bash
ollama pull qwen3.5:9b
ollama run qwen3.5:9b
```

题图审核用 `--model qwen3.5:9b --vision-model qwen3.5:9b`。模型参数可替换，项目不绑定某个模型。

## 标定协议v2：重新试标

新任务包含 `protocol_version: 2`；旧任务保留原提示和核验语义，不能用旧任务来衡量本轮优化。结果项记录协议版本、实际模型、生成参数和最多两次协议纠正历史。服务器会重建纠正对话并复核提示哈希，不允许用自行声称的“已纠正”跳过校验。纠正只看到该轮自己的前次输出与后端生成的错误提示，不能看到另一轮或来源答案。

重新试标：在旧任务中点击“重新导出本批（保留旧结果）”，或从已有题库导出新任务；使用新的结果文件名，避免断点续跑直接复用旧输出。后台的命令示例会按当前任务生成文件名，默认模型名为本机已配置的 `qwen38-audit`，可修改为其它已安装模型。

```bash
cd /home/sink/AI-teacher
.venv/bin/python -m app.local_calibration run \
  --task /home/sink/Downloads/新任务.json \
  --output /home/sink/Downloads/审核结果-v2.json \
  --model qwen38-audit
```

- 默认 `--temperature 0.6 --max-tokens 8192 --thinking auto`。Ollama另设top_p=0.95、top_k=20；auto不发送think覆盖项，保留模型默认思考模式。可显式选on/off；OpenAI兼容模式不假定各家思考参数一致。
- 新schema要求非空评分证据、答案等价规则与可接受答案。通过项的主知识由细题型的正式goal_ids关联约束；主要/辅助/前置知识不重复。模型不满足规则时最多自动纠正两次，仍失败则留置。
- 来源答案对两轮盲解故意隐藏，不应因未提供来源答案或正常LaTeX/填空格式而拒审；仅最终复核看到来源答案。
- 数值及无序数值解集按精确分数判等，不从长段文字里猜答案。仅对完整匹配的常数四则运算、特定数轴定点距离题和四集合有理数分类题做来源独立复算；不覆盖任意应用题、证明题、图片题或综合动点题。
- 单一数值填空必须使用numeric；选择题答案必须是选项字母。评分证据是学生答卷中应观察到的步骤或结果，标签依据则必须引用题干原文。
- 一致答案、两次模型盲解及AI最终复核仍不等于数学证明；复杂题可能继续留置。AI标定题独立掌握证据权重仍为0，不为提高入库率放宽答案、来源版本和题干校验。
