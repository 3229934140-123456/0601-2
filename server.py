import json
import re
import time
import uuid
import math
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

from app.database import db
from app.models import (
    Video, VideoStatus, Comment, Danmaku, Draft, DraftHistory,
    UploadTask, UploadChunk, Report, ReportStatus,
    NotificationType, Topic, TopicApply, UploadStatus, VideoStatsDaily
)


def success(data=None, message="success"):
    return {"code": 0, "message": message, "data": data}


def error(message, code=1):
    return {"code": code, "message": message}


def get_user_id(headers):
    return headers.get("x-user-id", "u1")


def enrich_video(v, uid):
    author = db.users.get(v.user_id)
    likes = db.user_likes.get(uid, set())
    collects = db.user_collects.get(uid, set())
    follows = db.user_followings.get(uid, set())
    topic_list = []
    for tid in v.topics:
        t = db.topics.get(tid)
        if t:
            topic_list.append(t.to_dict())
    return {
        **v.to_dict(),
        "author": {
            "id": author.id if author else v.user_id,
            "nickname": author.nickname if author else "未知用户",
            "avatar": author.avatar if author else "",
            "isVerified": author.is_verified if author else False,
        } if author else None,
        "isLiked": v.id in likes,
        "isCollected": v.id in collects,
        "isFollowed": v.user_id in follows,
        "topicList": topic_list,
    }


def enrich_user(u, uid):
    follows = db.user_followings.get(uid, set())
    fans = db.user_followers.get(uid, set())
    return {
        **u.to_dict(),
        "isFollowed": u.id in follows,
        "isFollowingMe": u.id in fans,
    }


def enrich_comment(c, uid):
    u = db.users.get(c.user_id)
    liked = db.comment_likes.get(c.id, set())
    return {
        **c.to_dict(),
        "user": {
            "id": u.id if u else "",
            "nickname": u.nickname if u else "",
            "avatar": u.avatar if u else "",
            "isVerified": u.is_verified if u else False,
        } if u else None,
        "isLiked": uid in liked,
    }


def handle_video(path, qp, uid, body=None, method="GET"):
    if method == "GET":
        if path == "/api/video/recommend":
            page, ps = int(qp.get("page", ["1"])[0]), int(qp.get("pageSize", ["10"])[0])
            vs = sorted([v for v in db.videos.values() if v.status == VideoStatus.PUBLISHED],
                        key=lambda x: x.likes_count, reverse=True)
            s, e = (page - 1) * ps, page * ps
            return success({
                "list": [enrich_video(v, uid) for v in vs[s:e]],
                "total": len(vs), "page": page, "pageSize": ps, "hasMore": e < len(vs)
            })
        if path == "/api/video/following":
            page, ps = int(qp.get("page", ["1"])[0]), int(qp.get("pageSize", ["10"])[0])
            fs = db.user_followings.get(uid, set())
            vs = sorted([v for v in db.videos.values()
                         if v.status == VideoStatus.PUBLISHED and v.user_id in fs],
                        key=lambda x: x.created_at, reverse=True)
            s, e = (page - 1) * ps, page * ps
            return success({
                "list": [enrich_video(v, uid) for v in vs[s:e]],
                "total": len(vs), "page": page, "pageSize": ps, "hasMore": e < len(vs)
            })
        if path == "/api/video/hot/ranking":
            t = qp.get("type", ["hot"])[0]
            limit = int(qp.get("limit", ["20"])[0])
            vs = [v for v in db.videos.values() if v.status == VideoStatus.PUBLISHED]
            if t == "likes":
                vs.sort(key=lambda x: x.likes_count, reverse=True)
            elif t == "new":
                vs.sort(key=lambda x: x.created_at, reverse=True)
            else:
                vs.sort(key=lambda x: x.views_count, reverse=True)
            vs = vs[:limit]
            items = []
            for i, v in enumerate(vs):
                a = db.users.get(v.user_id)
                items.append({
                    "rank": i + 1,
                    "id": v.id,
                    "title": v.title,
                    "coverUrl": v.cover_url,
                    "duration": v.duration,
                    "viewsCount": v.views_count,
                    "likesCount": v.likes_count,
                    "isLiked": v.id in db.user_likes.get(uid, set()),
                    "author": {"id": a.id, "nickname": a.nickname, "avatar": a.avatar} if a else None
                })
            return success({"list": items, "updateTime": int(time.time() * 1000)})
        m = re.match(r"/api/video/([\w-]+)$", path)
        if m:
            vid = m.group(1)
            v = db.videos.get(vid)
            if not v or v.status == VideoStatus.REMOVED:
                return error("视频不存在", 404)
            v.views_count += 1
            if v.status == VideoStatus.PUBLISHED and v.topics:
                db.add_topic_interaction(v.topics, views=1)
            return success(enrich_video(v, uid))
    return None


def handle_publish(path, qp, uid, body=None, method="GET"):
    if path == "/api/publish/upload/init" and method == "POST":
        file_name = body.get("fileName", "")
        file_size = int(body.get("fileSize", 0))
        if not file_name or file_size <= 0:
            return error("文件名和文件大小不能为空", 400)
        chunk_size = int(body.get("chunkSize", 5 * 1024 * 1024))
        total_chunks = math.ceil(file_size / chunk_size)
        chunks = []
        for i in range(total_chunks):
            size = chunk_size if i < total_chunks - 1 else file_size - (total_chunks - 1) * chunk_size
            chunks.append(UploadChunk(chunk_index=i, size=size, uploaded=False, failed=False))
        tid = str(uuid.uuid4())[:8]
        task = UploadTask(
            id=tid, user_id=uid, file_name=file_name, file_size=file_size,
            uploaded_size=0, status=UploadStatus.INIT, video_url=None,
            chunk_size=chunk_size, total_chunks=total_chunks, chunks=chunks,
            created_at=int(time.time() * 1000), updated_at=int(time.time() * 1000)
        )
        db.upload_tasks[tid] = task
        return success(task.to_dict(), "上传任务创建成功")

    m = re.match(r"/api/publish/upload/([\w-]+)/chunk$", path)
    if m and method == "POST":
        tid = m.group(1)
        task = db.upload_tasks.get(tid)
        if not task:
            return error("上传任务不存在", 404)
        if task.user_id != uid:
            return error("无权限操作此任务", 403)
        if task.status == UploadStatus.CANCELLED:
            return error("上传任务已取消", 400)
        chunk_index = int(body.get("chunkIndex", 0))
        if chunk_index < 0 or chunk_index >= task.total_chunks:
            return error("分片索引无效", 400)
        chunk = task.chunks[chunk_index]
        chunk.uploaded = True
        chunk.failed = False
        task.uploaded_size = sum(c.size for c in task.chunks if c.uploaded)
        task.status = UploadStatus.UPLOADING
        task.updated_at = int(time.time() * 1000)
        uploaded_count = sum(1 for c in task.chunks if c.uploaded)
        return success({
            "chunkIndex": chunk_index,
            "uploaded": True,
            "uploadedChunks": uploaded_count,
            "totalChunks": task.total_chunks,
            "progress": int(uploaded_count / task.total_chunks * 100)
        }, "分片上传成功")

    m = re.match(r"/api/publish/upload/([\w-]+)/chunk/retry$", path)
    if m and method == "POST":
        tid = m.group(1)
        task = db.upload_tasks.get(tid)
        if not task:
            return error("上传任务不存在", 404)
        if task.user_id != uid:
            return error("无权限操作此任务", 403)
        chunk_index = int(body.get("chunkIndex", 0))
        if chunk_index < 0 or chunk_index >= task.total_chunks:
            return error("分片索引无效", 400)
        chunk = task.chunks[chunk_index]
        chunk.uploaded = False
        chunk.failed = True
        task.updated_at = int(time.time() * 1000)
        return success({"chunkIndex": chunk_index, "failed": True}, "分片标记为失败，可重新上传")

    m = re.match(r"/api/publish/upload/([\w-]+)/status$", path)
    if m and method == "GET":
        tid = m.group(1)
        task = db.upload_tasks.get(tid)
        if not task:
            return error("上传任务不存在", 404)
        if task.user_id != uid:
            return error("无权限查看此任务", 403)
        data = task.to_dict()
        data["chunks"] = [c.to_dict() for c in task.chunks]
        return success(data)

    m = re.match(r"/api/publish/upload/([\w-]+)/cancel$", path)
    if m and method == "POST":
        tid = m.group(1)
        task = db.upload_tasks.get(tid)
        if not task:
            return error("上传任务不存在", 404)
        if task.user_id != uid:
            return error("无权限操作此任务", 403)
        task.status = UploadStatus.CANCELLED
        task.updated_at = int(time.time() * 1000)
        return success(task.to_dict(), "上传已取消")

    m = re.match(r"/api/publish/upload/([\w-]+)/complete$", path)
    if m and method == "POST":
        tid = m.group(1)
        task = db.upload_tasks.get(tid)
        if not task:
            return error("上传任务不存在", 404)
        if task.user_id != uid:
            return error("无权限操作此任务", 403)
        failed_chunks = [c.chunk_index for c in task.chunks if not c.uploaded]
        if failed_chunks:
            return success({
                "completed": False,
                "failedChunks": failed_chunks,
                "message": "存在未上传或失败的分片"
            }, "上传未完成")
        task.status = UploadStatus.COMPLETED
        task.video_url = f"https://example.com/uploads/{tid}.mp4"
        task.updated_at = int(time.time() * 1000)
        data = task.to_dict()
        return success({"completed": True, "videoUrl": task.video_url, "task": data}, "上传完成")

    if path == "/api/publish/upload/list" and method == "GET":
        tasks = [t for t in db.upload_tasks.values() if t.user_id == uid]
        tasks.sort(key=lambda x: x.created_at, reverse=True)
        return success({"list": [t.to_dict() for t in tasks], "total": len(tasks)})

    if path == "/api/publish/video" and method == "POST":
        title = body.get("title", "").strip()
        video_url = body.get("videoUrl", "").strip()
        cover_url = body.get("coverUrl", "").strip()
        duration = int(body.get("duration", 0))
        description = body.get("description", "")
        topic_ids = body.get("topics", []) or []
        if not title:
            return error("标题不能为空", 400)
        if len(title) > 100:
            return error("标题不能超过100字", 400)
        if not video_url:
            return error("视频地址不能为空", 400)
        if not cover_url:
            return error("封面不能为空", 400)
        if duration <= 0:
            return error("视频时长无效", 400)
        if len(topic_ids) > 5:
            return error("最多绑定5个话题", 400)
        valid_topics = []
        for tid in topic_ids:
            if tid in db.topics:
                valid_topics.append(tid)
        vid = str(uuid.uuid4())[:8]
        now = int(time.time() * 1000)
        video = Video(
            id=vid, user_id=uid, title=title, description=description,
            cover_url=cover_url, video_url=video_url, duration=duration,
            likes_count=0, comments_count=0, shares_count=0, views_count=0,
            collects_count=0, topics=valid_topics, status=VideoStatus.REVIEWING,
            created_at=now, updated_at=now
        )
        db.videos[vid] = video
        db.video_topics[vid] = valid_topics
        user = db.users.get(uid)
        if user:
            user.works_count += 1
        db.add_notification(uid, NotificationType.SYSTEM, "视频审核中",
                            f'你的视频"{title}"已提交审核',
                            related_id=vid, related_type="video")
        return success({"videoId": vid, "status": VideoStatus.REVIEWING}, "发布成功，正在审核中")

    if path == "/api/publish/drafts" and method == "GET":
        drafts = db.drafts.get(uid, [])
        drafts.sort(key=lambda x: x.updated_at, reverse=True)
        page = int(qp.get("page", ["1"])[0])
        ps = int(qp.get("pageSize", ["20"])[0])
        s, e = (page - 1) * ps, page * ps
        return success({
            "list": [d.to_dict() for d in drafts[s:e]],
            "total": len(drafts), "page": page, "pageSize": ps,
            "hasMore": e < len(drafts)
        })

    if path == "/api/publish/drafts/save" and method == "POST":
        draft_id = body.get("draftId")
        title = body.get("title", "")
        description = body.get("description", "")
        cover_url = body.get("coverUrl", "")
        video_url = body.get("videoUrl", "")
        duration = int(body.get("duration", 0))
        topics = body.get("topics", []) or []
        now = int(time.time() * 1000)
        user_drafts = db.drafts.get(uid, [])
        if draft_id:
            draft = next((d for d in user_drafts if d.id == draft_id), None)
            if not draft:
                return error("草稿不存在", 404)
            if len(draft.history) < 10:
                history = DraftHistory(
                    version=len(draft.history) + 1,
                    title=draft.title, description=draft.description,
                    cover_url=draft.cover_url, video_url=draft.video_url,
                    duration=draft.duration, topics=draft.topics[:],
                    updated_at=draft.updated_at
                )
                draft.history.append(history)
            else:
                for i in range(9):
                    draft.history[i] = draft.history[i + 1]
                history = DraftHistory(
                    version=len(draft.history) + 1,
                    title=draft.title, description=draft.description,
                    cover_url=draft.cover_url, video_url=draft.video_url,
                    duration=draft.duration, topics=draft.topics[:],
                    updated_at=draft.updated_at
                )
                draft.history[9] = history
            draft.title = title
            draft.description = description
            draft.cover_url = cover_url
            draft.video_url = video_url
            draft.duration = duration
            draft.topics = topics
            if duration > 0:
                draft.duration_unknown = False
            draft.updated_at = now
            return success({"draftId": draft.id, **draft.to_dict()}, "草稿保存成功")
        else:
            did = str(uuid.uuid4())[:8]
            draft = Draft(
                id=did, user_id=uid, title=title, description=description,
                cover_url=cover_url, video_url=video_url, duration=duration,
                topics=topics, updated_at=now, history=[],
                duration_unknown=duration == 0
            )
            if uid not in db.drafts:
                db.drafts[uid] = []
            db.drafts[uid].append(draft)
            return success({"draftId": did, **draft.to_dict()}, "草稿创建成功")

    m = re.match(r"/api/publish/drafts/([\w-]+)$", path)
    if m and method == "GET":
        did = m.group(1)
        drafts = db.drafts.get(uid, [])
        draft = next((d for d in drafts if d.id == did), None)
        if not draft:
            return error("草稿不存在", 404)
        data = draft.to_dict()
        data["history"] = [h.to_dict() for h in reversed(draft.history)]
        return success(data)

    if m and method == "DELETE":
        did = m.group(1)
        drafts = db.drafts.get(uid, [])
        draft = next((d for d in drafts if d.id == did), None)
        if not draft:
            return error("草稿不存在", 404)
        db.drafts[uid] = [d for d in drafts if d.id != did]
        return success(None, "草稿删除成功")

    m = re.match(r"/api/publish/drafts/([\w-]+)/restore$", path)
    if m and method == "POST":
        did = m.group(1)
        version = int(body.get("version", 0))
        drafts = db.drafts.get(uid, [])
        draft = next((d for d in drafts if d.id == did), None)
        if not draft:
            return error("草稿不存在", 404)
        history = next((h for h in draft.history if h.version == version), None)
        if not history:
            return error("历史版本不存在", 404)
        h = DraftHistory(
            version=len(draft.history) + 1,
            title=draft.title, description=draft.description,
            cover_url=draft.cover_url, video_url=draft.video_url,
            duration=draft.duration, topics=draft.topics[:],
            updated_at=draft.updated_at
        )
        draft.history.append(h)
        draft.title = history.title
        draft.description = history.description
        draft.cover_url = history.cover_url
        draft.video_url = history.video_url
        draft.duration = history.duration
        draft.topics = history.topics[:]
        draft.updated_at = int(time.time() * 1000)
        return success(draft.to_dict(), "恢复成功")

    m = re.match(r"/api/publish/drafts/from-video/([\w-]+)$", path)
    if m and method == "POST":
        vid = m.group(1)
        v = db.videos.get(vid)
        if not v:
            return error("视频不存在", 404)
        if v.user_id != uid:
            return error("无权限操作", 403)
        did = str(uuid.uuid4())[:8]
        now = int(time.time() * 1000)
        draft = Draft(
            id=did, user_id=uid, title=v.title, description=v.description,
            cover_url=v.cover_url, video_url=v.video_url, duration=v.duration,
            topics=v.topics[:], updated_at=now, history=[]
        )
        if uid not in db.drafts:
            db.drafts[uid] = []
        db.drafts[uid].append(draft)
        return success({"draftId": did, **draft.to_dict()}, "已保存为草稿")

    m = re.match(r"/api/publish/drafts/from-upload/([\w-]+)$", path)
    if m and method == "POST":
        tid = m.group(1)
        task = db.upload_tasks.get(tid)
        if not task:
            return error("上传任务不存在", 404)
        if task.user_id != uid:
            return error("无权限操作", 403)
        if task.status != UploadStatus.COMPLETED:
            return error("上传未完成，无法保存为草稿", 400)
        did = str(uuid.uuid4())[:8]
        now = int(time.time() * 1000)
        title = body.get("title", task.file_name) if body else task.file_name
        cover_url = body.get("coverUrl", "") if body else ""
        description = body.get("description", "") if body else ""
        topics = body.get("topics", []) if body else []
        duration = body.get("duration", 0) if body else 0
        if not cover_url:
            cover_url = f"https://picsum.photos/seed/{tid}/720/1280"
        duration_unknown = duration == 0
        draft = Draft(
            id=did, user_id=uid, title=title, description=description,
            cover_url=cover_url, video_url=task.video_url or "",
            duration=duration, topics=topics, updated_at=now, history=[],
            file_size=task.file_size, upload_task_id=tid,
            duration_unknown=duration_unknown
        )
        if uid not in db.drafts:
            db.drafts[uid] = []
        db.drafts[uid].append(draft)
        return success({"draftId": did, **draft.to_dict()}, "已保存为草稿")

    m = re.match(r"/api/publish/drafts/([\w-]+)/update-duration$", path)
    if m and method == "POST":
        did = m.group(1)
        user_drafts = db.drafts.get(uid, [])
        draft = next((d for d in user_drafts if d.id == did), None)
        if not draft:
            return error("草稿不存在", 404)
        duration = int(body.get("duration", 0) or 0)
        if duration <= 0:
            return error("视频时长必须大于0", 400)
        _save_draft_history(draft)
        draft.duration = duration
        draft.duration_unknown = False
        draft.updated_at = int(time.time() * 1000)
        return success(draft.to_dict(), "时长已更新")

    if path == "/api/publish/drafts/batch-delete" and method == "POST":
        draft_ids = body.get("draftIds", []) or []
        user_drafts = db.drafts.get(uid, [])
        deleted = 0
        for did in draft_ids:
            draft = next((d for d in user_drafts if d.id == did), None)
            if draft:
                user_drafts.remove(draft)
                deleted += 1
        return success({"deleted": deleted, "total": len(user_drafts)}, f"已删除{deleted}个草稿")

    if path == "/api/publish/upload/batch-clean" and method == "POST":
        status_filter = body.get("status", ["cancelled", "failed"]) or ["cancelled", "failed"]
        tasks = [t for t in db.upload_tasks.values() if t.user_id == uid]
        deleted = 0
        for t in tasks:
            if t.status in status_filter:
                del db.upload_tasks[t.id]
                deleted += 1
        return success({"deleted": deleted}, f"已清理{deleted}个上传任务")

    if path == "/api/publish/workbench" and method == "GET":
        page = int(qp.get("page", ["1"])[0])
        ps = int(qp.get("pageSize", ["20"])[0])
        status = qp.get("status", ["all"])[0]
        keyword = qp.get("keyword", [""])[0]
        topic_id = qp.get("topicId", [""])[0]
        start_date = qp.get("startDate", [None])[0]
        end_date = qp.get("endDate", [None])[0]
        type_filter = qp.get("type", ["video"])[0]

        if type_filter == "draft":
            items = db.drafts.get(uid, [])
            result = []
            for d in items:
                if keyword and keyword not in d.title:
                    continue
                if topic_id and topic_id not in d.topics:
                    continue
                if start_date:
                    try:
                        t = int(time.mktime(time.strptime(start_date, "%Y-%m-%d")) * 1000)
                        if d.updated_at < t:
                            continue
                    except:
                        pass
                if end_date:
                    try:
                        t = int(time.mktime(time.strptime(end_date, "%Y-%m-%d")) * 1000) + 86400000
                        if d.updated_at >= t:
                            continue
                    except:
                        pass
                result.append(d)
            result.sort(key=lambda x: x.updated_at, reverse=True)
            s, e = (page - 1) * ps, page * ps
            return success({
                "list": [d.to_dict() for d in result[s:e]],
                "total": len(result), "page": page, "pageSize": ps,
                "hasMore": e < len(result)
            })

        if type_filter == "upload":
            items = [t for t in db.upload_tasks.values() if t.user_id == uid]
            if status != "all":
                if status == "uploading":
                    items = [t for t in items if t.status in [UploadStatus.INIT, UploadStatus.UPLOADING]]
                elif status == "failed":
                    items = [t for t in items if t.status == UploadStatus.FAILED]
                else:
                    items = [t for t in items if t.status == status]
            if keyword:
                kw = keyword.lower()
                items = [t for t in items if kw in t.file_name.lower()]
            if start_date:
                try:
                    t = int(time.mktime(time.strptime(start_date, "%Y-%m-%d")) * 1000)
                    items = [x for x in items if x.created_at >= t]
                except:
                    pass
            if end_date:
                try:
                    t = int(time.mktime(time.strptime(end_date, "%Y-%m-%d")) * 1000) + 86400000
                    items = [x for x in items if x.created_at < t]
                except:
                    pass
            items.sort(key=lambda x: x.created_at, reverse=True)
            s, e = (page - 1) * ps, page * ps
            return success({
                "list": [t.to_dict() for t in items[s:e]],
                "total": len(items), "page": page, "pageSize": ps,
                "hasMore": e < len(items)
            })

        vs = [v for v in db.videos.values() if v.user_id == uid]
        if status != "all":
            vs = [v for v in vs if v.status == status]
        if keyword:
            kw = keyword.lower()
            vs = [v for v in vs if kw in v.title.lower() or kw in v.description.lower()]
        if topic_id:
            vs = [v for v in vs if topic_id in v.topics]
        if start_date:
            try:
                t = int(time.mktime(time.strptime(start_date, "%Y-%m-%d")) * 1000)
                vs = [v for v in vs if v.created_at >= t]
            except:
                pass
        if end_date:
            try:
                t = int(time.mktime(time.strptime(end_date, "%Y-%m-%d")) * 1000) + 86400000
                vs = [v for v in vs if v.created_at < t]
            except:
                pass

        vs.sort(key=lambda x: x.created_at, reverse=True)
        s, e = (page - 1) * ps, page * ps
        items = []
        for v in vs[s:e]:
            item = enrich_video(v, uid)
            items.append(item)

        stats = {
            "total": len([v for v in db.videos.values() if v.user_id == uid]),
            "published": len([v for v in db.videos.values() if v.user_id == uid and v.status == VideoStatus.PUBLISHED]),
            "reviewing": len([v for v in db.videos.values() if v.user_id == uid and v.status == VideoStatus.REVIEWING]),
            "removed": len([v for v in db.videos.values() if v.user_id == uid and v.status == VideoStatus.REMOVED]),
            "rejected": len([v for v in db.videos.values() if v.user_id == uid and v.status == VideoStatus.REJECTED]),
            "drafts": len(db.drafts.get(uid, [])),
            "uploading": len([t for t in db.upload_tasks.values() if t.user_id == uid and t.status in [UploadStatus.INIT, UploadStatus.UPLOADING]]),
            "uploadFailed": len([t for t in db.upload_tasks.values() if t.user_id == uid and t.status == UploadStatus.FAILED]),
        }

        return success({
            "list": items, "total": len(vs),
            "page": page, "pageSize": ps, "hasMore": e < len(vs),
            "stats": stats
        })

    m = re.match(r"/api/publish/video/([\w-]+)/resubmit$", path)
    if m and method == "POST":
        vid = m.group(1)
        v = db.videos.get(vid)
        if not v or v.user_id != uid:
            return error("作品不存在", 404)
        if v.status != VideoStatus.REJECTED:
            return error("只有被驳回的作品才能重新提交", 400)
        title = body.get("title", v.title)
        description = body.get("description", v.description)
        cover_url = body.get("coverUrl", v.cover_url)
        topics = body.get("topics", v.topics)
        if not title or len(title) > 100:
            return error("标题不能为空且不能超过100字", 400)
        if not cover_url:
            return error("封面不能为空", 400)
        v.title = title
        v.description = description
        v.cover_url = cover_url
        v.topics = topics
        v.status = VideoStatus.REVIEWING
        v.reject_reason = None
        v.updated_at = int(time.time() * 1000)
        return success({"videoId": vid, "status": v.status}, "已重新提交审核")

    if path == "/api/publish/topics/suggest" and method == "GET":
        kw = qp.get("keyword", [""])[0]
        kwl = kw.lower()
        sort = qp.get("sort", ["heat"])[0]
        ts = list(db.topics.values())
        if kwl:
            ts = [t for t in ts if kwl in t.name.lower() or kwl in t.description.lower()]
        if sort == "videoCount":
            ts.sort(key=lambda x: x.video_count, reverse=True)
        elif sort == "views":
            ts.sort(key=lambda x: x.views_count, reverse=True)
        else:
            ts.sort(key=lambda x: x.heat, reverse=True)
        return success({"list": [t.to_dict() for t in ts[:10]], "total": len(ts)})

    if path == "/api/publish/topics/apply" and method == "POST":
        name = body.get("name", "").strip()
        description = body.get("description", "").strip()
        if not name:
            return error("话题名称不能为空", 400)
        if len(name) > 20:
            return error("话题名称不能超过20字", 400)
        for t in db.topics.values():
            if t.name == name:
                return error("话题已存在", 400)
        aid = str(uuid.uuid4())[:8]
        apply = TopicApply(
            id=aid, user_id=uid, name=name, description=description,
            status="pending", created_at=int(time.time() * 1000), reject_reason=None
        )
        db.topic_applies[aid] = apply
        return success({"applyId": aid, "status": "pending"}, "申请已提交，等待审核")

    return None


def handle_account(path, qp, uid, body=None, method="GET"):
    if method == "GET":
        if path == "/api/account/profile":
            u = db.users.get(uid)
            if not u:
                return error("用户不存在", 404)
            return success(enrich_user(u, uid))
        m = re.match(r"/api/account/([\w-]+)$", path)
        if m:
            uid2 = m.group(1)
            u = db.users.get(uid2)
            if not u:
                return error("用户不存在", 404)
            return success(enrich_user(u, uid))
        m = re.match(r"/api/account/([\w-]+)/videos$", path)
        if m:
            uid2 = m.group(1)
            page = int(qp.get("page", ["1"])[0])
            ps = int(qp.get("pageSize", ["10"])[0])
            vs = sorted([v for v in db.videos.values()
                         if v.user_id == uid2 and v.status == VideoStatus.PUBLISHED],
                        key=lambda x: x.created_at, reverse=True)
            s, e = (page - 1) * ps, page * ps
            return success({
                "list": [enrich_video(v, uid) for v in vs[s:e]],
                "total": len(vs), "page": page, "pageSize": ps, "hasMore": e < len(vs)
            })
        m = re.match(r"/api/account/([\w-]+)/likes$", path)
        if m:
            uid2 = m.group(1)
            page = int(qp.get("page", ["1"])[0])
            ps = int(qp.get("pageSize", ["10"])[0])
            liked = db.user_likes.get(uid2, set())
            vs = sorted([v for v in db.videos.values()
                         if v.id in liked and v.status == VideoStatus.PUBLISHED],
                        key=lambda x: x.created_at, reverse=True)
            s, e = (page - 1) * ps, page * ps
            return success({
                "list": [enrich_video(v, uid) for v in vs[s:e]],
                "total": len(vs), "page": page, "pageSize": ps, "hasMore": e < len(vs)
            })
        m = re.match(r"/api/account/([\w-]+)/collects$", path)
        if m:
            uid2 = m.group(1)
            page = int(qp.get("page", ["1"])[0])
            ps = int(qp.get("pageSize", ["10"])[0])
            cols = db.user_collects.get(uid2, set())
            vs = sorted([v for v in db.videos.values()
                         if v.id in cols and v.status == VideoStatus.PUBLISHED],
                        key=lambda x: x.created_at, reverse=True)
            s, e = (page - 1) * ps, page * ps
            return success({
                "list": [enrich_video(v, uid) for v in vs[s:e]],
                "total": len(vs), "page": page, "pageSize": ps, "hasMore": e < len(vs)
            })
        m = re.match(r"/api/account/([\w-]+)/following$", path)
        if m:
            uid2 = m.group(1)
            page = int(qp.get("page", ["1"])[0])
            ps = int(qp.get("pageSize", ["10"])[0])
            fids = list(db.user_followings.get(uid2, set()))
            users = [enrich_user(db.users[fid], uid) for fid in fids if fid in db.users]
            users.sort(key=lambda x: x["followersCount"], reverse=True)
            s, e = (page - 1) * ps, page * ps
            return success({
                "list": users[s:e], "total": len(users),
                "page": page, "pageSize": ps, "hasMore": e < len(users)
            })
        m = re.match(r"/api/account/([\w-]+)/followers$", path)
        if m:
            uid2 = m.group(1)
            page = int(qp.get("page", ["1"])[0])
            ps = int(qp.get("pageSize", ["10"])[0])
            fids = list(db.user_followers.get(uid2, set()))
            users = [enrich_user(db.users[fid], uid) for fid in fids if fid in db.users]
            users.sort(key=lambda x: x["followersCount"], reverse=True)
            s, e = (page - 1) * ps, page * ps
            return success({
                "list": users[s:e], "total": len(users),
                "page": page, "pageSize": ps, "hasMore": e < len(users)
            })
    if method == "PUT" and path == "/api/account/profile":
        u = db.users.get(uid)
        if not u:
            return error("用户不存在", 404)
        nickname = body.get("nickname")
        bio = body.get("bio")
        avatar = body.get("avatar")
        if nickname:
            u.nickname = nickname
        if bio is not None:
            u.bio = bio
        if avatar:
            u.avatar = avatar
        return success(u.to_dict(), "资料更新成功")
    return None


def handle_interaction(path, qp, uid, body=None, method="GET"):
    m = re.match(r"/api/interaction/video/([\w-]+)/like$", path)
    if m and method == "POST":
        vid = m.group(1)
        v = db.videos.get(vid)
        if not v or v.status == VideoStatus.REMOVED:
            return error("视频不存在", 404)
        likes = db.user_likes.get(uid, set())
        if vid in likes:
            likes.remove(vid)
            v.likes_count = max(0, v.likes_count - 1)
            liked = False
            if v.status == VideoStatus.PUBLISHED and v.topics:
                db.add_topic_interaction(v.topics, likes=-1)
        else:
            likes.add(vid)
            v.likes_count += 1
            liked = True
            if v.status == VideoStatus.PUBLISHED and v.topics:
                db.add_topic_interaction(v.topics, likes=1)
            if v.user_id != uid:
                user = db.users.get(uid)
                db.add_notification(v.user_id, NotificationType.LIKE, "收到新点赞",
                                    f'{user.nickname if user else "有人"} 赞了你的视频',
                                    related_id=vid, related_type="video",
                                    extra={"fromUserId": uid})
        db.user_likes[uid] = likes
        author = db.users.get(v.user_id)
        if author:
            author.likes_count = sum(x.likes_count for x in db.videos.values() if x.user_id == v.user_id)
        return success({"isLiked": liked, "likesCount": v.likes_count})

    m = re.match(r"/api/interaction/video/([\w-]+)/collect$", path)
    if m and method == "POST":
        vid = m.group(1)
        v = db.videos.get(vid)
        if not v or v.status == VideoStatus.REMOVED:
            return error("视频不存在", 404)
        cols = db.user_collects.get(uid, set())
        if vid in cols:
            cols.remove(vid)
            v.collects_count = max(0, v.collects_count - 1)
            collected = False
            if v.status == VideoStatus.PUBLISHED and v.topics:
                db.add_topic_interaction(v.topics, collects=-1)
        else:
            cols.add(vid)
            v.collects_count += 1
            collected = True
            if v.status == VideoStatus.PUBLISHED and v.topics:
                db.add_topic_interaction(v.topics, collects=1)
        db.user_collects[uid] = cols
        return success({"isCollected": collected, "collectsCount": v.collects_count})

    m = re.match(r"/api/interaction/video/([\w-]+)/share$", path)
    if m and method == "POST":
        vid = m.group(1)
        v = db.videos.get(vid)
        if not v or v.status == VideoStatus.REMOVED:
            return error("视频不存在", 404)
        v.shares_count += 1
        if v.status == VideoStatus.PUBLISHED and v.topics:
            db.add_topic_interaction(v.topics, shares=1)
        return success({"sharesCount": v.shares_count})

    m = re.match(r"/api/interaction/video/([\w-]+)/comments$", path)
    if m and method == "GET":
        vid = m.group(1)
        v = db.videos.get(vid)
        if not v:
            return error("视频不存在", 404)
        page = int(qp.get("page", ["1"])[0])
        ps = int(qp.get("pageSize", ["20"])[0])
        sort = qp.get("sort", ["hot"])[0]
        all_cids = db.video_comments.get(vid, [])
        cs = [db.comments[cid] for cid in all_cids if cid in db.comments]
        cs = [c for c in cs if c.parent_id is None and not c.is_deleted]
        if sort == "new":
            cs.sort(key=lambda x: x.created_at, reverse=True)
        else:
            cs.sort(key=lambda x: x.likes_count, reverse=True)
        s, e = (page - 1) * ps, page * ps
        items = []
        for c in cs[s:e]:
            item = enrich_comment(c, uid)
            reply_cids = [cid for cid in all_cids if cid in db.comments
                          and db.comments[cid].root_id == c.id
                          and not db.comments[cid].is_deleted]
            replies = [db.comments[cid] for cid in reply_cids[:3]]
            item["replies"] = [enrich_comment(r, uid) for r in replies]
            item["repliesTotal"] = len(reply_cids)
            items.append(item)
        return success({
            "list": items, "total": len(cs),
            "page": page, "pageSize": ps, "hasMore": e < len(cs)
        })

    if m and method == "POST":
        vid = m.group(1)
        v = db.videos.get(vid)
        if not v:
            return error("视频不存在", 404)
        content = body.get("content", "").strip()
        if not content:
            return error("评论内容不能为空", 400)
        if len(content) > 500:
            return error("评论内容不能超过500字", 400)
        cid = str(uuid.uuid4())[:8]
        parent_id = body.get("parentId")
        root_id = body.get("rootId")
        parent = None
        if parent_id and parent_id in db.comments:
            parent = db.comments[parent_id]
            if not root_id:
                root_id = parent.root_id if parent.root_id else parent.id
        c = Comment(
            id=cid, video_id=vid, user_id=uid, content=content,
            likes_count=0, reply_count=0,
            parent_id=parent_id, root_id=root_id,
            created_at=int(time.time() * 1000), is_deleted=False
        )
        db.comments[cid] = c
        db.comment_likes[cid] = set()
        if vid not in db.video_comments:
            db.video_comments[vid] = []
        db.video_comments[vid].append(cid)
        v.comments_count += 1
        if v.status == VideoStatus.PUBLISHED and v.topics:
            db.add_topic_interaction(v.topics, comments=1)
        if parent:
            parent.reply_count += 1
        if v.user_id != uid:
            user = db.users.get(uid)
            db.add_notification(v.user_id, NotificationType.COMMENT, "收到新评论",
                                f'{user.nickname if user else "有人"} 评论了你的视频：{content[:30]}',
                                related_id=vid, related_type="video",
                                extra={"commentId": cid})
        return success(enrich_comment(c, uid), "评论成功")

    m = re.match(r"/api/interaction/comments/([\w-]+)/like$", path)
    if m and method == "POST":
        cid = m.group(1)
        c = db.comments.get(cid)
        if not c or c.is_deleted:
            return error("评论不存在", 404)
        liked_set = db.comment_likes.get(cid, set())
        if uid in liked_set:
            liked_set.remove(uid)
            c.likes_count = max(0, c.likes_count - 1)
            liked = False
        else:
            liked_set.add(uid)
            c.likes_count += 1
            liked = True
        db.comment_likes[cid] = liked_set
        return success({"isLiked": liked, "likesCount": c.likes_count})

    m = re.match(r"/api/interaction/comments/([\w-]+)$", path)
    if m and method == "DELETE":
        cid = m.group(1)
        c = db.comments.get(cid)
        if not c:
            return error("评论不存在", 404)
        if c.user_id != uid:
            return error("无权限删除此评论", 403)
        c.is_deleted = True
        v = db.videos.get(c.video_id)
        if v:
            v.comments_count = max(0, v.comments_count - 1)
        return success(None, "评论删除成功")

    m = re.match(r"/api/interaction/comments/([\w-]+)/replies$", path)
    if m and method == "GET":
        cid = m.group(1)
        c = db.comments.get(cid)
        if not c:
            return error("评论不存在", 404)
        page = int(qp.get("page", ["1"])[0])
        ps = int(qp.get("pageSize", ["20"])[0])
        root_id = c.root_id if c.root_id else c.id
        all_cids = db.video_comments.get(c.video_id, [])
        replies = [db.comments[rcid] for rcid in all_cids
                   if rcid in db.comments
                   and db.comments[rcid].root_id == root_id
                   and db.comments[rcid].parent_id == root_id
                   and not db.comments[rcid].is_deleted
                   and rcid != root_id]
        replies.sort(key=lambda x: x.created_at)
        s, e = (page - 1) * ps, page * ps
        items = [enrich_comment(r, uid) for r in replies[s:e]]
        return success({
            "list": items, "total": len(replies),
            "page": page, "pageSize": ps, "hasMore": e < len(replies)
        })

    m = re.match(r"/api/interaction/video/([\w-]+)/danmakus$", path)
    if m and method == "GET":
        vid = m.group(1)
        dms = db.danmakus.get(vid, [])
        return success({"list": [d.to_dict() for d in dms]})
    if m and method == "POST":
        vid = m.group(1)
        v = db.videos.get(vid)
        if not v:
            return error("视频不存在", 404)
        content = body.get("content", "").strip()
        timestamp = float(body.get("timestamp", 0))
        color = body.get("color", "#ffffff")
        if not content:
            return error("弹幕内容不能为空", 400)
        did = str(uuid.uuid4())[:8]
        dm = Danmaku(
            id=did, video_id=vid, user_id=uid, content=content,
            timestamp=timestamp, color=color,
            created_at=int(time.time() * 1000)
        )
        if vid not in db.danmakus:
            db.danmakus[vid] = []
        db.danmakus[vid].append(dm)
        return success(dm.to_dict(), "弹幕发送成功")

    m = re.match(r"/api/interaction/user/([\w-]+)/follow$", path)
    if m and method == "POST":
        target_uid = m.group(1)
        if target_uid == uid:
            return error("不能关注自己", 400)
        target = db.users.get(target_uid)
        if not target:
            return error("用户不存在", 404)
        followings = db.user_followings.get(uid, set())
        followers = db.user_followers.get(target_uid, set())
        if target_uid in followings:
            followings.remove(target_uid)
            followers.discard(uid)
            followed = False
            target.followers_count = max(0, target.followers_count - 1)
            me = db.users.get(uid)
            if me:
                me.following_count = max(0, me.following_count - 1)
        else:
            followings.add(target_uid)
            followers.add(uid)
            followed = True
            target.followers_count += 1
            me = db.users.get(uid)
            if me:
                me.following_count += 1
            user = db.users.get(uid)
            db.add_notification(target_uid, NotificationType.FOLLOW, "收到新关注",
                                f'{user.nickname if user else "有人"} 关注了你',
                                related_id=uid, related_type="user")
        db.user_followings[uid] = followings
        db.user_followers[target_uid] = followers
        return success({"isFollowed": followed, "followersCount": target.followers_count})

    return None


def handle_search(path, qp, uid, body=None, method="GET"):
    if method != "GET":
        return None
    if path == "/api/search/video":
        kw = qp.get("keyword", [""])[0]
        page = int(qp.get("page", ["1"])[0])
        ps = int(qp.get("pageSize", ["20"])[0])
        sb = qp.get("sortBy", ["comprehensive"])[0]
        if not kw:
            vs = [v for v in db.videos.values() if v.status == VideoStatus.PUBLISHED]
        else:
            kwl = kw.lower()
            vs = [v for v in db.videos.values()
                  if v.status == VideoStatus.PUBLISHED
                  and (kwl in v.title.lower() or kwl in v.description.lower())]
        if sb == "likes":
            vs.sort(key=lambda x: x.likes_count, reverse=True)
        elif sb == "views":
            vs.sort(key=lambda x: x.views_count, reverse=True)
        elif sb == "new":
            vs.sort(key=lambda x: x.created_at, reverse=True)
        else:
            kwl = kw.lower()
            vs.sort(key=lambda x: (10 if kwl in x.title.lower() else 0) + x.views_count / 1000, reverse=True)
        s, e = (page - 1) * ps, page * ps
        items = []
        for v in vs[s:e]:
            a = db.users.get(v.user_id)
            author = {"id": a.id, "nickname": a.nickname, "avatar": a.avatar} if a else None
            items.append({
                "id": v.id, "title": v.title, "description": v.description,
                "coverUrl": v.cover_url, "duration": v.duration,
                "likesCount": v.likes_count, "commentsCount": v.comments_count,
                "viewsCount": v.views_count,
                "isLiked": v.id in db.user_likes.get(uid, set()),
                "author": author
            })
        return success({
            "list": items,
            "total": len(vs), "page": page, "pageSize": ps, "hasMore": e < len(vs)
        })
    if path == "/api/search/user":
        kw = qp.get("keyword", [""])[0]
        page, ps = int(qp.get("page", ["1"])[0]), int(qp.get("pageSize", ["20"])[0])
        if not kw:
            return success({"list": [], "total": 0, "page": page, "pageSize": ps, "hasMore": False})
        kwl = kw.lower()
        us = [u for u in db.users.values()
              if kwl in u.nickname.lower() or kwl in u.username.lower()]
        us.sort(key=lambda x: x.followers_count, reverse=True)
        s, e = (page - 1) * ps, page * ps
        fs = db.user_followings.get(uid, set())
        items = []
        for u in us[s:e]:
            items.append({
                "id": u.id, "nickname": u.nickname, "username": u.username,
                "avatar": u.avatar, "bio": u.bio,
                "followersCount": u.followers_count, "worksCount": u.works_count,
                "isVerified": u.is_verified, "isFollowed": u.id in fs
            })
        return success({
            "list": items,
            "total": len(us), "page": page, "pageSize": ps, "hasMore": e < len(us)
        })
    if path == "/api/search/topic":
        kw = qp.get("keyword", [""])[0]
        page, ps = int(qp.get("page", ["1"])[0]), int(qp.get("pageSize", ["20"])[0])
        sort = qp.get("sort", ["heat"])[0]
        ts = list(db.topics.values())
        if kw:
            kwl = kw.lower()
            ts = [t for t in ts if kwl in t.name.lower() or kwl in t.description.lower()]
        if sort == "videoCount":
            ts.sort(key=lambda x: x.video_count, reverse=True)
        elif sort == "views":
            ts.sort(key=lambda x: x.views_count, reverse=True)
        else:
            ts.sort(key=lambda x: x.heat, reverse=True)
        s, e = (page - 1) * ps, page * ps
        return success({
            "list": [t.to_dict() for t in ts[s:e]],
            "total": len(ts), "page": page, "pageSize": ps, "hasMore": e < len(ts)
        })
    if path == "/api/search/hot/words":
        return success({"list": [
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
        ], "updateTime": int(time.time() * 1000)})
    if path == "/api/search/hot/videos":
        limit = int(qp.get("limit", ["20"])[0])
        vs = sorted([v for v in db.videos.values() if v.status == VideoStatus.PUBLISHED],
                    key=lambda x: x.views_count, reverse=True)[:limit]
        ul = db.user_likes.get(uid, set())
        items = []
        for i, v in enumerate(vs):
            a = db.users.get(v.user_id)
            author = {"id": a.id, "nickname": a.nickname, "avatar": a.avatar} if a else None
            items.append({
                "rank": i + 1, "id": v.id, "title": v.title, "coverUrl": v.cover_url,
                "duration": v.duration, "viewsCount": v.views_count,
                "likesCount": v.likes_count, "isLiked": v.id in ul,
                "author": author
            })
        return success({"list": items, "updateTime": int(time.time() * 1000)})
    if path == "/api/search/hot/creators":
        limit = int(qp.get("limit", ["20"])[0])
        us = sorted(list(db.users.values()), key=lambda x: x.followers_count, reverse=True)[:limit]
        fs = db.user_followings.get(uid, set())
        return success({"list": [
            {"rank": i + 1, "id": u.id, "nickname": u.nickname, "avatar": u.avatar,
             "bio": u.bio, "followersCount": u.followers_count, "worksCount": u.works_count,
             "likesCount": u.likes_count, "isVerified": u.is_verified, "isFollowed": u.id in fs}
            for i, u in enumerate(us)
        ], "updateTime": int(time.time() * 1000)})
    return None


def handle_creator(path, qp, uid, body=None, method="GET"):
    if method != "GET":
        return None
    if path == "/api/creator/overview":
        u = db.users.get(uid)
        if not u:
            return error("用户不存在", 404)
        vs = [v for v in db.videos.values() if v.user_id == uid and v.status == VideoStatus.PUBLISHED]
        tv = sum(v.views_count for v in vs)
        tl = sum(v.likes_count for v in vs)
        tc = sum(v.comments_count for v in vs)
        ts = sum(v.shares_count for v in vs)
        tcol = sum(v.collects_count for v in vs)
        return success({
            "summary": {
                "followersCount": u.followers_count, "worksCount": u.works_count,
                "totalViews": tv, "totalLikes": tl, "totalComments": tc,
                "totalShares": ts, "totalCollects": tcol
            },
            "today": {
                "newFans": int(u.followers_count * 0.05),
                "newViews": int(tv * 0.03),
                "newLikes": int(tl * 0.02),
                "newComments": int(tc * 0.04),
                "newCollects": int(tcol * 0.03)
            },
            "trend": {
                "fansTrend": [120, 150, 180, 200, 220, 250, 280],
                "viewsTrend": [5000, 6000, 5500, 7000, 6500, 8000, 9000],
                "likesTrend": [200, 250, 230, 280, 300, 350, 400],
            }
        })

    if path == "/api/creator/videos":
        page = int(qp.get("page", ["1"])[0])
        ps = int(qp.get("pageSize", ["10"])[0])
        status = qp.get("status", ["all"])[0]
        vs = [v for v in db.videos.values() if v.user_id == uid]
        if status != "all":
            vs = [v for v in vs if v.status == status]
        vs.sort(key=lambda x: x.created_at, reverse=True)
        s, e = (page - 1) * ps, page * ps
        items = []
        for v in vs[s:e]:
            items.append({
                **v.to_dict(),
                "heat": int(v.views_count * 0.1 + v.likes_count * 2 + v.comments_count * 5)
            })
        return success({
            "list": items, "total": len(vs),
            "page": page, "pageSize": ps, "hasMore": e < len(vs)
        })

    m = re.match(r"/api/creator/video/([\w-]+)$", path)
    if m:
        vid = m.group(1)
        v = db.videos.get(vid)
        if not v or v.user_id != uid:
            return error("视频不存在", 404)
        stats_list = db.video_stats_daily.get(vid, [])
        return success({
            "video": v.to_dict(),
            "stats": {
                "views": v.views_count,
                "likes": v.likes_count,
                "comments": v.comments_count,
                "collects": v.collects_count,
                "shares": v.shares_count
            },
            "dailyStats": [s.to_dict() for s in stats_list[:7]],
            "playDuration": int(v.duration * v.views_count * 0.6),
            "completionRate": 68.5
        })

    if path == "/api/creator/earnings":
        earning = db.earnings.get(uid)
        if not earning:
            return error("数据不存在", 404)
        return success({
            **earning.to_dict(),
            "dailyEarnings": [
                {"date": f"2026-06-0{i+1}", "amount": 10 + i * 3.5} for i in range(7)
            ],
            "monthEarnings": [
                {"month": "2026-01", "amount": 800},
                {"month": "2026-02", "amount": 1200},
                {"month": "2026-03", "amount": 950},
                {"month": "2026-04", "amount": 1500},
                {"month": "2026-05", "amount": 1800},
                {"month": "2026-06", "amount": 2200},
            ]
        })

    if path == "/api/creator/fans":
        u = db.users.get(uid)
        return success({
            "total": u.followers_count if u else 0,
            "todayNew": 128,
            "gender": {"male": 45, "female": 55},
            "age": [
                {"range": "18-24", "percent": 35},
                {"range": "25-34", "percent": 40},
                {"range": "35-44", "percent": 15},
                {"range": "45+", "percent": 10},
            ],
            "region": [
                {"name": "广东", "percent": 18},
                {"name": "北京", "percent": 12},
                {"name": "上海", "percent": 10},
                {"name": "浙江", "percent": 9},
                {"name": "江苏", "percent": 8},
            ],
            "activeTime": [2, 1, 0, 0, 0, 1, 3, 8, 15, 20, 18, 15,
                           12, 10, 8, 10, 15, 25, 35, 40, 38, 30, 20, 10]
        })

    if path == "/api/creator/stats/trend":
        period = qp.get("period", ["7d"])[0]
        start_date = qp.get("startDate", [None])[0]
        end_date = qp.get("endDate", [None])[0]
        days = 7
        start_ts = 0
        end_ts = 0
        if period == "30d":
            days = 30
            end_ts = int(time.time() * 1000)
            start_ts = end_ts - 86400000 * (days - 1)
        elif period == "custom" and start_date and end_date:
            try:
                t1 = int(time.mktime(time.strptime(start_date, "%Y-%m-%d")) * 1000)
                t2 = int(time.mktime(time.strptime(end_date, "%Y-%m-%d")) * 1000)
                days = max(1, min(90, int((t2 - t1) / 86400000) + 1))
                start_ts = t1
                end_ts = t2
            except:
                days = 7
                end_ts = int(time.time() * 1000)
                start_ts = end_ts - 86400000 * (days - 1)
        else:
            days = 7
            end_ts = int(time.time() * 1000)
            start_ts = end_ts - 86400000 * (days - 1)
        views = []
        likes = []
        comments = []
        collects = []
        shares = []
        new_fans = []
        earnings = []
        dates = []
        for i in range(days):
            d = start_ts + 86400000 * i
            date_str = time.strftime("%Y-%m-%d", time.localtime(d / 1000))
            dates.append(date_str)
            base = 1000 + i * 100
            seed = hash(date_str) % 1000
            views.append(int(base * (1 + 0.2 * math.sin(seed * 0.01))))
            likes.append(int(base * 0.05 * (1 + 0.3 * math.cos(seed * 0.02))))
            comments.append(int(base * 0.01 * (1 + 0.2 * math.sin(seed * 0.03))))
            collects.append(int(base * 0.008 * (1 + 0.25 * math.cos(seed * 0.04))))
            shares.append(int(base * 0.005 * (1 + 0.15 * math.sin(seed * 0.05))))
            new_fans.append(int(50 + i * 3 + 10 * math.sin(seed * 0.06)))
            earnings.append(round(10 + i * 1.5 + 3 * math.sin(seed * 0.07), 2))
        actual_start = dates[0] if dates else start_date
        actual_end = dates[-1] if dates else end_date
        return success({
            "period": period, "days": days,
            "startDate": actual_start,
            "endDate": actual_end,
            "dates": dates,
            "views": views, "likes": likes, "comments": comments,
            "collects": collects, "shares": shares,
            "newFans": new_fans, "earnings": earnings,
            "summary": {
                "totalViews": sum(views),
                "totalLikes": sum(likes),
                "totalComments": sum(comments),
                "totalCollects": sum(collects),
                "totalShares": sum(shares),
                "totalNewFans": sum(new_fans),
                "totalEarnings": round(sum(earnings), 2)
            }
        })

    m = re.match(r"/api/creator/video/([\w-]+)/stats$", path)
    if m:
        vid = m.group(1)
        period = qp.get("period", ["7d"])[0]
        start_date = qp.get("startDate", [None])[0]
        end_date = qp.get("endDate", [None])[0]
        v = db.videos.get(vid)
        if not v or v.user_id != uid:
            return error("视频不存在", 404)
        stats_list = db.video_stats_daily.get(vid, [])
        if period == "custom" and start_date and end_date:
            filtered = []
            for s in stats_list:
                if start_date <= s.date <= end_date:
                    filtered.append(s)
            stats = list(reversed(filtered))
        else:
            days = 7
            if period == "30d":
                days = 30
            stats = list(reversed(stats_list[:days]))
        total_views = sum(s.views for s in stats)
        total_likes = sum(s.likes for s in stats)
        total_comments = sum(s.comments for s in stats)
        total_collects = sum(s.collects for s in stats)
        total_shares = sum(s.shares for s in stats)
        total_new_fans = sum(s.new_fans for s in stats)
        total_earnings = sum(s.earnings for s in stats)
        return success({
            "period": period,
            "startDate": start_date,
            "endDate": end_date,
            "total": {
                "views": total_views,
                "likes": total_likes,
                "comments": total_comments,
                "collects": total_collects,
                "shares": total_shares,
                "newFans": total_new_fans,
                "earnings": round(total_earnings, 2)
            },
            "daily": [s.to_dict() for s in stats],
            "playDuration": [int(v.duration * 0.6 * s.views / 60) for s in stats],
            "completionRate": [60 + i * 2 for i in range(len(stats))]
        })

    if path == "/api/creator/stats/videos":
        page = int(qp.get("page", ["1"])[0])
        ps = int(qp.get("pageSize", ["20"])[0])
        sort_by = qp.get("sortBy", ["views"])[0]
        sort_order = qp.get("sortOrder", ["desc"])[0]
        period = qp.get("period", ["7d"])[0]
        start_date = qp.get("startDate", [None])[0]
        end_date = qp.get("endDate", [None])[0]
        user_videos = [v for v in db.videos.values() if v.user_id == uid]
        items = []
        for v in user_videos:
            stats_list = db.video_stats_daily.get(v.id, [])
            if period == "custom" and start_date and end_date:
                stats = [s for s in stats_list if start_date <= s.date <= end_date]
            else:
                days = 7 if period == "7d" else 30
                stats = stats_list[:days]
            item = {
                "videoId": v.id,
                "title": v.title,
                "coverUrl": v.cover_url,
                "status": v.status,
                "views": sum(s.views for s in stats),
                "likes": sum(s.likes for s in stats),
                "comments": sum(s.comments for s in stats),
                "collects": sum(s.collects for s in stats),
                "shares": sum(s.shares for s in stats),
                "newFans": sum(s.new_fans for s in stats),
                "earnings": round(sum(s.earnings for s in stats), 2),
                "publishedAt": v.created_at
            }
            items.append(item)
        valid_sort_fields = ["views", "likes", "comments", "collects", "shares", "newFans", "earnings", "publishedAt"]
        if sort_by not in valid_sort_fields:
            sort_by = "views"
        reverse = sort_order == "desc"
        items.sort(key=lambda x: x.get(sort_by, 0), reverse=reverse)
        summary = {
            "totalVideos": len(items),
            "totalViews": sum(r["views"] for r in items),
            "totalLikes": sum(r["likes"] for r in items),
            "totalComments": sum(r["comments"] for r in items),
            "totalCollects": sum(r["collects"] for r in items),
            "totalShares": sum(r["shares"] for r in items),
            "totalNewFans": sum(r["newFans"] for r in items),
            "totalEarnings": round(sum(r["earnings"] for r in items), 2)
        }
        s, e = (page - 1) * ps, page * ps
        return success({
            "list": items[s:e],
            "total": len(items),
            "page": page, "pageSize": ps, "hasMore": e < len(items),
            "summary": summary,
            "period": period, "startDate": start_date, "endDate": end_date
        })

    if path == "/api/creator/stats/topics":
        page = int(qp.get("page", ["1"])[0])
        ps = int(qp.get("pageSize", ["20"])[0])
        sort_by = qp.get("sortBy", ["views"])[0]
        sort_order = qp.get("sortOrder", ["desc"])[0]
        period = qp.get("period", ["7d"])[0]
        start_date = qp.get("startDate", [None])[0]
        end_date = qp.get("endDate", [None])[0]
        user_videos = [v for v in db.videos.values() if v.user_id == uid]
        topic_stats = {}
        for v in user_videos:
            stats_list = db.video_stats_daily.get(v.id, [])
            if period == "custom" and start_date and end_date:
                stats = [s for s in stats_list if start_date <= s.date <= end_date]
            else:
                days = 7 if period == "7d" else 30
                stats = stats_list[:days]
            for tid in v.topics:
                if tid not in topic_stats:
                    t = db.topics.get(tid)
                    topic_stats[tid] = {
                        "topicId": tid,
                        "topicName": t.name if t else tid,
                        "videoCount": 0,
                        "views": 0,
                        "likes": 0,
                        "comments": 0,
                        "collects": 0,
                        "shares": 0,
                        "newFans": 0,
                        "earnings": 0.0
                    }
                topic_stats[tid]["videoCount"] += 1
                topic_stats[tid]["views"] += sum(s.views for s in stats)
                topic_stats[tid]["likes"] += sum(s.likes for s in stats)
                topic_stats[tid]["comments"] += sum(s.comments for s in stats)
                topic_stats[tid]["collects"] += sum(s.collects for s in stats)
                topic_stats[tid]["shares"] += sum(s.shares for s in stats)
                topic_stats[tid]["newFans"] += sum(s.new_fans for s in stats)
                topic_stats[tid]["earnings"] += sum(s.earnings for s in stats)
        result = list(topic_stats.values())
        valid_sort_fields = ["views", "likes", "comments", "collects", "shares", "newFans", "earnings", "videoCount"]
        if sort_by not in valid_sort_fields:
            sort_by = "views"
        reverse = sort_order == "desc"
        result.sort(key=lambda x: x.get(sort_by, 0), reverse=reverse)
        summary = {
            "totalTopics": len(result),
            "totalViews": sum(r["views"] for r in result),
            "totalLikes": sum(r["likes"] for r in result),
            "totalComments": sum(r["comments"] for r in result),
            "totalCollects": sum(r["collects"] for r in result),
            "totalShares": sum(r["shares"] for r in result),
            "totalNewFans": sum(r["newFans"] for r in result),
            "totalEarnings": round(sum(r["earnings"] for r in result), 2)
        }
        s, e = (page - 1) * ps, page * ps
        for r in result:
            r["earnings"] = round(r["earnings"], 2)
        return success({
            "list": result[s:e],
            "total": len(result),
            "page": page, "pageSize": ps, "hasMore": e < len(result),
            "summary": summary,
            "period": period, "startDate": start_date, "endDate": end_date
        })

    if path == "/api/creator/stats/time-slots":
        period = qp.get("period", ["7d"])[0]
        start_date = qp.get("startDate", [None])[0]
        end_date = qp.get("endDate", [None])[0]
        user_videos = [v for v in db.videos.values() if v.user_id == uid]
        hourly_views = [0] * 24
        hourly_likes = [0] * 24
        hourly_comments = [0] * 24
        hourly_collects = [0] * 24
        hourly_shares = [0] * 24
        hourly_new_fans = [0] * 24
        hourly_earnings = [0.0] * 24
        for v in user_videos:
            stats_list = db.video_stats_daily.get(v.id, [])
            if period == "custom" and start_date and end_date:
                stats = [s for s in stats_list if start_date <= s.date <= end_date]
            else:
                days = 7 if period == "7d" else 30
                stats = stats_list[:days]
            for s in stats:
                hour_idx = hash(v.id + s.date) % 24
                hourly_views[hour_idx] += int(s.views / 24)
                hourly_likes[hour_idx] += int(s.likes / 24)
                hourly_comments[hour_idx] += int(s.comments / 24)
                hourly_collects[hour_idx] += int(s.collects / 24)
                hourly_shares[hour_idx] += int(s.shares / 24)
                hourly_new_fans[hour_idx] += int(s.new_fans / 24)
                hourly_earnings[hour_idx] += s.earnings / 24
        list_data = []
        for h in range(24):
            list_data.append({
                "hour": h,
                "views": hourly_views[h],
                "likes": hourly_likes[h],
                "comments": hourly_comments[h],
                "collects": hourly_collects[h],
                "shares": hourly_shares[h],
                "newFans": hourly_new_fans[h],
                "earnings": round(hourly_earnings[h], 2)
            })
        summary = {
            "totalViews": sum(hourly_views),
            "totalLikes": sum(hourly_likes),
            "totalComments": sum(hourly_comments),
            "totalCollects": sum(hourly_collects),
            "totalShares": sum(hourly_shares),
            "totalNewFans": sum(hourly_new_fans),
            "totalEarnings": round(sum(hourly_earnings), 2)
        }
        return success({
            "period": period,
            "startDate": start_date,
            "endDate": end_date,
            "hours": list(range(24)),
            "views": hourly_views,
            "likes": hourly_likes,
            "comments": hourly_comments,
            "collects": hourly_collects,
            "shares": hourly_shares,
            "newFans": hourly_new_fans,
            "earnings": [round(x, 2) for x in hourly_earnings],
            "list": list_data,
            "summary": summary
        })

    return None


def handle_audit(path, qp, uid, body=None, method="GET"):
    if method == "GET":
        if path == "/api/audit/report/list":
            page = int(qp.get("page", ["1"])[0])
            ps = int(qp.get("pageSize", ["20"])[0])
            st = qp.get("status", ["all"])[0]
            reason = qp.get("reason", ["all"])[0]
            start_date = qp.get("startDate", [None])[0]
            end_date = qp.get("endDate", [None])[0]
            rs = list(db.reports.values())
            if st != "all":
                rs = [r for r in rs if r.status == st]
            if reason != "all":
                rs = [r for r in rs if r.reason == reason]
            if start_date:
                try:
                    t = int(time.mktime(time.strptime(start_date, "%Y-%m-%d")) * 1000)
                    rs = [r for r in rs if r.created_at >= t]
                except:
                    pass
            if end_date:
                try:
                    t = int(time.mktime(time.strptime(end_date, "%Y-%m-%d")) * 1000) + 86400000
                    rs = [r for r in rs if r.created_at < t]
                except:
                    pass
            rs.sort(key=lambda x: x.created_at, reverse=True)
            s, e = (page - 1) * ps, page * ps
            items = []
            for r in rs[s:e]:
                v = db.videos.get(r.video_id)
                u = db.users.get(r.user_id)
                video_info = {"id": v.id, "title": v.title, "coverUrl": v.cover_url,
                              "status": v.status} if v else None
                reporter_info = {"id": u.id, "nickname": u.nickname,
                                 "avatar": u.avatar} if u else None
                items.append({
                    "id": r.id, "video": video_info, "reporter": reporter_info,
                    "reason": r.reason, "description": r.description,
                    "status": r.status, "createdAt": r.created_at,
                    "handlerId": r.handler_id, "handleNote": r.handle_note,
                    "handledAt": r.handled_at
                })
            return success({
                "list": items,
                "total": len(rs), "page": page, "pageSize": ps, "hasMore": e < len(rs)
            })

        m = re.match(r"/api/audit/report/([\w-]+)$", path)
        if m:
            rid = m.group(1)
            r = db.reports.get(rid)
            if not r:
                return error("举报不存在", 404)
            v = db.videos.get(r.video_id)
            u = db.users.get(r.user_id)
            video_info = v.to_dict() if v else None
            reporter_info = {"id": u.id, "nickname": u.nickname,
                             "avatar": u.avatar} if u else None
            records = db.get_report_handle_records(rid)
            records.sort(key=lambda x: x.created_at)
            timeline = [rec.to_dict() for rec in records]
            return success({
                **r.to_dict(),
                "video": video_info,
                "reporter": reporter_info,
                "timeline": timeline
            })

        if path == "/api/audit/report/reasons":
            return success({"list": [
                {"value": "porn", "label": "色情低俗"},
                {"value": "violence", "label": "暴力血腥"},
                {"value": "plagiarism", "label": "抄袭搬运"},
                {"value": "fake", "label": "虚假信息"},
                {"value": "illegal", "label": "违法违规"},
                {"value": "other", "label": "其他"},
            ]})

        if path == "/api/audit/notifications":
            page = int(qp.get("page", ["1"])[0])
            ps = int(qp.get("pageSize", ["20"])[0])
            t = qp.get("type", ["all"])[0]
            is_read = qp.get("isRead", [None])[0]
            start_date = qp.get("startDate", [None])[0]
            end_date = qp.get("endDate", [None])[0]
            ns = db.notifications.get(uid, [])
            if t != "all":
                ns = [n for n in ns if n.type == t]
            if is_read is not None:
                read_flag = is_read == "true" or is_read == "1"
                ns = [n for n in ns if n.is_read == read_flag]
            if start_date:
                try:
                    t_ms = int(time.mktime(time.strptime(start_date, "%Y-%m-%d")) * 1000)
                    ns = [n for n in ns if n.created_at >= t_ms]
                except:
                    pass
            if end_date:
                try:
                    t_ms = int(time.mktime(time.strptime(end_date, "%Y-%m-%d")) * 1000) + 86400000
                    ns = [n for n in ns if n.created_at < t_ms]
                except:
                    pass
            s, e = (page - 1) * ps, page * ps
            uc = sum(1 for n in db.notifications.get(uid, []) if not n.is_read)
            type_unread = {}
            all_types = ["like", "comment", "reply", "follow", "system",
                         "audit_pass", "audit_reject", "report_progress",
                         "video_remove", "video_restore", "topic_apply"]
            for nt in all_types:
                type_unread[nt] = sum(1 for n in db.notifications.get(uid, [])
                                       if not n.is_read and n.type == nt)
            return success({
                "list": [n.to_dict() for n in ns[s:e]],
                "total": len(ns),
                "unreadCount": uc,
                "unreadByType": type_unread,
                "page": page, "pageSize": ps, "hasMore": e < len(ns)
            })

        if path == "/api/audit/notifications/unread-count":
            ns = db.notifications.get(uid, [])
            return success({
                "total": sum(1 for n in ns if not n.is_read),
                "like": sum(1 for n in ns if not n.is_read and n.type == "like"),
                "comment": sum(1 for n in ns if not n.is_read and n.type == "comment"),
                "reply": sum(1 for n in ns if not n.is_read and n.type == "reply"),
                "follow": sum(1 for n in ns if not n.is_read and n.type == "follow"),
                "system": sum(1 for n in ns if not n.is_read and n.type == "system"),
                "audit_pass": sum(1 for n in ns if not n.is_read and n.type == "audit_pass"),
                "audit_reject": sum(1 for n in ns if not n.is_read and n.type == "audit_reject"),
                "report_progress": sum(1 for n in ns if not n.is_read and n.type == "report_progress"),
                "video_remove": sum(1 for n in ns if not n.is_read and n.type == "video_remove"),
                "video_restore": sum(1 for n in ns if not n.is_read and n.type == "video_restore"),
                "topic_apply": sum(1 for n in ns if not n.is_read and n.type == "topic_apply"),
            })

        if path == "/api/audit/audit/videos":
            page = int(qp.get("page", ["1"])[0])
            ps = int(qp.get("pageSize", ["20"])[0])
            st = qp.get("status", ["reviewing"])[0]
            reason = qp.get("reason", ["all"])[0]
            start_date = qp.get("startDate", [None])[0]
            end_date = qp.get("endDate", [None])[0]
            author_keyword = qp.get("author", [""])[0]
            vs = [v for v in db.videos.values() if v.status == st]
            if reason != "all":
                reported_video_ids = set()
                for r in db.reports.values():
                    if r.reason == reason:
                        reported_video_ids.add(r.video_id)
                vs = [v for v in vs if v.id in reported_video_ids]
            if author_keyword:
                ak = author_keyword.lower()
                vs = [v for v in vs if ak in (db.users.get(v.user_id).nickname.lower() if db.users.get(v.user_id) else "")]
            if start_date:
                try:
                    t = int(time.mktime(time.strptime(start_date, "%Y-%m-%d")) * 1000)
                    vs = [v for v in vs if v.created_at >= t]
                except:
                    pass
            if end_date:
                try:
                    t = int(time.mktime(time.strptime(end_date, "%Y-%m-%d")) * 1000) + 86400000
                    vs = [v for v in vs if v.created_at < t]
                except:
                    pass
            vs.sort(key=lambda x: x.created_at)
            s, e = (page - 1) * ps, page * ps
            items = []
            for v in vs[s:e]:
                a = db.users.get(v.user_id)
                author = {"id": a.id, "nickname": a.nickname, "avatar": a.avatar} if a else None
                items.append({
                    "id": v.id, "title": v.title, "description": v.description,
                    "coverUrl": v.cover_url, "videoUrl": v.video_url,
                    "duration": v.duration, "status": v.status,
                    "topics": v.topics, "author": author,
                    "createdAt": v.created_at
                })
            return success({
                "list": items,
                "total": len(vs), "page": page, "pageSize": ps, "hasMore": e < len(vs)
            })

        if path == "/api/audit/operation/videos/export":
            page = int(qp.get("page", ["1"])[0])
            ps = int(qp.get("pageSize", ["50"])[0])
            status = qp.get("status", ["all"])[0]
            topic_id = qp.get("topicId", [""])[0]
            author_id = qp.get("authorId", [""])[0]
            start_date = qp.get("startDate", [None])[0]
            end_date = qp.get("endDate", [None])[0]
            vs = list(db.videos.values())
            if status != "all":
                vs = [v for v in vs if v.status == status]
            if topic_id:
                vs = [v for v in vs if topic_id in v.topics]
            if author_id:
                vs = [v for v in vs if v.user_id == author_id]
            if start_date:
                try:
                    t = int(time.mktime(time.strptime(start_date, "%Y-%m-%d")) * 1000)
                    vs = [v for v in vs if v.created_at >= t]
                except:
                    pass
            if end_date:
                try:
                    t = int(time.mktime(time.strptime(end_date, "%Y-%m-%d")) * 1000) + 86400000
                    vs = [v for v in vs if v.created_at < t]
                except:
                    pass
            vs.sort(key=lambda x: x.created_at, reverse=True)
            s, e = (page - 1) * ps, page * ps
            items = []
            for v in vs[s:e]:
                author = db.users.get(v.user_id)
                topic_names = []
                for tid in v.topics:
                    t = db.topics.get(tid)
                    if t:
                        topic_names.append(t.name)
                items.append({
                    "videoId": v.id,
                    "title": v.title,
                    "description": v.description,
                    "coverUrl": v.cover_url,
                    "videoUrl": v.video_url,
                    "duration": v.duration,
                    "status": v.status,
                    "viewsCount": v.views_count,
                    "likesCount": v.likes_count,
                    "commentsCount": v.comments_count,
                    "collectsCount": v.collects_count,
                    "sharesCount": v.shares_count,
                    "topics": v.topics,
                    "topicNames": topic_names,
                    "authorId": v.user_id,
                    "authorNickname": author.nickname if author else "",
                    "authorAvatar": author.avatar if author else "",
                    "createdAt": v.created_at,
                    "updatedAt": v.updated_at,
                    "rejectReason": v.reject_reason
                })
            return success({
                "list": items,
                "total": len(vs),
                "page": page, "pageSize": ps, "hasMore": e < len(vs)
            })

    if method == "POST":
        if path == "/api/audit/report/video":
            vid = body.get("videoId", "")
            v = db.videos.get(vid)
            if not v:
                return error("视频不存在", 404)
            reason = body.get("reason", "")
            description = body.get("description", "")
            if not reason:
                return error("举报原因不能为空", 400)
            rid = str(uuid.uuid4())[:8]
            r = Report(
                id=rid, video_id=vid, user_id=uid, reason=reason,
                description=description, status=ReportStatus.PENDING,
                created_at=int(time.time() * 1000),
                handler_id=None, handle_note=None, handled_at=None
            )
            db.reports[rid] = r
            db.add_notification(uid, NotificationType.REPORT_PROGRESS, "举报提交成功",
                                f'你举报的视频"{v.title}"已提交，我们会尽快处理',
                                related_id=rid, related_type="report")
            return success({"reportId": rid, "status": ReportStatus.PENDING}, "举报提交成功")

        m = re.match(r"/api/audit/report/([\w-]+)/process$", path)
        if m:
            rid = m.group(1)
            r = db.reports.get(rid)
            if not r:
                return error("举报不存在", 404)
            action = body.get("action", "")
            note = body.get("note", "")
            if action not in ["resolve", "reject", "processing"]:
                return error("无效的操作类型", 400)
            now = int(time.time() * 1000)
            if action == "resolve":
                r.status = ReportStatus.RESOLVED
                v = db.videos.get(r.video_id)
                if v and v.status == VideoStatus.PUBLISHED:
                    v.status = VideoStatus.REMOVED
                    v.updated_at = now
                    db.add_topic_video_count(v.topics, -1)
                    db.add_notification(v.user_id, NotificationType.VIDEO_REMOVE, "视频已下架",
                                        f'你的视频"{v.title}"因违规已被下架',
                                        related_id=v.id, related_type="video")
            elif action == "reject":
                r.status = ReportStatus.REJECTED
            else:
                r.status = ReportStatus.PROCESSING
            r.handler_id = uid
            r.handle_note = note
            r.handled_at = now
            db.add_report_handle_record(rid, uid, action, note)
            reporter = db.users.get(r.user_id)
            if reporter:
                status_text = "已处理" if action == "resolve" else "已驳回" if action == "reject" else "处理中"
                db.add_notification(r.user_id, NotificationType.REPORT_PROGRESS, f"举报{status_text}",
                                    f'你举报的视频处理结果：{note or status_text}',
                                    related_id=rid, related_type="report")
            return success({"reportId": rid, "status": r.status}, "处理成功")

        m = re.match(r"/api/audit/video/([\w-]+)/remove$", path)
        if m:
            vid = m.group(1)
            v = db.videos.get(vid)
            if not v:
                return error("视频不存在", 404)
            if v.status != VideoStatus.PUBLISHED:
                return error("只有已发布的视频才能下架", 400)
            reason = body.get("reason", "违反平台规定")
            v.status = VideoStatus.REMOVED
            v.updated_at = int(time.time() * 1000)
            db.add_topic_video_count(v.topics, -1)
            db.add_topic_interaction_by_video(v, -1)
            db.add_notification(v.user_id, NotificationType.VIDEO_REMOVE, "视频已下架",
                                f'你的视频"{v.title}"已被下架，原因：{reason}',
                                related_id=vid, related_type="video",
                                extra={"reason": reason})
            return success({"videoId": vid, "status": VideoStatus.REMOVED}, "视频已下架")

        m = re.match(r"/api/audit/video/([\w-]+)/restore$", path)
        if m:
            vid = m.group(1)
            v = db.videos.get(vid)
            if not v:
                return error("视频不存在", 404)
            if v.status != VideoStatus.REMOVED:
                return error("只有已下架的视频才能恢复", 400)
            v.status = VideoStatus.PUBLISHED
            v.updated_at = int(time.time() * 1000)
            db.add_topic_video_count(v.topics, 1)
            db.add_topic_interaction_by_video(v, 1)
            db.add_notification(v.user_id, NotificationType.VIDEO_RESTORE, "视频已恢复",
                                f'你的视频"{v.title}"已恢复上架',
                                related_id=vid, related_type="video")
            return success({"videoId": vid, "status": VideoStatus.PUBLISHED}, "视频已恢复")

        m = re.match(r"/api/audit/video/([\w-]+)/approve$", path)
        if m:
            vid = m.group(1)
            v = db.videos.get(vid)
            if not v:
                return error("视频不存在", 404)
            if v.status != VideoStatus.REVIEWING:
                return error("视频状态不支持此操作", 400)
            v.status = VideoStatus.PUBLISHED
            v.updated_at = int(time.time() * 1000)
            db.add_topic_video_count(v.topics, 1)
            db.add_notification(v.user_id, NotificationType.AUDIT_PASS, "视频审核通过",
                                f'你的视频"{v.title}"已通过审核',
                                related_id=vid, related_type="video")
            return success({"videoId": vid, "status": VideoStatus.PUBLISHED}, "审核通过")

        m = re.match(r"/api/audit/video/([\w-]+)/reject$", path)
        if m:
            vid = m.group(1)
            v = db.videos.get(vid)
            if not v:
                return error("视频不存在", 404)
            if v.status != VideoStatus.REVIEWING:
                return error("视频状态不支持此操作", 400)
            reason = body.get("reason", "内容不符合规范")
            note = body.get("note", "")
            v.status = VideoStatus.REJECTED
            v.reject_reason = reason
            v.updated_at = int(time.time() * 1000)
            db.add_notification(v.user_id, NotificationType.AUDIT_REJECT, "视频审核未通过",
                                f'你的视频"{v.title}"未通过审核，原因：{reason}',
                                related_id=vid, related_type="video",
                                extra={"reason": reason})
            return success({"videoId": vid, "status": VideoStatus.REJECTED, "rejectReason": reason}, "已驳回")

        if path == "/api/audit/video/batch-approve" and method == "POST":
            video_ids = body.get("videoIds", []) or []
            results = []
            for vid in video_ids:
                v = db.videos.get(vid)
                if not v:
                    results.append({"videoId": vid, "success": False, "reason": "视频不存在"})
                elif v.status != VideoStatus.REVIEWING:
                    results.append({"videoId": vid, "success": False, "reason": "状态错误，非待审核"})
                else:
                    v.status = VideoStatus.PUBLISHED
                    v.updated_at = int(time.time() * 1000)
                    db.add_topic_video_count(v.topics, 1)
                    db.add_notification(v.user_id, NotificationType.AUDIT_PASS, "视频审核通过",
                                        f'你的视频"{v.title}"已通过审核',
                                        related_id=vid, related_type="video")
                    results.append({"videoId": vid, "success": True})
            success_count = sum(1 for r in results if r["success"])
            return success({"success": success_count, "total": len(video_ids), "results": results},
                           f"已批量通过{success_count}个视频")

        if path == "/api/audit/video/batch-remove" and method == "POST":
            video_ids = body.get("videoIds", []) or []
            reason = body.get("reason", "批量下架")
            note = body.get("note", "")
            results = []
            for vid in video_ids:
                v = db.videos.get(vid)
                if not v:
                    results.append({"videoId": vid, "success": False, "reason": "视频不存在"})
                elif v.status != VideoStatus.PUBLISHED:
                    results.append({"videoId": vid, "success": False, "reason": "状态错误，非已发布"})
                else:
                    v.status = VideoStatus.REMOVED
                    v.updated_at = int(time.time() * 1000)
                    db.add_topic_video_count(v.topics, -1)
                    db.add_notification(v.user_id, NotificationType.VIDEO_REMOVE, "视频已下架",
                                        f'你的视频"{v.title}"已被下架，原因：{reason}',
                                        related_id=vid, related_type="video",
                                        extra={"reason": reason})
                    results.append({"videoId": vid, "success": True})
            success_count = sum(1 for r in results if r["success"])
            return success({"success": success_count, "total": len(video_ids), "results": results},
                           f"已批量下架{success_count}个视频")

        if path == "/api/audit/video/batch-reject" and method == "POST":
            video_ids = body.get("videoIds", []) or []
            reason = body.get("reason", "内容不符合规范")
            note = body.get("note", "")
            results = []
            for vid in video_ids:
                v = db.videos.get(vid)
                if not v:
                    results.append({"videoId": vid, "success": False, "reason": "视频不存在"})
                elif v.status != VideoStatus.REVIEWING:
                    results.append({"videoId": vid, "success": False, "reason": "状态错误，非待审核"})
                else:
                    v.status = VideoStatus.REJECTED
                    v.reject_reason = reason
                    v.updated_at = int(time.time() * 1000)
                    db.add_notification(v.user_id, NotificationType.AUDIT_REJECT, "视频审核未通过",
                                        f'你的视频"{v.title}"未通过审核，原因：{reason}',
                                        related_id=vid, related_type="video",
                                        extra={"reason": reason})
                    results.append({"videoId": vid, "success": True})
            success_count = sum(1 for r in results if r["success"])
            return success({"success": success_count, "total": len(video_ids), "results": results},
                           f"已批量驳回{success_count}个视频")

        if path == "/api/audit/notifications/read":
            nid = body.get("notificationId")
            if nid:
                ns = db.notifications.get(uid, [])
                for n in ns:
                    if n.id == nid:
                        n.is_read = True
                        break
                return success(None, "已标记为已读")
            else:
                ns = db.notifications.get(uid, [])
                for n in ns:
                    n.is_read = True
                return success(None, "全部已标记为已读")

        if path == "/api/audit/topic/approvals":
            page = int(body.get("page", 1))
            ps = int(body.get("pageSize", 20))
            st = body.get("status", "pending")
            tas = [ta for ta in db.topic_applies.values() if ta.status == st]
            tas.sort(key=lambda x: x.created_at, reverse=True)
            s, e = (page - 1) * ps, page * ps
            return success({
                "list": [ta.to_dict() for ta in tas[s:e]],
                "total": len(tas), "page": page, "pageSize": ps, "hasMore": e < len(tas)
            })

        m = re.match(r"/api/audit/topic/apply/([\w-]+)/approve$", path)
        if m:
            aid = m.group(1)
            ta = db.topic_applies.get(aid)
            if not ta:
                return error("申请不存在", 404)
            tid = str(uuid.uuid4())[:8]
            topic = Topic(
                id=tid, name=ta.name, description=ta.description,
                video_count=0, views_count=0,
                cover=f'https://picsum.photos/seed/{tid}/400/300',
                heat=0, created_at=int(time.time() * 1000),
                creator_id=ta.user_id, is_official=False
            )
            db.topics[tid] = topic
            ta.status = "approved"
            db.add_notification(ta.user_id, NotificationType.TOPIC_APPLY, "话题创建成功",
                                f'你申请的话题"{ta.name}"已通过审核',
                                related_id=tid, related_type="topic")
            return success({"topicId": tid, "name": ta.name}, "话题已创建")

        m = re.match(r"/api/audit/topic/apply/([\w-]+)/reject$", path)
        if m:
            aid = m.group(1)
            ta = db.topic_applies.get(aid)
            if not ta:
                return error("申请不存在", 404)
            reason = body.get("reason", "不符合平台规范")
            ta.status = "rejected"
            ta.reject_reason = reason
            db.add_notification(ta.user_id, NotificationType.TOPIC_APPLY, "话题申请被驳回",
                                f'你申请的话题"{ta.name}"未通过，原因：{reason}',
                                related_id=aid, related_type="topic_apply")
            return success(None, "已驳回")

        if path == "/api/audit/operation/trend":
            period = body.get("period", "7d") if body else "7d"
            start_date = body.get("startDate") if body else None
            end_date = body.get("endDate") if body else None
            days = 7
            start_ts = 0
            end_ts = 0
            if period == "30d":
                days = 30
                end_ts = int(time.time() * 1000)
                start_ts = end_ts - 86400000 * (days - 1)
            elif period == "custom" and start_date and end_date:
                try:
                    t1 = int(time.mktime(time.strptime(start_date, "%Y-%m-%d")) * 1000)
                    t2 = int(time.mktime(time.strptime(end_date, "%Y-%m-%d")) * 1000)
                    days = max(1, min(90, int((t2 - t1) / 86400000) + 1))
                    start_ts = t1
                    end_ts = t2
                except:
                    days = 7
                    end_ts = int(time.time() * 1000)
                    start_ts = end_ts - 86400000 * (days - 1)
            else:
                days = 7
                end_ts = int(time.time() * 1000)
                start_ts = end_ts - 86400000 * (days - 1)
            all_stats = db.platform_stats_daily
            stats_by_date = {s.date: s for s in all_stats}
            stats = []
            dates = []
            for i in range(days):
                d_ts = start_ts + 86400000 * i
                date_str = time.strftime("%Y-%m-%d", time.localtime(d_ts / 1000))
                dates.append(date_str)
                if date_str in stats_by_date:
                    stats.append(stats_by_date[date_str])
                else:
                    seed = hash(date_str) % 1000
                    stats.append(PlatformStatsDaily(
                        date=date_str,
                        video_publish_count=50 + int(20 * math.sin(seed * 0.03)),
                        video_audit_pass_count=45 + int(15 * math.sin(seed * 0.03)),
                        video_audit_reject_count=5 + int(3 * math.sin(seed * 0.05)),
                        report_count=20 + int(10 * math.sin(seed * 0.04)),
                        video_remove_count=3 + int(2 * math.sin(seed * 0.06)),
                        active_creators=1000 + int(200 * math.sin(seed * 0.02)),
                        interactions_count=50000 + int(10000 * math.sin(seed * 0.025)),
                        new_users=100 + int(50 * math.sin(seed * 0.035)),
                        earnings=round(5000 + 2000 * math.sin(seed * 0.03) + 500 * math.cos(seed * 0.02), 2),
                    ))
            actual_start = dates[0] if dates else start_date
            actual_end = dates[-1] if dates else end_date
            return success({
                "period": period, "days": days,
                "startDate": actual_start, "endDate": actual_end,
                "dates": dates,
                "videoPublishCount": [s.video_publish_count for s in stats],
                "videoAuditPassCount": [s.video_audit_pass_count for s in stats],
                "videoAuditRejectCount": [s.video_audit_reject_count for s in stats],
                "reportCount": [s.report_count for s in stats],
                "videoRemoveCount": [s.video_remove_count for s in stats],
                "activeCreators": [s.active_creators for s in stats],
                "interactionsCount": [s.interactions_count for s in stats],
                "newUsers": [s.new_users for s in stats],
                "earnings": [s.earnings for s in stats],
                "summary": {
                    "totalVideoPublish": sum(s.video_publish_count for s in stats),
                    "totalAuditPass": sum(s.video_audit_pass_count for s in stats),
                    "totalAuditReject": sum(s.video_audit_reject_count for s in stats),
                    "auditPassRate": round(sum(s.video_audit_pass_count for s in stats) / max(1, sum(s.video_publish_count for s in stats)) * 100, 2),
                    "totalReport": sum(s.report_count for s in stats),
                    "totalRemove": sum(s.video_remove_count for s in stats),
                    "totalInteractions": sum(s.interactions_count for s in stats),
                    "totalNewUsers": sum(s.new_users for s in stats),
                    "totalEarnings": round(sum(s.earnings for s in stats), 2),
                }
            })

        if path == "/api/audit/operation/top-topics":
            period = body.get("period", "7d") if body else "7d"
            start_date = body.get("startDate") if body else None
            end_date = body.get("endDate") if body else None
            page = int((body.get("page", 1) if body else 1))
            ps = int((body.get("pageSize", 10) if body else 10))
            sort_by = body.get("sortBy", "heat") if body else "heat"
            days = 7
            start_ts = 0
            end_ts = 0
            actual_start = ""
            actual_end = ""
            if period == "30d":
                days = 30
                end_ts = int(time.time() * 1000)
                start_ts = end_ts - 86400000 * (days - 1)
            elif period == "custom" and start_date and end_date:
                try:
                    t1 = int(time.mktime(time.strptime(start_date, "%Y-%m-%d")) * 1000)
                    t2 = int(time.mktime(time.strptime(end_date, "%Y-%m-%d")) * 1000)
                    days = max(1, min(90, int((t2 - t1) / 86400000) + 1))
                    start_ts = t1
                    end_ts = t2
                except:
                    days = 7
                    end_ts = int(time.time() * 1000)
                    start_ts = end_ts - 86400000 * (days - 1)
            else:
                days = 7
                end_ts = int(time.time() * 1000)
                start_ts = end_ts - 86400000 * (days - 1)
            actual_start = time.strftime("%Y-%m-%d", time.localtime(start_ts / 1000))
            actual_end = time.strftime("%Y-%m-%d", time.localtime(end_ts / 1000))
            ratio = days / 30.0
            topics = list(db.topics.values())
            result = []
            for t in topics:
                seed = hash(t.id + actual_start + actual_end) % 1000
                inc_views = max(0, int(t.views_count * ratio * (0.05 + 0.001 * (seed % 50))))
                inc_likes = max(0, int(t.likes_count * ratio * (0.05 + 0.001 * ((seed + 10) % 50))))
                inc_comments = max(0, int(t.comments_count * ratio * (0.05 + 0.001 * ((seed + 20) % 50))))
                inc_collects = max(0, int(t.collects_count * ratio * (0.05 + 0.001 * ((seed + 30) % 50))))
                inc_shares = max(0, int(t.shares_count * ratio * (0.05 + 0.001 * ((seed + 40) % 50))))
                inc_videos = max(1, int(t.video_count * ratio * 0.05))
                inc_heat = inc_views + inc_likes * 2 + inc_comments * 3 + inc_collects * 2 + inc_shares * 5 + inc_videos * 50
                result.append({
                    "id": t.id,
                    "name": t.name,
                    "cover": t.cover,
                    "videoCount": t.video_count,
                    "viewsCount": t.views_count,
                    "likesCount": t.likes_count,
                    "commentsCount": t.comments_count,
                    "collectsCount": t.collects_count,
                    "sharesCount": t.shares_count,
                    "heat": t.heat,
                    "isOfficial": t.is_official,
                    "periodVideoCount": inc_videos,
                    "periodViews": inc_views,
                    "periodLikes": inc_likes,
                    "periodComments": inc_comments,
                    "periodCollects": inc_collects,
                    "periodShares": inc_shares,
                    "periodHeat": inc_heat
                })
            sort_fields = {
                "heat": "periodHeat",
                "views": "periodViews",
                "likes": "periodLikes",
                "comments": "periodComments",
                "videoCount": "periodVideoCount"
            }
            sort_key = sort_fields.get(sort_by, "periodHeat")
            result.sort(key=lambda x: x.get(sort_key, 0), reverse=True)
            s, e = (page - 1) * ps, page * ps
            return success({
                "list": result[s:e],
                "total": len(result),
                "page": page, "pageSize": ps, "hasMore": e < len(result),
                "period": period,
                "startDate": actual_start,
                "endDate": actual_end,
                "days": days
            })

        if path == "/api/audit/operation/top-report-reasons":
            period = body.get("period", "7d") if body else "7d"
            start_date = body.get("startDate") if body else None
            end_date = body.get("endDate") if body else None
            page = int((body.get("page", 1) if body else 1))
            ps = int((body.get("pageSize", 10) if body else 10))
            days = 7
            start_ts = 0
            end_ts = 0
            actual_start = ""
            actual_end = ""
            if period == "30d":
                days = 30
                end_ts = int(time.time() * 1000)
                start_ts = end_ts - 86400000 * (days - 1)
            elif period == "custom" and start_date and end_date:
                try:
                    t1 = int(time.mktime(time.strptime(start_date, "%Y-%m-%d")) * 1000)
                    t2 = int(time.mktime(time.strptime(end_date, "%Y-%m-%d")) * 1000)
                    days = max(1, min(90, int((t2 - t1) / 86400000) + 1))
                    start_ts = t1
                    end_ts = t2 + 86400000
                except:
                    days = 7
                    end_ts = int(time.time() * 1000)
                    start_ts = end_ts - 86400000 * (days - 1)
            else:
                days = 7
                end_ts = int(time.time() * 1000)
                start_ts = end_ts - 86400000 * (days - 1)
            actual_start = time.strftime("%Y-%m-%d", time.localtime(start_ts / 1000))
            actual_end = time.strftime("%Y-%m-%d", time.localtime((end_ts - 86400000) / 1000)) if end_ts > start_ts else actual_start
            reason_count_period = {}
            reason_count_total = {}
            for r in db.reports.values():
                reason = r.reason
                reason_count_total[reason] = reason_count_total.get(reason, 0) + 1
                if r.created_at >= start_ts and r.created_at < end_ts:
                    reason_count_period[reason] = reason_count_period.get(reason, 0) + 1
            result = sorted([
                {"reason": k, "count": v, "totalCount": reason_count_total.get(k, v)}
                for k, v in reason_count_period.items()
            ], key=lambda x: x["count"], reverse=True)
            s, e = (page - 1) * ps, page * ps
            return success({
                "list": result[s:e],
                "total": len(result),
                "page": page, "pageSize": ps, "hasMore": e < len(result),
                "period": period,
                "startDate": actual_start,
                "endDate": actual_end,
                "days": days
            })

    return None


class Handler(BaseHTTPRequestHandler):
    def _send_json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        self.end_headers()
        self.wfile.write(body)

    def _body(self):
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            return {}
        try:
            return json.loads(self.rfile.read(length).decode("utf-8"))
        except:
            return {}

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        self.end_headers()

    def do_GET(self):
        p = urlparse(self.path)
        uid = get_user_id(self.headers)
        result = self._route(p.path, parse_qs(p.query), uid, None, "GET")
        if result is not None:
            self._send_json(result)
        else:
            self._send_json(error("接口不存在", 404), 404)

    def do_POST(self):
        p = urlparse(self.path)
        uid = get_user_id(self.headers)
        body = self._body()
        result = self._route(p.path, parse_qs(p.query), uid, body, "POST")
        if result is not None:
            self._send_json(result)
        else:
            self._send_json(error("接口不存在", 404), 404)

    def do_PUT(self):
        p = urlparse(self.path)
        uid = get_user_id(self.headers)
        body = self._body()
        result = self._route(p.path, parse_qs(p.query), uid, body, "PUT")
        if result is not None:
            self._send_json(result)
        else:
            self._send_json(error("接口不存在", 404), 404)

    def do_DELETE(self):
        p = urlparse(self.path)
        uid = get_user_id(self.headers)
        result = self._route(p.path, parse_qs(p.query), uid, None, "DELETE")
        if result is not None:
            self._send_json(result)
        else:
            self._send_json(error("接口不存在", 404), 404)

    def _route(self, path, qp, uid, body, method):
        if path == "/" or path == "":
            return success({
                "name": "短视频平台后端服务",
                "version": "2.0.0",
                "description": "为多个客户端提供内容与互动能力的短视频平台后端",
                "apis": {
                    "video": "/api/video - 视频流接口",
                    "publish": "/api/publish - 发布接口",
                    "account": "/api/account - 账号接口",
                    "interaction": "/api/interaction - 互动接口",
                    "search": "/api/search - 搜索接口",
                    "creator": "/api/creator - 创作者接口",
                    "audit": "/api/audit - 审核接口"
                }
            })
        handlers = [
            handle_video, handle_publish, handle_account,
            handle_interaction, handle_search, handle_creator, handle_audit
        ]
        for handler in handlers:
            r = handler(path, qp, uid, body, method)
            if r is not None:
                return r
        return None

    def log_message(self, format, *args):
        pass


if __name__ == "__main__":
    server = HTTPServer(("0.0.0.0", 8000), Handler)
    print("=" * 40)
    print("  短视频平台后端服务已启动")
    print("  服务地址: http://localhost:8000")
    print("=" * 40)
    print()
    print("  API 分组：")
    print("  1. 视频流接口   - /api/video")
    print("  2. 发布接口     - /api/publish")
    print("  3. 账号接口     - /api/account")
    print("  4. 互动接口     - /api/interaction")
    print("  5. 搜索接口     - /api/search")
    print("  6. 创作者接口   - /api/creator")
    print("  7. 审核接口     - /api/audit")
    print()
    print("  测试账号 (x-user-id): u1 ~ u6")
    print("  管理员账号 (x-user-id): u_admin")
    print("=" * 40)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n服务已停止")
        server.server_close()
