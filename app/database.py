import uuid
import time
from typing import Dict, List, Set, Optional
from .models import (
    User, Video, Comment, Danmaku, Draft, UploadTask,
    Report, Notification, Topic, Earning, VideoStatus, ReportStatus, NotificationType
)


class Database:
    def __init__(self):
        self.users: Dict[str, User] = {}
        self.videos: Dict[str, Video] = {}
        self.comments: Dict[str, Comment] = {}
        self.danmakus: Dict[str, List[Danmaku]] = {}
        self.drafts: Dict[str, List[Draft]] = {}
        self.upload_tasks: Dict[str, UploadTask] = {}
        self.reports: Dict[str, Report] = {}
        self.notifications: Dict[str, List[Notification]] = {}
        self.topics: Dict[str, Topic] = {}
        self.earnings: Dict[str, Earning] = {}

        self.user_followings: Dict[str, Set[str]] = {}
        self.user_followers: Dict[str, Set[str]] = {}
        self.user_likes: Dict[str, Set[str]] = {}
        self.user_collects: Dict[str, Set[str]] = {}
        self.comment_likes: Dict[str, Set[str]] = {}
        self.video_comments: Dict[str, List[str]] = {}

        self._init_mock_data()

    def _init_mock_data(self):
        now = int(time.time() * 1000)

        mock_users = [
            User(id='u1', username='creator01', nickname='美食探店达人', avatar='https://picsum.photos/seed/u1/200/200', bio='分享各地美食，带你吃遍天下', followers_count=125800, following_count=230, works_count=156, likes_count=890000, is_verified=True, created_at=now - 86400000 * 365),
            User(id='u2', username='travel_girl', nickname='旅行的意义', avatar='https://picsum.photos/seed/u2/200/200', bio='环游世界中，用镜头记录美好', followers_count=56000, following_count=180, works_count=89, likes_count=450000, is_verified=True, created_at=now - 86400000 * 200),
            User(id='u3', username='tech_geek', nickname='科技极客', avatar='https://picsum.photos/seed/u3/200/200', bio='数码产品评测，科技资讯分享', followers_count=230000, following_count=150, works_count=234, likes_count=1200000, is_verified=True, created_at=now - 86400000 * 500),
            User(id='u4', username='fitness_pro', nickname='健身教练小李', avatar='https://picsum.photos/seed/u4/200/200', bio='专业健身指导，帮你塑造完美身材', followers_count=89000, following_count=95, works_count=178, likes_count=670000, is_verified=False, created_at=now - 86400000 * 150),
            User(id='u5', username='cute_cat', nickname='猫咪日记', avatar='https://picsum.photos/seed/u5/200/200', bio='记录我家猫咪的日常', followers_count=15000, following_count=320, works_count=67, likes_count=98000, is_verified=False, created_at=now - 86400000 * 100),
            User(id='u6', username='music_lover', nickname='音乐分享家', avatar='https://picsum.photos/seed/u6/200/200', bio='好音乐值得被听到', followers_count=34000, following_count=210, works_count=112, likes_count=280000, is_verified=False, created_at=now - 86400000 * 180),
        ]
        for u in mock_users:
            self.users[u.id] = u

        mock_topics = [
            Topic(id='t1', name='美食探店', description='分享各地美食探店体验', video_count=12500, views_count=8900000, cover='https://picsum.photos/seed/t1/400/300'),
            Topic(id='t2', name='旅行vlog', description='记录旅行中的美好时光', video_count=23400, views_count=15000000, cover='https://picsum.photos/seed/t2/400/300'),
            Topic(id='t3', name='科技数码', description='最新科技产品评测分享', video_count=8900, views_count=6700000, cover='https://picsum.photos/seed/t3/400/300'),
            Topic(id='t4', name='健身打卡', description='一起健身，打卡每一天', video_count=18700, views_count=9800000, cover='https://picsum.photos/seed/t4/400/300'),
            Topic(id='t5', name='萌宠日常', description='萌宠的治愈系日常', video_count=34500, views_count=23000000, cover='https://picsum.photos/seed/t5/400/300'),
            Topic(id='t6', name='音乐分享', description='好音乐推荐与分享', video_count=15600, views_count=7800000, cover='https://picsum.photos/seed/t6/400/300'),
        ]
        for t in mock_topics:
            self.topics[t.id] = t

        video_titles = [
            '今天去吃了这家超火的火锅店，味道绝了！',
            '云南大理旅行vlog，洱海的风景太美了',
            '最新款旗舰手机开箱评测，值不值得买？',
            '30天马甲线挑战Day1，跟我一起练',
            '我家猫主子今天又做了什么傻事',
            '这首小众歌曲太好听了，单曲循环中',
            '探店隐藏在巷子里的百年老店',
            '一个人的旅行，遇见更好的自己',
            '程序员的一天是怎么度过的',
            '新手健身最容易犯的5个错误',
            '猫咪第一次见到雪的反应太可爱了',
            '盘点今年最火的十首歌',
            '街边小吃测评，这家必吃',
            '西藏自驾之旅，风景震撼人心',
            '拆解最新款无线耳机，看看内部结构',
        ]
        video_descs = [
            '喜欢的话记得点赞关注哦~',
            '分享给你身边的朋友吧',
            '评论区告诉我你的看法',
            '下期想看什么，评论告诉我',
            '记得三连支持一下~',
        ]

        for i in range(30):
            user_idx = i % 6
            topic_ids = ['t' + str(user_idx + 1)]
            if i % 3 == 0:
                topic_ids.append('t' + str(((i + 2) % 6) + 1))

            video = Video(
                id=f'v{i+1}',
                user_id=f'u{user_idx+1}',
                title=video_titles[i % len(video_titles)],
                description=video_descs[i % len(video_descs)],
                cover_url=f'https://picsum.photos/seed/v{i+1}/720/1280',
                video_url=f'https://example.com/videos/v{i+1}.mp4',
                duration=30 + (i * 7) % 90,
                likes_count=1000 + int((i * 137) % 50000),
                comments_count=100 + int((i * 53) % 2000),
                shares_count=10 + int((i * 17) % 500),
                views_count=10000 + int((i * 231) % 500000),
                collects_count=50 + int((i * 29) % 3000),
                topics=topic_ids,
                status=VideoStatus.PUBLISHED,
                created_at=now - 86400000 * i,
                updated_at=now - 86400000 * i,
            )
            self.videos[video.id] = video

        for u in mock_users:
            self.user_followings[u.id] = set()
            self.user_followers[u.id] = set()
            self.user_likes[u.id] = set()
            self.user_collects[u.id] = set()
            self.notifications[u.id] = []
            self.drafts[u.id] = []
            self.earnings[u.id] = Earning(
                user_id=u.id,
                total_earnings=1000 + int((hash(u.id) % 50000)),
                today_earnings=10 + int((hash(u.id) % 500)),
                week_earnings=100 + int((hash(u.id) % 3000)),
                month_earnings=500 + int((hash(u.id) % 10000)),
                withdrawable=200 + int((hash(u.id) % 3000)),
                pending=50 + int((hash(u.id) % 500)),
            )

        for i in range(20):
            video_idx = i % 30
            user_idx = (i + 3) % 6
            comment_id = f'c{i+1}'
            contents = [
                '这个视频太精彩了！',
                '学到了很多，感谢分享',
                '已关注，期待更多作品',
                '哈哈哈笑死我了',
                'bgm是什么呀，好好听',
                'up主好厉害',
                '第一次评论，支持一下',
            ]
            comment = Comment(
                id=comment_id,
                video_id=f'v{video_idx+1}',
                user_id=f'u{user_idx+1}',
                content=contents[i % 7],
                likes_count=10 + int((i * 13) % 500),
                reply_count=int((i * 3) % 10),
                parent_id=None,
                created_at=now - 3600000 * i,
            )
            self.comments[comment_id] = comment
            self.comment_likes[comment_id] = set()

            vid = f'v{video_idx+1}'
            if vid not in self.video_comments:
                self.video_comments[vid] = []
            self.video_comments[vid].append(comment_id)

        for i in range(30):
            vid = f'v{i+1}'
            if vid not in self.danmakus:
                self.danmakus[vid] = []
            for j in range(5):
                contents = ['666', '前方高能', '哈哈哈哈', '打卡', '好看', '厉害']
                colors = ['#ffffff', '#ff0000', '#00ff00', '#ffff00']
                self.danmakus[vid].append(Danmaku(
                    id=f'd{i*5+j+1}',
                    video_id=vid,
                    user_id=f'u{j%6+1}',
                    content=contents[j % 6],
                    timestamp=(j + 1) * 5,
                    color=colors[j % 4],
                    created_at=now - 86400000 * i,
                ))

        current_user = 'u1'
        for i in range(2, 6):
            self.user_followings[current_user].add(f'u{i}')
            self.user_followers[f'u{i}'].add(current_user)

        for i in range(1, 11):
            self.user_likes[current_user].add(f'v{i}')
        for i in range(1, 6):
            self.user_collects[current_user].add(f'v{i}')

        notifications = [
            Notification(id='n1', user_id='u1', type=NotificationType.LIKE, content='用户旅行的意义 赞了你的视频', related_id='v1', is_read=False, created_at=now - 3600000),
            Notification(id='n2', user_id='u1', type=NotificationType.COMMENT, content='科技极客 评论了你的视频：这个视频太精彩了！', related_id='v1', is_read=False, created_at=now - 7200000),
            Notification(id='n3', user_id='u1', type=NotificationType.FOLLOW, content='健身教练小李 关注了你', related_id='u4', is_read=True, created_at=now - 86400000),
            Notification(id='n4', user_id='u1', type=NotificationType.SYSTEM, content='恭喜你，你的作品获得了热门推荐', related_id='v2', is_read=True, created_at=now - 172800000),
        ]
        self.notifications['u1'] = notifications

        draft = Draft(
            id='d1',
            user_id='u1',
            title='未发布的美食探店视频',
            description='草稿描述...',
            cover_url='https://picsum.photos/seed/draft1/720/1280',
            video_url='https://example.com/drafts/d1.mp4',
            duration=45,
            topics=['t1'],
            updated_at=now - 3600000,
        )
        self.drafts['u1'].append(draft)


db = Database()


def add_notification(user_id: str, type: NotificationType, content: str, related_id: Optional[str] = None):
    notification = Notification(
        id=str(uuid.uuid4()),
        user_id=user_id,
        type=type,
        content=content,
        related_id=related_id,
        is_read=False,
        created_at=int(time.time() * 1000),
    )
    if user_id not in db.notifications:
        db.notifications[user_id] = []
    db.notifications[user_id].insert(0, notification)
