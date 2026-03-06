from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import delete

from app.db.base import get_db
from app.db.models import WhatsAppBotConfig, KnowledgeChunk
from app.api.calendar import get_docs_service
from app.services.rag_service import ingest_text

router = APIRouter()

def read_structural_elements(elements):
    """Recursively extract text from Google Docs structural elements"""
    text = ""
    for value in elements:
        if 'paragraph' in value:
            elements = value.get('paragraph').get('elements')
            for elem in elements:
                text += elem.get('textRun', {}).get('content', '')
        elif 'table' in value:
            # The text in table cells are in nested structural elements
            table = value.get('table')
            for row in table.get('tableRows'):
                cells = row.get('tableCells')
                for cell in cells:
                    text += read_structural_elements(cell.get('content'))
        elif 'tableOfContents' in value:
            # The text in the TOC is also in a structural element
            text += read_structural_elements(value.get('tableOfContents').get('content'))
    return text

@router.post("/sync/{bot_config_id}")
async def sync_knowledge_doc(bot_config_id: str, db: AsyncSession = Depends(get_db)):
    """
    Downloads the user's connected Google Doc, wipes old knowledge from Google Docs,
    and ingests the new content into the RAG database.
    """
    res = await db.execute(select(WhatsAppBotConfig).filter(WhatsAppBotConfig.id == bot_config_id))
    config = res.scalar_one_or_none()
    
    if not config:
        raise HTTPException(status_code=404, detail="Bot config not found")
        
    if not config.google_doc_id:
        raise HTTPException(status_code=400, detail="No Google Doc connected to this bot. Please connect Google Calendar/Docs first.")
        
    # Get Google Docs service
    docs_service = await get_docs_service(db, bot_config_id)
    if not docs_service:
        raise HTTPException(status_code=400, detail="Google API connection failed or token expired.")
        
    try:
        # Fetch the document
        document = docs_service.documents().get(documentId=config.google_doc_id).execute()
        
        # Extract plaintext
        doc_content = document.get('body').get('content')
        full_text = read_structural_elements(doc_content)
        
        if not full_text.strip():
            return {"status": "success", "message": "Document is empty. Nothing to sync.", "chunks_ingested": 0}
            
        # 1. Wipe old "google_docs" data for this user
        await db.execute(
            delete(KnowledgeChunk)
            .where(KnowledgeChunk.user_id == config.user_id)
            .where(KnowledgeChunk.source_type == "google_docs")
        )
        
        # 2. Ingest the new text
        count, err = await ingest_text(
            db=db,
            text=full_text,
            user_id=config.user_id,
            category="google_docs_knowledge",
            source_type="google_docs"
        )
        
        if err:
            raise Exception(f"Ingestion error: {err}")
            
        return {
            "status": "success", 
            "message": "Knowledge Base synced successfully!", 
            "chunks_ingested": count
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to sync Google Doc: {str(e)}")
