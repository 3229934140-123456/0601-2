import time
from fastapi import APIRouter, Depends
from ..database import db
from ..utils import success, get_current_user_id

router = APIRouter()


@router.get("/video")
async def search_videos(
    keyword: str = "",
    page: int = 1,
    page_size: int = 20,
    sort_by: str = "relevance",
    current_user_id: str = Depends(get_current_user_id),
):
    if not keyword:
        return success({"list": [], "total": 0, "page": page, "pageSize": page_size, "hasMore": False})

    keyword_lower = keyword.lower()

    videos = [
        v for v in db.videos.values()
        if v.status == "published" and (
            keyword_lower in v.title.lower() or
            keyword_lower in v.description.lower()
        )
    ]

    if sort_by == "new":
        videos.sort(key=lambda v: v.created_at, reverse=True)
    elif sort_by == "likes":
        videos.sort(key=lambda v: v.likes_count, reverse=True)
    elif sort_by == "views":
        videos.sort(key=lambda v: v.views_count, reverse=True)
    else:
        def relevance_score(v):
            title_match = 10 if keyword_lower in v.title.lower() else 0
            return title_match + v.views_count / 1000
        videos.sort(key=relevance_score, reverse=True)

    start = (page - 1) * page_size
    end = start + page_size
    result_videos = videos[start:end]

    user_likes = db.user_likes.get(current_user_id, set())
    video_list = []
    for v in result_videos:
        author = db.users.get(v.user_id)
        video_list.append({
            "id": v.id,
            "title": v.title,
            "description": v.description,
            "coverUrl": v.cover_url,
            "duration": v.duration,
            "likesCount": v.likes_count,
            "commentsCount": v.comments_count,
            "viewsCount": v.views_count,
            "isLiked": v.id in user_likes,
            "author": {
                "id": author.id if author else "",
                "nickname": author.nickname if author else "",
                "avatar": author.avatar if author else "",
            } if author else None,
        })

    return success({
        "list": video_list,
        "total": len(videos),
        "page": page,
        "pageSize": page_size,
        "hasMore": end < len(videos),
    })


@router.get("/user")
async def search_users(
    keyword: str = "",
    page: int = 1,
    page_size: int = 20,
    current_user_id: str = Depends(get_current_user_id),
):
    if not keyword:
        return success({"list": [], "total": 0, "page": page, "pageSize": page_size, "hasMore": False})

    keyword_lower = keyword.lower()

    users = [
        u for u in db.users.values()
        if keyword_lower in u.nickname.lower() or
           keyword_lower in u.username.lower()
    ]
    users.sort(key=lambda u: u.followers_count, reverse=True)

    start = (page - 1) * page_size
    end = start + page_size
    result_users = users[start:end]

    user_followings = db.user_followings.get(current_user_id, set())
    user_list = [
        {
            "id": u.id,
            "nickname": u.nickname,
            "username": u.username,
            "avatar": u.avatar,
            "bio": u.bio,
            "followersCount": u.followers_count,
            "worksCount": u.works_count,
            "isVerified": u.is_verified,
            "isFollowed": u.id in user_followings,
        }
        for u in result_users
    ]

    return success({
        "list": user_list,
        "total": len(users),
        "page": page,
        "pageSize": page_size,
        "hasMore": end < len(users),
    })


@router.get("/topic")
async def search_topics(
    keyword: str = "",
    page: int = 1,
    page_size: int = 20,
):
    if not keyword:
        topics = list(db.topics.values())
        topics.sort(key=lambda t: t.views_count, reverse=True)
        start = (page - 1) * page_size
        end = start + page_size
        return success({
            "list": [t.model_dump() for t in topics[start:end]],
            "total": len(topics),
            "page": page,
            "pageSize": page_size,
            "hasMore": end < len(topics),
        })

    keyword_lower = keyword.lower()

    topics = [
        t for t in db.topics.values()
        if keyword_lower in t.name.lower() or
           keyword_lower in t.description.lower()
    ]
    topics.sort(key=lambda t: t.views_count, reverse=True)

    start = (page - 1) * page_size
    end = start + page_size
    result_topics = topics[start:end]

    return success({
        "list": [t.model_dump() for t in result_topics],
        "total": len(topics),
        "page": page,
        "pageSize": page_size,
        "hasMore": end < len(topics),
    })


@router.get("/hot/words")
async def hot_words():
    hot_words = [
        {"word": "美食探店", "hot": 98000, "tag": "热"},
        {"word": "旅行vlog", "hot": 76000, "tag": "新"},
        {"word": "健身打卡", "hot": 65000, "tag": "热"},
        {"word": "萌宠日常", "hot": 58000, "tag": ""},
        {"word": "科技数码", "hot": 45000, "tag": ""},
        {"word": "音乐分享", "hot": 38000, "tag": "新"},
        {"word": "穿搭分享", "hot": 32000, "tag": ""},
        {"word": "搞笑视频", "hot": 28000, "tag": ""},
        {"word": "知识科普", "hot": 23000, "tag": ""},
        {"word": "生活记录", "hot": 18000, "tag": ""},
    ]

    return success({
        "list": hot_words,
        "updateTime": int(time.time() * 1000),
    })


@router.get("/hot/videos")
async def hot_videos(
    limit: int = 20,
    current_user_id: str = Depends(get_current_user_id),
):
    hot_videos_list = [
        v for v in db.videos.values()
        if v.status == "published"
    ]
    hot_videos_list.sort(key=lambda v: v.views_count, reverse=True)
    hot_videos_list = hot_videos_list[:limit]

    user_likes = db.user_likes.get(current_user_id, set())
    video_list = []
    for i, v in enumerate(hot_videos_list):
        author = db.users.get(v.user_id)
        video_list.append({
            "rank": i + 1,
            "id": v.id,
            "title": v.title,
            "coverUrl": v.cover_url,
            "duration": v.duration,
            "viewsCount": v.views_count,
            "likesCount": v.likes_count,
            "isLiked": v.id in user_likes,
            "author": {
                "id": author.id if author else "",
                "nickname": author.nickname if author else "",
                "avatar": author.avatar if author else "",
            } if author else None,
        })

    return success({
        "list": video_list,
        "updateTime": int(time.time() * 1000),
    })


@router.get("/hot/creators")
async def hot_creators(
    limit: int = 20,
    current_user_id: str = Depends(get_current_user_id),
):
    creators = list(db.users.values())
    creators.sort(key=lambda u: u.followers_count, reverse=True)
    creators = creators[:limit]

    user_followings = db.user_followings.get(current_user_id, set())
    creator_list = [
        {
            "rank": i + 1,
            "id": u.id,
            "nickname": u.nickname,
            "avatar": u.avatar,
            "bio": u.bio,
            "followersCount": u.followers_count,
            "worksCount": u.works_count,
            "likesCount": u.likes_count,
            "isVerified": u.is_verified,
            "isFollowed": u.id in user_followings,
        }
        for i, u in enumerate(creators)
    ]

    return success({
        "list": creator_list,
        "updateTime": int(time.time() * 1000),
    })
