"""Items router — detail, save, unsave, saved list."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
import aiosqlite

from app.database import get_db
from app.dependencies import verify_api_key
from app.schemas.item import FeedItem, ItemDetail, SaveResponse

router = APIRouter(prefix="/items", dependencies=[Depends(verify_api_key)])


@router.get("/{item_id}", response_model=ItemDetail)
async def get_item(
    item_id: int,
    db: aiosqlite.Connection = Depends(get_db),
) -> ItemDetail:
    async with db.execute(
        """
        SELECT i.*, s.name AS source_name
        FROM items i
        JOIN sources s ON i.source_id = s.id
        WHERE i.id = ?
        """,
        (item_id,),
    ) as cur:
        row = await cur.fetchone()

    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")

    return ItemDetail.from_row(row)


@router.post("/{item_id}/save", response_model=SaveResponse)
async def save_item(
    item_id: int,
    db: aiosqlite.Connection = Depends(get_db),
) -> SaveResponse:
    async with db.execute("SELECT id FROM items WHERE id = ?", (item_id,)) as cur:
        if not await cur.fetchone():
            raise HTTPException(status_code=404, detail="Item not found")

    await db.execute("UPDATE items SET saved = 1 WHERE id = ?", (item_id,))
    await db.commit()
    return SaveResponse(item_id=item_id, saved=True)


@router.delete("/{item_id}/save", response_model=SaveResponse)
async def unsave_item(
    item_id: int,
    db: aiosqlite.Connection = Depends(get_db),
) -> SaveResponse:
    async with db.execute("SELECT id FROM items WHERE id = ?", (item_id,)) as cur:
        if not await cur.fetchone():
            raise HTTPException(status_code=404, detail="Item not found")

    await db.execute("UPDATE items SET saved = 0 WHERE id = ?", (item_id,))
    await db.commit()
    return SaveResponse(item_id=item_id, saved=False)


# Saved list lives under /saved (separate router) but is included here for DRY
saved_router = APIRouter(prefix="/saved", dependencies=[Depends(verify_api_key)])


@saved_router.get("", response_model=list[FeedItem])
async def list_saved(
    db: aiosqlite.Connection = Depends(get_db),
) -> list[FeedItem]:
    async with db.execute(
        """
        SELECT i.*, s.name AS source_name
        FROM items i
        JOIN sources s ON i.source_id = s.id
        WHERE i.saved = 1
        ORDER BY i.importance_score DESC, i.processed_at DESC
        """,
    ) as cur:
        rows = await cur.fetchall()
    return [FeedItem.from_row(r) for r in rows]
