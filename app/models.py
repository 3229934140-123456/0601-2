from dataclasses import dataclass, field
from typing import Optional, List
from enum import Enum


class VideoStatus(str, Enum):
    DRAFT = "draft"
    REVIEWING = "reviewing"
    PUBLISHED = "published"
    REMOVED = "removed"


class ReportStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    RESOLVED = "resolved"


class NotificationType(str, Enum):
    LIKE = "like"
    COMMENT = "comment"
    FOLLOW = "follow"
    SYSTEM = "system"


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
    created_at: int

    def to_dict(self):
        return {
            "id": self.id,
            "videoId": self.video_id,
            "userId": self.user_id,
            "content": self.content,
            "likesCount": self.likes_count,
            "replyCount": self.reply_count,
            "parentId": self.parent_id,
            "createdAt": self.created_at,
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
        }


@dataclass
class UploadTask:
    id: str
    user_id: str
    file_name: str
    file_size: int
    uploaded_size: int
    status: str
    video_url: Optional[str]
    created_at: int

    def to_dict(self):
        return {
            "id": self.id,
            "userId": self.user_id,
            "fileName": self.file_name,
            "fileSize": self.file_size,
            "uploadedSize": self.uploaded_size,
            "status": self.status,
            "videoUrl": self.video_url,
            "createdAt": self.created_at,
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

    def to_dict(self):
        return {
            "id": self.id,
            "videoId": self.video_id,
            "userId": self.user_id,
            "reason": self.reason,
            "description": self.description,
            "status": self.status,
            "createdAt": self.created_at,
        }


@dataclass
class Notification:
    id: str
    user_id: str
    type: NotificationType
    content: str
    related_id: Optional[str]
    is_read: bool
    created_at: int

    def to_dict(self):
        return {
            "id": self.id,
            "userId": self.user_id,
            "type": self.type,
            "content": self.content,
            "relatedId": self.related_id,
            "isRead": self.is_read,
            "createdAt": self.created_at,
        }


@dataclass
class Topic:
    id: str
    name: str
    description: str
    video_count: int
    views_count: int
    cover: str

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "videoCount": self.video_count,
            "viewsCount": self.views_count,
            "cover": self.cover,
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
