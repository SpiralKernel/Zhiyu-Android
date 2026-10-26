#!/usr/bin/env python3
"""Build candidate annotations for the pinned C-Eval middle-school physics shard.

This is a reproducible data-generation script. It does not call a model or modify
application code. Source answers remain source_only; no marks are invented.
"""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from app.question_annotation import source_fingerprint
INPUT = ROOT / "data/annotations/physics-20261012/input-2.jsonl"
OUTPUT = ROOT / "data/annotations/physics-20261012/output-2.jsonl"
EXAMPLES = ROOT / "app/data/physics_annotation_examples_2.json"

PINS = [('bank:ceval-physics:physics:dev:0', '21cb34c2d81dd16aac98ce74c706504bf4a6194dec3af3d69778b615078be0e8'), ('bank:ceval-physics:physics:dev:1', 'a2fc41a844fecfb7a4dbf2512186ab58c1d47d8ba4db4470b38ca2506b9717eb'), ('bank:ceval-physics:physics:dev:2', '11a1a96fcaac344733951c1f4a48d335e2a4d57bcd701f78f55ecd0942e9d216'), ('bank:ceval-physics:physics:dev:3', 'a071c1a5414b0a4620ef4619821ae199a3c142bd723e9286d594a717b7b4b32a'), ('bank:ceval-physics:physics:dev:4', '2ec53f6ba5d7bee8b9178c403914817f688b1f28b952739bbdc8f659747defc9'), ('bank:ceval-physics:physics:val:0', '22f27419449ee1b2b06f93418ece39005c3e4a4316f2c8d49ece5a31790c1d7f'), ('bank:ceval-physics:physics:val:1', 'de9a216cd308e99448762b49a20310a42e2deb19a9f39bdf46edf257db9ab675'), ('bank:ceval-physics:physics:val:2', '0655fdfbeac1eb079aac744a9414f468b685e9ef43fe5c086c71a785870d3b63'), ('bank:ceval-physics:physics:val:3', 'b451d0f1a37983ba669249bd533d1400df6f47bfbd5d9612ab7763d03d7d0677'), ('bank:ceval-physics:physics:val:4', '000ea806877c15d2bdfe9e896ca71e20210361d9c169dada59e1a78ead539bbe'), ('bank:ceval-physics:physics:val:5', 'f0aec6d875108b627e9cea0152cacfdd6497226d1c01c2f3c1cce1c99f2ee1d2'), ('bank:ceval-physics:physics:val:6', '9fd38945ab8a06f93b3be247faac0fb58cca3854fba877610c359cfbb8d96f2e'), ('bank:ceval-physics:physics:val:7', '4924d097a6622bce03bc09638462afce0d2ee2a4cd571f3562f0ea1a8df9c756'), ('bank:ceval-physics:physics:val:8', 'cd6dbc025cd2e489db36120489ab0513e360213e22cabc4effa4939831b4a017'), ('bank:ceval-physics:physics:val:9', '1853e9171b4947aba8fb8486ba79c9e7e15f4f971f5e4309e935f2954ce1ef02'), ('bank:ceval-physics:physics:val:10', '7bbb43ca9560c69a55e0d355888d0306ccd2e89520f6505e7ae14f8873738f6b'), ('bank:ceval-physics:physics:val:11', '64d9912ff954ec58541261a64a35c4a40328f12bd4ec9789559b011f5ff083b3'), ('bank:ceval-physics:physics:val:12', '9d1d39d17586024558f8393f7f0c410cd1736629acb222f5779ca2f6181b8956'), ('bank:ceval-physics:physics:val:13', '3402abc673c270a9b7c32bef9187075317a1c1c30870832864d0852f62f442e5'), ('bank:ceval-physics:physics:val:14', '26ddb4cc0ae53121a6641730511829d1607de8dffd9b4452e71bb661a744034d'), ('bank:ceval-physics:physics:val:15', '3432de37a8176ddf4b6d5a756595e498b65d5fdde7eedc01400d066c5f851256'), ('bank:ceval-physics:physics:val:16', '515044f8e956415168e6ae4bde5e172d038298f489748a9f2f7bf30014b8e47c'), ('bank:ceval-physics:physics:val:17', 'a844243a304d26932e3f629b999148d991c44685c781e941bd265092a53061b5'), ('bank:ceval-physics:physics:val:18', 'd920787cb595dfaea1044c8a707d1dddd511bbc8ead959aadc31494b57691cf9')]

# primary, supporting, prerequisites, task, difficulty, rationale, evidence, errors
ITEMS = [
    (["音色是声音的特性之一，不同发声体的音色不同"], ["声音的频率、振幅和音调、响度的区别"], ["声音由物体振动产生"], "依据音色辨认发声乐器", 1, "频率关系到音调，振幅关系到响度；不同乐器的音色不同，可据此辨认。", "说明辨认不同乐器依据其音色差异。", "把音色与音调或响度混为一谈。"),
    (["牛顿第一定律、惯性与运动状态变化"], ["力的作用是相互的；平衡力与相互作用力的区别"], ["速度和运动方向共同描述运动状态"], "分析运动情境中的受力与运动并选择正确表述", 2, "头球/滑行/转弯等实例需区分力的效果、惯性和作用力；相互作用力分别作用于两个物体。", "能用惯性、运动状态变化或相互作用力的正确规律辨析选项。", "把惯性说成一种力；把运动方向改变视为运动状态不变；混淆平衡力与相互作用力。"),
    (["透镜对光的作用及远视眼矫正"], ["平面镜成像特点；照相机成像条件；显微镜物镜成像"], ["凸透镜和凹透镜对光线的作用"], "辨析常见光学成像与视力矫正陈述", 2, "远视眼用凸透镜矫正，平面镜成虚像，照相机物距通常大于二倍焦距；显微镜物镜成倒立放大的实像。", "根据透镜、平面镜及仪器成像规律判断陈述。", "混淆远视与近视矫正镜片；把平面镜像当作实像；颠倒照相机物距条件。"),
    (["可再生能源与不可再生能源的区分"], ["太阳能的来源及利用"], ["能源资源的基本分类"], "从能源实例中识别可再生能源", 1, "太阳能在自然过程中可持续获得；石油、煤炭和核燃料属于有限能源资源。", "依据能源是否能在较短时间内自然补充作出分类。", "将核燃料因能量密度高而误判为可再生能源。"),
    (["物态变化中的液化、凝华及吸放热"], ["霜、雾、露、雪的形成"], ["物质三态及其变化方向"], "判断自然现象对应的物态变化及热量变化", 2, "露由水蒸气液化成小水滴，液化放热；霜和雪通常由水蒸气凝华形成并放热，雾由水蒸气液化形成。", "同时匹配变化类型和吸放热情况。", "把凝华说成凝固；将液化或凝华误判为吸热。"),
    (["家庭电路安全用电"], ["保险丝、开关和测电笔的使用"], ["火线、零线及电路通断"], "选择符合安全用电要求的操作", 1, "更换灯泡前断开开关可切断电路，降低触电风险；其余做法可能导致过流或触电。", "识别操作是否能切断电源并避免触电或过流。", "认为铜丝可替代保险丝；把开关接零线；手触测电笔笔尖。"),
    (["内燃机四冲程及能量转化"], ["柴油机工作过程"], ["内能、机械能及能量转化"], "识别柴油机将内能转化为机械能的冲程", 1, "做功冲程中燃气膨胀推动活塞，将内能转化为机械能。", "指出做功冲程及燃气对活塞做功的能量转化。", "将压缩冲程与做功冲程的能量方向颠倒。"),
    (["运动和静止的相对性及参照物"], ["相对运动的诗句描述"], ["参照物的选取"], "从描述中识别运动物体与所用参照物", 2, "“小小竹排江中游”描述竹排相对岸运动；“青山两岸走”是以竹排为参照物观察到的相对运动。", "分别辨认前句运动物体及后句参照物。", "忽略参照物选择会影响运动描述。"),
    (["力可以改变物体的运动状态"], ["惯性与牛顿第三定律"], ["力的作用效果"], "判断头球过程中力、惯性和参照物相关陈述", 2, "头对足球的力可改变足球的运动状态；相互作用力大小相等；惯性不会因接触力消失而消失。", "以力改变运动状态解释正确选项。", "认为相互作用力大小不相等；认为惯性是力或会随作用力消失。"),
    (["滚动摩擦与滑动摩擦"], ["轴承中滚动体的作用"], ["摩擦力的方向及影响因素"], "识别自行车部件中减小有害摩擦的设计", 1, "车轴处轴承中的滚动体以滚动代替滑动，可减小摩擦。", "指出滚动代替滑动从而减小摩擦。", "把轮胎、把手等需要摩擦的部位误认作减摩装置。"),
    (["压力作用效果与压强"], ["滚动摩擦和磁悬浮减摩"], ["压力、受力面积与压强的关系"], "辨析压强和摩擦相关实例", 2, "月球车多个轮子增大受力面积，在压力一定时减小对地面的压强。", "使用压强随受力面积增大而减小的关系解释多轮设计。", "将增大受力面积说成增大压强；混淆减摩与增摩。"),
    (["二力平衡条件"], ["重力、支持力、压力及相互作用力"], ["力的平衡与作用对象"], "判断静止列车所受力之间的关系", 2, "列车静止在水平轨道，竖直方向重力与轨道支持力作用于同一物体、大小相等、方向相反，是平衡力。", "按同一物体、等大、反向、共线判断平衡力。", "把重力和列车对轨道的压力当作一对平衡力；混淆相互作用力和二力平衡。"),
    (["不透明物体颜色与反射色光"], ["植物对不同颜色光的吸收与反射"], ["色光及物体反射光的关系"], "依据叶片反射色光判断对植物生长不利的光", 2, "按题干模型，绿色叶片反射绿光；被反射的光未被叶片有效吸收用于光合作用，因此对应选项为绿光。", "依据题设给出的反射色光模型作答。", "把物体呈现的颜色误认为其主要吸收的颜色。"),
    (["内燃机做功冲程中的能量转化"], ["机械摩擦、电热器及压缩引燃中的能量转化"], ["内能与机械能"], "识别内能转化为机械能的过程", 1, "内燃机做功冲程中高温高压燃气推动活塞，内能转化为机械能。", "指出燃气推动活塞及内能转机械能。", "将压缩空气或电热过程误认为内能转机械能。"),
    (["光的反射定律"], ["平面镜成像及倒影"], ["光在界面处的传播"], "判断水面或平面镜倒影形成的光学原理", 1, "倒影来自物体光线在水面等界面反射后进入观察者眼睛。", "指出倒影由光的反射形成。", "与折射、色散或光沿直线传播混淆。"),
    (["电磁波传播及月球自转、公转"], ["地球公转与季节；地月通信"], ["太阳系天体运动"], "辨析地月通信、季节位置及月球运动特征", 2, "地月间可用电磁波通信；月球自转周期与绕地公转周期相同，因而大致总以同一面朝向地球。", "识别电磁波可在真空传播及月球同步自转的事实。", "认为真空不能传播电磁波；混淆公转与自转周期。"),
    (["常见物理量的估测"], ["长度、质量、温度和时间的生活量级"], ["常用单位及数量级判断"], "比较日常估测值与合理生活量级", 2, "初中课桌高度约为数十厘米，75 cm合理；夏季月均气温、书包重力和50 m短跑时间的其他数值偏离常见量级。", "将估计的量与生活熟悉的量级比较，并注意单位。", "把质量与重力混淆；忽略单位或数量级。"),
    (["增大有益摩擦的方法"], ["压力对摩擦力的影响"], ["摩擦力与压力的定性关系"], "识别通过增大压力来增大摩擦的做法", 1, "刹车时用力捏闸增大闸皮与车轮间的压力，从而增大摩擦力。", "说明增大正压力可增大接触面间摩擦。", "把润滑、滚动替代滑动或光滑表面误判为增摩。"),
    (["安全用电与雷电防护"], ["保护接地及避雷设施"], ["导体、绝缘体与触电风险"], "选择符合安全用电原则的校园措施", 1, "安装避雷针可为雷电提供导入大地的通路，保护建筑及人员。", "指出避雷针用于雷电防护并导雷入地。", "在高压线附近活动；设备外壳不接地；使用绝缘层破损的电线。"),
    (["超导体的零电阻特性及应用"], ["电阻发热和输电损耗"], ["电流、电阻与电能转化"], "根据超导零电阻特性选择合适应用", 2, "输电导线电阻趋近于零可减少电流通过时的电能损耗；保险丝、电炉丝和变阻器均需要电阻或发热。", "将零电阻特性与减少输电损耗相联系。", "认为超导材料适合需要电阻发热或调阻的元件。"),
    (["力的相互作用与牛顿第三定律"], ["动能和重力势能；惯性"], ["力和运动的关系"], "辨析斜向击球后的相互作用、能量和运动状态", 2, "球下落时重力使其速度大小增大、运动状态改变；击球瞬间球和球棒相互作用力大小相等。", "依据重力改变运动状态判断下落过程的正确说法。", "认为作用力与反作用力大小不同；把上升过程说成势能转动能；认为合力消失后速度减小。"),
    (["力是改变物体运动状态的原因"], ["惯性；平衡力与摩擦力"], ["运动状态和受力分析"], "判断力与运动状态变化的基本规律", 2, "运动状态改变意味着速度大小或方向改变，需有非零合力；物体静止时推力与静摩擦力可平衡。", "用合力改变运动状态解释正确选项。", "认为惯性使急刹车乘客向后倾；静止时推力必小于摩擦力；认为飞行足球不受力。"),
    (["声音由物体振动产生"], ["音调、响度、音色及声音传播"], ["振动与声源"], "辨析发声、噪声控制及声音特性", 1, "教师说话的声源是声带振动；振幅影响响度而非音调，振动若无介质或频率不在可听范围也未必听到。", "指出人声由声带振动产生。", "把振幅与音调混淆；认为一切振动都能被人听到。"),
    (["凸透镜成像规律及照相机原理"], ["实像与虚像"], ["凸透镜成像的物距和像距"], "判断监控摄像机镜头所成像的性质", 1, "摄像机物体通常位于凸透镜二倍焦距以外，在像侧形成倒立、缩小的实像。", "依据照相机/摄像机成像规律判断像的倒正、大小和虚实。", "把凸透镜实像说成正立或虚像。"),
]


def build_entry(entry, i):
    q = entry["question"]
    primary, supporting, prerequisites, task, level, rationale, evidence, error = ITEMS[i]
    options = "\n".join(f"{o['key']}. {o['text']}" for o in q["options"])
    prompt = f"题干：{q['stem']}\n选项：\n{options}"
    basis = "来源未提供可核验的难度等级；按概念数量与推理步骤作候选估计，未经校准。"
    annotation = {
        "schema_version": 1,
        "response_format": "single_choice",
        "knowledge": {"primary": primary, "supporting": supporting, "prerequisites": prerequisites},
        "fine_types": [task],
        "difficulty": {"level": level, "basis": basis, "origin": "luna", "calibrated": False},
        "curriculum": {"grade": None, "term": None, "goal_ids": [], "scope_status": "unknown", "basis": "来源仅标注初中阶段；未提供具体年级、学期或课程目标。"},
        "answer_spec": {"mode": "choice", "accepted_answers": [q["answer"]], "equivalence": "exact", "constraints": ["按题干选择一个最符合初中物理规律的选项。"], "unit": None, "tolerance": None},
        "parts": [{
            "id": "whole", "prompt": prompt, "reference_answer": q["answer"],
            "solution_steps": [rationale], "knowledge_tags": primary + supporting,
            "type_tags": [task], "depends_on": [], "points": None,
            "rubric": [{"id": "choice_and_physics_basis", "description": "唯一选择符合题意且与对应物理规律一致的选项。", "points": None, "evidence_required": evidence}],
            "common_errors": [{"description": error, "knowledge_tags": primary, "type_tags": [task]}],
        }],
        "grading": {"mode": "objective", "full_score": None, "allow_alternative_methods": True, "uncertainty_policy": "review_required"},
        "review": {"status": "candidate", "answer_status": "source_only", "issues": ["answer_source_only", "rubric_unscored", "curriculum_unknown"], "method": "item_read", "notes": "逐题阅读题干、选项和可用来源解析，并按物理概念形成候选标注。参考选项沿用来源答案，未标记checked；题目未提供分值，rubric不赋分；未提供具体册次。"},
        "origin": {"model": "gpt-6-luna", "batch_id": "physics-20261012-input-2"},
    }
    return {"question_id": entry["question_id"], "source_sha256": entry["source_sha256"], "decision": "annotate", "reason": "逐题阅读后的候选标注；来源答案保留 source_only，rubric 有概念依据但不虚构分值。", "annotation": annotation}


def main():
    entries = [json.loads(line) for line in INPUT.read_text(encoding="utf-8").splitlines() if line.strip()]
    if len(entries) != len(ITEMS):
        raise ValueError(f"expected {len(ITEMS)} input rows, got {len(entries)}")
    if [e["question"]["id"] for e in entries] != [e["question_id"] for e in entries]:
        raise ValueError("input question IDs are inconsistent")
    if [(e['question_id'],source_fingerprint(e['question'])) for e in entries] != PINS:
        raise ValueError('C-Eval题目顺序或来源内容变化，需建立新批次')
    if any(e['source_sha256']!=h for e,(_,h) in zip(entries,PINS)):
        raise ValueError('C-Eval输入来源哈希变化')
    outputs = [build_entry(e, i) for i, e in enumerate(entries)]
    OUTPUT.write_text("".join(json.dumps(o, ensure_ascii=False, separators=(",", ":")) + "\n" for o in outputs), encoding="utf-8")
    EXAMPLES.parent.mkdir(parents=True, exist_ok=True)
    EXAMPLES.write_text(json.dumps(outputs[:3], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {len(outputs)} annotations to {OUTPUT}")


if __name__ == "__main__":
    main()
