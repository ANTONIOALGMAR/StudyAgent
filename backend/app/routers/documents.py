"""Router: Documentos (upload, PDF, áudio)."""

from __future__ import annotations

import uuid as uuid_mod
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, Response

from ..agent.agent import PermissionDeniedError, StudyAgent
from ..config import DOCUMENTS_DIR as documents_dir
from ..security.permissions import PermissionManager

router = APIRouter(prefix="/api")
agent = StudyAgent()
permissions = PermissionManager()


from fastapi import Depends
from ..auth import get_current_user

@router.post("/documents/upload")
async def upload_document(request: Request, file: UploadFile = File(...), owner_user_id: str = Depends(get_current_user)):  # noqa: B008
    try:
        permissions.require("file_access")
    except PermissionDeniedError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc

    from ..tools.documents import extract_pdf

    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="arquivo vazio")
    name = file.filename or "documento"
    suffix = Path(name).suffix.lower()
    if suffix not in (".pdf", ".txt", ".md"):
        raise HTTPException(status_code=400, detail="formatos aceitos: pdf, txt, md")
    save_path = Path(documents_dir) / f"{uuid_mod.uuid4().hex[:8]}{suffix}"
    save_path.write_bytes(raw)
    if suffix == ".pdf":
        try:
            pages, text = extract_pdf(save_path)
        except Exception as exc:
            save_path.unlink(missing_ok=True)
            raise HTTPException(status_code=400, detail=f"PDF inválido: {exc}") from exc
        save_path.with_suffix(".txt").write_text(text, encoding="utf-8")
    else:
        pages = 1
        text = raw.decode("utf-8", errors="ignore")
    doc_id = agent.memory.add_document(name, str(save_path), pages, len(text), owner_user_id=owner_user_id)
    return {"id": doc_id, "name": name, "pages": pages, "chars": len(text), "owner_user_id": owner_user_id or "default"}


@router.get("/documents/{doc_id}/file")
def document_file(doc_id: str, requester: str = Depends(get_current_user)):
    try:
        permissions.require("file_access")
    except PermissionDeniedError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    doc = agent.memory.get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="documento não encontrado")
    # ownership check: requester provided by dependency; allow access if owner_user_id is 'default' (public)
    owner = doc.get("owner_user_id") or "default"
    if owner != "default" and (not requester or requester.strip() == ""):
        raise HTTPException(status_code=403, detail="acesso negado ao documento")
    if owner != "default" and requester and requester.strip() != owner:
        raise HTTPException(status_code=403, detail="acesso negado ao documento")
    path = Path(doc["path"])
    if not path.exists():
        raise HTTPException(status_code=404, detail="arquivo não encontrado no disco")
    return FileResponse(
        path,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="{doc["name"]}"',
            "Cache-Control": "private, max-age=3600",
        },
    )


def _doc_parts(doc_id: str):
    doc = agent.memory.get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="documento não encontrado")
    from pathlib import Path as _Path

    from ..tools.documents import load_document_text, split_narration
    path = _Path(doc["path"])
    if not path.exists():
        raise HTTPException(status_code=404, detail="arquivo não encontrado no disco")
    _, text = load_document_text(path)
    return doc, split_narration(text)


@router.get("/documents/{doc_id}/audio/plan")
def document_audio_plan(doc_id: str, requester: str = Depends(get_current_user)):
    try:
        permissions.require("file_access")
    except PermissionDeniedError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    doc = agent.memory.get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="documento não encontrado")
    # ownership check
    owner = doc.get("owner_user_id") or "default"
    if owner != "default" and (not requester or requester.strip() == ""):
        raise HTTPException(status_code=403, detail="acesso negado ao documento")
    if owner != "default" and requester and requester.strip() != owner:
        raise HTTPException(status_code=403, detail="acesso negado ao documento")
    doc, partes = _doc_parts(doc_id)
    if not partes:
        raise HTTPException(status_code=400, detail="documento sem texto legível")
    kind = "página" if (doc["pages"] or 1) > 1 else "parte"
    return {"total": len(partes), "kind": kind, "name": doc["name"]}


@router.get("/documents/{doc_id}/audio")
async def document_audio(doc_id: str, idx: int = 0, requester: str = Depends(get_current_user)):
    try:
        permissions.require("file_access")
    except PermissionDeniedError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    # ownership check similar to document_file
    doc = agent.memory.get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="documento não encontrado")
    owner = doc.get("owner_user_id") or "default"
    if owner != "default" and (not requester or requester.strip() == ""):
        raise HTTPException(status_code=403, detail="acesso negado ao documento")
    if owner != "default" and requester and requester.strip() != owner:
        raise HTTPException(status_code=403, detail="acesso negado ao documento")
    _, partes = _doc_parts(doc_id)
    if not 0 <= idx < len(partes):
        raise HTTPException(status_code=404, detail=f"parte {idx} fora do alcance")
    from ..audio import text_to_speech
    wav = await run_in_threadpool(text_to_speech.synthesize, partes[idx])
    return Response(content=wav, media_type="audio/wav", headers={"Cache-Control": "no-store"})
