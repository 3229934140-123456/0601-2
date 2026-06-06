from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional, List
from ..database import db
from ..utils import success, get_current_user_id
from ..models import User

router = APIRouter()


class ProfileUpdateRequest(BaseModel):
    nickname: Optional[str] = None
    avatar: Optional[str] = None
    bio: Optional[str] = None


def enrich_user(user: User, current_user_id: str):
    user_followings = db.user_followings.get(current_user_id, set())
    my_followers = db.user_followers.get(current_user_id, set())

    return {
        **user.model_dump(),
        "isFollowed": user.id in user_followings,
        "isFollowingMe": user.id in my_followers,
    }


@router.get("/profile")
async def get_profile(current_user_id: str = Depends(get_current_user_id)):
    user = db.users.get(current_user_id)
    if not user:
        raise HTTPException(status_code=404, detail=success(None, "用户不存在"))

    return success(user.model_dump())


@router.put("/profile")
async def update_profile(
    req: ProfileUpdateRequest,
    current_user_id: str = Depends(get_current_user_id),
):
    user = db.users.get(current_user_id)
    if not user:
        raise HTTPException(status_code=404, detail=success(None, "用户不存在"))

    if req.nickname is not None:
        user.nickname = req.nickname
    if req.avatar is not None:
        user.avatar = req.avatar
    if req.bio is not None:
        user.bio = req.bio

    return success(user.model_dump(), "资料更新成功")


@router.get("/{user_id}")
async def get_user(
    user_id: str,
    current_user_id: str = Depends(get_current_user_id),
):
    user = db.users.get(user_id)
    if not user:
        raise HTTPException(status_code=404, detail=success(None, "用户不存在"))

    return success(enrich_user(user, current_user_id))


@router.get("/{user_id}/videos")
async def get_user_videos(
    user_id: str,
    page: int = 1,
    page_size: int = 20,
):
    user_videos = [
        v for v in db.videos.values()
        if v.user_id == user_id and v.status == "published"
    ]
    user_videos.sort(key=lambda v: v.created_at, reverse=True)

    start = (page - 1) * page_size
    end = start + page_size
    videos = user_videos[start:end]

    video_list = [
        {
            "id": v.id,
            "title": v.title,
            "coverUrl": v.cover_url,
            "duration": v.duration,
            "likesCount": v.likes_count,
            "viewsCount": v.views_count,
            "createdAt": v.created_at,
        }
        for v in videos
    ]

    return success({
        "list": video_list,
        "total": len(user_videos),
        "page": page,
        "pageSize": page_size,
        "hasMore": end < len(user_videos),
    })


@router.get("/{user_id}/likes")
async def get_user_likes(
    user_id: str,
    page: int = 1,
    page_size: int = 20,
):
    liked_set = db.user_likes.get(user_id, set())

    liked_videos = [
        v for v in db.videos.values()
        if v.id in liked_set and v.status == "published"
    ]
    liked_videos.sort(key=lambda v: v.created_at, reverse=True)

    start = (page - 1) * page_size
    end = start + page_size
    videos = liked_videos[start:end]

    video_list = [
        {
            "id": v.id,
            "title": v.title,
            "coverUrl": v.cover_url,
            "duration": v.duration,
            "likesCount": v.likes_count,
            "viewsCount": v.views_count,
        }
        for v in videos
    ]

    return success({
        "list": video_list,
        "total": len(liked_videos),
        "page": page,
        "pageSize": page_size,
        "hasMore": end < len(liked_videos),
    })


@router.get("/{user_id}/collects")
async def get_user_collects(
    user_id: str,
    page: int = 1,
    page_size: int = 20,
):
    collected_set = db.user_collects.get(user_id, set())

    collected_videos = [
        v for v in db.videos.values()
        if v.id in collected_set and v.status == "published"
    ]
    collected_videos.sort(key=lambda v: v.created_at, reverse=True)

    start = (page - 1) * page_size
    end = start + page_size
    videos = collected_videos[start:end]

    video_list = [
        {
            "id": v.id,
            "title": v.title,
            "coverUrl": v.cover_url,
            "duration": v.duration,
            "likesCount": v.likes_count,
            "viewsCount": v.views_count,
        }
        for v in videos
    ]

    return success({
        "list": video_list,
        "total": len(collected_videos),
        "page": page,
        "pageSize": page_size,
        "hasMore": end < len(collected_videos),
    })


@router.get("/{user_id}/following")
async def get_user_following(
    user_id: str,
    page: int = 1,
    page_size: int = 20,
    current_user_id: str = Depends(get_current_user_id),
):
    following_ids = list(db.user_followings.get(user_id, set()))

    following_users = [
        db.users[uid] for uid in following_ids if uid in db.users
    ]
    following_users.sort(key=lambda u: u.followers_count, reverse=True)

    start = (page - 1) * page_size
    end = start + page_size
    users = [enrich_user(u, current_user_id) for u in following_users[start:end]]

    return success({
        "list": users,
        "total": len(following_users),
        "page": page,
        "pageSize": page_size,
        "hasMore": end < len(following_users),
    })


@router.get("/{user_id}/followers")
async def get_user_followers(
    user_id: str,
    page: int = 1,
    page_size: int = 20,
    current_user_id: str = Depends(get_current_user_id),
):
    follower_ids = list(db.user_followers.get(user_id, set()))

    follower_users = [
        db.users[uid] for uid in follower_ids if uid in db.users
    ]
    follower_users.sort(key=lambda u: u.followers_count, reverse=True)

    start = (page - 1) * page_size
    end = start + page_size
    users = [enrich_user(u, current_user_id) for u in follower_users[start:end]]

    return success({
        "list": users,
        "total": len(follower_users),
        "page": page,
        "pageSize": page_size,
        "hasMore": end < len(follower_users),
    })
