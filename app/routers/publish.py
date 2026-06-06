import uuid
import time
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional, List
from ..database import db
from ..utils import success, get_current_user_id
from ..models import VideoStatus, Draft, UploadTask

router = APIRouter()


class UploadInitRequest(BaseModel):
    fileName: str
    fileSize: int


class ChunkRequest(BaseModel):
    chunkSize: int = 1024 * 1024
    chunkIndex: int = 0


class CoverSelectRequest(BaseModel):
    videoUrl: str
    timestamp: float = 0


class PublishVideoRequest(BaseModel):
    title: str = ""
    description: str = ""
    coverUrl: str = ""
    videoUrl: str = ""
    duration: int = 0
    topics: List[str] = []
    draftId: Optional[str] = None


class DraftCreateRequest(BaseModel):
    title: str = ""
    description: str = ""
    coverUrl: str = ""
    videoUrl: str = ""
    duration: int = 0
    topics: List[str] = []


class DraftUpdateRequest(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    coverUrl: Optional[str] = None
    videoUrl: Optional[str] = None
    duration: Optional[int] = None
    topics: Optional[List[str]] = None


@router.post("/upload/init")
async def upload_init(
    req: UploadInitRequest,
    current_user_id: str = Depends(get_current_user_id),
):
    task_id = str(uuid.uuid4())
    upload_task = UploadTask(
        id=task_id,
        user_id=current_user_id,
        file_name=req.fileName,
        file_size=req.fileSize,
        uploaded_size=0,
        status="uploading",
        created_at=int(time.time() * 1000),
    )
    db.upload_tasks[task_id] = upload_task

    return success({
        "taskId": task_id,
        "uploadUrl": f"/api/publish/upload/{task_id}",
    })


@router.get("/upload/{task_id}/status")
async def upload_status(task_id: str):
    task = db.upload_tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=success(None, "上传任务不存在"))

    return success({
        "taskId": task.id,
        "status": task.status,
        "uploadedSize": task.uploaded_size,
        "fileSize": task.file_size,
        "progress": int((task.uploaded_size / task.file_size) * 100),
        "videoUrl": task.video_url,
    })


@router.post("/upload/{task_id}/chunk")
async def upload_chunk(
    task_id: str,
    req: ChunkRequest,
):
    task = db.upload_tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=success(None, "上传任务不存在"))

    task.uploaded_size += req.chunkSize

    if task.uploaded_size >= task.file_size:
        task.status = "success"
        task.video_url = f"https://example.com/videos/{task_id}.mp4"

    return success({
        "taskId": task.id,
        "uploadedSize": task.uploaded_size,
        "progress": int((task.uploaded_size / task.file_size) * 100),
    })


@router.get("/drafts")
async def get_drafts(current_user_id: str = Depends(get_current_user_id)):
    drafts = db.drafts.get(current_user_id, [])
    sorted_drafts = sorted(drafts, key=lambda d: d.updated_at, reverse=True)

    return success({
        "list": [d.model_dump() for d in sorted_drafts],
        "total": len(sorted_drafts),
    })


@router.post("/drafts")
async def create_draft(
    req: DraftCreateRequest,
    current_user_id: str = Depends(get_current_user_id),
):
    draft_id = str(uuid.uuid4())
    draft = Draft(
        id=draft_id,
        user_id=current_user_id,
        title=req.title,
        description=req.description,
        cover_url=req.coverUrl,
        video_url=req.videoUrl,
        duration=req.duration,
        topics=req.topics,
        updated_at=int(time.time() * 1000),
    )

    if current_user_id not in db.drafts:
        db.drafts[current_user_id] = []
    db.drafts[current_user_id].append(draft)

    return success({
        "draftId": draft_id,
        **draft.model_dump(),
    }, "草稿保存成功")


@router.put("/drafts/{draft_id}")
async def update_draft(
    draft_id: str,
    req: DraftUpdateRequest,
    current_user_id: str = Depends(get_current_user_id),
):
    drafts = db.drafts.get(current_user_id, [])
    draft_index = None
    for i, d in enumerate(drafts):
        if d.id == draft_id:
            draft_index = i
            break

    if draft_index is None:
        raise HTTPException(status_code=404, detail=success(None, "草稿不存在"))

    draft = drafts[draft_index]
    if req.title is not None:
        draft.title = req.title
    if req.description is not None:
        draft.description = req.description
    if req.coverUrl is not None:
        draft.cover_url = req.coverUrl
    if req.videoUrl is not None:
        draft.video_url = req.videoUrl
    if req.duration is not None:
        draft.duration = req.duration
    if req.topics is not None:
        draft.topics = req.topics
    draft.updated_at = int(time.time() * 1000)

    return success(draft.model_dump(), "草稿更新成功")


@router.delete("/drafts/{draft_id}")
async def delete_draft(
    draft_id: str,
    current_user_id: str = Depends(get_current_user_id),
):
    drafts = db.drafts.get(current_user_id, [])
    filtered = [d for d in drafts if d.id != draft_id]

    if len(filtered) == len(drafts):
        raise HTTPException(status_code=404, detail=success(None, "草稿不存在"))

    db.drafts[current_user_id] = filtered
    return success(None, "草稿删除成功")


@router.post("/cover/select")
async def select_cover(req: CoverSelectRequest):
    cover_url = f"https://picsum.photos/seed/{int(time.time())}/720/1280"

    frames = []
    for i in range(5):
        frames.append({
            "index": i,
            "timestamp": i * 5,
            "thumbnailUrl": f"https://picsum.photos/seed/frame{i}/180/320",
        })

    return success({
        "selectedCover": cover_url,
        "frames": frames,
    }, "封面生成成功")


@router.get("/topics/suggest")
async def suggest_topics(keyword: str = ""):
    topics = list(db.topics.values())

    if keyword:
        keyword_lower = keyword.lower()
        topics = [t for t in topics if keyword_lower in t.name.lower()]

    topics.sort(key=lambda t: t.video_count, reverse=True)

    return success({
        "list": [t.model_dump() for t in topics[:10]],
    })


@router.post("/video")
async def publish_video(
    req: PublishVideoRequest,
    current_user_id: str = Depends(get_current_user_id),
):
    video_id = str(uuid.uuid4())
    now = int(time.time() * 1000)

    from ..models import Video
    video = Video(
        id=video_id,
        user_id=current_user_id,
        title=req.title,
        description=req.description,
        cover_url=req.coverUrl,
        video_url=req.videoUrl,
        duration=req.duration,
        likes_count=0,
        comments_count=0,
        shares_count=0,
        views_count=0,
        collects_count=0,
        topics=req.topics,
        status=VideoStatus.REVIEWING,
        created_at=now,
        updated_at=now,
    )

    db.videos[video_id] = video

    if req.draftId:
        drafts = db.drafts.get(current_user_id, [])
        db.drafts[current_user_id] = [d for d in drafts if d.id != req.draftId]

    user = db.users.get(current_user_id)
    if user:
        user.works_count += 1

    for topic_id in req.topics:
        topic = db.topics.get(topic_id)
        if topic:
            topic.video_count += 1

    return success({
        "videoId": video_id,
        "status": "reviewing",
        "estimatedTime": "预计10分钟内完成审核",
    }, "视频提交成功，正在审核中")


@router.get("/video/{video_id}/status")
async def video_publish_status(video_id: str):
    video = db.videos.get(video_id)
    if not video:
        raise HTTPException(status_code=404, detail=success(None, "视频不存在"))

    result = {
        "videoId": video.id,
        "status": video.status,
        "title": video.title,
        "createdAt": video.created_at,
    }
    if video.status == VideoStatus.REMOVED:
        result["rejectReason"] = "内容不符合平台规范"

    return success(result)
