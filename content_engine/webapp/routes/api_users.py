from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from psycopg_pool import ConnectionPool
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

from content_engine.db import users_repo
from content_engine.webapp.deps import get_db_pool, require_admin

router = APIRouter(prefix="/api")

VALID_ROLES = {"admin", "viewer"}


class AdminUserOut(BaseModel):
    id: str
    email: str
    role: str
    created_at: datetime


class UpdateRoleRequest(BaseModel):
    role: str


@router.get("/users", response_model=list[AdminUserOut])
async def list_users(pool: ConnectionPool = Depends(get_db_pool), admin: dict = Depends(require_admin)):
    return await run_in_threadpool(users_repo.list_users, pool)


@router.put("/users/{user_id}/role", response_model=AdminUserOut)
async def update_user_role(
    user_id: str,
    payload: UpdateRoleRequest,
    pool: ConnectionPool = Depends(get_db_pool),
    admin: dict = Depends(require_admin),
):
    role = payload.role.strip().lower()
    if role not in VALID_ROLES:
        raise HTTPException(status_code=400, detail=f"role must be one of {sorted(VALID_ROLES)}")
    if user_id == admin["id"] and role != "admin":
        raise HTTPException(status_code=400, detail="You cannot demote your own account")

    updated = await run_in_threadpool(users_repo.update_role, pool, user_id, role)
    if updated is None:
        raise HTTPException(status_code=404, detail="User not found")
    return updated
