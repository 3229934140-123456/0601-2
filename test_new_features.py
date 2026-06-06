import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database import db
from app.models import *
from server import handle_publish, handle_creator, handle_audit, handle_interaction

def test_upload_flow():
    print("=== 1. 测试上传流程 ===")
    uid = "u1"
    
    # 初始化上传
    r = handle_publish("/api/publish/upload/init", {}, uid, 
                      {"fileName": "test.mp4", "fileSize": 15728640}, "POST")
    print("初始化上传:", r["code"], r["message"])
    if r["code"] != 0:
        return False
    taskId = r["data"]["taskId"]
    print("  taskId:", taskId)
    print("  uploadUrl:", r["data"]["uploadUrl"])
    print("  status:", r["data"]["status"])
    print("  totalChunks:", r["data"]["totalChunks"])
    
    # 上传分片
    r = handle_publish(f"/api/publish/upload/{taskId}/chunk", {}, uid,
                      {"chunkIndex": 0}, "POST")
    print("上传分片0:", r["code"], "progress:", r["data"].get("progress"))
    
    r = handle_publish(f"/api/publish/upload/{taskId}/chunk", {}, uid,
                      {"chunkIndex": 1}, "POST")
    print("上传分片1:", r["code"], "progress:", r["data"].get("progress"))
    
    # 查询状态
    r = handle_publish(f"/api/publish/upload/{taskId}/status", {}, uid, None, "GET")
    print("查询状态:", r["code"], "status:", r["data"]["status"], "progress:", r["data"]["progress"])
    
    # 标记失败分片
    r = handle_publish(f"/api/publish/upload/{taskId}/chunk/retry", {}, uid,
                      {"chunkIndex": 1}, "POST")
    print("标记分片失败:", r["code"])
    
    # 取消上传
    r = handle_publish(f"/api/publish/upload/{taskId}/cancel", {}, uid, {}, "POST")
    print("取消上传:", r["code"], "status:", r["data"]["status"])
    
    print()
    return True

def test_publish_validation():
    print("=== 2. 测试发布字段校验 ===")
    uid = "u1"
    
    # 标题为空
    r = handle_publish("/api/publish/video", {}, uid,
                      {"title": "", "videoUrl": "test.mp4", "coverUrl": "test.jpg", "duration": 30}, "POST")
    print("空标题:", r["code"], r["message"])
    
    # 视频地址为空
    r = handle_publish("/api/publish/video", {}, uid,
                      {"title": "测试", "videoUrl": "", "coverUrl": "test.jpg", "duration": 30}, "POST")
    print("空视频地址:", r["code"], r["message"])
    
    # 封面为空
    r = handle_publish("/api/publish/video", {}, uid,
                      {"title": "测试", "videoUrl": "test.mp4", "coverUrl": "", "duration": 30}, "POST")
    print("空封面:", r["code"], r["message"])
    
    # 时长无效
    r = handle_publish("/api/publish/video", {}, uid,
                      {"title": "测试", "videoUrl": "test.mp4", "coverUrl": "test.jpg", "duration": 0}, "POST")
    print("无效时长:", r["code"], r["message"])
    
    # 正常发布
    r = handle_publish("/api/publish/video", {}, uid,
                      {"title": "测试视频", "videoUrl": "https://example.com/test.mp4", 
                       "coverUrl": "https://example.com/cover.jpg", "duration": 60,
                       "topics": ["t1", "t2"], "description": "测试描述"}, "POST")
    print("正常发布:", r["code"], r["message"], "videoId:", r["data"].get("videoId"))
    
    print()
    return True

def test_drafts():
    print("=== 3. 测试草稿能力 ===")
    uid = "u1"
    
    # 草稿列表
    r = handle_publish("/api/publish/drafts", {"page": ["1"], "pageSize": ["10"]}, uid, None, "GET")
    print("草稿列表:", r["code"], "total:", r["data"]["total"])
    
    # 新建草稿
    r = handle_publish("/api/publish/drafts/save", {}, uid,
                      {"title": "新草稿", "description": "测试", "coverUrl": "test.jpg",
                       "videoUrl": "test.mp4", "duration": 30, "topics": ["t1"]}, "POST")
    print("新建草稿:", r["code"], "draftId:", r["data"].get("draftId"))
    draftId = r["data"]["draftId"]
    
    # 更新草稿（应该产生历史版本）
    r = handle_publish("/api/publish/drafts/save", {}, uid,
                      {"draftId": draftId, "title": "新草稿 v2", "description": "测试 v2", 
                       "coverUrl": "test2.jpg", "videoUrl": "test2.mp4", "duration": 45, "topics": ["t1", "t2"]}, "POST")
    print("更新草稿:", r["code"], "historyCount:", r["data"].get("historyCount"))
    
    # 草稿详情（含历史版本）
    r = handle_publish(f"/api/publish/drafts/{draftId}", {}, uid, None, "GET")
    print("草稿详情:", r["code"], "历史版本数:", len(r["data"].get("history", [])))
    
    # 恢复历史版本
    if r["data"].get("history"):
        v = r["data"]["history"][-1]["version"]
        r = handle_publish(f"/api/publish/drafts/{draftId}/restore", {}, uid,
                          {"version": v}, "POST")
        print("恢复版本:", r["code"])
    
    # 从视频保存为草稿
    r = handle_publish("/api/publish/drafts/from-video/v1", {}, uid, {}, "POST")
    print("从视频存草稿:", r["code"])
    
    print()
    return True

def test_topics():
    print("=== 4. 测试话题管理 ===")
    uid = "u1"
    
    # 话题推荐（按热度）
    r = handle_publish("/api/publish/topics/suggest", {"sort": ["heat"]}, uid, None, "GET")
    print("话题推荐(热度):", r["code"], "count:", len(r["data"]["list"]))
    if r["data"]["list"]:
        print("  top1:", r["data"]["list"][0]["name"], "heat:", r["data"]["list"][0]["heat"])
    
    # 按视频数排序
    r = handle_publish("/api/publish/topics/suggest", {"sort": ["videoCount"]}, uid, None, "GET")
    print("话题推荐(视频数):", r["code"])
    if r["data"]["list"]:
        print("  top1:", r["data"]["list"][0]["name"], "videoCount:", r["data"]["list"][0]["videoCount"])
    
    # 关键词搜索
    r = handle_publish("/api/publish/topics/suggest", {"keyword": ["美食"]}, uid, None, "GET")
    print("关键词搜索(美食):", r["code"], "count:", len(r["data"]["list"]))
    
    # 申请新话题
    r = handle_publish("/api/publish/topics/apply", {}, uid,
                      {"name": "测试话题" + str(hash(uid))[:4], "description": "测试描述"}, "POST")
    print("申请新话题:", r["code"], r["message"])
    
    print()
    return True

def test_comments():
    print("=== 5. 测试评论互动 ===")
    uid = "u1"
    
    # 评论列表
    r = handle_interaction("/api/interaction/video/v1/comments", {"page": ["1"], "pageSize": ["5"]}, uid, None, "GET")
    print("评论列表:", r["code"], "total:", r["data"]["total"])
    
    # 评论点赞
    r = handle_interaction("/api/interaction/comments/c1/like", {}, uid, {}, "POST")
    print("点赞评论c1:", r["code"], "isLiked:", r["data"]["isLiked"], "likesCount:", r["data"]["likesCount"])
    
    # 二级回复列表
    r = handle_interaction("/api/interaction/comments/c1/replies", {"page": ["1"], "pageSize": ["10"]}, uid, None, "GET")
    print("二级回复列表:", r["code"], "total:", r["data"]["total"])
    
    # 删除自己的评论
    # 先发一条评论
    r = handle_interaction("/api/interaction/video/v1/comments", {}, uid, {"content": "测试删除"}, "POST")
    if r["code"] == 0:
        cid = r["data"]["id"]
        r = handle_interaction(f"/api/interaction/comments/{cid}", {}, uid, None, "DELETE")
        print("删除评论:", r["code"], r["message"])
    
    print()
    return True

def test_notifications():
    print("=== 6. 测试消息通知 ===")
    uid = "u1"
    
    # 消息列表
    r = handle_audit("/api/audit/notifications", {"page": ["1"], "pageSize": ["5"], "type": ["all"]}, uid, None, "GET")
    print("消息列表:", r["code"], "total:", r["data"]["total"], "unreadCount:", r["data"]["unreadCount"])
    
    # 按类型筛选
    r = handle_audit("/api/audit/notifications", {"page": ["1"], "pageSize": ["5"], "type": ["like"]}, uid, None, "GET")
    print("点赞消息:", r["code"], "total:", r["data"]["total"])
    
    r = handle_audit("/api/audit/notifications", {"page": ["1"], "pageSize": ["5"], "type": ["audit"]}, uid, None, "GET")
    print("审核消息:", r["code"], "total:", r["data"]["total"])
    
    # 未读数
    r = handle_audit("/api/audit/notifications/unread-count", {}, uid, None, "GET")
    print("未读数统计:", r["code"], "total:", r["data"]["total"])
    
    # 全部已读
    r = handle_audit("/api/audit/notifications/read", {}, uid, {}, "POST")
    print("全部已读:", r["code"], r["message"])
    
    # 再次查未读数
    r = handle_audit("/api/audit/notifications/unread-count", {}, uid, None, "GET")
    print("已读后未读数:", r["code"], "total:", r["data"]["total"])
    
    print()
    return True

def test_creator_stats():
    print("=== 7. 测试创作者数据 ===")
    uid = "u1"
    
    # 7天趋势
    r = handle_creator("/api/creator/stats/trend", {"period": ["7d"]}, uid, None, "GET")
    print("7天趋势:", r["code"], "days:", r["data"]["days"])
    print("  totalViews:", r["data"]["summary"]["totalViews"])
    print("  totalLikes:", r["data"]["summary"]["totalLikes"])
    print("  totalNewFans:", r["data"]["summary"]["totalNewFans"])
    print("  totalEarnings:", r["data"]["summary"]["totalEarnings"])
    
    # 30天趋势
    r = handle_creator("/api/creator/stats/trend", {"period": ["30d"]}, uid, None, "GET")
    print("30天趋势:", r["code"], "days:", r["data"]["days"])
    
    # 单作品统计
    r = handle_creator("/api/creator/video/v1/stats", {"period": ["7d"]}, uid, None, "GET")
    print("单作品统计(v1,7天):", r["code"])
    if r["code"] == 0:
        print("  totalViews:", r["data"]["total"]["views"])
    
    print()
    return True

def test_audit():
    print("=== 8. 测试审核流程 ===")
    uid = "u_admin"
    
    # 举报列表
    r = handle_audit("/api/audit/report/list", {"page": ["1"], "pageSize": ["10"], "status": ["all"]}, uid, None, "GET")
    print("举报列表:", r["code"], "total:", r["data"]["total"])
    
    # 按状态筛选
    r = handle_audit("/api/audit/report/list", {"page": ["1"], "pageSize": ["10"], "status": ["pending"]}, uid, None, "GET")
    print("待处理举报:", r["code"], "total:", r["data"]["total"])
    
    # 举报详情
    r = handle_audit("/api/audit/report/r1", {}, uid, None, "GET")
    print("举报详情r1:", r["code"], "status:", r["data"]["status"])
    
    # 处理举报（加备注）
    r = handle_audit("/api/audit/report/r1/process", {}, uid,
                    {"action": "processing", "note": "正在核实内容"}, "POST")
    print("处理举报:", r["code"], "status:", r["data"]["status"])
    
    # 视频下架
    r = handle_audit("/api/audit/video/v10/remove", {}, uid, {"reason": "内容违规"}, "POST")
    print("视频下架:", r["code"], "status:", r["data"]["status"])
    
    # 视频恢复
    r = handle_audit("/api/audit/video/v10/restore", {}, uid, {}, "POST")
    print("视频恢复:", r["code"], "status:", r["data"]["status"])
    
    # 审核视频列表
    r = handle_audit("/api/audit/audit/videos", {"page": ["1"], "pageSize": ["10"], "status": ["reviewing"]}, uid, None, "GET")
    print("待审核视频:", r["code"], "total:", r["data"]["total"])
    
    # 话题申请列表
    r = handle_audit("/api/audit/topic/approvals", {}, uid,
                    {"page": 1, "pageSize": 10, "status": "pending"}, "POST")
    print("话题申请列表:", r["code"], "total:", r["data"]["total"])
    
    print()
    return True

def main():
    print("=" * 60)
    print("  短视频平台新功能测试")
    print("=" * 60)
    print()
    
    tests = [
        ("上传流程", test_upload_flow),
        ("发布校验", test_publish_validation),
        ("草稿能力", test_drafts),
        ("话题管理", test_topics),
        ("评论互动", test_comments),
        ("消息通知", test_notifications),
        ("创作者数据", test_creator_stats),
        ("审核流程", test_audit),
    ]
    
    passed = 0
    total = len(tests)
    
    for name, fn in tests:
        try:
            if fn():
                passed += 1
                print("[PASS] " + name)
            else:
                print("[FAIL] " + name)
        except Exception as e:
            print("[FAIL] " + name + ": " + str(e))
            import traceback
            traceback.print_exc()
        print()
    
    print("=" * 60)
    print(f"  结果: {passed}/{total} 通过")
    print("=" * 60)
    
    return 0 if passed == total else 1

if __name__ == "__main__":
    sys.exit(main())
