import asyncio, os
os.environ["PYTHONIOENCODING"] = "utf-8"
from app.db.base import SessionLocal
from app.services.rag_service import search_knowledge
from uuid import UUID

async def test():
    db = SessionLocal()
    uid = UUID("5665942e-8779-44d4-81d3-c7ec0aa3bcf8")
    
    queries = ["What is on the menu?", "breakfast items", "sandwich price", "how much is dosa"]
    for q in queries:
        results = await search_knowledge(db, q, uid)
        print(f'Query: "{q}" -> {len(results)} results')
        for r in results:
            content = r.content[:100].encode("ascii", errors="replace").decode()
            print(f"  -> {content}")
        print()

asyncio.run(test())
