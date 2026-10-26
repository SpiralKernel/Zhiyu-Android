"""Senior AI types are scoped to textbook volumes, independent of school schedules."""
import hashlib
import json

from app.db import dumps
from app.identity import book_id
from app.question_types import normalize_name


def items(db):
    return [json.loads(r['data']) for r in db.execute(
        'SELECT data FROM scoped_question_types WHERE book_id=? ORDER BY id LIMIT 100', (book_id(),))]


def register(db, type_id, name, definition=''):
    norm = normalize_name(name)
    from app.senior_bank import types_for_book
    canonical = next((t for t in types_for_book(db,book_id()) if t['id']==type_id or normalize_name(t['name'])==norm), None)
    if canonical:
        return canonical['id']
    row = db.execute('SELECT id FROM scoped_question_types WHERE book_id=? AND (id=? OR normalized_name=?)',
                     (book_id(), type_id, norm)).fetchone()
    if row:
        return row[0]
    if type_id and (type_id.startswith('m7a:') or db.execute('SELECT 1 FROM question_types WHERE id=?', (type_id,)).fetchone()
            or db.execute('SELECT 1 FROM scoped_question_types WHERE id=?', (type_id,)).fetchone()):
        return None
    tid = 'ai:' + hashlib.sha256((book_id()+':'+norm).encode()).hexdigest()[:20]
    data = {'id':tid, 'name':name, 'description':definition, 'book_id':book_id(),
            'source':'ai', 'needs_review':True}
    db.execute('INSERT INTO scoped_question_types VALUES(?,?,?,?)', (tid, book_id(), norm, dumps(data)))
    return tid
