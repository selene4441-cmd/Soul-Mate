from fastapi import APIRouter

from app.dependencies import CsrfProtected, CurrentUser, DbSession
from app.modules.blocks import create_block, list_blocks, revoke_block
from app.schemas import BlockCreate, BlockResponse

router = APIRouter(prefix="/blocks", tags=["safety"])


@router.get("", response_model=list[BlockResponse])
def get_blocks(user: CurrentUser, db: DbSession) -> list[BlockResponse]:
    return list_blocks(db, user)


@router.post("", response_model=BlockResponse, status_code=201)
def block_user(
    payload: BlockCreate,
    user: CurrentUser,
    db: DbSession,
    _csrf: CsrfProtected,
) -> BlockResponse:
    return create_block(db, user, payload)


@router.delete("/{user_id}", status_code=204)
def unblock_user(
    user_id: str,
    user: CurrentUser,
    db: DbSession,
    _csrf: CsrfProtected,
) -> None:
    revoke_block(db, user, user_id)
