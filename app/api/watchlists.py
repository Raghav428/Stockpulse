from fastapi import APIRouter, HTTPException, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.postgresql import get_db
from app.core.auth import get_current_user
from app.models.models import User, Watchlist, WatchlistItem
from app.schemas.schema import WatchlistCreate, AppendWatchlist, WatchlistResponse


router = APIRouter(prefix='/api/v1/watchlists')


@router.post("", status_code=status.HTTP_201_CREATED, response_model=WatchlistResponse)
async def create_watchlist(
    data: WatchlistCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Create a new watchlist for the authenticated user."""
    watchlist = Watchlist(name=data.name, user_id=user.id)
    db.add(watchlist)
    await db.commit()
    await db.refresh(watchlist)

    # Re-fetch with items eagerly loaded so WatchlistResponse.symbols populates correctly
    result = await db.execute(
        select(Watchlist)
        .where(Watchlist.id == watchlist.id)
        .options(selectinload(Watchlist.items))
    )
    return WatchlistResponse.model_validate(result.scalar_one())


@router.get("", response_model=list[WatchlistResponse])
async def get_watchlists(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Return all watchlists belonging to the authenticated user."""
    result = await db.execute(
        select(Watchlist)
        .where(Watchlist.user_id == user.id)
        .options(selectinload(Watchlist.items))
    )
    return [WatchlistResponse.model_validate(wl) for wl in result.scalars().all()]


@router.post("/{id}/stocks", status_code=status.HTTP_201_CREATED)
async def add_stock(
    id: int,
    data: AppendWatchlist,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Add a stock symbol to an existing watchlist owned by the authenticated user."""
    result = await db.execute(
        select(Watchlist).where(Watchlist.id == id, Watchlist.user_id == user.id)
    )
    watchlist = result.scalar_one_or_none()

    if not watchlist:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Watchlist not found"
        )

    # Guard against duplicate symbols (db constraint will also catch this, but give a clean error)
    existing = await db.execute(
        select(WatchlistItem).where(
            WatchlistItem.watchlist_id == id,
            WatchlistItem.symbol == data.symbol.upper()
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"{data.symbol.upper()} is already in this watchlist"
        )

    item = WatchlistItem(watchlist_id=id, symbol=data.symbol.upper())
    db.add(item)
    await db.commit()

    return {"detail": f"{data.symbol.upper()} added to watchlist '{watchlist.name}'"}


@router.delete("/{id}/stocks/{symbol}", status_code=status.HTTP_200_OK)
async def remove_stock(
    id: int,
    symbol: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Remove a stock symbol from a watchlist owned by the authenticated user."""
    # Verify the watchlist belongs to this user
    result = await db.execute(
        select(Watchlist).where(Watchlist.id == id, Watchlist.user_id == user.id)
    )
    watchlist = result.scalar_one_or_none()

    if not watchlist:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Watchlist not found"
        )

    item_result = await db.execute(
        select(WatchlistItem).where(
            WatchlistItem.watchlist_id == id,
            WatchlistItem.symbol == symbol.upper()
        )
    )
    item = item_result.scalar_one_or_none()

    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{symbol.upper()} not found in this watchlist"
        )

    await db.delete(item)
    await db.commit()

    return {"detail": f"{symbol.upper()} removed from watchlist '{watchlist.name}'"}
