import json
import re
import time
import uuid
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

from app.database import db, add_notification
from app.models import Video, VideoStatus, Comment, Danmaku, Draft
from app.models import UploadTask, Report, ReportStatus, NotificationType


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
    return {
        **v.to_dict(),
        "author": {
            "id": author.id if author else v.user_id,
            "nickname": author.nickname if author else "未知用户",
            "avatar": author.avatar if author else "",
            "isVerified": author.is_verified if author else False,
        },
        "isLiked": v.id in likes,
        "isCollected": v.id in collects,
        "isFollowed": v.user_id in follows,
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
            vs = sorted([v for v in db.videos.values() if v.status == "published"],
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
                         if v.status == "published" and v.user_id in fs],
                        key=lambda x: x.created_at, reverse=True)
            s, e = (page - 1) * ps, page * ps
            return success({
                "list": [enrich_video(v, uid) for v in vs[s:e]],
                "total": len(vs), "page": page, "pageSize": ps, "hasMore": e < len(vs)
            })
        if path == "/api/video/hot/ranking":
            t = qp.get("type", ["hot"])[0]
            limit = int(qp.get("limit", ["20"])[0])
            vs = [v for v in db.videos.values() if v.status == "published"]
            if t == "likes":
                vs.sort(key=lambda x: x.likes_count, reverse=True)
            elif t == "new":
                vs.sort(key=lambda x: x.created_at, reverse=True)
            else:
                vs.sort(key=lambda x: x.views_count, reverse=True)
            return success({
                "type": t, "updateTime": int(time.time() * 1000),
                "list": [enrich_video(v, uid) for v in vs[:limit]]
            })
        m = re.match(r"^/api/video/([^/]+)$", path)
        if m:
            v = db.videos.get(m.group(1))
            if not v or v.status != "published":
                return error("视频不存在", 404)
            v.views_count += 1
            return success(enrich_video(v, uid))
    return None


def handle_publish(path, qp, uid, body=None, method="GET"):
    if method == "GET":
        if path == "/api/publish/drafts":
            ds = sorted(db.drafts.get(uid, []), key=lambda d: d.updated_at, reverse=True)
            return success({"list": [d.to_dict() for d in ds], "total": len(ds)})
        if path == "/api/publish/topics/suggest":
            kw = qp.get("keyword", [""])[0]
            ts = list(db.topics.values())
            if kw:
                ts = [t for t in ts if kw.lower() in t.name.lower()]
            ts.sort(key=lambda t: t.video_count, reverse=True)
            return success({"list": [t.to_dict() for t in ts[:10]]})
        m = re.match(r"^/api/publish/upload/([^/]+)/status$", path)
        if m:
            t = db.upload_tasks.get(m.group(1))
            if not t:
                return error("上传任务不存在", 404)
            return success({
                "taskId": t.id, "status": t.status,
                "uploadedSize": t.uploaded_size, "fileSize": t.file_size,
                "progress": int(t.uploaded_size / t.file_size * 100),
                "videoUrl": t.video_url
            })
        m = re.match(r"^/api/publish/video/([^/]+)/status$", path)
        if m:
            v = db.videos.get(m.group(1))
            if not v:
                return error("视频不存在", 404)
            r = {"videoId": v.id, "status": v.status, "title": v.title, "createdAt": v.created_at}
            if v.status == VideoStatus.REMOVED:
                r["rejectReason"] = "内容不符合平台规范"
            return success(r)
    if method == "POST":
        if path == "/api/publish/upload/init":
            tid = str(uuid.uuid4())
            t = UploadTask(id=tid, user_id=uid, file_name=body.get("fileName", ""),
                           file_size=body.get("fileSize", 0), uploaded_size=0,
                           status="uploading", created_at=int(time.time() * 1000))
            db.upload_tasks[tid] = t
            return success({"taskId": tid, "uploadUrl": f"/api/publish/upload/{tid}"})
        if path == "/api/publish/drafts":
            did = str(uuid.uuid4())
            d = Draft(id=did, user_id=uid, title=body.get("title", ""),
                      description=body.get("description", ""),
                      cover_url=body.get("coverUrl", ""),
                      video_url=body.get("videoUrl", ""),
                      duration=body.get("duration", 0),
                      topics=body.get("topics", []),
                      updated_at=int(time.time() * 1000))
            if uid not in db.drafts:
                db.drafts[uid] = []
            db.drafts[uid].append(d)
            return success({"draftId": did, **d.to_dict()}, "草稿保存成功")
        if path == "/api/publish/cover/select":
            url = f"https://picsum.photos/seed/{int(time.time())}/720/1280"
            frames = [{"index": i, "timestamp": i * 5,
                       "thumbnailUrl": f"https://picsum.photos/seed/frame{i}/180/320"}
                      for i in range(5)]
            return success({"selectedCover": url, "frames": frames}, "封面生成成功")
        if path == "/api/publish/video":
            vid = str(uuid.uuid4())
            now = int(time.time() * 1000)
            v = Video(id=vid, user_id=uid, title=body.get("title", ""),
                      description=body.get("description", ""),
                      cover_url=body.get("coverUrl", ""),
                      video_url=body.get("videoUrl", ""),
                      duration=body.get("duration", 0),
                      likes_count=0, comments_count=0, shares_count=0,
                      views_count=0, collects_count=0,
                      topics=body.get("topics", []), status=VideoStatus.REVIEWING,
                      created_at=now, updated_at=now)
            db.videos[vid] = v
            if body.get("draftId"):
                db.drafts[uid] = [d for d in db.drafts.get(uid, [])
                                  if d.id != body["draftId"]]
            u = db.users.get(uid)
            if u:
                u.works_count += 1
            for tid in body.get("topics", []):
                tp = db.topics.get(tid)
                if tp:
                    tp.video_count += 1
            return success({"videoId": vid, "status": "reviewing",
                            "estimatedTime": "预计10分钟内完成审核"},
                           "视频提交成功，正在审核中")
        m = re.match(r"^/api/publish/upload/([^/]+)/chunk$", path)
        if m:
            t = db.upload_tasks.get(m.group(1))
            if not t:
                return error("上传任务不存在", 404)
            t.uploaded_size += body.get("chunkSize", 1024 * 1024)
            if t.uploaded_size >= t.file_size:
                t.status = "success"
                t.video_url = f"https://example.com/videos/{t.id}.mp4"
            return success({"taskId": t.id, "uploadedSize": t.uploaded_size,
                            "progress": int(t.uploaded_size / t.file_size * 100)})
    if method == "PUT":
        m = re.match(r"^/api/publish/drafts/([^/]+)$", path)
        if m:
            ds = db.drafts.get(uid, [])
            d = next((x for x in ds if x.id == m.group(1)), None)
            if not d:
                return error("草稿不存在", 404)
            for k, ak in [("title", "title"), ("description", "description"),
                          ("coverUrl", "cover_url"), ("videoUrl", "video_url"),
                          ("duration", "duration"), ("topics", "topics")]:
                if k in body:
                    setattr(d, ak, body[k])
            d.updated_at = int(time.time() * 1000)
            return success(d.to_dict(), "草稿更新成功")
    if method == "DELETE":
        m = re.match(r"^/api/publish/drafts/([^/]+)$", path)
        if m:
            ds = db.drafts.get(uid, [])
            fd = [d for d in ds if d.id != m.group(1)]
            if len(fd) == len(ds):
                return error("草稿不存在", 404)
            db.drafts[uid] = fd
            return success(None, "草稿删除成功")
    return None


def handle_account(path, qp, uid, body=None, method="GET"):
    if method == "GET":
        if path == "/api/account/profile":
            u = db.users.get(uid)
            if not u:
                return error("用户不存在", 404)
            return success(u.to_dict())
        m = re.match(r"^/api/account/([^/]+)$", path)
        if m:
            u = db.users.get(m.group(1))
            if not u:
                return error("用户不存在", 404)
            return success(enrich_user(u, uid))
        m = re.match(r"^/api/account/([^/]+)/videos$", path)
        if m:
            page, ps = int(qp.get("page", ["1"])[0]), int(qp.get("pageSize", ["20"])[0])
            vs = sorted([v for v in db.videos.values()
                         if v.user_id == m.group(1) and v.status == "published"],
                        key=lambda x: x.created_at, reverse=True)
            s, e = (page - 1) * ps, page * ps
            return success({
                "list": [{"id": v.id, "title": v.title, "coverUrl": v.cover_url,
                          "duration": v.duration, "likesCount": v.likes_count,
                          "viewsCount": v.views_count, "createdAt": v.created_at}
                         for v in vs[s:e]],
                "total": len(vs), "page": page, "pageSize": ps, "hasMore": e < len(vs)
            })
        m = re.match(r"^/api/account/([^/]+)/likes$", path)
        if m:
            page, ps = int(qp.get("page", ["1"])[0]), int(qp.get("pageSize", ["20"])[0])
            liked = db.user_likes.get(m.group(1), set())
            vs = sorted([v for v in db.videos.values()
                         if v.id in liked and v.status == "published"],
                        key=lambda x: x.created_at, reverse=True)
            s, e = (page - 1) * ps, page * ps
            return success({
                "list": [{"id": v.id, "title": v.title, "coverUrl": v.cover_url,
                          "duration": v.duration, "likesCount": v.likes_count,
                          "viewsCount": v.views_count} for v in vs[s:e]],
                "total": len(vs), "page": page, "pageSize": ps, "hasMore": e < len(vs)
            })
        m = re.match(r"^/api/account/([^/]+)/collects$", path)
        if m:
            page, ps = int(qp.get("page", ["1"])[0]), int(qp.get("pageSize", ["20"])[0])
            col = db.user_collects.get(m.group(1), set())
            vs = sorted([v for v in db.videos.values()
                         if v.id in col and v.status == "published"],
                        key=lambda x: x.created_at, reverse=True)
            s, e = (page - 1) * ps, page * ps
            return success({
                "list": [{"id": v.id, "title": v.title, "coverUrl": v.cover_url,
                          "duration": v.duration, "likesCount": v.likes_count,
                          "viewsCount": v.views_count} for v in vs[s:e]],
                "total": len(vs), "page": page, "pageSize": ps, "hasMore": e < len(vs)
            })
        for sub in ["following", "followers"]:
            m = re.match(rf"^/api/account/([^/]+)/{sub}$", path)
            if m:
                page, ps = int(qp.get("page", ["1"])[0]), int(qp.get("pageSize", ["20"])[0])
                s2 = db.user_followings.get(m.group(1), set()) if sub == "following" \
                    else db.user_followers.get(m.group(1), set())
                us = sorted([db.users[x] for x in s2 if x in db.users],
                            key=lambda x: x.followers_count, reverse=True)
                s, e = (page - 1) * ps, page * ps
                return success({
                    "list": [enrich_user(u, uid) for u in us[s:e]],
                    "total": len(us), "page": page, "pageSize": ps, "hasMore": e < len(us)
                })
    if method == "PUT":
        if path == "/api/account/profile":
            u = db.users.get(uid)
            if not u:
                return error("用户不存在", 404)
            for k in ["nickname", "avatar", "bio"]:
                if k in body:
                    setattr(u, k, body[k])
            return success(u.to_dict(), "资料更新成功")
    return None


def handle_interaction(path, qp, uid, body=None, method="GET"):
    if method == "GET":
        m = re.match(r"^/api/interaction/video/([^/]+)/comments$", path)
        if m:
            page, ps = int(qp.get("page", ["1"])[0]), int(qp.get("pageSize", ["20"])[0])
            cids = db.video_comments.get(m.group(1), [])
            cs = sorted([db.comments[c] for c in cids
                         if c in db.comments and db.comments[c].parent_id is None],
                        key=lambda x: x.created_at, reverse=True)
            s, e = (page - 1) * ps, page * ps
            return success({
                "list": [enrich_comment(c, uid) for c in cs[s:e]],
                "total": len(cs), "page": page, "pageSize": ps, "hasMore": e < len(cs)
            })
        m = re.match(r"^/api/interaction/comment/([^/]+)/replies$", path)
        if m:
            page, ps = int(qp.get("page", ["1"])[0]), int(qp.get("pageSize", ["20"])[0])
            cs = sorted([c for c in db.comments.values() if c.parent_id == m.group(1)],
                        key=lambda x: x.created_at)
            s, e = (page - 1) * ps, page * ps
            return success({
                "list": [enrich_comment(c, uid) for c in cs[s:e]],
                "total": len(cs), "page": page, "pageSize": ps, "hasMore": e < len(cs)
            })
        m = re.match(r"^/api/interaction/video/([^/]+)/danmakus$", path)
        if m:
            ds = db.danmakus.get(m.group(1), [])
            return success({"list": [d.to_dict() for d in ds]})
    if method == "POST":
        m = re.match(r"^/api/interaction/video/([^/]+)/like$", path)
        if m:
            v = db.videos.get(m.group(1))
            if not v:
                return error("视频不存在", 404)
            ls = db.user_likes.get(uid, set())
            liked = v.id in ls
            if liked:
                ls.discard(v.id)
                v.likes_count = max(0, v.likes_count - 1)
            else:
                ls.add(v.id)
                v.likes_count += 1
                if v.user_id != uid:
                    cu = db.users.get(uid)
                    add_notification(v.user_id, NotificationType.LIKE,
                                     f"{cu.nickname if cu else '有人'} 赞了你的视频", v.id)
            db.user_likes[uid] = ls
            return success({"isLiked": not liked, "likesCount": v.likes_count})
        m = re.match(r"^/api/interaction/video/([^/]+)/collect$", path)
        if m:
            v = db.videos.get(m.group(1))
            if not v:
                return error("视频不存在", 404)
            cs = db.user_collects.get(uid, set())
            col = v.id in cs
            if col:
                cs.discard(v.id)
                v.collects_count = max(0, v.collects_count - 1)
            else:
                cs.add(v.id)
                v.collects_count += 1
            db.user_collects[uid] = cs
            return success({"isCollected": not col, "collectsCount": v.collects_count})
        m = re.match(r"^/api/interaction/video/([^/]+)/share$", path)
        if m:
            v = db.videos.get(m.group(1))
            if not v:
                return error("视频不存在", 404)
            v.shares_count += 1
            return success({"sharesCount": v.shares_count,
                            "shareUrl": f"https://example.com/video/{v.id}"})
        m = re.match(r"^/api/interaction/video/([^/]+)/comments$", path)
        if m:
            v = db.videos.get(m.group(1))
            if not v:
                return error("视频不存在", 404)
            cid = str(uuid.uuid4())
            c = Comment(id=cid, video_id=m.group(1), user_id=uid,
                        content=body.get("content", ""), likes_count=0,
                        reply_count=0, parent_id=body.get("parentId"),
                        created_at=int(time.time() * 1000))
            db.comments[cid] = c
            db.comment_likes[cid] = set()
            if m.group(1) not in db.video_comments:
                db.video_comments[m.group(1)] = []
            db.video_comments[m.group(1)].append(cid)
            v.comments_count += 1
            if body.get("parentId"):
                pc = db.comments.get(body["parentId"])
                if pc:
                    pc.reply_count += 1
            if v.user_id != uid and not body.get("parentId"):
                cu = db.users.get(uid)
                add_notification(v.user_id, NotificationType.COMMENT,
                                 f"{cu.nickname if cu else '有人'} 评论了你的视频：{body.get('content', '')[:20]}",
                                 v.id)
            return success(enrich_comment(c, uid), "评论成功")
        m = re.match(r"^/api/interaction/comment/([^/]+)/like$", path)
        if m:
            c = db.comments.get(m.group(1))
            if not c:
                return error("评论不存在", 404)
            ls = db.comment_likes.get(m.group(1), set())
            liked = uid in ls
            if liked:
                ls.discard(uid)
                c.likes_count = max(0, c.likes_count - 1)
            else:
                ls.add(uid)
                c.likes_count += 1
            db.comment_likes[m.group(1)] = ls
            return success({"isLiked": not liked, "likesCount": c.likes_count})
        m = re.match(r"^/api/interaction/video/([^/]+)/danmakus$", path)
        if m:
            v = db.videos.get(m.group(1))
            if not v:
                return error("视频不存在", 404)
            d = Danmaku(id=str(uuid.uuid4()), video_id=m.group(1), user_id=uid,
                        content=body.get("content", ""),
                        timestamp=body.get("timestamp", 0),
                        color=body.get("color", "#ffffff"),
                        created_at=int(time.time() * 1000))
            if m.group(1) not in db.danmakus:
                db.danmakus[m.group(1)] = []
            db.danmakus[m.group(1)].append(d)
            return success(d.to_dict(), "弹幕发送成功")
        m = re.match(r"^/api/interaction/user/([^/]+)/follow$", path)
        if m:
            tid = m.group(1)
            if tid == uid:
                return error("不能关注自己", 400)
            tu = db.users.get(tid)
            if not tu:
                return error("用户不存在", 404)
            fs = db.user_followings.get(uid, set())
            fss = db.user_followers.get(tid, set())
            f = tid in fs
            if f:
                fs.discard(tid)
                fss.discard(uid)
                tu.followers_count = max(0, tu.followers_count - 1)
                cu = db.users.get(uid)
                if cu:
                    cu.following_count = max(0, cu.following_count - 1)
            else:
                fs.add(tid)
                fss.add(uid)
                tu.followers_count += 1
                cu = db.users.get(uid)
                if cu:
                    cu.following_count += 1
                cu2 = db.users.get(uid)
                add_notification(tid, NotificationType.FOLLOW,
                                 f"{cu2.nickname if cu2 else '有人'} 关注了你", uid)
            db.user_followings[uid] = fs
            db.user_followers[tid] = fss
            return success({"isFollowed": not f, "followersCount": tu.followers_count})
    return None


def handle_search(path, qp, uid, body=None, method="GET"):
    if method != "GET":
        return None
    if path == "/api/search/video":
        kw = qp.get("keyword", [""])[0]
        page, ps = int(qp.get("page", ["1"])[0]), int(qp.get("pageSize", ["20"])[0])
        sb = qp.get("sortBy", ["relevance"])[0]
        if not kw:
            return success({"list": [], "total": 0, "page": page, "pageSize": ps, "hasMore": False})
        kwl = kw.lower()
        vs = [v for v in db.videos.values() if v.status == "published" and
              (kwl in v.title.lower() or kwl in v.description.lower())]
        if sb == "new":
            vs.sort(key=lambda x: x.created_at, reverse=True)
        elif sb == "likes":
            vs.sort(key=lambda x: x.likes_count, reverse=True)
        elif sb == "views":
            vs.sort(key=lambda x: x.views_count, reverse=True)
        else:
            vs.sort(key=lambda x: (10 if kwl in x.title.lower() else 0) + x.views_count / 1000, reverse=True)
        s, e = (page - 1) * ps, page * ps
        ul = db.user_likes.get(uid, set())
        items = []
        for v in vs[s:e]:
            a = db.users.get(v.user_id)
            author = {"id": a.id, "nickname": a.nickname, "avatar": a.avatar} if a else None
            items.append({
                "id": v.id, "title": v.title, "description": v.description,
                "coverUrl": v.cover_url, "duration": v.duration,
                "likesCount": v.likes_count, "commentsCount": v.comments_count,
                "viewsCount": v.views_count, "isLiked": v.id in ul,
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
        return success({
            "list": [{"id": u.id, "nickname": u.nickname, "username": u.username,
                      "avatar": u.avatar, "bio": u.bio,
                      "followersCount": u.followers_count, "worksCount": u.works_count,
                      "isVerified": u.is_verified, "isFollowed": u.id in fs}
                     for u in us[s:e]],
            "total": len(us), "page": page, "pageSize": ps, "hasMore": e < len(us)
        })
    if path == "/api/search/topic":
        kw = qp.get("keyword", [""])[0]
        page, ps = int(qp.get("page", ["1"])[0]), int(qp.get("pageSize", ["20"])[0])
        ts = list(db.topics.values())
        if kw:
            kwl = kw.lower()
            ts = [t for t in ts if kwl in t.name.lower() or kwl in t.description.lower()]
        ts.sort(key=lambda x: x.views_count, reverse=True)
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
        vs = sorted([v for v in db.videos.values() if v.status == "published"],
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
        vs = [v for v in db.videos.values() if v.user_id == uid and v.status == "published"]
        tv = sum(v.views_count for v in vs)
        tl = sum(v.likes_count for v in vs)
        tc = sum(v.comments_count for v in vs)
        ts = sum(v.shares_count for v in vs)
        return success({
            "summary": {"followersCount": u.followers_count, "worksCount": u.works_count,
                        "totalViews": tv, "totalLikes": tl, "totalComments": tc, "totalShares": ts},
            "today": {"newFans": int(u.followers_count * 0.05), "newViews": int(tv * 0.03),
                      "newLikes": int(tl * 0.02), "newComments": int(tc * 0.04)},
            "trend": {"fansTrend": [120, 150, 180, 200, 220, 250, 280],
                      "viewsTrend": [5000, 6200, 7800, 8500, 9200, 10500, 12000],
                      "likesTrend": [800, 950, 1100, 1300, 1500, 1700, 2000],
                      "dates": ["06-01", "06-02", "06-03", "06-04", "06-05", "06-06", "06-07"]}
        })
    if path == "/api/creator/videos":
        page, ps = int(qp.get("page", ["1"])[0]), int(qp.get("pageSize", ["20"])[0])
        st = qp.get("status", ["all"])[0]
        vs = [v for v in db.videos.values() if v.user_id == uid]
        if st != "all":
            vs = [v for v in vs if v.status == st]
        vs.sort(key=lambda x: x.created_at, reverse=True)
        s, e = (page - 1) * ps, page * ps
        return success({
            "list": [{"id": v.id, "title": v.title, "coverUrl": v.cover_url,
                      "duration": v.duration, "status": v.status,
                      "viewsCount": v.views_count, "likesCount": v.likes_count,
                      "commentsCount": v.comments_count, "sharesCount": v.shares_count,
                      "createdAt": v.created_at} for v in vs[s:e]],
            "total": len(vs), "page": page, "pageSize": ps, "hasMore": e < len(vs)
        })
    if path == "/api/creator/earnings":
        e = db.earnings.get(uid)
        if not e:
            return error("收益数据不存在", 404)
        return success({
            "total": {"totalEarnings": e.total_earnings,
                      "withdrawable": e.withdrawable, "pending": e.pending},
            "overview": {"today": e.today_earnings,
                         "yesterday": int(e.today_earnings * 0.85),
                         "week": e.week_earnings, "month": e.month_earnings},
            "trend": {"daily": [
                {"date": "06-01", "amount": 35.5}, {"date": "06-02", "amount": 42.3},
                {"date": "06-03", "amount": 38.7}, {"date": "06-04", "amount": 55.2},
                {"date": "06-05", "amount": 48.9}, {"date": "06-06", "amount": 62.1},
                {"date": "06-07", "amount": e.today_earnings}]},
            "sources": [
                {"name": "创作收益", "amount": int(e.month_earnings * 0.6), "percent": 60},
                {"name": "广告分成", "amount": int(e.month_earnings * 0.25), "percent": 25},
                {"name": "直播打赏", "amount": int(e.month_earnings * 0.1), "percent": 10},
                {"name": "其他", "amount": int(e.month_earnings * 0.05), "percent": 5}]
        })
    if path == "/api/creator/fans":
        u = db.users.get(uid)
        if not u:
            return error("用户不存在", 404)
        fids = list(db.user_followers.get(uid, set()))
        fus = [db.users[x] for x in fids if x in db.users][:10]
        fs = db.user_followings.get(uid, set())
        now = int(time.time() * 1000)
        return success({
            "total": u.followers_count, "newToday": int(u.followers_count * 0.02),
            "trend": {"data": [100, 150, 200, 280, 350, 420, 500],
                      "dates": ["06-01", "06-02", "06-03", "06-04", "06-05", "06-06", "06-07"]},
            "recentFans": [{"id": fu.id, "nickname": fu.nickname, "avatar": fu.avatar,
                            "isFollowBack": fu.id in fs,
                            "followTime": now - 3600000 * (i + 1)}
                           for i, fu in enumerate(fus)],
            "analysis": {
                "gender": {"male": 58, "female": 42},
                "age": [{"range": "18-24", "percent": 40}, {"range": "25-30", "percent": 30},
                        {"range": "31-40", "percent": 20}, {"range": "其他", "percent": 10}],
                "activeTime": [
                    {"hour": 0, "value": 20}, {"hour": 6, "value": 15},
                    {"hour": 12, "value": 45}, {"hour": 18, "value": 70},
                    {"hour": 21, "value": 90}, {"hour": 23, "value": 50}]}
        })
    m = re.match(r"^/api/creator/videos/([^/]+)/data$", path)
    if m:
        v = db.videos.get(m.group(1))
        if not v or v.user_id != uid:
            return error("视频不存在", 404)
        return success({
            "videoId": v.id, "title": v.title, "coverUrl": v.cover_url,
            "views": {"total": v.views_count, "today": int(v.views_count * 0.1),
                      "trend": {"data": [100, 250, 380, 520, 680, 850, 1000],
                                "dates": ["06-01", "06-02", "06-03", "06-04", "06-05", "06-06", "06-07"]}},
            "interactions": {"likes": v.likes_count, "comments": v.comments_count,
                             "shares": v.shares_count, "collects": v.collects_count},
            "audience": {
                "gender": {"male": 55, "female": 45},
                "age": [{"range": "<18", "percent": 10}, {"range": "18-24", "percent": 35},
                        {"range": "25-30", "percent": 28}, {"range": "31-40", "percent": 18},
                        {"range": ">40", "percent": 9}],
                "regions": [
                    {"name": "广东", "value": 15}, {"name": "浙江", "value": 12},
                    {"name": "江苏", "value": 10}, {"name": "北京", "value": 9},
                    {"name": "上海", "value": 8}, {"name": "其他", "value": 46}]},
            "playDuration": {
                "avgPlayDuration": int(v.duration * 0.7), "completionRate": 68.5,
                "dropPoints": [
                    {"time": 0, "retention": 100}, {"time": 5, "retention": 85},
                    {"time": 10, "retention": 72}, {"time": 15, "retention": 65},
                    {"time": 20, "retention": 58}, {"time": 25, "retention": 52},
                    {"time": 30, "retention": 45}]}})
    return None


def handle_audit(path, qp, uid, body=None, method="GET"):
    if method == "GET":
        if path == "/api/audit/report/list":
            page, ps = int(qp.get("page", ["1"])[0]), int(qp.get("pageSize", ["20"])[0])
            st = qp.get("status", ["all"])[0]
            rs = list(db.reports.values())
            if st != "all":
                rs = [r for r in rs if r.status == st]
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
                    "status": r.status, "createdAt": r.created_at
                })
            return success({
                "list": items,
                "total": len(rs), "page": page, "pageSize": ps, "hasMore": e < len(rs)
            })
        if path == "/api/audit/notifications":
            page, ps = int(qp.get("page", ["1"])[0]), int(qp.get("pageSize", ["20"])[0])
            t = qp.get("type", ["all"])[0]
            ns = db.notifications.get(uid, [])
            if t != "all":
                ns = [n for n in ns if n.type == t]
            s, e = (page - 1) * ps, page * ps
            uc = sum(1 for n in ns if not n.is_read)
            return success({
                "list": [n.to_dict() for n in ns[s:e]],
                "total": len(ns), "unreadCount": uc,
                "page": page, "pageSize": ps, "hasMore": e < len(ns)
            })
        if path == "/api/audit/notifications/unread-count":
            ns = db.notifications.get(uid, [])
            return success({"total": sum(1 for n in ns if not n.is_read),
                            "byType": {
                                "like": sum(1 for n in ns if not n.is_read and n.type == "like"),
                                "comment": sum(1 for n in ns if not n.is_read and n.type == "comment"),
                                "follow": sum(1 for n in ns if not n.is_read and n.type == "follow"),
                                "system": sum(1 for n in ns if not n.is_read and n.type == "system")}})
        if path == "/api/audit/audit/videos":
            page, ps = int(qp.get("page", ["1"])[0]), int(qp.get("pageSize", ["20"])[0])
            st = qp.get("status", ["reviewing"])[0]
            vs = [v for v in db.videos.values() if v.status == st]
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
    if method == "POST":
        if path == "/api/audit/report/video":
            v = db.videos.get(body.get("videoId", ""))
            if not v:
                return error("视频不存在", 404)
            rid = str(uuid.uuid4())
            r = Report(id=rid, video_id=body.get("videoId", ""), user_id=uid,
                       reason=body.get("reason", ""), description=body.get("description", ""),
                       status=ReportStatus.PENDING, created_at=int(time.time() * 1000))
            db.reports[rid] = r
            return success({"reportId": rid}, "举报已提交，我们将尽快处理")
        m = re.match(r"^/api/audit/report/([^/]+)/process$", path)
        if m:
            r = db.reports.get(m.group(1))
            if not r:
                return error("举报记录不存在", 404)
            r.status = ReportStatus.PROCESSING
            if body.get("action") == "remove":
                v = db.videos.get(r.video_id)
                if v:
                    v.status = VideoStatus.REMOVED
                    v.updated_at = int(time.time() * 1000)
                    add_notification(v.user_id, NotificationType.SYSTEM,
                                     f'您的视频"{v.title}"因违反平台规范已被下架', v.id)
                r.status = ReportStatus.RESOLVED
            elif body.get("action") == "dismiss":
                r.status = ReportStatus.RESOLVED
            return success({"reportId": r.id, "status": r.status}, "处理完成")
        m = re.match(r"^/api/audit/video/([^/]+)/remove$", path)
        if m:
            v = db.videos.get(m.group(1))
            if not v:
                return error("视频不存在", 404)
            v.status = VideoStatus.REMOVED
            v.updated_at = int(time.time() * 1000)
            add_notification(v.user_id, NotificationType.SYSTEM,
                             f'您的视频"{v.title}"因{body.get("reason", "违反平台规范")}已被下架', v.id)
            return success({"videoId": v.id, "status": "removed"}, "视频已下架")
        m = re.match(r"^/api/audit/video/([^/]+)/restore$", path)
        if m:
            v = db.videos.get(m.group(1))
            if not v:
                return error("视频不存在", 404)
            v.status = VideoStatus.PUBLISHED
            v.updated_at = int(time.time() * 1000)
            add_notification(v.user_id, NotificationType.SYSTEM,
                             f'您的视频"{v.title}"已恢复上架', v.id)
            return success({"videoId": v.id, "status": "published"}, "视频已恢复")
        m = re.match(r"^/api/audit/notifications/([^/]+)/read$", path)
        if m:
            ns = db.notifications.get(uid, [])
            n = next((x for x in ns if x.id == m.group(1)), None)
            if not n:
                return error("通知不存在", 404)
            n.is_read = True
            return success(None, "已标记为已读")
        if path == "/api/audit/notifications/read-all":
            ns = db.notifications.get(uid, [])
            for n in ns:
                n.is_read = True
            return success(None, "全部标记为已读")
        m = re.match(r"^/api/audit/audit/videos/([^/]+)/approve$", path)
        if m:
            v = db.videos.get(m.group(1))
            if not v or v.status != VideoStatus.REVIEWING:
                return error("视频不存在或状态不正确", 404)
            v.status = VideoStatus.PUBLISHED
            v.updated_at = int(time.time() * 1000)
            add_notification(v.user_id, NotificationType.SYSTEM,
                             f'您的视频"{v.title}"审核通过，已发布', v.id)
            return success({"videoId": v.id, "status": "published"}, "审核通过")
        m = re.match(r"^/api/audit/audit/videos/([^/]+)/reject$", path)
        if m:
            v = db.videos.get(m.group(1))
            if not v or v.status != VideoStatus.REVIEWING:
                return error("视频不存在或状态不正确", 404)
            v.status = VideoStatus.REMOVED
            v.updated_at = int(time.time() * 1000)
            reason = body.get("reason", "不符合平台规范")
            add_notification(v.user_id, NotificationType.SYSTEM,
                             f'您的视频"{v.title}"审核未通过，原因：{reason}', v.id)
            return success({"videoId": v.id, "status": "removed"}, "审核驳回")
    return None


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def _set_headers(self, code=200):
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, x-user-id")
        self.end_headers()

    def _send(self, data, code=200):
        self._set_headers(code)
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))

    def _body(self):
        cl = int(self.headers.get("Content-Length", 0))
        if cl == 0:
            return {}
        try:
            return json.loads(self.rfile.read(cl).decode("utf-8"))
        except:
            return {}

    def do_OPTIONS(self):
        self._set_headers(200)

    def do_GET(self):
        p = urlparse(self.path)
        uid = get_user_id(self.headers)
        result = self._route(p.path, parse_qs(p.query), uid, None, "GET")
        self._send_result(result)

    def do_POST(self):
        p = urlparse(self.path)
        uid = get_user_id(self.headers)
        result = self._route(p.path, parse_qs(p.query), uid, self._body(), "POST")
        self._send_result(result)

    def do_PUT(self):
        p = urlparse(self.path)
        uid = get_user_id(self.headers)
        result = self._route(p.path, parse_qs(p.query), uid, self._body(), "PUT")
        self._send_result(result)

    def do_DELETE(self):
        p = urlparse(self.path)
        uid = get_user_id(self.headers)
        result = self._route(p.path, parse_qs(p.query), uid, None, "DELETE")
        self._send_result(result)

    def _route(self, path, qp, uid, body, method):
        if path == "/":
            return success({
                "name": "短视频平台后端服务", "version": "1.0.0",
                "description": "为多个客户端提供内容与互动能力的短视频平台后端",
                "apis": {
                    "video": "/api/video - 视频流接口",
                    "publish": "/api/publish - 发布接口",
                    "account": "/api/account - 账号接口",
                    "interaction": "/api/interaction - 互动接口",
                    "search": "/api/search - 搜索接口",
                    "creator": "/api/creator - 创作者接口",
                    "audit": "/api/audit - 审核接口",
                }
            })

        for handler in [handle_video, handle_publish, handle_account,
                        handle_interaction, handle_search, handle_creator, handle_audit]:
            r = handler(path, qp, uid, body, method)
            if r is not None:
                return r

        return error("接口不存在", 404)

    def _send_result(self, result):
        code = result.get("code", 0)
        status = 200
        if code == 404:
            status = 404
        elif code >= 400:
            status = code
        elif code != 0:
            status = 400
        self._send(result, status)


def run_server(port=8000):
    server = HTTPServer(("", port), Handler)
    print("=" * 40)
    print("  短视频平台后端服务已启动")
    print(f"  服务地址: http://localhost:{port}")
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
    print("=" * 40)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n服务已停止")
        server.server_close()


if __name__ == "__main__":
    run_server()
