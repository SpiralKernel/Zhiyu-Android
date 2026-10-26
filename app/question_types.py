"""题型注册与画像；按学科、年级和名称区分，并保留 AI 新建来源。"""
import hashlib
import json
import unicodedata

BASE_TYPES = {
    "opposite": "数轴对称求相反数", "absolute": "负数的绝对值", "addition": "负数减负数",
    "multiply": "两个负数相乘", "substitution": "一次代数式代入负数", "like_terms": "同类项系数相加",
    "brackets": "负号去括号后求值", "linear": "ax+b=c 型方程", "word_equation": "含固定费用的购物建模",
    "segment": "已知全长求中点分段", "power:0": "幂前负号与平方", "power:1": "负数底数的平方",
    "angle:0": "已知角求余角", "angle:1": "已知角求补角",
}
CHALLENGE_TYPES = {
    "opposite": "数轴平移与对称复合", "absolute": "绝对值条件下的分式求值", "addition": "有理数分数混合加减",
    "multiply": "带分数的乘除混合运算", "power": "含负号和括号的乘方综合",
    "substitution": "二次代数式代入求值", "like_terms": "多字母整式的系数提取",
    "brackets": "双重括号代入求值", "linear": "含括号与分母的一元一次方程",
    "word_equation": "两类商品与数量关系建模", "segment": "两个中点的线段综合", "angle": "角的倍数与补角建模",
}
COARSE_NAMES = {"物理", "初中物理", "物理题", "力学", "电学", "光学", "未分类", "未分类题型", "无法判断", "数学", "初中数学", "数学题", "选择题", "单选题", "多选题", "计算题", "应用题"}


def normalize_name(name):
    return "".join(unicodedata.normalize("NFKC", name).split()).casefold()


def template_type_id(q):
    if q.get('provenance', {}).get('family') == 'foundations':
        return q['question_type']
    if q.get("provenance", {}).get("kind") == "original_challenge_template":
        return "challenge:" + q["knowledge_id"]
    key = q["knowledge_id"]
    if key in {"power", "angle"}:
        key += ":" + str(q["parameters"]["variant"])
    return "template:" + key


def ensure_templates(db):
    for prefix, catalog in [("template:", BASE_TYPES), ("challenge:", CHALLENGE_TYPES)]:
        for key, name in catalog.items():
            knowledge = key.split(":")[0]
            data = {"id": prefix+key, "name": name, "description": "原创参数化模板的明确题型", "subject": "math", "grade": 7, "term": 1,
                    "knowledge_ids": [knowledge], "source": "template", "needs_review": False}
            db.execute("INSERT OR IGNORE INTO question_types(id,subject,grade,term,normalized_name,data) VALUES(?,'math',7,1,?,?)",
                       (data["id"], normalize_name(name), json.dumps(data, ensure_ascii=False)))
    from app.foundations import CATALOG
    from app.math_catalog import TYPE_MAP
    for key, (knowledge, structures) in CATALOG.items():
        target = TYPE_MAP['m7a:'+key]
        data = {'id':target['id'],'name':target['name'],'description':target['can_do'],
                'subject':'math','grade':7,'term':1,'knowledge_ids':[knowledge],
                'source':'template','needs_review':False,'structures':list(structures)}
        db.execute("INSERT OR IGNORE INTO question_types VALUES(?,'math',7,1,?,?)",
                   (target['id'],normalize_name(target['name']),json.dumps(data,ensure_ascii=False)))
        db.execute('UPDATE question_types SET data=? WHERE id=?',(json.dumps(data,ensure_ascii=False),target['id']))


def register_ai_type(db, item, import_id):
    known = db.execute("SELECT id FROM question_types WHERE id=? AND subject='math' AND grade=7 AND term=1", (item.question_type_id,)).fetchone()
    if known:
        return known["id"]
    name = item.question_type_name.strip()
    if not name or normalize_name(name) in COARSE_NAMES:
        return None
    normalized = normalize_name(name)
    existing = db.execute("SELECT id FROM question_types WHERE subject='math' AND grade=7 AND term=1 AND normalized_name=?", (normalized,)).fetchone()
    if existing:
        return existing["id"]
    from app.math_catalog import TYPE_MAP, resolve_type
    canonical = resolve_type(item.question_type_id, name)
    if canonical:
        for legacy_id in TYPE_MAP[canonical]["legacy_type_ids"]:
            if db.execute("SELECT 1 FROM question_types WHERE id=?", (legacy_id,)).fetchone():
                return legacy_id
        target = TYPE_MAP[canonical]
        data = {"id":canonical,"name":target["name"],"description":target["can_do"],
                "subject":"math","grade":7,"term":1,"knowledge_ids":item.knowledge_ids,
                "source":"catalog","needs_review":False}
        db.execute("INSERT OR IGNORE INTO question_types VALUES(?,'math',7,1,?,?)",
                   (canonical,normalize_name(target["name"]),json.dumps(data,ensure_ascii=False)))
        return canonical
    type_id = "ai:" + hashlib.sha256(("math:7:1:"+normalized).encode()).hexdigest()[:20]
    data = {"id": type_id, "name": name, "description": item.question_type_description,
            "subject": "math", "grade": 7, "term": 1, "knowledge_ids": item.knowledge_ids,
            "source": "ai", "source_import_id": import_id, "needs_review": True}
    db.execute("INSERT INTO question_types VALUES(?,'math',7,1,?,?)", (type_id, normalized, json.dumps(data, ensure_ascii=False)))
    from app.db import audit
    audit(db, "ai_question_type_created", {"type_id": type_id, "import_id": import_id})
    return type_id


def type_profile(db, student_id=None):
    from app.identity import student_id as current_id
    student_id = student_id or current_id()
    types = {r["id"]: {**json.loads(r["data"]), "attempts": 0, "correct": 0, "success": 0., "failure": 0., "last_seen": None, "challenge_attempts": 0}
             for r in db.execute("SELECT * FROM question_types ORDER BY id")}
    def add(type_id, correct, weight, timestamp, challenge=False):
        if type_id not in types:
            return
        row = types[type_id]
        row["attempts"] += 1
        row["correct"] += int(correct)
        row["success" if correct else "failure"] += weight
        row["last_seen"] = max(timestamp, row["last_seen"] or "")
        row["challenge_attempts"] += int(challenge)
    for row in db.execute("SELECT a.result,a.submitted_at,q.data FROM attempts a JOIN questions q ON a.question_id=q.id WHERE student_id=? AND status='submitted'", (student_id,)):
        result, q = json.loads(row["result"]), json.loads(row["data"])
        if result.get("evidence_weight", 1) > 0:
            add(template_type_id(q), result["correct"], result.get("evidence_weight", 1), row["submitted_at"], q["difficulty"] == 3)
    for row in db.execute("SELECT e.*,i.data FROM import_evidence e JOIN import_items i ON e.item_id=i.id WHERE e.student_id=?", (student_id,)):
        item = json.loads(row["data"])
        add(item.get("question_type_id"), row["verdict"] == "correct", row["weight"], row["created_at"])
    result = []
    for row in types.values():
        count = row["attempts"]
        probability = (1+row["success"])/(2+row["success"]+row["failure"])
        row["mastery"] = round(probability, 3) if count else None
        row["status"] = "尚未诊断" if not count else "证据不足" if count < 3 else "掌握较稳" if probability >= .8 else "需要巩固" if probability < .6 else "正在进步"
        del row["success"], row["failure"]
        result.append(row)
    return sorted(result, key=lambda r: (not bool(r["attempts"]), r["mastery"] or 0, r["name"]))
