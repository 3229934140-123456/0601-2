import uuid
import time
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from ..database import db, add_notification
from ..utils import success, get_current_user_id
from ..models import Comment, Danmaku, NotificationType

router = APIRouter()


class CommentCreateRequest(BaseModel):
    content: str
    parentId: Optional[str] = None


class DanmakuCreateRequest(BaseModel):
    content: str
    timestamp: float = 0
    color: str = "#ffffff"


def enrich_comment(comment: Comment, current_user_id: str):
    user = db.users.get(comment.user_id)
    liked_set = db.comment_likes.get(comment.id, set())

    return {
        **comment.model_dump(),
        "user": {
            "id": user.id if user else "",
            "nickname": user.nickname if user else "",
            "avatar": user.avatar if user else "",
            "isVerified": user.is_verified if user else False,
        } if user else None,
        "isLiked": current_user_id in liked_set,
    }


@router.post("/video/{video_id}/like")
async def like_video(
    video_id: str,
    current_user_id: str = Depends(get_current_user_id),
):
    video = db.videos.get(video_id)
    if not video:
        raise HTTPException(status_code=404, detail=success(None, "视频不存在"))

    liked_set = db.user_likes.get(current_user_id, set())
    is_liked = video_id in liked_set

    if is_liked:
        liked_set.discard(video_id)
        video.likes_count = max(0, video.likes_count - 1)
    else:
        liked_set.add(video_id)
        video.likes_count += 1

        if video.user_id != current_user_id:
            current_user = db.users.get(current_user_id)
            add_notification(
                video.user_id,
                NotificationType.LIKE,
                f"{current_user.nickname if current_user else '有人'} 赞了你的视频",
                video_id,
            )

    db.user_likes[current_user_id] = liked_set

    return success({
        "isLiked": not is_liked,
        "likesCount": video.likes_count,
    })


@router.post("/video/{video_id}/collect")
async def collect_video(
    video_id: str,
    current_user_id: str = Depends(get_current_user_id),
):
    video = db.videos.get(video_id)
    if not video:
        raise HTTPException(status_code=404, detail=success(None, "视频不存在"))

    collected_set = db.user_collects.get(current_user_id, set())
    is_collected = video_id in collected_set

    if is_collected:
        collected_set.discard(video_id)
        video.collects_count = max(0, video.collects_count - 1)
    else:
        collected_set.add(video_id)
        video.collects_count += 1

    db.user_collects[current_user_id] = collected_set

    return success({
        "isCollected": not is_collected,
        "collectsCount": video.collects_count,
    })


@router.post("/video/{video_id}/share")
async def share_video(video_id: str):
    video = db.videos.get(video_id)
    if not video:
        raise HTTPException(status_code=404, detail=success(None, "视频不存在"))

    video.shares_count += 1

    return success({
        "sharesCount": video.shares_count,
        "shareUrl": f"https://example.com/video/{video_id}",
    })


@router.get("/video/{video_id}/comments")
async def get_comments(
    video_id: str,
    page: int = 1,
    page_size: int = 20,
    current_user_id: str = Depends(get_current_user_id),
):
    comment_ids = db.video_comments.get(video_id, [])
    all_comments = [
        db.comments[cid] for cid in comment_ids
        if cid in db.comments and db.comments[cid].parent_id is None
    ]
    all_comments.sort(key=lambda c: c.created_at, reverse=True)

    start = (page - 1) * page_size
    end = start + page_size
    comments = [enrich_comment(c, current_user_id) for c in all_comments[start:end]]

    return success({
        "list": comments,
        "total": len(all_comments),
        "page": page,
        "pageSize": page_size,
        "hasMore": end < len(all_comments),
    })


@router.post("/video/{video_id}/comments")
async def create_comment(
    video_id: str,
    req: CommentCreateRequest,
    current_user_id: str = Depends(get_current_user_id),
):
    video = db.videos.get(video_id)
    if not video:
        raise HTTPException(status_code=404, detail=success(None, "视频不存在"))

    comment_id = str(uuid.uuid4())
    comment = Comment(
        id=comment_id,
        video_id=video_id,
        user_id=current_user_id,
        content=req.content,
        likes_count=0,
        reply_count=0,
        parent_id=req.parentId,
        created_at=int(time.time() * 1000),
    )

    db.comments[comment_id] = comment
    db.comment_likes[comment_id] = set()

    if video_id not in db.video_comments:
        db.video_comments[video_id] = []
    db.video_comments[video_id].append(comment_id)

    video.comments_count += 1

    if req.parentId:
        parent_comment = db.comments.get(req.parentId)
        if parent_comment:
            parent_comment.reply_count += 1

    if video.user_id != current_user_id and not req.parentId:
        current_user = db.users.get(current_user_id)
        add_notification(
            video.user_id,
            NotificationType.COMMENT,
            f"{current_user.nickname if current_user else '有人'} 评论了你的视频：{req.content[:20]}",
            video_id,
        )

    return success(enrich_comment(comment, current_user_id), "评论成功")


@router.post("/comment/{comment_id}/like")
async def like_comment(
    comment_id: str,
    current_user_id: str = Depends(get_current_user_id),
):
    comment = db.comments.get(comment_id)
    if not comment:
        raise HTTPException(status_code=404, detail=success(None, "评论不存在"))

    liked_set = db.comment_likes.get(comment_id, set())
    is_liked = current_user_id in liked_set

    if is_liked:
        liked_set.discard(current_user_id)
        comment.likes_count = max(0, comment.likes_count - 1)
    else:
        liked_set.add(current_user_id)
        comment.likes_count += 1

    db.comment_likes[comment_id] = liked_set

    return success({
        "isLiked": not is_liked,
        "likesCount": comment.likes_count,
    })


@router.get("/comment/{comment_id}/replies")
async def get_comment_replies(
    comment_id: str,
    page: int = 1,
    page_size: int = 20,
    current_user_id: str = Depends(get_current_user_id),
):
    all_comments = [
        c for c in db.comments.values()
        if c.parent_id == comment_id
    ]
    all_comments.sort(key=lambda c: c.created_at)

    start = (page - 1) * page_size
    end = start + page_size
    replies = [enrich_comment(c, current_user_id) for c in all_comments[start:end]]

    return success({
        "list": replies,
        "total": len(all_comments),
        "page": page,
        "pageSize": page_size,
        "hasMore": end < len(all_comments),
    })


@router.get("/video/{video_id}/danmakus")
async def get_danmakus(video_id: str):
    danmakus = db.danmakus.get(video_id, [])
    return success({"list": [d.model_dump() for d in danmakus]})


@router.post("/video/{video_id}/danmakus")
async def send_danmaku(
    video_id: str,
    req: DanmakuCreateRequest,
    current_user_id: str = Depends(get_current_user_id),
):
    video = db.videos.get(video_id)
    if not video:
        raise HTTPException(status_code=404, detail=success(None, "视频不存在"))

    danmaku = Danmaku(
        id=str(uuid.uuid4()),
        video_id=video_id,
        user_id=current_user_id,
        content=req.content,
        timestamp=req.timestamp,
        color=req.color,
        created_at=int(time.time() * 1000),
    )

    if video_id not in db.danmakus:
        db.danmakus[video_id] = []
    db.danmakus[video_id].append(danmaku)

    return success(danmaku.model_dump(), "弹幕发送成功")


@router.post("/user/{user_id}/follow")
async def follow_user(
    user_id: str,
    current_user_id: str = Depends(get_current_user_id),
):
    if user_id == current_user_id:
        raise HTTPException(status_code=400, detail=success(None, "不能关注自己"))

    target_user = db.users.get(user_id)
    if not target_user:
        raise HTTPException(status_code=404, detail=success(None, "用户不存在"))

    following_set = db.user_followings.get(current_user_id, set())
    followers_set = db.user_followers.get(user_id, set())

    is_followed = user_id in following_set

    if is_followed:
        following_set.discard(user_id)
        followers_set.discard(current_user_id)
        target_user.followers_count = max(0, target_user.followers_count - 1)

        current_user = db.users.get(current_user_id)
        if current_user:
            current_user.following_count = max(0, current_user.following_count - 1)
    else:
        following_set.add(user_id)
        followers_set.add(current_user_id)
        target_user.followers_count += 1

        current_user = db.users.get(current_user_id)
        if current_user:
            current_user.following_count += 1

        current_user_obj = db.users.get(current_user_id)
        add_notification(
            user_id,
            NotificationType.FOLLOW,
            f"{current_user_obj.nickname if current_user_obj else '有人'} 关注了你",
            current_user_id,
        )

    db.user_followings[current_user_id] = following_set
    db.user_followers[user_id] = followers_set

    return success({
        "isFollowed": not is_followed,
        "followersCount": target_user.followers_count,
    })
