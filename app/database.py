import uuid
import time
import math
from typing import Dict, List, Set, Optional
from .models import (
    User, Video, Comment, Danmaku, Draft, DraftHistory, UploadTask, UploadChunk,
    Report, Notification, Topic, TopicApply, Earning, VideoStatsDaily,
    ReportHandleRecord, PlatformStatsDaily,
    VideoStatus, ReportStatus, NotificationType, UploadStatus
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
        self.topic_applies: Dict[str, TopicApply] = {}
        self.earnings: Dict[str, Earning] = {}
        self.video_stats_daily: Dict[str, List[VideoStatsDaily]] = {}
        self.report_handle_records: Dict[str, List[ReportHandleRecord]] = {}
        self.platform_stats_daily: List[PlatformStatsDaily] = []

        self.user_followings: Dict[str, Set[str]] = {}
        self.user_followers: Dict[str, Set[str]] = {}
        self.user_likes: Dict[str, Set[str]] = {}
        self.user_collects: Dict[str, Set[str]] = {}
        self.comment_likes: Dict[str, Set[str]] = {}
        self.video_comments: Dict[str, List[str]] = {}
        self.video_topics: Dict[str, List[str]] = {}

        self._init_mock_data()

    def add_notification(self, user_id: str, n_type: NotificationType, title: str,
                         content: str, related_id: Optional[str] = None,
                         related_type: Optional[str] = None, extra: Optional[dict] = None):
        nid = str(uuid.uuid4())[:8]
        n = Notification(
            id=nid, user_id=user_id, type=n_type, title=title, content=content,
            related_id=related_id, related_type=related_type,
            is_read=False, created_at=int(time.time() * 1000),
            extra=extra or {}
        )
        if user_id not in self.notifications:
            self.notifications[user_id] = []
        self.notifications[user_id].insert(0, n)

    def add_topic_video_count(self, topic_ids: List[str], delta: int = 1):
        for tid in topic_ids:
            t = self.topics.get(tid)
            if t:
                t.video_count = max(0, t.video_count + delta)
                t.heat = max(0, t.heat + delta * 100)

    def add_topic_interaction(self, topic_ids: List[str], views: int = 0, likes: int = 0,
                              comments: int = 0, collects: int = 0, shares: int = 0):
        for tid in topic_ids:
            t = self.topics.get(tid)
            if t:
                t.views_count = max(0, t.views_count + views)
                t.likes_count = max(0, t.likes_count + likes)
                t.comments_count = max(0, t.comments_count + comments)
                t.collects_count = max(0, t.collects_count + collects)
                t.shares_count = max(0, t.shares_count + shares)
                heat_delta = views + likes * 2 + comments * 3 + collects * 2 + shares * 5
                t.heat = max(0, t.heat + heat_delta)

    def add_topic_interaction_by_video(self, video, multiplier: int = 1):
        views = video.views_count * multiplier
        likes = video.likes_count * multiplier
        comments = video.comments_count * multiplier
        collects = video.collects_count * multiplier
        shares = video.shares_count * multiplier
        for tid in video.topics:
            t = self.topics.get(tid)
            if t:
                t.views_count = max(0, t.views_count + views)
                t.likes_count = max(0, t.likes_count + likes)
                t.comments_count = max(0, t.comments_count + comments)
                t.collects_count = max(0, t.collects_count + collects)
                t.shares_count = max(0, t.shares_count + shares)
                heat_delta = views + likes * 2 + comments * 3 + collects * 2 + shares * 5
                t.heat = max(0, t.heat + heat_delta)

    def add_topic_views(self, topic_id: str, views: int):
        t = self.topics.get(topic_id)
        if t:
            t.views_count += views

    def add_report_handle_record(self, report_id: str, handler_id: str,
                                  action: str, note: str):
        handler = self.users.get(handler_id)
        handler_name = handler.nickname if handler else "系统"
        rid = str(uuid.uuid4())[:8]
        record = ReportHandleRecord(
            id=rid, report_id=report_id, handler_id=handler_id,
            handler_name=handler_name, action=action, note=note,
            created_at=int(time.time() * 1000)
        )
        if report_id not in self.report_handle_records:
            self.report_handle_records[report_id] = []
        self.report_handle_records[report_id].append(record)
        return record

    def get_report_handle_records(self, report_id: str) -> List[ReportHandleRecord]:
        return self.report_handle_records.get(report_id, [])

    def _init_mock_data(self):
        now = int(time.time() * 1000)

        mock_users = [
            User(id='u1', username='creator01', nickname='美食探店达人', avatar='https://picsum.photos/seed/u1/200/200', bio='分享各地美食，带你吃遍天下', followers_count=125800, following_count=230, works_count=156, likes_count=890000, is_verified=True, created_at=now - 86400000 * 365),
            User(id='u2', username='travel_girl', nickname='旅行的意义', avatar='https://picsum.photos/seed/u2/200/200', bio='环游世界中，用镜头记录美好', followers_count=56000, following_count=180, works_count=89, likes_count=450000, is_verified=True, created_at=now - 86400000 * 200),
            User(id='u3', username='tech_geek', nickname='科技极客', avatar='https://picsum.photos/seed/u3/200/200', bio='数码产品评测，科技资讯分享', followers_count=230000, following_count=150, works_count=234, likes_count=1200000, is_verified=True, created_at=now - 86400000 * 500),
            User(id='u4', username='fitness_pro', nickname='健身教练小李', avatar='https://picsum.photos/seed/u4/200/200', bio='专业健身指导，帮你塑造完美身材', followers_count=89000, following_count=95, works_count=178, likes_count=670000, is_verified=False, created_at=now - 86400000 * 150),
            User(id='u5', username='cute_cat', nickname='猫咪日记', avatar='https://picsum.photos/seed/u5/200/200', bio='记录我家猫咪的日常', followers_count=15000, following_count=320, works_count=67, likes_count=98000, is_verified=False, created_at=now - 86400000 * 100),
            User(id='u6', username='music_lover', nickname='音乐分享家', avatar='https://picsum.photos/seed/u6/200/200', bio='好音乐值得被听到', followers_count=34000, following_count=210, works_count=112, likes_count=280000, is_verified=False, created_at=now - 86400000 * 180),
            User(id='u_admin', username='admin', nickname='平台管理员', avatar='https://picsum.photos/seed/admin/200/200', bio='平台官方账号', followers_count=999999, following_count=0, works_count=0, likes_count=0, is_verified=True, created_at=now - 86400000 * 1000),
        ]
        for u in mock_users:
            self.users[u.id] = u

        mock_topics = [
            Topic(id='t1', name='美食探店', description='分享各地美食探店体验', video_count=12500, views_count=8900000, likes_count=450000, comments_count=89000, collects_count=67000, shares_count=34000, cover='https://picsum.photos/seed/t1/400/300', heat=98000, created_at=now - 86400000 * 300),
            Topic(id='t2', name='旅行vlog', description='记录旅行中的美好时光', video_count=23400, views_count=15000000, likes_count=780000, comments_count=156000, collects_count=120000, shares_count=67000, cover='https://picsum.photos/seed/t2/400/300', heat=87000, created_at=now - 86400000 * 280),
            Topic(id='t3', name='科技数码', description='最新科技产品评测分享', video_count=8900, views_count=6700000, likes_count=340000, comments_count=67000, collects_count=45000, shares_count=23000, cover='https://picsum.photos/seed/t3/400/300', heat=76000, created_at=now - 86400000 * 250),
            Topic(id='t4', name='健身打卡', description='一起健身，打卡每一天', video_count=18700, views_count=9800000, likes_count=560000, comments_count=112000, collects_count=89000, shares_count=45000, cover='https://picsum.photos/seed/t4/400/300', heat=65000, created_at=now - 86400000 * 200),
            Topic(id='t5', name='萌宠日常', description='萌宠的治愈系日常', video_count=34500, views_count=23000000, likes_count=1200000, comments_count=230000, collects_count=180000, shares_count=98000, cover='https://picsum.photos/seed/t5/400/300', heat=92000, created_at=now - 86400000 * 180),
            Topic(id='t6', name='音乐分享', description='好音乐推荐与分享', video_count=15600, views_count=7800000, likes_count=390000, comments_count=78000, collects_count=56000, shares_count=34000, cover='https://picsum.photos/seed/t6/400/300', heat=54000, created_at=now - 86400000 * 150),
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
            self.video_topics[video.id] = topic_ids

            stats_list = []
            for d in range(30):
                day = now - 86400000 * d
                date_str = time.strftime('%Y-%m-%d', time.localtime(day / 1000))
                base_v = int(video.views_count / 30 * (1 + 0.1 * math.sin(d)))
                base_l = int(video.likes_count / 30 * (1 + 0.15 * math.cos(d)))
                stats = VideoStatsDaily(
                    video_id=video.id, date=date_str,
                    views=max(10, base_v),
                    likes=max(5, base_l),
                    comments=max(1, int(base_l * 0.05)),
                    collects=max(1, int(base_l * 0.03)),
                    shares=max(1, int(base_l * 0.02)),
                )
                stats_list.append(stats)
            self.video_stats_daily[video.id] = stats_list

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
                reply_count=0,
                parent_id=None,
                root_id=None,
                created_at=now - 3600000 * i,
                is_deleted=False,
            )
            self.comments[comment_id] = comment
            self.comment_likes[comment_id] = set()
            if comment.video_id not in self.video_comments:
                self.video_comments[comment.video_id] = []
            self.video_comments[comment.video_id].append(comment_id)

        for i in range(5):
            parent_id = f'c{i*3+1}'
            parent = self.comments.get(parent_id)
            if parent:
                for j in range(2):
                    reply_id = f'cr{i}_{j}'
                    reply = Comment(
                        id=reply_id,
                        video_id=parent.video_id,
                        user_id=f'u{(j + 1) % 6 + 1}',
                        content=f'回复{i} - {j}',
                        likes_count=int((i + j) * 5),
                        reply_count=0,
                        parent_id=parent.id,
                        root_id=parent.id,
                        created_at=now - 3600000 * (i + j + 1),
                        is_deleted=False,
                    )
                    self.comments[reply_id] = reply
                    self.comment_likes[reply_id] = set()
                    if parent.video_id not in self.video_comments:
                        self.video_comments[parent.video_id] = []
                    self.video_comments[parent.video_id].append(reply_id)
                    parent.reply_count += 1

        for vid in ['v1', 'v2', 'v3', 'v4', 'v5']:
            self.danmakus[vid] = []
            for i in range(10):
                dm = Danmaku(
                    id=f'dm_{vid}_{i}',
                    video_id=vid,
                    user_id=f'u{(i % 6) + 1}',
                    content=f'弹幕{i+1} - 666',
                    timestamp=float(i * 5 + 1),
                    color='#ffffff',
                    created_at=now - 3600000 * i,
                )
                self.danmakus[vid].append(dm)

        for uid in ['u1', 'u2', 'u3']:
            for i in range(2):
                did = f'd{uid}_{i+1}'
                history = []
                for v in range(2):
                    h = DraftHistory(
                        version=v + 1,
                        title=f'草稿{i+1} 第{v+1}版',
                        description=f'草稿描述 v{v+1}',
                        cover_url=f'https://picsum.photos/seed/draft{uid}{i}{v}/720/1280',
                        video_url=f'https://example.com/drafts/{did}_v{v}.mp4',
                        duration=30 + i * 10 + v * 5,
                        topics=['t1'] if i == 0 else ['t2'],
                        updated_at=now - 86400000 * (v + 1),
                    )
                    history.append(h)
                draft = Draft(
                    id=did,
                    user_id=uid,
                    title=f'我的草稿{i+1}',
                    description='这是一个草稿的描述',
                    cover_url=f'https://picsum.photos/seed/draft{uid}{i}/720/1280',
                    video_url=f'https://example.com/drafts/{did}.mp4',
                    duration=30 + i * 10,
                    topics=['t1', 't2'] if i == 0 else ['t3'],
                    updated_at=now - 3600000 * (i + 1),
                    history=history,
                )
                self.drafts[uid].append(draft)

        for i in range(3):
            tid = f'upload_u1_{i+1}'
            file_size = (i + 1) * 1024 * 1024 * 50
            chunk_size = 1024 * 1024 * 5
            total_chunks = math.ceil(file_size / chunk_size)
            chunks = []
            uploaded_n = int(total_chunks * (0.3 + i * 0.3))
            for j in range(total_chunks):
                c = UploadChunk(
                    chunk_index=j,
                    size=chunk_size if j < total_chunks - 1 else file_size - (total_chunks - 1) * chunk_size,
                    uploaded=j < uploaded_n,
                    failed=False,
                )
                chunks.append(c)
            status = UploadStatus.UPLOADING if i < 2 else UploadStatus.COMPLETED
            task = UploadTask(
                id=tid,
                user_id='u1',
                file_name=f'video_{i+1}.mp4',
                file_size=file_size,
                uploaded_size=sum(c.size for c in chunks if c.uploaded),
                status=status,
                video_url=f'https://example.com/uploads/{tid}.mp4' if status == UploadStatus.COMPLETED else None,
                chunk_size=chunk_size,
                total_chunks=total_chunks,
                chunks=chunks,
                created_at=now - 86400000 * i,
                updated_at=now - 3600000 * i,
            )
            self.upload_tasks[tid] = task

        mock_reports = [
            Report(id='r1', video_id='v5', user_id='u2', reason='色情低俗', description='视频内容低俗', status=ReportStatus.PENDING, created_at=now - 3600000 * 24),
            Report(id='r2', video_id='v8', user_id='u3', reason='抄袭搬运', description='抄袭他人作品', status=ReportStatus.PROCESSING, created_at=now - 3600000 * 12, handler_id='u_admin', handle_note='正在核实', handled_at=now - 3600000 * 6),
            Report(id='r3', video_id='v12', user_id='u1', reason='虚假信息', description='内容不实', status=ReportStatus.RESOLVED, created_at=now - 86400000 * 2, handler_id='u_admin', handle_note='已下架处理', handled_at=now - 86400000),
        ]
        for r in mock_reports:
            self.reports[r.id] = r

        mock_applies = [
            TopicApply(id='ta1', user_id='u1', name='美食教程', description='分享美食制作教程', status='pending', created_at=now - 3600000 * 10),
            TopicApply(id='ta2', user_id='u4', name='减脂餐', description='分享健康减脂餐食', status='approved', created_at=now - 86400000 * 3),
        ]
        for ta in mock_applies:
            self.topic_applies[ta.id] = ta

        notification_types = [
            (NotificationType.LIKE, '收到新点赞', '有人点赞了你的视频'),
            (NotificationType.COMMENT, '收到新评论', '有人评论了你的视频'),
            (NotificationType.FOLLOW, '收到新关注', '有人关注了你'),
            (NotificationType.SYSTEM, '系统通知', '你的账号已通过实名认证'),
            (NotificationType.AUDIT_PASS, '审核通知', '你的视频已通过审核'),
            (NotificationType.REPORT_PROGRESS, '举报反馈', '你举报的视频已处理'),
        ]
        for i, (n_type, title, content) in enumerate(notification_types):
            for j in range(2):
                self.add_notification(
                    'u1', n_type, title, content,
                    related_id=f'v{i+1}', related_type='video',
                    extra={'source': 'system'}
                )

        for i in range(1, 6):
            target_uid = f'u{i}'
            self.user_followings['u1'].add(target_uid)
            self.user_followers[target_uid].add('u1')

        for i in range(1, 11):
            self.user_likes['u1'].add(f'v{i}')
            self.user_collects['u1'].add(f'v{i*2}')

        for uid in ['u1', 'u2', 'u3']:
            for i in range(5):
                self.add_notification(
                    uid, NotificationType.LIKE, '收到新点赞',
                    f'用户点赞了你的作品',
                    related_id=f'v{i+1}', related_type='video'
                )
                self.add_notification(
                    uid, NotificationType.COMMENT, '收到新评论',
                    f'用户评论了你的作品',
                    related_id=f'v{i+1}', related_type='video'
                )
        self.add_notification(
            'u1', NotificationType.AUDIT_PASS, '审核结果通知',
            '你的视频"今天去吃了这家超火的火锅店，味道绝了！"已通过审核',
            related_id='v1', related_type='video'
        )
        self.add_notification(
            'u5', NotificationType.VIDEO_REMOVE, '审核结果通知',
            '你的视频因内容违规已被下架',
            related_id='v5', related_type='video'
        )

        for i in range(5):
            vid = f'v_review_{i+1}'
            video = Video(
                id=vid, user_id=f'u{(i % 6) + 1}',
                title=f'待审核视频{i+1}',
                description='等待审核的视频',
                cover_url=f'https://picsum.photos/seed/{vid}/720/1280',
                video_url=f'https://example.com/videos/{vid}.mp4',
                duration=30 + i * 10,
                likes_count=0, comments_count=0, shares_count=0,
                views_count=0, collects_count=0,
                topics=[f't{(i % 6) + 1}'],
                status=VideoStatus.REVIEWING,
                created_at=now - 3600000 * i,
                updated_at=now - 3600000 * i,
            )
            self.videos[vid] = video
            self.video_topics[vid] = [f't{(i % 6) + 1}']

        for i in range(3):
            vid = f'v_removed_{i+1}'
            video = Video(
                id=vid, user_id=f'u{(i % 6) + 1}',
                title=f'已下架视频{i+1}',
                description='违规已下架的视频',
                cover_url=f'https://picsum.photos/seed/{vid}/720/1280',
                video_url=f'https://example.com/videos/{vid}.mp4',
                duration=30 + i * 10,
                likes_count=100 + i * 50, comments_count=10 + i * 5,
                shares_count=5 + i * 2, views_count=1000 + i * 500,
                collects_count=20 + i * 10,
                topics=[f't{(i % 6) + 1}'],
                status=VideoStatus.REMOVED,
                created_at=now - 86400000 * (i + 5),
                updated_at=now - 86400000 * (i + 2),
            )
            self.videos[vid] = video
            self.video_topics[vid] = [f't{(i % 6) + 1}']

        for i in range(4):
            vid = f'v_rejected_{i+1}'
            reject_reasons = ['内容质量不达标', '标题存在夸大宣传', '封面涉嫌违规', '版权问题']
            video = Video(
                id=vid, user_id=f'u{(i % 6) + 1}',
                title=f'被驳回视频{i+1}',
                description='审核未通过的视频',
                cover_url=f'https://picsum.photos/seed/{vid}/720/1280',
                video_url=f'https://example.com/videos/{vid}.mp4',
                duration=25 + i * 8,
                likes_count=0, comments_count=0, shares_count=0,
                views_count=0, collects_count=0,
                topics=[f't{(i % 6) + 1}'],
                status=VideoStatus.REJECTED,
                reject_reason=reject_reasons[i],
                created_at=now - 86400000 * (i + 3),
                updated_at=now - 86400000 * (i + 1),
            )
            self.videos[vid] = video
            self.video_topics[vid] = [f't{(i % 6) + 1}']

        self.add_report_handle_record('r2', 'u_admin', 'processing', '正在核实举报内容')
        self.add_report_handle_record('r2', 'u_admin', 'processing', '已联系创作者核实')
        self.add_report_handle_record('r3', 'u_admin', 'resolve', '确认违规，已下架视频')

        for d in range(30):
            day = now - 86400000 * d
            date_str = time.strftime('%Y-%m-%d', time.localtime(day / 1000))
            stats = PlatformStatsDaily(
                date=date_str,
                video_publish_count=50 + int(20 * math.sin(d * 0.3)),
                video_audit_pass_count=45 + int(15 * math.sin(d * 0.3)),
                video_audit_reject_count=5 + int(3 * math.sin(d * 0.5)),
                report_count=20 + int(10 * math.sin(d * 0.4)),
                video_remove_count=3 + int(2 * math.sin(d * 0.6)),
                active_creators=1000 + int(200 * math.sin(d * 0.2)),
                interactions_count=50000 + int(10000 * math.sin(d * 0.25)),
                new_users=100 + int(50 * math.sin(d * 0.35)),
                earnings=round(5000 + 2000 * math.sin(d * 0.3) + 500 * math.cos(d * 0.2), 2),
            )
            self.platform_stats_daily.append(stats)

        more_notifications = [
            (NotificationType.REPLY, '收到新回复', '有人回复了你的评论'),
            (NotificationType.AUDIT_PASS, '审核通过', '你的视频已通过审核'),
            (NotificationType.AUDIT_REJECT, '审核未通过', '你的视频未通过审核'),
            (NotificationType.REPORT_PROGRESS, '举报进度', '你举报的视频有新的处理进展'),
            (NotificationType.VIDEO_REMOVE, '视频下架通知', '你的视频因违规已被下架'),
            (NotificationType.VIDEO_RESTORE, '视频恢复通知', '你的视频已恢复上架'),
            (NotificationType.TOPIC_APPLY, '话题申请结果', '你申请的话题有审核结果'),
        ]
        for i, (n_type, title, content) in enumerate(more_notifications):
            self.add_notification('u1', n_type, title, content,
                                  related_id=f'v{i+10}', related_type='video')


db = Database()
