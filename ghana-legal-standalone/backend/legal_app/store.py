import json
import re
import sqlite3
from contextlib import contextmanager
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from uuid import uuid4


SEARCH_STOP_WORDS = frozenset("""
a an the and or of to in on at for by with as is are was were be been being
it its this that these those which what how whether from under given does do
did can could would should may might will shall have has had their them they such than
""".split())


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id() -> str:
    return uuid4().hex


class Store:
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.upload_dir = data_dir / "uploads"
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        self.path = data_dir / "legal.sqlite3"
        self.evidence_preparation_lock = Lock()
        self.analysis_job_lock = Lock()
        self.analysis_create_lock = Lock()
        with self.connect() as db:
            db.executescript("""
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS matters (
                    id TEXT PRIMARY KEY, name TEXT NOT NULL, reference TEXT NOT NULL,
                    description TEXT NOT NULL, created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS documents (
                    id TEXT PRIMARY KEY, filename TEXT NOT NULL, title TEXT NOT NULL,
                    kind TEXT NOT NULL, matter_id TEXT REFERENCES matters(id),
                    court TEXT NOT NULL, citation TEXT NOT NULL, decision_date TEXT NOT NULL,
                    source_url TEXT NOT NULL, permission_note TEXT NOT NULL,
                    sha256 TEXT NOT NULL, created_at TEXT NOT NULL,
                    unit_count INTEGER NOT NULL, chunk_count INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS chunks (
                    id INTEGER PRIMARY KEY, document_id TEXT NOT NULL REFERENCES documents(id),
                    locator TEXT NOT NULL, text TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS chunks_document ON chunks(document_id);
                CREATE INDEX IF NOT EXISTS documents_matter ON documents(matter_id);
                CREATE VIRTUAL TABLE IF NOT EXISTS passages USING fts5(
                    text, content='chunks', content_rowid='id', tokenize='unicode61'
                );
                CREATE TRIGGER IF NOT EXISTS chunks_insert AFTER INSERT ON chunks BEGIN
                    INSERT INTO passages(rowid, text) VALUES (new.id, new.text);
                END;
                CREATE TABLE IF NOT EXISTS reports (
                    id TEXT PRIMARY KEY, kind TEXT NOT NULL, matter_id TEXT REFERENCES matters(id),
                    query TEXT NOT NULL, payload TEXT NOT NULL, created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS evidence_selections (
                    id TEXT PRIMARY KEY, matter_id TEXT NOT NULL REFERENCES matters(id),
                    payload TEXT NOT NULL, created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS evidence_preparations (
                    cache_key TEXT PRIMARY KEY, payload TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS evidence_reviews (
                    id TEXT PRIMARY KEY, matter_id TEXT NOT NULL REFERENCES matters(id),
                    payload TEXT NOT NULL, created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS analysis_jobs (
                    id TEXT PRIMARY KEY, matter_id TEXT NOT NULL REFERENCES matters(id),
                    status TEXT NOT NULL, payload TEXT NOT NULL, created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
            """)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=20)
        try:
            db.row_factory = sqlite3.Row
            db.execute("PRAGMA foreign_keys=ON")
            with db:
                yield db
        finally:
            db.close()

    def matters(self):
        with self.connect() as db:
            return [dict(row) for row in db.execute("""
                SELECT m.*, (SELECT COUNT(*) FROM documents d WHERE d.matter_id=m.id)
                AS document_count FROM matters m ORDER BY m.created_at DESC
            """)]

    def matter(self, matter_id):
        with self.connect() as db:
            row = db.execute("SELECT * FROM matters WHERE id=?", (matter_id,)).fetchone()
            return dict(row) if row else None

    def create_matter(self, payload):
        item = {"id": new_id(), **payload, "created_at": now()}
        with self.connect() as db:
            db.execute("INSERT INTO matters VALUES (:id,:name,:reference,:description,:created_at)", item)
        return {**item, "document_count": 0}

    def documents(self):
        with self.connect() as db:
            return [dict(row) for row in db.execute("SELECT * FROM documents ORDER BY created_at DESC")]

    def document(self, document_id):
        with self.connect() as db:
            row = db.execute("SELECT * FROM documents WHERE id=?", (document_id,)).fetchone()
            return dict(row) if row else None

    def add_document(self, attributes, content, units, chunks):
        with self.connect() as db:
            existing = db.execute("""SELECT * FROM documents
                WHERE sha256=? AND kind=? AND matter_id IS ?""",
                (attributes["sha256"], attributes["kind"], attributes["matter_id"])).fetchone()
            if existing:
                return dict(existing)
        item = {"id": new_id(), **attributes, "created_at": now(),
                "unit_count": len(units), "chunk_count": len(chunks)}
        path = self.upload_dir / item["id"]
        path.write_bytes(content)
        try:
            with self.connect() as db:
                db.execute("""INSERT INTO documents VALUES (
                    :id,:filename,:title,:kind,:matter_id,:court,:citation,:decision_date,
                    :source_url,:permission_note,:sha256,:created_at,:unit_count,:chunk_count
                )""", item)
                db.executemany("INSERT INTO chunks(document_id,locator,text) VALUES (?,?,?)",
                               [(item["id"], location, text) for location, text in chunks])
        except Exception:
            path.unlink(missing_ok=True)
            raise
        return item

    def source(self, chunk_id):
        with self.connect() as db:
            row = db.execute("""SELECT c.id AS chunk_id,c.locator,c.text,
                d.id AS document_id,d.title,d.filename,d.kind,d.court,d.citation,
                d.decision_date,d.source_url FROM chunks c JOIN documents d ON d.id=c.document_id
                WHERE c.id=?""", (chunk_id,)).fetchone()
            return dict(row) if row else None

    def search(self, query, matter_id=None, scope="library", limit=12):
        # Legacy briefs embedded source IDs in issue text; these are not legal search terms.
        query = re.sub(r"\(\s*source_ids\s*:\s*[\d,\s]+\)", "", query, flags=re.IGNORECASE)
        tokens = list(dict.fromkeys(token for token in re.findall(r"\w{2,}", query.lower())
                                   if token not in SEARCH_STOP_WORDS))[:60]
        if not tokens:
            return []
        expression = " OR ".join('"' + token + '"' for token in tokens)
        if scope == "library":
            condition, params = "d.kind != 'matter'", []
        elif scope == "matter":
            condition, params = "d.kind = 'matter' AND d.matter_id=?", [matter_id]
        else:
            condition, params = "(d.kind != 'matter' OR d.matter_id=?)", [matter_id]
        with self.connect() as db:
            rows = db.execute(f"""SELECT c.id AS chunk_id,c.locator,c.text,
                d.id AS document_id,d.title,d.filename,d.kind,d.court,d.citation,
                d.decision_date,d.source_url
                FROM passages JOIN chunks c ON c.id=passages.rowid
                JOIN documents d ON d.id=c.document_id
                WHERE passages MATCH ? AND {condition}
                ORDER BY bm25(passages), c.id LIMIT 100""", [expression, *params]).fetchall()
        result, per_document = [], {}
        for row in rows:
            key = row["document_id"]
            if per_document.get(key, 0) < 3:
                result.append(dict(row))
                per_document[key] = per_document.get(key, 0) + 1
            if len(result) == limit:
                break
        return result

    def matter_passages(self, matter_id):
        with self.connect() as db:
            rows = db.execute("""SELECT c.id,c.document_id,c.locator FROM chunks c JOIN documents d ON d.id=c.document_id
                WHERE d.kind='matter' AND d.matter_id=? ORDER BY d.created_at,c.id""", (matter_id,)).fetchall()
        documents = {}
        for row in rows:
            documents.setdefault(row['document_id'], {}).setdefault(row['locator'], deque()).append(row['id'])
        queues = []
        for pages in documents.values():
            values = list(pages.values())
            order = []
            intervals = deque([(0, len(values) - 1)])
            # Sample page ranges, not just the first forty passages of the first file.
            while intervals:
                left, right = intervals.popleft()
                if left > right:
                    continue
                order.append(values[left])
                if right > left:
                    order.append(values[right])
                    middle = (left + right) // 2
                    intervals.extend([(left + 1, middle), (middle + 1, right - 1)])
            queues.append(deque(order))
        selected = set()
        while any(queues) and len(selected) < 40:
            for pages in queues:
                if pages and len(selected) < 40:
                    page = pages.popleft()
                    selected.add(page.popleft())
                    if page:
                        pages.append(page)
        return [self.source(row['id']) for row in rows if row['id'] in selected], len(rows) > len(selected)

    def source_context(self, source, radius=1):
        # Adjacent chunks stay in the same document; IDs are not assumed contiguous.
        with self.connect() as db:
            ids = [row["id"] for row in db.execute(
                "SELECT id FROM chunks WHERE document_id=? ORDER BY id", (source["document_id"],))]
        position = ids.index(source["chunk_id"])
        return [self.source(chunk_id) for chunk_id in ids[max(0, position-radius):position+radius+1]]

    def save_report(self, kind, matter_id, query, payload):
        item = {"id": new_id(), "kind": kind, "matter_id": matter_id,
                "query": query, "created_at": now(), "payload": payload}
        with self.connect() as db:
            db.execute("INSERT INTO reports VALUES (?,?,?,?,?,?)", (
                item["id"], kind, matter_id, query, json.dumps(payload), item["created_at"]))
        return item

    def save_evidence_selection(self, matter_id, payload):
        item = {"id": new_id(), "matter_id": matter_id, "payload": payload, "created_at": now()}
        with self.connect() as db:
            db.execute("INSERT INTO evidence_selections VALUES (?,?,?,?)",
                       (item["id"], matter_id, json.dumps(payload), item["created_at"]))
        return item

    def evidence_selection(self, selection_id):
        with self.connect() as db:
            row = db.execute("SELECT * FROM evidence_selections WHERE id=?", (selection_id,)).fetchone()
        return {**dict(row), "payload": json.loads(row["payload"])} if row else None

    def evidence_preparation(self, cache_key):
        with self.connect() as db:
            row = db.execute('SELECT payload FROM evidence_preparations WHERE cache_key=?', (cache_key,)).fetchone()
        return json.loads(row['payload']) if row else None

    def save_evidence_preparation(self, cache_key, payload):
        with self.connect() as db:
            db.execute('INSERT INTO evidence_preparations VALUES (?,?) ON CONFLICT(cache_key) DO UPDATE SET payload=excluded.payload',
                       (cache_key, json.dumps(payload)))

    def discard_evidence_preparation(self, cache_key):
        with self.connect() as db:
            db.execute('DELETE FROM evidence_preparations WHERE cache_key=?', (cache_key,))

    def save_evidence_review(self, matter_id, payload):
        item = {'id': new_id(), 'matter_id': matter_id, 'payload': payload, 'created_at': now()}
        with self.connect() as db:
            db.execute('INSERT INTO evidence_reviews VALUES (?,?,?,?)',
                       (item['id'], matter_id, json.dumps(payload), item['created_at']))
        return item

    def evidence_review(self, review_id):
        with self.connect() as db:
            row = db.execute('SELECT * FROM evidence_reviews WHERE id=?', (review_id,)).fetchone()
        return {**dict(row), 'payload': json.loads(row['payload'])} if row else None

    def reports(self):
        with self.connect() as db:
            rows = db.execute("SELECT * FROM reports ORDER BY created_at DESC LIMIT 100").fetchall()
        return [{**dict(row), "payload": json.loads(row["payload"])} for row in rows]

    def analysis_jobs(self, matter_id):
        with self.connect() as db:
            rows = db.execute('SELECT payload FROM analysis_jobs WHERE matter_id=? ORDER BY created_at DESC LIMIT 20',
                              (matter_id,)).fetchall()
        return [json.loads(row['payload']) for row in rows]

    def analysis_job(self, job_id):
        with self.connect() as db:
            row = db.execute('SELECT payload FROM analysis_jobs WHERE id=?', (job_id,)).fetchone()
        return json.loads(row['payload']) if row else None

    def save_analysis_job(self, job):
        job['updated_at'] = now()
        with self.connect() as db:
            db.execute('''INSERT INTO analysis_jobs VALUES (?,?,?,?,?,?)
                ON CONFLICT(id) DO UPDATE SET status=excluded.status,payload=excluded.payload,updated_at=excluded.updated_at''',
                (job['id'], job['matter_id'], job['status'], json.dumps(job), job['created_at'], job['updated_at']))

    def recover_analysis_jobs(self):
        # Called once at API startup. Interrupted work requires an explicit resume.
        with self.connect() as db:
            rows = db.execute("SELECT payload FROM analysis_jobs WHERE status IN ('running','queued')").fetchall()
            for row in rows:
                job = json.loads(row['payload'])
                job.update(status='paused', retry_at=None, message='The API restarted. Completed steps are saved; resume analysis.', updated_at=now())
                db.execute('UPDATE analysis_jobs SET status=?,payload=?,updated_at=? WHERE id=?',
                           (job['status'], json.dumps(job), job['updated_at'], job['id']))

    def finish_analysis_job(self, job, payload):
        # A saved report and completed job become visible together, including after a crash.
        item = {'id': new_id(), 'kind': 'case_analysis', 'matter_id': job['matter_id'],
                'query': 'Termination, notice, cure and remedial access', 'created_at': now(), 'payload': payload}
        job.update(status='completed', report_id=item['id'], progress=100, message='Draft report ready for lawyer review.', updated_at=now())
        with self.connect() as db:
            db.execute('INSERT INTO reports VALUES (?,?,?,?,?,?)', (item['id'], item['kind'], item['matter_id'],
                       item['query'], json.dumps(payload), item['created_at']))
            db.execute('UPDATE analysis_jobs SET status=?,payload=?,updated_at=? WHERE id=?',
                       (job['status'], json.dumps(job), job['updated_at'], job['id']))
        return item

    def report(self, report_id):
        with self.connect() as db:
            row = db.execute("SELECT * FROM reports WHERE id=?", (report_id,)).fetchone()
        return {**dict(row), "payload": json.loads(row["payload"])} if row else None

    def dashboard(self):
        with self.connect() as db:
            counts = {
                "matters": db.execute("SELECT COUNT(*) FROM matters").fetchone()[0],
                "matter_documents": db.execute("SELECT COUNT(*) FROM documents WHERE kind='matter'").fetchone()[0],
                "judgments": db.execute("SELECT COUNT(*) FROM documents WHERE kind='judgment'").fetchone()[0],
                "statutes": db.execute("SELECT COUNT(*) FROM documents WHERE kind='statute'").fetchone()[0],
                "reports": db.execute("SELECT COUNT(*) FROM reports").fetchone()[0],
                "library_updated_at": db.execute("SELECT MAX(created_at) FROM documents WHERE kind!='matter'").fetchone()[0],
            }
        return {**counts, "recent_documents": self.documents()[:6], "recent_reports": self.reports()[:5]}
