from fastapi import APIRouter, Depends, HTTPException
from ..database import db
from ..utils import success, get_current_user_id

router = APIRouter()


@router.get("/overview")
async def creator_overview(current_user_id: str = Depends(get_current_user_id)):
    user = db.users.get(current_user_id)
    if not user:
        raise HTTPException(status_code=404, detail=success(None, "用户不存在"))

    videos = [
        v for v in db.videos.values()
        if v.user_id == current_user_id and v.status == "published"
    ]

    total_views = sum(v.views_count for v in videos)
    total_likes = sum(v.likes_count for v in videos)
    total_comments = sum(v.comments_count for v in videos)
    total_shares = sum(v.shares_count for v in videos)

    new_fans = int(user.followers_count * 0.05)
    new_views = int(total_views * 0.03)
    new_likes = int(total_likes * 0.02)

    return success({
        "summary": {
            "followersCount": user.followers_count,
            "worksCount": user.works_count,
            "totalViews": total_views,
            "totalLikes": total_likes,
            "totalComments": total_comments,
            "totalShares": total_shares,
        },
        "today": {
            "newFans": new_fans,
            "newViews": new_views,
            "newLikes": new_likes,
            "newComments": int(total_comments * 0.04),
        },
        "trend": {
            "fansTrend": [120, 150, 180, 200, 220, 250, 280],
            "viewsTrend": [5000, 6200, 7800, 8500, 9200, 10500, 12000],
            "likesTrend": [800, 950, 1100, 1300, 1500, 1700, 2000],
            "dates": ["06-01", "06-02", "06-03", "06-04", "06-05", "06-06", "06-07"],
        },
    })


@router.get("/videos")
async def creator_videos(
    page: int = 1,
    page_size: int = 20,
    status: str = "all",
    current_user_id: str = Depends(get_current_user_id),
):
    videos = [
        v for v in db.videos.values()
        if v.user_id == current_user_id
    ]

    if status != "all":
        videos = [v for v in videos if v.status == status]

    videos.sort(key=lambda v: v.created_at, reverse=True)

    start = (page - 1) * page_size
    end = start + page_size
    result_videos = videos[start:end]

    video_list = [
        {
            "id": v.id,
            "title": v.title,
            "coverUrl": v.cover_url,
            "duration": v.duration,
            "status": v.status,
            "viewsCount": v.views_count,
            "likesCount": v.likes_count,
            "commentsCount": v.comments_count,
            "sharesCount": v.shares_count,
            "createdAt": v.created_at,
        }
        for v in result_videos
    ]

    return success({
        "list": video_list,
        "total": len(videos),
        "page": page,
        "pageSize": page_size,
        "hasMore": end < len(videos),
    })


@router.get("/videos/{video_id}/data")
async def video_data(
    video_id: str,
    current_user_id: str = Depends(get_current_user_id),
):
    video = db.videos.get(video_id)
    if not video or video.user_id != current_user_id:
        raise HTTPException(status_code=404, detail=success(None, "视频不存在"))

    return success({
        "videoId": video.id,
        "title": video.title,
        "coverUrl": video.cover_url,
        "views": {
            "total": video.views_count,
            "today": int(video.views_count * 0.1),
            "trend": {
                "data": [100, 250, 380, 520, 680, 850, 1000],
                "dates": ["06-01", "06-02", "06-03", "06-04", "06-05", "06-06", "06-07"],
            },
        },
        "interactions": {
            "likes": video.likes_count,
            "comments": video.comments_count,
            "shares": video.shares_count,
            "collects": video.collects_count,
        },
        "audience": {
            "gender": {"male": 55, "female": 45},
            "age": [
                {"range": "<18", "percent": 10},
                {"range": "18-24", "percent": 35},
                {"range": "25-30", "percent": 28},
                {"range": "31-40", "percent": 18},
                {"range": ">40", "percent": 9},
            ],
            "regions": [
                {"name": "广东", "value": 15},
                {"name": "浙江", "value": 12},
                {"name": "江苏", "value": 10},
                {"name": "北京", "value": 9},
                {"name": "上海", "value": 8},
                {"name": "其他", "value": 46},
            ],
        },
        "playDuration": {
            "avgPlayDuration": int(video.duration * 0.7),
            "completionRate": 68.5,
            "dropPoints": [
                {"time": 0, "retention": 100},
                {"time": 5, "retention": 85},
                {"time": 10, "retention": 72},
                {"time": 15, "retention": 65},
                {"time": 20, "retention": 58},
                {"time": 25, "retention": 52},
                {"time": 30, "retention": 45},
            ],
        },
    })


@router.get("/earnings")
async def creator_earnings(current_user_id: str = Depends(get_current_user_id)):
    earning = db.earnings.get(current_user_id)
    if not earning:
        raise HTTPException(status_code=404, detail=success(None, "收益数据不存在"))

    return success({
        "total": {
            "totalEarnings": earning.total_earnings,
            "withdrawable": earning.withdrawable,
            "pending": earning.pending,
        },
        "overview": {
            "today": earning.today_earnings,
            "yesterday": int(earning.today_earnings * 0.85),
            "week": earning.week_earnings,
            "month": earning.month_earnings,
        },
        "trend": {
            "daily": [
                {"date": "06-01", "amount": 35.5},
                {"date": "06-02", "amount": 42.3},
                {"date": "06-03", "amount": 38.7},
                {"date": "06-04", "amount": 55.2},
                {"date": "06-05", "amount": 48.9},
                {"date": "06-06", "amount": 62.1},
                {"date": "06-07", "amount": earning.today_earnings},
            ],
        },
        "sources": [
            {"name": "创作收益", "amount": int(earning.month_earnings * 0.6), "percent": 60},
            {"name": "广告分成", "amount": int(earning.month_earnings * 0.25), "percent": 25},
            {"name": "直播打赏", "amount": int(earning.month_earnings * 0.1), "percent": 10},
            {"name": "其他", "amount": int(earning.month_earnings * 0.05), "percent": 5},
        ],
    })


@router.get("/fans")
async def creator_fans(current_user_id: str = Depends(get_current_user_id)):
    user = db.users.get(current_user_id)
    if not user:
        raise HTTPException(status_code=404, detail=success(None, "用户不存在"))

    follower_ids = list(db.user_followers.get(current_user_id, set()))
    follower_users = [
        db.users[uid] for uid in follower_ids if uid in db.users
    ][:10]

    user_followings = db.user_followings.get(current_user_id, set())
    import time
    recent_fans = [
        {
            "id": u.id,
            "nickname": u.nickname,
            "avatar": u.avatar,
            "isFollowBack": u.id in user_followings,
            "followTime": int(time.time() * 1000) - 3600000 * (i + 1),
        }
        for i, u in enumerate(follower_users)
    ]

    return success({
        "total": user.followers_count,
        "newToday": int(user.followers_count * 0.02),
        "trend": {
            "data": [100, 150, 200, 280, 350, 420, 500],
            "dates": ["06-01", "06-02", "06-03", "06-04", "06-05", "06-06", "06-07"],
        },
        "recentFans": recent_fans,
        "analysis": {
            "gender": {"male": 58, "female": 42},
            "age": [
                {"range": "18-24", "percent": 40},
                {"range": "25-30", "percent": 30},
                {"range": "31-40", "percent": 20},
                {"range": "其他", "percent": 10},
            ],
            "activeTime": [
                {"hour": 0, "value": 20},
                {"hour": 6, "value": 15},
                {"hour": 12, "value": 45},
                {"hour": 18, "value": 70},
                {"hour": 21, "value": 90},
                {"hour": 23, "value": 50},
            ],
        },
    })
