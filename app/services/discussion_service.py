import json
from typing import List, Tuple, Optional
from sqlalchemy import select, func, or_, and_, desc, update
from sqlalchemy.orm import selectinload, joinedload
from sqlalchemy.ext.asyncio import AsyncSession
from models import DiscussionPost, DiscussionReply, User, UserRole, School, Branch
from schemas.discussion import PostCreate, ReplyCreate
from core.exceptions import NotFoundException, ForbiddenException, ValidationException

async def get_posts(
    db: AsyncSession, 
    user: User,
    search: Optional[str] = None, 
    page: int = 1, 
    per_page: int = 20
) -> Tuple[List[DiscussionPost], int]:
    """
    Fetches non-deleted posts with search, pagination, AND selective access filtering.
    Pinned posts come first, then latest.
    """
    # Base filter: not deleted
    stmt = select(DiscussionPost).where(DiscussionPost.is_deleted == False)
    
    # --- SELECTIVE ACCESS FILTERING ---
    # Admins see everything.
    # Others see: 
    # 1. Posts they authored
    # 2. Posts with no restrictions
    # 3. Posts where they match ALL school/branch/year restrictions
    # 4. Posts where their email is in the restrict_emails list
    
    if user.role != UserRole.admin:
        access_filters = [
            DiscussionPost.author_id == user.id, # Author
            and_(
                DiscussionPost.restrict_school_id == None,
                DiscussionPost.restrict_branch_id == None,
                DiscussionPost.restrict_batch_year == None,
                DiscussionPost.restrict_emails == None
            ) # No restrictions
        ]
        
        # Email match (simplified JSON check since it's a small TEXT field)
        access_filters.append(DiscussionPost.restrict_emails.ilike(f'%"{user.email}"%'))
        
        # Student attribute match
        if user.role == UserRole.student:
            from models import StudentProfile
            prof_result = await db.execute(
                select(StudentProfile).where(StudentProfile.user_id == user.id).options(joinedload(StudentProfile.branch))
            )
            profile = prof_result.scalar_one_or_none()
            
            if profile:
                # Logical: (Match School OR No School) AND (Match Branch OR No Branch) AND (Match Year OR No Year)
                student_match = and_(
                    or_(DiscussionPost.restrict_school_id == None, DiscussionPost.restrict_school_id == profile.branch.school_id),
                    or_(DiscussionPost.restrict_branch_id == None, DiscussionPost.restrict_branch_id == profile.branch_id),
                    or_(DiscussionPost.restrict_batch_year == None, DiscussionPost.restrict_batch_year == profile.batch_year)
                )
                access_filters.append(student_match)
            
        stmt = stmt.where(or_(*access_filters))
    # --- END FILTERING ---

    if search:
        search_filter = f"%{search}%"
        stmt = stmt.where(or_(
            DiscussionPost.title.ilike(search_filter),
            DiscussionPost.body.ilike(search_filter)
        ))
    
    # Count total for pagination
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total_result = await db.execute(count_stmt)
    total = total_result.scalar() or 0
    
    # Order: Pinned DESC, Created AT DESC
    stmt = stmt.order_by(desc(DiscussionPost.is_pinned), desc(DiscussionPost.created_at))
    
    # Pagination
    offset = (page - 1) * per_page
    stmt = stmt.offset(offset).limit(per_page)
    
    # Eager load author AND replies (to fix MissingGreenlet crash in router)
    stmt = stmt.options(
        joinedload(DiscussionPost.author),
        selectinload(DiscussionPost.replies)
    )
    
    result = await db.execute(stmt)
    posts = list(result.scalars().unique().all())
    
    return posts, total

async def create_post(db: AsyncSession, author_id: int, data: PostCreate) -> DiscussionPost:
    """Creates a new post with optional restrictions."""
    post = DiscussionPost(
        author_id=author_id,
        title=data.title,
        body=data.body,
        restrict_school_id=data.restrict_school_id,
        restrict_branch_id=data.restrict_branch_id,
        restrict_batch_year=data.restrict_batch_year,
        restrict_emails=json.dumps(data.restrict_emails) if data.restrict_emails else None
    )
    db.add(post)
    await db.commit()
    await db.refresh(post)
    return post

async def get_post_detail(db: AsyncSession, post_id: int, user: User) -> DiscussionPost:
    """Fetches a single post with non-deleted replies and enforces access check."""
    stmt = select(DiscussionPost).where(
        DiscussionPost.id == post_id,
        DiscussionPost.is_deleted == False
    ).options(
        joinedload(DiscussionPost.author),
        selectinload(DiscussionPost.replies.and_(DiscussionReply.is_deleted == False))
        .joinedload(DiscussionReply.author)
    )
    
    result = await db.execute(stmt)
    post = result.scalar_one_or_none()
    
    if not post:
        raise NotFoundException("Post not found")
        
    # Access check on detail view
    if user.role != UserRole.admin and post.author_id != user.id:
        # Check restrictions
        has_restrictions = any([
            post.restrict_school_id, post.restrict_branch_id, 
            post.restrict_batch_year, post.restrict_emails
        ])
        
        if has_restrictions:
            is_allowed = False
            # Check email
            if post.restrict_emails:
                allowed_emails = json.loads(post.restrict_emails)
                if user.email in allowed_emails:
                    is_allowed = True
            
            # Check student attributes
            if not is_allowed and user.role == UserRole.student:
                from models import StudentProfile
                prof_result = await db.execute(
                    select(StudentProfile).where(StudentProfile.user_id == user.id).options(joinedload(StudentProfile.branch))
                )
                profile = prof_result.scalar_one_or_none()
                
                if profile:
                    match_school = post.restrict_school_id is None or post.restrict_school_id == profile.branch.school_id
                    match_branch = post.restrict_branch_id is None or post.restrict_branch_id == profile.branch_id
                    match_year = post.restrict_batch_year is None or post.restrict_batch_year == profile.batch_year
                    
                    if match_school and match_branch and match_year:
                        is_allowed = True
            
            if not is_allowed:
                raise ForbiddenException("You do not have permission to view this discussion")

    return post

# ... rest of the file (toggle_pin, delete_post, create_reply, delete_reply) ...
async def toggle_pin(db: AsyncSession, post_id: int) -> bool:
    """Toggles the pinned status of a post."""
    post = await db.get(DiscussionPost, post_id)
    if not post or post.is_deleted:
        raise NotFoundException("Post not found")
    
    post.is_pinned = not post.is_pinned
    await db.commit()
    return post.is_pinned

async def delete_post(db: AsyncSession, post_id: int, user_id: int, user_role: UserRole):
    """Soft deletes a post and its replies. Only admin or author."""
    if not post or post.is_deleted:
        raise NotFoundException("Post not found")
    
    if user_role != UserRole.admin and post.author_id != user_id:
        raise ForbiddenException("Not authorized to delete this post")
    
    post.is_deleted = True
    
    # Soft delete all replies too
    stmt = update(DiscussionReply).where(DiscussionReply.post_id == post_id).values(is_deleted=True)
    await db.execute(stmt)
    
    await db.commit()

async def create_reply(db: AsyncSession, post_id: int, author_id: int, data: ReplyCreate) -> DiscussionReply:
    """Creates a reply to a post."""
    # Verify post exists and not deleted
    post = await db.get(DiscussionPost, post_id)
    if not post or post.is_deleted:
        raise NotFoundException("Post not found")
        
    reply = DiscussionReply(
        post_id=post_id,
        author_id=author_id,
        body=data.body
    )
    db.add(reply)
    await db.commit()
    await db.refresh(reply)
    return reply

async def delete_reply(db: AsyncSession, reply_id: int, user_id: int, user_role: UserRole):
    """Soft deletes a reply. Only admin or author."""
    reply = await db.get(DiscussionReply, reply_id)
    if not reply or reply.is_deleted:
        raise NotFoundException("Reply not found")
    
    if user_role != UserRole.admin and reply.author_id != user_id:
        raise ForbiddenException("Not authorized to delete this reply")
    
    reply.is_deleted = True
    await db.commit()
