import uuid
import time
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from ..database import db, add_notification
from ..utils import success, get_current_user_id
from ..models import Report, ReportStatus, VideoStatus, NotificationType

router = APIRouter()


class ReportRequest(BaseModel):
    videoId: str
    reason: str
    description: str = ""


class ProcessReportRequest(BaseModel):
    action: str
    remark: Optional[str] = None


class RemoveVideoRequest(BaseModel):
    reason: str = ""


class RejectVideoRequest(BaseModel):
    reason: str = "不符合平台规范"


@router.post("/report/video")
async def report_video(
    req: ReportRequest,
    current_user_id: str = Depends(get_current_user_id),
):
    video = db.videos.get(req.videoId)
    if not video:
        raise HTTPException(status_code=404, detail=success(None, "视频不存在"))

    report_id = str(uuid.uuid4())
    report = Report(
        id=report_id,
        video_id=req.videoId,
        user_id=current_user_id,
        reason=req.reason,
        description=req.description,
        status=ReportStatus.PENDING,
        created_at=int(time.time() * 1000),
    )

    db.reports[report_id] = report

    return success({"reportId": report_id}, "举报已提交，我们将尽快处理")


@router.get("/report/list")
async def report_list(
    page: int = 1,
    page_size: int = 20,
    status: str = "all",
):
    reports = list(db.reports.values())

    if status != "all":
        reports = [r for r in reports if r.status == status]

    reports.sort(key=lambda r: r.created_at, reverse=True)

    start = (page - 1) * page_size
    end = start + page_size
    result_reports = reports[start:end]

    report_list = []
    for r in result_reports:
        video = db.videos.get(r.video_id)
        user = db.users.get(r.user_id)
        report_list.append({
            "id": r.id,
            "video": {
                "id": video.id if video else "",
                "title": video.title if video else "",
                "coverUrl": video.cover_url if video else "",
                "status": video.status if video else "",
            } if video else None,
            "reporter": {
                "id": user.id if user else "",
                "nickname": user.nickname if user else "",
                "avatar": user.avatar if user else "",
            } if user else None,
            "reason": r.reason,
            "description": r.description,
            "status": r.status,
            "createdAt": r.created_at,
        })

    return success({
        "list": report_list,
        "total": len(reports),
        "page": page,
        "pageSize": page_size,
        "hasMore": end < len(reports),
    })


@router.post("/report/{report_id}/process")
async def process_report(
    report_id: str,
    req: ProcessReportRequest,
):
    report = db.reports.get(report_id)
    if not report:
        raise HTTPException(status_code=404, detail=success(None, "举报记录不存在"))

    report.status = ReportStatus.PROCESSING

    if req.action == "remove":
        video = db.videos.get(report.video_id)
        if video:
            video.status = VideoStatus.REMOVED
            video.updated_at = int(time.time() * 1000)

            add_notification(
                video.user_id,
                NotificationType.SYSTEM,
                f'您的视频"{video.title}"因违反平台规范已被下架',
                video.id,
            )
        report.status = ReportStatus.RESOLVED
    elif req.action == "dismiss":
        report.status = ReportStatus.RESOLVED

    return success({"reportId": report_id, "status": report.status}, "处理完成")


@router.post("/video/{video_id}/remove")
async def remove_video(
    video_id: str,
    req: RemoveVideoRequest,
):
    video = db.videos.get(video_id)
    if not video:
        raise HTTPException(status_code=404, detail=success(None, "视频不存在"))

    video.status = VideoStatus.REMOVED
    video.updated_at = int(time.time() * 1000)

    add_notification(
        video.user_id,
        NotificationType.SYSTEM,
        f'您的视频"{video.title}"因{req.reason or "违反平台规范"}已被下架',
        video.id,
    )

    return success({"videoId": video_id, "status": "removed"}, "视频已下架")


@router.post("/video/{video_id}/restore")
async def restore_video(video_id: str):
    video = db.videos.get(video_id)
    if not video:
        raise HTTPException(status_code=404, detail=success(None, "视频不存在"))

    video.status = VideoStatus.PUBLISHED
    video.updated_at = int(time.time() * 1000)

    add_notification(
        video.user_id,
        NotificationType.SYSTEM,
        f'您的视频"{video.title}"已恢复上架',
        video.id,
    )

    return success({"videoId": video_id, "status": "published"}, "视频已恢复")


@router.get("/notifications")
async def get_notifications(
    page: int = 1,
    page_size: int = 20,
    type: str = "all",
    current_user_id: str = Depends(get_current_user_id),
):
    notifications = db.notifications.get(current_user_id, [])

    if type != "all":
        notifications = [n for n in notifications if n.type == type]

    start = (page - 1) * page_size
    end = start + page_size
    result_notifications = notifications[start:end]

    unread_count = sum(1 for n in notifications if not n.is_read)

    return success({
        "list": [n.model_dump() for n in result_notifications],
        "total": len(notifications),
        "unreadCount": unread_count,
        "page": page,
        "pageSize": page_size,
        "hasMore": end < len(notifications),
    })


@router.get("/notifications/unread-count")
async def unread_count(current_user_id: str = Depends(get_current_user_id)):
    notifications = db.notifications.get(current_user_id, [])

    unread_count = sum(1 for n in notifications if not n.is_read)

    by_type = {
        "like": sum(1 for n in notifications if not n.is_read and n.type == "like"),
        "comment": sum(1 for n in notifications if not n.is_read and n.type == "comment"),
        "follow": sum(1 for n in notifications if not n.is_read and n.type == "follow"),
        "system": sum(1 for n in notifications if not n.is_read and n.type == "system"),
    }

    return success({
        "total": unread_count,
        "byType": by_type,
    })


@router.post("/notifications/{notification_id}/read")
async def mark_notification_read(
    notification_id: str,
    current_user_id: str = Depends(get_current_user_id),
):
    notifications = db.notifications.get(current_user_id, [])
    notification = next((n for n in notifications if n.id == notification_id), None)

    if not notification:
        raise HTTPException(status_code=404, detail=success(None, "通知不存在"))

    notification.is_read = True

    return success(None, "已标记为已读")


@router.post("/notifications/read-all")
async def mark_all_read(current_user_id: str = Depends(get_current_user_id)):
    notifications = db.notifications.get(current_user_id, [])

    for n in notifications:
        n.is_read = True

    return success(None, "全部标记为已读")


@router.get("/audit/videos")
async def audit_videos(
    page: int = 1,
    page_size: int = 20,
    status: str = "reviewing",
):
    videos = [v for v in db.videos.values() if v.status == status]
    videos.sort(key=lambda v: v.created_at)

    start = (page - 1) * page_size
    end = start + page_size
    result_videos = videos[start:end]

    video_list = []
    for v in result_videos:
        author = db.users.get(v.user_id)
        video_list.append({
            "id": v.id,
            "title": v.title,
            "description": v.description,
            "coverUrl": v.cover_url,
            "videoUrl": v.video_url,
            "duration": v.duration,
            "status": v.status,
            "topics": v.topics,
            "author": {
                "id": author.id if author else "",
                "nickname": author.nickname if author else "",
                "avatar": author.avatar if author else "",
            } if author else None,
            "createdAt": v.created_at,
        })

    return success({
        "list": video_list,
        "total": len(videos),
        "page": page,
        "pageSize": page_size,
        "hasMore": end < len(videos),
    })


@router.post("/audit/videos/{video_id}/approve")
async def approve_video(video_id: str):
    video = db.videos.get(video_id)
    if not video or video.status != VideoStatus.REVIEWING:
        raise HTTPException(status_code=404, detail=success(None, "视频不存在或状态不正确"))

    video.status = VideoStatus.PUBLISHED
    video.updated_at = int(time.time() * 1000)

    add_notification(
        video.user_id,
        NotificationType.SYSTEM,
        f'您的视频"{video.title}"审核通过，已发布',
        video.id,
    )

    return success({"videoId": video_id, "status": "published"}, "审核通过")


@router.post("/audit/videos/{video_id}/reject")
async def reject_video(
    video_id: str,
    req: RejectVideoRequest,
):
    video = db.videos.get(video_id)
    if not video or video.status != VideoStatus.REVIEWING:
        raise HTTPException(status_code=404, detail=success(None, "视频不存在或状态不正确"))

    video.status = VideoStatus.REMOVED
    video.updated_at = int(time.time() * 1000)

    add_notification(
        video.user_id,
        NotificationType.SYSTEM,
        f'您的视频"{video.title}"审核未通过，原因：{req.reason}',
        video.id,
    )

    return success({"videoId": video_id, "status": "removed"}, "审核驳回")
