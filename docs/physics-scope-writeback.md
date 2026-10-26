# 物理册次与受控题型回写

入口为 `scripts/apply_physics_scope.py`，实现位于 `app/physics_scope_writeback.py`。

```bash
PYTHONPATH=. .venv/bin/python scripts/apply_physics_scope.py \
  data/annotations/physics-scope-20261022 \
  --expected-reviewed 1500 \
  --output data/annotations/physics-scope-20261022/continuation-400c-20261023/dry-run.json
```

默认演练并回滚。实际回写增加 `--apply`，输出另指定为 `writeback.json`；脚本先通过 SQLite backup API 备份完整数据库，备份权限为0600，再执行独立事务。`--expected-reviewed` 指累计完成双轮的不同题目数量，不是两轮记录总数。

只应用完成双轮且已解决分歧的 `aligned` 结果，`hold` 不写入。逐题比对冻结来源的完整数据库JSON快照哈希；任一题来源变化或后续映射失败，整批回滚。重复执行通过已应用标记和有效载荷哈希识别，跳过已应用结果。

回写主适用册次、年级学期、最低册次、本册课程目标、逐问受控题型名称及固定ID证据，重建相关题型索引与课程映射。跨册先备目标留在 `quality.textbook_scope.dependency_goal_ids`，不冒充当前册目标。原自由题型保存在同一证据的 `previous_fine_types`、`previous_part_type_tags`；不再作为本次受控分类的依据。

题干、选项、答案、解法、评分细则、来源难度、答案审核状态、可练状态及学生作答记录保持原值。`curriculum.scope_status` 为 `candidate`，课程映射明确标为AI候选；没有教师身份、答案认证或掌握度分数。原 `curriculum_unknown` 问题标记在已有册次后移除，其余标记保留。

重新导入相同来源时，导入器先检查既有来源指纹，再检查已应用有效载荷哈希，只有两者一致才保留册次及受控标注；来源或标注发生变化时不会无条件套用旧结果。

历史 `input-*.jsonl`、标签库和Luna初审/复核保持冻结。回写后的题目JSON会与最初快照不同，续批时应对照回写账本的 `before_sha256` / `after_sha256`，不能把已授权的元数据回写误判为来源题干变化。尚未批注的题仍须匹配原始快照。后续补充缺失能力时新建标签库版本，不修改本轮冻结目录。
