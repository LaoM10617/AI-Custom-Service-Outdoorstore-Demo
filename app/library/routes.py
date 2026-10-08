"""Single-file bounded uploads, persistent library management and source previews."""
import html
from urllib.parse import quote

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel, StrictBool
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import UploadFile
from starlette.requests import ClientDisconnect
from starlette.exceptions import HTTPException as StarletteHTTPException

from .store import get_library, LibraryError, MAX_BYTES

router = APIRouter(prefix="/api/v1/documents")


@router.get("")
def list_documents():
    return {"documents": get_library().list_documents()}


@router.post("", status_code=201)
async def upload_document(request: Request):
    received = 0

    async def receive():
        nonlocal received
        message = await request.receive()
        received += len(message.get("body", b""))
        if received > MAX_BYTES + 64*1024:
            raise LibraryError("Upload exceeds the 20 MB file limit.", 413)
        return message

    try:
        bounded = Request(request.scope, receive)
        async with bounded.form(max_files=1, max_fields=1) as form:
            file = form.get("file")
            if not isinstance(file, UploadFile) or set(form) - {"file", "id_column"}:
                raise LibraryError("Provide a PDF or CSV in the file field.")
            id_column = form.get("id_column", "")
            if not isinstance(id_column, str) or len(id_column) > 120:
                raise LibraryError("Order ID column must be a column name of at most 120 characters.")
            content = await file.read(MAX_BYTES+1)
            return await run_in_threadpool(get_library().ingest, file.filename or "", content, id_column.strip())
    except LibraryError as exc:
        raise HTTPException(exc.status, str(exc)) from None
    except (StarletteHTTPException, ClientDisconnect):
        raise HTTPException(422, "A complete single-file upload is required.") from None


class DocumentState(BaseModel):
    active: StrictBool


@router.patch("/{document_id}")
def document_state(document_id: str, state: DocumentState):
    try:
        get_library().set_active(document_id, state.active)
        return {"document_id": document_id, "active": state.active}
    except LibraryError as exc:
        raise HTTPException(exc.status, str(exc)) from None


@router.get("/{document_id}/file")
def original_file(document_id: str):
    try:
        doc, content = get_library().source(document_id)
    except LibraryError as exc:
        raise HTTPException(exc.status, str(exc)) from None
    disposition = "inline" if doc["kind"] == "pdf" else "attachment"
    return Response(content, media_type="application/pdf" if doc["kind"] == "pdf" else "text/csv; charset=utf-8",
                    headers={"Content-Disposition": f"{disposition}; filename*=UTF-8''{quote(doc['name'])}",
                             "X-Content-Type-Options": "nosniff"})


@router.get("/{document_id}/records/{record_number}", response_class=HTMLResponse)
def record_preview(document_id: str, record_number: int):
    try:
        data = get_library().record(document_id, record_number)
    except LibraryError as exc:
        raise HTTPException(exc.status, str(exc)) from None
    rows = "".join(f"<tr><th>{html.escape(key)}</th><td>{html.escape(value)}</td></tr>" for key,value in data["fields"].items())
    return HTMLResponse(f"<!doctype html><html lang='en'><meta charset='utf-8'><title>Order record</title>"
        "<style>body{font:16px system-ui;margin:32px;color:#183c4c}table{border-collapse:collapse}"
        "th,td{text-align:left;border-bottom:1px solid #c4dbe2;padding:12px;white-space:pre-wrap}</style>"
        f"<h1>Record {record_number}</h1><table>{rows}</table></html>")
