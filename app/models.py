from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from enum import Enum


class VideoStatus(str, Enum):
    DRAFT = "draft"
    REVIEWING = "reviewing"
    PUBLISHED = "published"
    REMOVED = "removed"
    REJECTED = "rejected"


class ReportStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    RESOLVED = "resolved"
    REJECTED = "rejected"


class NotificationType(str, Enum):
    LIKE = "like"
    COMMENT = "comment"
    REPLY = "reply"
    FOLLOW = "follow"
    SYSTEM = "system"
    AUDIT_PASS = "audit_pass"
    AUDIT_REJECT = "audit_reject"
    REPORT_PROGRESS = "report_progress"
    VIDEO_REMOVE = "video_remove"
    VIDEO_RESTORE = "video_restore"
    TOPIC_APPLY = "topic_apply"


class UploadStatus(str, Enum):
    INIT = "init"
    UPLOADING = "uploading"
    PAUSED = "paused"
    CANCELLED = "cancelled"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class User:
    id: str
    username: str
    nickname: str
    avatar: str
    bio: str
    followers_count: int
    following_count: int
    works_count: int
    likes_count: int
    is_verified: bool
    created_at: int

    def to_dict(self):
        return {
            "id": self.id,
            "username": self.username,
            "nickname": self.nickname,
            "avatar": self.avatar,
            "bio": self.bio,
            "followersCount": self.followers_count,
            "followingCount": self.following_count,
            "worksCount": self.works_count,
            "likesCount": self.likes_count,
            "isVerified": self.is_verified,
            "createdAt": self.created_at,
        }


@dataclass
class Video:
    id: str
    user_id: str
    title: str
    description: str
    cover_url: str
    video_url: str
    duration: int
    likes_count: int
    comments_count: int
    shares_count: int
    views_count: int
    collects_count: int
    topics: List[str]
    status: VideoStatus
    created_at: int
    updated_at: int
    reject_reason: Optional[str] = None

    def to_dict(self):
        return {
            "id": self.id,
            "userId": self.user_id,
            "title": self.title,
            "description": self.description,
            "coverUrl": self.cover_url,
            "videoUrl": self.video_url,
            "duration": self.duration,
            "likesCount": self.likes_count,
            "commentsCount": self.comments_count,
            "sharesCount": self.shares_count,
            "viewsCount": self.views_count,
            "collectsCount": self.collects_count,
            "topics": self.topics,
            "status": self.status,
            "createdAt": self.created_at,
            "updatedAt": self.updated_at,
            "rejectReason": self.reject_reason,
        }


@dataclass
class Comment:
    id: str
    video_id: str
    user_id: str
    content: str
    likes_count: int
    reply_count: int
    parent_id: Optional[str]
    root_id: Optional[str]
    created_at: int
    is_deleted: bool = False

    def to_dict(self):
        return {
            "id": self.id,
            "videoId": self.video_id,
            "userId": self.user_id,
            "content": self.content,
            "likesCount": self.likes_count,
            "replyCount": self.reply_count,
            "parentId": self.parent_id,
            "rootId": self.root_id,
            "createdAt": self.created_at,
            "isDeleted": self.is_deleted,
        }


@dataclass
class Danmaku:
    id: str
    video_id: str
    user_id: str
    content: str
    timestamp: float
    color: str
    created_at: int

    def to_dict(self):
        return {
            "id": self.id,
            "videoId": self.video_id,
            "userId": self.user_id,
            "content": self.content,
            "timestamp": self.timestamp,
            "color": self.color,
            "createdAt": self.created_at,
        }


@dataclass
class DraftHistory:
    version: int
    title: str
    description: str
    cover_url: str
    video_url: str
    duration: int
    topics: List[str]
    updated_at: int

    def to_dict(self):
        return {
            "version": self.version,
            "title": self.title,
            "description": self.description,
            "coverUrl": self.cover_url,
            "videoUrl": self.video_url,
            "duration": self.duration,
            "topics": self.topics,
            "updatedAt": self.updated_at,
        }


@dataclass
class Draft:
    id: str
    user_id: str
    title: str
    description: str
    cover_url: str
    video_url: str
    duration: int
    topics: List[str]
    updated_at: int
    history: List[DraftHistory] = field(default_factory=list)
    file_size: int = 0
    upload_task_id: Optional[str] = None
    duration_unknown: bool = False

    def to_dict(self):
        return {
            "id": self.id,
            "userId": self.user_id,
            "title": self.title,
            "description": self.description,
            "coverUrl": self.cover_url,
            "videoUrl": self.video_url,
            "duration": self.duration,
            "topics": self.topics,
            "updatedAt": self.updated_at,
            "historyCount": len(self.history),
            "fileSize": self.file_size,
            "uploadTaskId": self.upload_task_id,
            "durationUnknown": self.duration_unknown,
        }


@dataclass
class UploadChunk:
    chunk_index: int
    size: int
    uploaded: bool = False
    failed: bool = False

    def to_dict(self):
        return {
            "chunkIndex": self.chunk_index,
            "size": self.size,
            "uploaded": self.uploaded,
            "failed": self.failed,
        }


@dataclass
class UploadTask:
    id: str
    user_id: str
    file_name: str
    file_size: int
    uploaded_size: int
    status: UploadStatus
    video_url: Optional[str]
    chunk_size: int
    total_chunks: int
    chunks: List[UploadChunk]
    created_at: int
    updated_at: int

    def to_dict(self):
        uploaded_count = sum(1 for c in self.chunks if c.uploaded)
        progress = int(uploaded_count / self.total_chunks * 100) if self.total_chunks > 0 else 0
        return {
            "id": self.id,
            "taskId": self.id,
            "userId": self.user_id,
            "fileName": self.file_name,
            "fileSize": self.file_size,
            "uploadedSize": self.uploaded_size,
            "status": self.status,
            "videoUrl": self.video_url,
            "chunkSize": self.chunk_size,
            "totalChunks": self.total_chunks,
            "uploadedChunks": uploaded_count,
            "progress": progress,
            "uploadUrl": f"/api/publish/upload/{self.id}/chunk",
            "createdAt": self.created_at,
            "updatedAt": self.updated_at,
        }


@dataclass
class Report:
    id: str
    video_id: str
    user_id: str
    reason: str
    description: str
    status: ReportStatus
    created_at: int
    handler_id: Optional[str] = None
    handle_note: Optional[str] = None
    handled_at: Optional[int] = None

    def to_dict(self):
        return {
            "id": self.id,
            "videoId": self.video_id,
            "userId": self.user_id,
            "reason": self.reason,
            "description": self.description,
            "status": self.status,
            "createdAt": self.created_at,
            "handlerId": self.handler_id,
            "handleNote": self.handle_note,
            "handledAt": self.handled_at,
        }


@dataclass
class Notification:
    id: str
    user_id: str
    type: NotificationType
    title: str
    content: str
    related_id: Optional[str]
    related_type: Optional[str]
    is_read: bool
    created_at: int
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self):
        return {
            "id": self.id,
            "userId": self.user_id,
            "type": self.type,
            "title": self.title,
            "content": self.content,
            "relatedId": self.related_id,
            "relatedType": self.related_type,
            "isRead": self.is_read,
            "createdAt": self.created_at,
            "extra": self.extra,
        }


@dataclass
class Topic:
    id: str
    name: str
    description: str
    video_count: int
    views_count: int
    likes_count: int
    comments_count: int
    collects_count: int
    shares_count: int
    cover: str
    heat: int
    created_at: int
    creator_id: Optional[str] = None
    is_official: bool = True

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "videoCount": self.video_count,
            "viewsCount": self.views_count,
            "likesCount": self.likes_count,
            "commentsCount": self.comments_count,
            "collectsCount": self.collects_count,
            "sharesCount": self.shares_count,
            "cover": self.cover,
            "heat": self.heat,
            "createdAt": self.created_at,
            "creatorId": self.creator_id,
            "isOfficial": self.is_official,
        }


@dataclass
class TopicApply:
    id: str
    user_id: str
    name: str
    description: str
    status: str
    created_at: int
    reject_reason: Optional[str] = None

    def to_dict(self):
        return {
            "id": self.id,
            "userId": self.user_id,
            "name": self.name,
            "description": self.description,
            "status": self.status,
            "createdAt": self.created_at,
            "rejectReason": self.reject_reason,
        }


@dataclass
class Earning:
    user_id: str
    total_earnings: float
    today_earnings: float
    week_earnings: float
    month_earnings: float
    withdrawable: float
    pending: float

    def to_dict(self):
        return {
            "userId": self.user_id,
            "totalEarnings": self.total_earnings,
            "todayEarnings": self.today_earnings,
            "weekEarnings": self.week_earnings,
            "monthEarnings": self.month_earnings,
            "withdrawable": self.withdrawable,
            "pending": self.pending,
        }


@dataclass
class VideoStatsDaily:
    video_id: str
    date: str
    views: int
    likes: int
    comments: int
    collects: int
    shares: int
    new_fans: int = 0
    earnings: float = 0.0

    def to_dict(self):
        return {
            "videoId": self.video_id,
            "date": self.date,
            "views": self.views,
            "likes": self.likes,
            "comments": self.comments,
            "collects": self.collects,
            "shares": self.shares,
            "newFans": self.new_fans,
            "earnings": self.earnings,
        }


@dataclass
class ReportHandleRecord:
    id: str
    report_id: str
    handler_id: str
    handler_name: str
    action: str
    note: str
    created_at: int

    def to_dict(self):
        return {
            "id": self.id,
            "reportId": self.report_id,
            "handlerId": self.handler_id,
            "handlerName": self.handler_name,
            "action": self.action,
            "note": self.note,
            "createdAt": self.created_at,
        }


@dataclass
class PlatformStatsDaily:
    date: str
    video_publish_count: int
    video_audit_pass_count: int
    video_audit_reject_count: int
    report_count: int
    video_remove_count: int
    active_creators: int
    interactions_count: int
    new_users: int
    earnings: float

    def to_dict(self):
        return {
            "date": self.date,
            "videoPublishCount": self.video_publish_count,
            "videoAuditPassCount": self.video_audit_pass_count,
            "videoAuditRejectCount": self.video_audit_reject_count,
            "reportCount": self.report_count,
            "videoRemoveCount": self.video_remove_count,
            "activeCreators": self.active_creators,
            "interactionsCount": self.interactions_count,
            "newUsers": self.new_users,
            "earnings": self.earnings,
        }
