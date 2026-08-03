from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_admin_user, get_current_user
from app.core.db import get_db
from app.models.knowledge import KnowledgeDocument, KnowledgeSource, KnowledgeSourceUser
from app.models.user import User
from app.schemas.knowledge import KnowledgeAssignments, KnowledgeSourceCreate, KnowledgeSourceUpdate, ManagedDocumentImport
from app.services.audit_service import log_audit_event
from app.services.knowledge_service import replace_managed_documents, resolve_knowledge_root, retrieve_knowledge
from app.tasks import sync_knowledge_source


router = APIRouter()


async def _source_response(db: AsyncSession, source: KnowledgeSource) -> dict:
    assigned = int((await db.execute(select(func.count()).select_from(KnowledgeSourceUser).where(
        KnowledgeSourceUser.source_id == source.id,
    ))).scalar_one())
    return {
        "id": str(source.id), "name": source.name, "slug": source.slug,
        "source_type": source.source_type, "root_path": source.root_path,
        "classification": source.classification, "is_active": source.is_active,
        "sync_status": source.sync_status, "sync_error": source.sync_error,
        "last_synced_at": source.last_synced_at, "document_count": source.document_count,
        "assigned_users": assigned,
    }


async def _validate_users(db: AsyncSession, user_ids: list[UUID]) -> None:
    if len(set(user_ids)) != len(user_ids):
        raise HTTPException(status_code=400, detail="Duplicate user assignment")
    if not user_ids:
        return
    found = set((await db.execute(select(User.id).where(User.id.in_(user_ids), User.is_active.is_(True)))).scalars())
    if found != set(user_ids):
        raise HTTPException(status_code=400, detail="One or more assigned users are unavailable")


@router.post("/admin/knowledge/sources", status_code=status.HTTP_201_CREATED)
async def create_source(
    request: KnowledgeSourceCreate,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin_user),
):
    if (await db.execute(select(KnowledgeSource).where(KnowledgeSource.slug == request.slug))).scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Knowledge source slug already exists")
    await _validate_users(db, request.allowed_user_ids)
    root_path = None
    if request.source_type == "local_folder":
        try:
            root_path = str(resolve_knowledge_root(request.root_path))
        except (ValueError, OSError):
            raise HTTPException(status_code=400, detail="Knowledge folder is unavailable or outside configured roots")
    source = KnowledgeSource(
        name=request.name, slug=request.slug, source_type=request.source_type,
        root_path=root_path, classification=request.classification,
    )
    db.add(source)
    await db.flush()
    for user_id in request.allowed_user_ids:
        db.add(KnowledgeSourceUser(source_id=source.id, user_id=user_id))
    await log_audit_event(db, admin.id, "knowledge_source_created", {"source_type": source.source_type, "classification": source.classification, "assigned_users": len(request.allowed_user_ids)}, event_category="connector", subject_type="knowledge_source", subject_id=str(source.id))
    return await _source_response(db, source)


@router.get("/admin/knowledge/sources")
async def list_sources(
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(get_current_admin_user),
):
    sources = (await db.execute(select(KnowledgeSource).order_by(KnowledgeSource.created_at.desc()))).scalars().all()
    return {"sources": [await _source_response(db, source) for source in sources], "count": len(sources)}


@router.put("/admin/knowledge/sources/{source_id}")
async def update_source(
    source_id: UUID,
    request: KnowledgeSourceUpdate,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin_user),
):
    source = await db.get(KnowledgeSource, source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Knowledge source not found")
    values = request.model_dump(exclude_unset=True)
    if "root_path" in values:
        if source.source_type != "local_folder" or not values["root_path"]:
            raise HTTPException(status_code=400, detail="Only local_folder sources accept a root_path")
        try:
            values["root_path"] = str(resolve_knowledge_root(values["root_path"]))
        except (ValueError, OSError):
            raise HTTPException(status_code=400, detail="Knowledge folder is unavailable or outside configured roots")
        source.sync_status = "pending"
    for key, value in values.items():
        setattr(source, key, value)
    await log_audit_event(db, admin.id, "knowledge_source_updated", {"changed_fields": sorted(values)}, event_category="connector", subject_type="knowledge_source", subject_id=str(source.id))
    return await _source_response(db, source)


@router.put("/admin/knowledge/sources/{source_id}/assignments")
async def replace_assignments(
    source_id: UUID,
    request: KnowledgeAssignments,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin_user),
):
    source = await db.get(KnowledgeSource, source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Knowledge source not found")
    await _validate_users(db, request.user_ids)
    await db.execute(delete(KnowledgeSourceUser).where(KnowledgeSourceUser.source_id == source.id))
    for user_id in request.user_ids:
        db.add(KnowledgeSourceUser(source_id=source.id, user_id=user_id))
    await log_audit_event(db, admin.id, "knowledge_assignments_replaced", {"assigned_users": len(request.user_ids)}, event_category="connector", subject_type="knowledge_source", subject_id=str(source.id))
    return {"status": "updated", "assigned_users": len(request.user_ids)}


@router.post("/admin/knowledge/sources/{source_id}/documents")
async def import_documents(
    source_id: UUID,
    request: ManagedDocumentImport,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin_user),
):
    source = await db.get(KnowledgeSource, source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Knowledge source not found")
    try:
        result = await replace_managed_documents(db, source, [item.model_dump() for item in request.documents], request.replace_all)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await log_audit_event(db, admin.id, "knowledge_documents_imported", result, event_category="connector", subject_type="knowledge_source", subject_id=str(source.id))
    return result


@router.post("/admin/knowledge/sources/{source_id}/sync", status_code=status.HTTP_202_ACCEPTED)
async def trigger_sync(
    source_id: UUID,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin_user),
):
    source = await db.get(KnowledgeSource, source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Knowledge source not found")
    if source.source_type != "local_folder":
        raise HTTPException(status_code=409, detail="Managed sources are synchronized by document import")
    source.sync_status = "queued"
    task = sync_knowledge_source.delay(str(source.id))
    await log_audit_event(db, admin.id, "knowledge_sync_queued", {"job_id": task.id}, event_category="connector", subject_type="knowledge_source", subject_id=str(source.id))
    return {"status": "queued", "job_id": task.id}


@router.delete("/admin/knowledge/sources/{source_id}")
async def delete_source(
    source_id: UUID,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin_user),
):
    source = await db.get(KnowledgeSource, source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Knowledge source not found")
    await log_audit_event(db, admin.id, "knowledge_source_deleted", event_category="connector", subject_type="knowledge_source", subject_id=str(source.id))
    await db.delete(source)
    return {"status": "deleted"}


@router.get("/knowledge/search")
async def search_knowledge(
    q: str = Query(min_length=1, max_length=1000),
    provider: str = Query(default="minimax", pattern="^(minimax|openai|ollama)$"),
    limit: int = Query(default=5, ge=1, le=20),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    results = await retrieve_knowledge(db, user.id, q, provider, is_admin=user.role == "admin", limit=limit)
    return {"results": [{key: value for key, value in item.items() if key != "content"} | {"excerpt": item["content"][:500]} for item in results], "count": len(results)}
