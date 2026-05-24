"""Document upload and management endpoints."""
import io
from uuid import uuid4
from fastapi import APIRouter, HTTPException, UploadFile, File
from app.core.db import supabase

router = APIRouter()


async def extract_text_from_pdf(file_content: bytes) -> str:
    """Extract text from PDF."""
    try:
        from PyPDF2 import PdfReader
        reader = PdfReader(io.BytesIO(file_content))
        text = ""
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text
        return text[:10000]
    except Exception:
        return "[PDF text extraction failed]"


async def extract_text_from_docx(file_content: bytes) -> str:
    """Extract text from DOCX."""
    try:
        import docx2txt
        result = docx2txt.process(io.BytesIO(file_content))
        if result:
            return result[:10000]
        return ""
    except Exception:
        return "[DOCX text extraction failed]"


@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    organization_id: str = None,
):
    """Upload a document for agent processing."""
    if not organization_id:
        raise HTTPException(status_code=400, detail="organization_id is required")
    
    try:
        file_content = await file.read()
        filename = file.filename if file.filename else f"doc_{str(uuid4())}"
        
        if "." in filename:
            file_type = filename.split(".")[-1].lower()
        else:
            file_type = "unknown"
        
        extracted_text = ""
        if file_type == "pdf":
            extracted_text = await extract_text_from_pdf(file_content)
        elif file_type == "docx":
            extracted_text = await extract_text_from_docx(file_content)
        elif file_type == "txt":
            try:
                extracted_text = file_content.decode("utf-8", errors="ignore")[:10000]
            except Exception:
                extracted_text = "[Text extraction failed]"
        
        storage_path = f"{organization_id}/{filename}"
        
        try:
            supabase.storage.from_("documents").upload(
                storage_path,
                file_content,
                file_options={"content-type": file.content_type if file.content_type else "application/octet-stream"},
            )
        except Exception:
            pass
        
        doc_id = str(uuid4())
        supabase.table("documents").insert({
            "id": doc_id,
            "organization_id": organization_id,
            "user_id": organization_id,
            "filename": filename,
            "file_type": file_type,
            "extracted_text": extracted_text,
            "storage_path": storage_path,
        }).execute()
        
        return {
            "document_id": doc_id,
            "filename": filename,
            "file_type": file_type,
            "text_extracted": len(extracted_text) > 0,
            "text_length": len(extracted_text),
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{organization_id}")
async def list_documents(organization_id: str):
    """List documents for an organization."""
    try:
        response = supabase.table("documents").select("*").eq("organization_id", organization_id).execute()
        docs = response.data if response.data else []
        return {
            "documents": docs,
            "count": len(docs),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/doc/{doc_id}")
async def get_document(doc_id: str):
    """Get a document with extracted text."""
    try:
        response = supabase.table("documents").select("*").eq("id", doc_id).single().execute()
        if not response.data:
            raise HTTPException(status_code=404, detail="Document not found")
        return response.data
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
