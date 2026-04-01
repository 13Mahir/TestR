from pydantic import BaseModel, constr
from typing import List, Optional
from datetime import datetime

class ReplyCreate(BaseModel):
    body: str

class ReplyOut(BaseModel):
    id: int
    body: str
    author_email: str
    author_role: str
    created_at: datetime
    can_delete: bool

class PostCreate(BaseModel):
    title: str
    body: str
    restrict_school_id: Optional[int] = None
    restrict_branch_id: Optional[int] = None
    restrict_batch_year: Optional[str] = None
    restrict_emails: Optional[List[str]] = None

class PostListOut(BaseModel):
    id: int
    title: str
    body_preview: str
    author_email: str
    author_role: str
    is_pinned: bool
    is_restricted: bool
    reply_count: int
    created_at: datetime

class PostListResponse(BaseModel):
    total: int
    page: int
    per_page: int
    pages: int
    posts: List[PostListOut]

class PostDetailOut(BaseModel):
    id: int
    title: str
    body: str
    author_email: str
    author_role: str
    is_pinned: bool
    created_at: datetime
    replies: List[ReplyOut]
    can_delete: bool
    can_pin: bool
    
    # Restriction info for UI
    is_restricted: bool
    restrict_school_name: Optional[str] = None
    restrict_branch_name: Optional[str] = None
    restrict_batch_year: Optional[str] = None
    restrict_emails: Optional[List[str]] = None

class MessageResponse(BaseModel):
    id: Optional[int] = None
    message: str

class PinToggleResponse(BaseModel):
    is_pinned: bool
    message: str
