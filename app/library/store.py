"""Atomic PDF evidence and exact CSV records with original-source locators.

PDF layout parsing and BM25 retrieval are migrated from SITECO Document Chat.
The generic CSV contract replaces its fixed SITECO price-list-only schema.
"""
from contextlib import contextmanager
from datetime import datetime, timezone
from hashlib import sha256
from io import StringIO
from pathlib import Path
import csv
import json
import os
import re
import sqlite3
import tempfile
import uuid

from .lexical import BM25Index
from .parsing import ParseError, ParseLimits, parse_document

MAX_BYTES = 20 * 1024 * 1024
MAX_DOCUMENTS = 30
MAX_RECORDS = 20_000


class LibraryError(ValueError):
    def __init__(self, message, status=422):
        super().__init__(message)
        self.status = status


def parse_orders(content, id_column=""):
    """Preserve IDs, raw field names and values; never infer numbers or run SQL."""
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise LibraryError("CSV must use UTF-8 encoding. Export as CSV UTF-8 and try again.") from None
    try:
        sample = text[:65536]
        try:
            delimiter = csv.Sniffer().sniff(sample, delimiters=",;\t|").delimiter
        except csv.Error:
            delimiter = ","
        rows = csv.reader(StringIO(text, newline=""), delimiter=delimiter, strict=True)
        headers = [h.strip() for h in next(rows, [])]
        if not headers or len(headers) > 64 or any(not h for h in headers) or len(set(headers)) != len(headers):
            raise LibraryError("CSV needs 1–64 unique, non-empty column headings.")
        if any(len(h) > 120 for h in headers):
            raise LibraryError("CSV column headings must be at most 120 characters.")
        aliases = {"orderid", "ordernumber", "orderno", "bestellnummer", "bestellnr", "订单号"}
        if not id_column:
            candidates = [h for h in headers if re.sub(r"[\W_]", "", h.casefold()) in aliases]
            if len(candidates) != 1:
                raise LibraryError("Specify the exact order ID column name. Available columns: " + ", ".join(headers))
            id_column = candidates[0]
        if id_column not in headers:
            raise LibraryError("Order ID column was not found. Available columns: " + ", ".join(headers))
        records, seen, duplicates = [], set(), 0
        for values in rows:
            if not values or all(not value.strip() for value in values):
                continue
            if len(records) >= MAX_RECORDS:
                raise LibraryError("CSV exceeds the 20,000-record limit.")
            if len(values) != len(headers):
                raise LibraryError(f"CSV record {len(records)+1} has a different number of fields than its headings.")
            data = dict(zip(headers, values))
            order_id = data[id_column].strip()
            if not order_id or len(order_id) > 128:
                raise LibraryError(f"CSV record {len(records)+1} needs an order ID of 1–128 characters.")
            if len(json.dumps(data)) > 8192:
                raise LibraryError(f"CSV record {len(records)+1} exceeds the supported record size.")
            duplicates += int(order_id in seen)
            seen.add(order_id)
            records.append((len(records)+1, order_id, data))
        if not records:
            raise LibraryError("CSV contains no order records.")
        return headers, id_column, records, duplicates
    except csv.Error:
        raise LibraryError("CSV quoting or field size is invalid.") from None


class DocumentLibrary:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.database = self.directory / "library.sqlite3"
        with self.connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS documents (
                    id TEXT PRIMARY KEY, name TEXT NOT NULL, kind TEXT NOT NULL,
                    digest TEXT NOT NULL UNIQUE, created TEXT NOT NULL,
                    active INTEGER NOT NULL DEFAULT 1, metadata TEXT NOT NULL, content BLOB NOT NULL);
                CREATE TABLE IF NOT EXISTS chunks (
                    id TEXT PRIMARY KEY, document_id TEXT NOT NULL,
                    page INTEGER NOT NULL, text TEXT NOT NULL, locator TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS records (
                    document_id TEXT NOT NULL, record_number INTEGER NOT NULL,
                    order_id TEXT NOT NULL COLLATE BINARY, fields TEXT NOT NULL,
                    PRIMARY KEY(document_id, record_number));
                CREATE INDEX IF NOT EXISTS record_order_idx ON records(order_id, document_id);
            """)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.database, timeout=10)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    @staticmethod
    def public(row):
        return {"document_id": row["id"], "name": row["name"], "kind": row["kind"],
                "created": row["created"], "active": bool(row["active"]),
                "status": "ready" if row["active"] else "archived",
                **json.loads(row["metadata"])}

    def list_documents(self):
        with self.connect() as db:
            return [self.public(r) for r in db.execute("SELECT id,name,kind,created,active,metadata FROM documents ORDER BY created DESC")]

    def scope(self, document_ids=None):
        active = {d["document_id"]: d for d in self.list_documents() if d["active"]}
        if document_ids is None:
            return list(active.values())
        if any(doc_id not in active for doc_id in document_ids):
            raise LibraryError("A selected document is unavailable. Refresh the library and select ready files.", 409)
        return [active[doc_id] for doc_id in dict.fromkeys(document_ids)]

    def ingest(self, filename, content, id_column=""):
        if not content or len(content) > MAX_BYTES:
            raise LibraryError("Choose a non-empty file of at most 20 MB.", 413)
        name = Path(filename.replace("\\", "/")).name[:180]
        kind = Path(name).suffix.lower().lstrip(".")
        if kind not in ("pdf", "csv"):
            raise LibraryError("Supported uploads: PDF and CSV.")
        digest = sha256(content + b"\0" + kind.encode() + b"\0" + id_column.encode()).hexdigest()
        with self.connect() as db:
            existing = db.execute("SELECT * FROM documents WHERE digest=?", (digest,)).fetchone()
            if existing and existing["active"]:
                return {**self.public(existing), "duplicate": True}
        records, chunks = [], []
        if kind == "csv":
            headers, key, records, duplicates = parse_orders(content, id_column)
            metadata = {"record_count": len(records), "id_column": key, "headers": headers,
                        "warnings": [f"{duplicates} repeated IDs retained as separate records."] if duplicates else []}
        else:
            if not content.lstrip().startswith(b"%PDF-"):
                raise LibraryError("The uploaded file does not have a PDF signature.")
            with tempfile.TemporaryDirectory(prefix="parse-", dir=self.directory) as folder:
                path = Path(folder) / "source.pdf"
                path.write_bytes(content)
                try:
                    parsed = parse_document(path, "application/pdf", ParseLimits(max_pages=50))
                except ParseError as exc:
                    raise LibraryError(str(exc) + " Text PDFs are supported; image-only scans need OCR first.") from None
                except Exception:
                    raise LibraryError("Cannot parse this PDF. Check that it is readable and not encrypted.") from None
            chunks = parsed.evidence
            metadata = {"page_count": parsed.page_count, "chunk_count": len(chunks),
                        "coverage": parsed.coverage,
                        "warnings": [f"Page {w.page_number}: {w.message}" for w in parsed.warnings]}
        doc_id = uuid.uuid4().hex
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            existing = db.execute("SELECT * FROM documents WHERE digest=?", (digest,)).fetchone()
            if existing:
                db.execute("UPDATE documents SET active=1 WHERE id=?", (existing["id"],))
                return {**self.public(existing), "active": True, "status": "ready", "duplicate": True}
            count = db.execute("SELECT count(*) FROM documents").fetchone()[0]
            if count >= MAX_DOCUMENTS:
                raise LibraryError("The library has reached its 30-file limit.", 409)
            db.execute("INSERT INTO documents VALUES (?,?,?,?,?,1,?,?)", (doc_id, name, kind, digest,
                datetime.now(timezone.utc).isoformat(), json.dumps(metadata), content))
            db.executemany("INSERT INTO records VALUES (?,?,?,?)", ((doc_id, n, key, json.dumps(values)) for n, key, values in records))
            db.executemany("INSERT INTO chunks VALUES (?,?,?,?,?)", ((doc_id+":"+c.evidence_id, doc_id,
                c.page_number, c.retrieval_text or c.text,
                json.dumps({"bbox": c.bbox, "section": c.section})) for c in chunks))
            row = db.execute("SELECT * FROM documents WHERE id=?", (doc_id,)).fetchone()
            return {**self.public(row), "duplicate": False}

    def set_active(self, doc_id, active):
        with self.connect() as db:
            if db.execute("UPDATE documents SET active=? WHERE id=?", (int(active), doc_id)).rowcount != 1:
                raise LibraryError("Document not found.", 404)

    def source(self, doc_id):
        with self.connect() as db:
            row = db.execute("SELECT * FROM documents WHERE id=? AND active=1", (doc_id,)).fetchone()
            if row is None:
                raise LibraryError("Document not found.", 404)
            return self.public(row), bytes(row["content"])

    def search(self, query, document_ids=None):
        docs = [d for d in self.scope(document_ids) if d["kind"] == "pdf"]
        if not docs:
            return {"has_documents": False, "matches": [], "message": "No PDF files selected."}
        ids = [d["document_id"] for d in docs]
        with self.connect() as db:
            rows = db.execute(f"SELECT * FROM chunks WHERE document_id IN ({','.join('?' for _ in ids)})", ids).fetchall()
        index = BM25Index()
        index.replace_documents([(r["id"], r["text"]) for r in rows])
        hits = index.search(query, 5)
        names = {d["document_id"]: d["name"] for d in docs}
        by_id = {r["id"]: r for r in rows}
        matches = []
        for hit in hits:
            row = by_id[hit]
            label = f"{names[row['document_id']]} · page {row['page']}"
            matches.append({"source": label, "document_id": row["document_id"], "page": row["page"],
                "text": row["text"], "locator": json.loads(row["locator"]),
                "url": f"/api/v1/documents/{row['document_id']}/file#page={row['page']}"})
        return {"has_documents": True, "matches": matches,
                "warnings": [w for d in docs for w in d.get("warnings", [])],
                "message": "Cite filenames and page numbers. No match means evidence was not retrieved, not that the fact is absent. Rewrite the search using document terms when needed."}

    def lookup(self, order_id, document_ids=None):
        docs = [d for d in self.scope(document_ids) if d["kind"] == "csv"]
        if not docs:
            return {"has_documents": False, "found": False, "matches": []}
        ids = [d["document_id"] for d in docs]
        params = (order_id.strip(), *ids)
        where = f"order_id=? AND document_id IN ({','.join('?' for _ in ids)})"
        with self.connect() as db:
            count = db.execute("SELECT count(*) FROM records WHERE " + where, params).fetchone()[0]
            rows = db.execute("SELECT * FROM records WHERE " + where + " ORDER BY document_id,record_number LIMIT 5", params).fetchall()
        names = {d["document_id"]: d["name"] for d in docs}
        matches = [{"source": f"{names[r['document_id']]} · record {r['record_number']}",
                    "document_id": r["document_id"], "record_number": r["record_number"],
                    "fields": json.loads(r["fields"]),
                    "url": f"/api/v1/documents/{r['document_id']}/records/{r['record_number']}"} for r in rows]
        return {"has_documents": True, "found": bool(matches), "order_id": order_id,
                "total_matches": count, "truncated": count > 5, "matches": matches,
                "message": "Exact string match. Preserve raw values and currency. Repeated IDs may be line items or conflicting records; do not silently choose one or infer an order total."}

    def record(self, doc_id, number):
        self.source(doc_id)
        with self.connect() as db:
            row = db.execute("SELECT * FROM records WHERE document_id=? AND record_number=?", (doc_id, number)).fetchone()
            if not row:
                raise LibraryError("Record not found.", 404)
            return {"record_number": number, "order_id": row["order_id"], "fields": json.loads(row["fields"])}


def get_library():
    directory = os.getenv("AIROBOT_LIBRARY_DIR") or str(Path(__file__).resolve().parents[2] / "data" / "library")
    return DocumentLibrary(directory)
