"""Use Android's PDF renderer when Poppler is unavailable."""
import base64
import json


def available():
    try:
        from java import jclass
        jclass('org.aiteacher.offline.PdfSupport')
        return True
    except ImportError:
        return False


def render_pages(data, start, end):
    from java import jclass
    encoded=str(jclass('org.aiteacher.offline.PdfSupport').render(base64.b64encode(data).decode(),start,end))
    return [base64.b64decode(s) for s in json.loads(encoded)]
