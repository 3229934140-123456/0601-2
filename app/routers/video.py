from fastapi import APIRouter, Depends, HTTPException
from typing import Optional
from ..database import db
from ..utils import success, get_current_user_id

router = APIRouter()


def enrich_video(video, current_user_id: str):
    author = db.users.get(video.user_id)
    user_likes = db.user_likes.get(current_user_id, set())
    user_collects = db.user_collects.get(current_user_id, set())
    user_followings = db.user_followings.get(current_user_id, set())

    return {
        **video.model_dump(),
        "author": {
            "id": author.id if author else video.user_id,
            "nickname": author.nickname if author else "未知用户",
            "avatar": author.avatar if author else "",
            "isVerified": author.is_verified if author else False,
        },
        "isLiked": video.id in user_likes,
        "isCollected": video.id in user_collects,
        "isFollowed": video.user_id in user_followings,
    }


@router.get("/recommend")
async def recommend(
    page: int = 1,
    page_size: int = 10,
    current_user_id: str = Depends(get_current_user_id),
):
    published_videos = [
        v for v in db.videos.values() if v.status == "published"
    ]
    published_videos.sort(key=lambda v: v.likes_count, reverse=True)

    start = (page - 1) * page_size
    end = start + page_size
    videos = published_videos[start:end]

    enriched_videos = [enrich_video(v, current_user_id) for v in videos]

    return success({
        "list": enriched_videos,
        "total": len(published_videos),
        "page": page,
        "pageSize": page_size,
        "hasMore": end < len(published_videos),
    })


@router.get("/following")
async def following_feed(
    page: int = 1,
    page_size: int = 10,
    current_user_id: str = Depends(get_current_user_id),
):
    following_set = db.user_followings.get(current_user_id, set())

    published_videos = [
        v for v in db.videos.values()
        if v.status == "published" and v.user_id in following_set
    ]
    published_videos.sort(key=lambda v: v.created_at, reverse=True)

    start = (page - 1) * page_size
    end = start + page_size
    videos = published_videos[start:end]

    enriched_videos = [enrich_video(v, current_user_id) for v in videos]

    return success({
        "list": enriched_videos,
        "total": len(published_videos),
        "page": page,
        "pageSize": page_size,
        "hasMore": end < len(published_videos),
    })


@router.get("/{video_id}")
async def video_detail(
    video_id: str,
    current_user_id: str = Depends(get_current_user_id),
):
    video = db.videos.get(video_id)

    if not video or video.status != "published":
        raise HTTPException(status_code=404, detail=success(None, "视频不存在"))

    video.views_count += 1

    return success(enrich_video(video, current_user_id))


@router.get("/hot/ranking")
async def hot_ranking(
    type: str = "hot",
    limit: int = 20,
    current_user_id: str = Depends(get_current_user_id),
):
    videos = [v for v in db.videos.values() if v.status == "published"]

    if type == "hot":
        videos.sort(key=lambda v: v.views_count, reverse=True)
    elif type == "likes":
        videos.sort(key=lambda v: v.likes_count, reverse=True)
    elif type == "new":
        videos.sort(key=lambda v: v.created_at, reverse=True)
    else:
        videos.sort(key=lambda v: v.views_count, reverse=True)

    top_videos = [enrich_video(v, current_user_id) for v in videos[:limit]]

    return success({
        "type": type,
        "updateTime": int(__import__("time").time() * 1000),
        "list": top_videos,
    })
