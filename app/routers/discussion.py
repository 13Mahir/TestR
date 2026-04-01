"""
routers/discussion.py
FastAPI router for the Discussion Forum.
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from core.database import get_db
from core.dependencies import get_current_user
from models import User, UserRole
from schemas.discussion import (
    PostCreate, PostListResponse, PostDetailOut, 
    ReplyCreate, MessageResponse, PinToggleResponse, 
    PostListOut, ReplyOut
)
from services import discussion_service as service
import math

import json

router = APIRouter(prefix="/api/discussion", tags=["discussion"])

@router.get("/posts", response_model=PostListResponse)
async def list_posts(
    search: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    posts, total = await service.get_posts(db, current_user, search, page, per_page)
    
    post_list = []
    for p in posts:
        # Check if restricted to show icon in UI
        is_restricted = any([p.restrict_school_id, p.restrict_branch_id, p.restrict_batch_year, p.restrict_emails])
        
        # Count non-deleted replies (eager loaded via selectinload in service)
        reply_count = sum(1 for r in p.replies if not r.is_deleted)
        
        post_list.append(PostListOut(
            id=p.id,
            title=p.title,
            body_preview=p.body[:120] + ("..." if len(p.body) > 120 else ""),
            author_email=p.author.email,
            author_role=p.author.role,
            is_pinned=p.is_pinned,
            is_restricted=is_restricted,
            reply_count=reply_count,
            created_at=p.created_at
        ))
        
    return PostListResponse(
        total=total,
        page=page,
        per_page=per_page,
        pages=math.ceil(total / per_page) if total > 0 else 1,
        posts=post_list
    )

@router.post("/posts", response_model=PostDetailOut, status_code=status.HTTP_201_CREATED)
async def create_post(
    data: PostCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Auth: admin or teacher only
    if current_user.role not in [UserRole.admin, UserRole.teacher]:
        raise HTTPException(status_code=403, detail="Only admins and teachers can create posts")
    
    # Validation
    if len(data.title) < 5 or len(data.title) > 255:
        raise HTTPException(status_code=422, detail="Title must be 5-255 characters")
    if len(data.body) < 10 or len(data.body) > 5000:
        raise HTTPException(status_code=422, detail="Body must be 10-5000 characters")
        
    post = await service.create_post(db, current_user.id, data)
    # Return full detail of the new post
    p = await service.get_post_detail(db, post.id, current_user)
    
    is_restricted = any([p.restrict_school_id, p.restrict_branch_id, p.restrict_batch_year, p.restrict_emails])
    
    return PostDetailOut(
        id=p.id,
        title=p.title,
        body=p.body,
        author_email=p.author.email,
        author_role=p.author.role,
        is_pinned=p.is_pinned,
        created_at=p.created_at,
        replies=[
            ReplyOut(
                id=r.id,
                body=r.body,
                author_email=r.author.email,
                author_role=r.author.role,
                created_at=r.created_at,
                can_delete=(current_user.role == UserRole.admin or r.author_id == current_user.id)
            )
            for r in p.replies
        ],
        can_delete=(current_user.role == UserRole.admin or p.author_id == current_user.id),
        can_pin=(current_user.role == UserRole.admin),
        is_restricted=is_restricted,
        restrict_school_name=None, 
        restrict_branch_name=None,
        restrict_batch_year=p.restrict_batch_year,
        restrict_emails=json.loads(p.restrict_emails) if p.restrict_emails else None
    )

@router.get("/posts/{post_id}", response_model=PostDetailOut)
async def get_post(
    post_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    p = await service.get_post_detail(db, post_id, current_user)
    
    is_restricted = any([p.restrict_school_id, p.restrict_branch_id, p.restrict_batch_year, p.restrict_emails])
    
    return PostDetailOut(
        id=p.id,
        title=p.title,
        body=p.body,
        author_email=p.author.email,
        author_role=p.author.role,
        is_pinned=p.is_pinned,
        created_at=p.created_at,
        replies=[
            ReplyOut(
                id=r.id,
                body=r.body,
                author_email=r.author.email,
                author_role=r.author.role,
                created_at=r.created_at,
                can_delete=(current_user.role == UserRole.admin or r.author_id == current_user.id)
            )
            for r in p.replies
        ],
        can_delete=(current_user.role == UserRole.admin or p.author_id == current_user.id),
        can_pin=(current_user.role == UserRole.admin),
        is_restricted=is_restricted,
        # Fetch names if needed - for now we'll pass IDs or leave as None if names aren't joined
        restrict_school_name=None, 
        restrict_branch_name=None,
        restrict_batch_year=p.restrict_batch_year,
        restrict_emails=json.loads(p.restrict_emails) if p.restrict_emails else None
    )

@router.patch("/posts/{post_id}/pin", response_model=PinToggleResponse)
async def pin_post(
    post_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role != UserRole.admin:
        raise HTTPException(status_code=403, detail="Only admins can pin posts")
        
    is_pinned = await service.toggle_pin(db, post_id)
    return PinToggleResponse(
        is_pinned=is_pinned,
        message="Post pinned." if is_pinned else "Post unpinned."
    )

@router.delete("/posts/{post_id}", response_model=MessageResponse)
async def delete_post(
    post_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    await service.delete_post(db, post_id, current_user.id, current_user.role)
    return MessageResponse(message="Post deleted.")

@router.post("/posts/{post_id}/replies", response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
async def create_reply(
    post_id: int,
    data: ReplyCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Validation
    if len(data.body) < 2 or len(data.body) > 2000:
        raise HTTPException(status_code=422, detail="Reply must be 2-2000 characters")
        
    reply = await service.create_reply(db, post_id, current_user.id, data)
    
    # Notify post author
    from services.notification_service import create_notification
    from models import DiscussionPost
    from sqlalchemy import select
    
    post_r = await db.execute(select(DiscussionPost).where(DiscussionPost.id == post_id))
    post = post_r.scalar_one_or_none()
    
    if post and post.author_id != current_user.id:
        await create_notification(
            db=db,
            user_id=post.author_id,
            type="DISCUSSION_REPLY",
            title="New reply to your post",
            body=f"{current_user.full_name or current_user.email} replied to your post: {post.title}",
            link=f"/discussion/{post_id}"
        )
        
    return MessageResponse(id=reply.id, message="Reply posted.")

@router.delete("/replies/{reply_id}", response_model=MessageResponse)
async def delete_reply(
    reply_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    await service.delete_reply(db, reply_id, current_user.id, current_user.role)
    return MessageResponse(message="Reply deleted.")
