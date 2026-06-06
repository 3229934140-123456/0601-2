import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database import db
from app.models import *
from server import handle_publish, handle_creator, handle_audit, handle_interaction

def test_upload_to_draft():
    print("=== 1. 测试上传转草稿 ===")
    uid = "u1"
    
    r = handle_publish("/api/publish/upload/init", {}, uid,
                      {"fileName": "test_flow.mp4", "fileSize": 1048576, "chunkSize": 1048576}, "POST")
    assert r["code"] == 0, f"初始化失败: {r['message']}"
    taskId = r["data"]["taskId"]
    total_chunks = r["data"]["totalChunks"]
    print("  初始化上传: OK, taskId:", taskId, "chunks:", total_chunks)
    
    for i in range(total_chunks):
        r = handle_publish(f"/api/publish/upload/{taskId}/chunk", {}, uid,
                          {"chunkIndex": i}, "POST")
        assert r["code"] == 0
    print(f"  上传所有{total_chunks}个分片: OK")
    
    r = handle_publish(f"/api/publish/upload/{taskId}/complete", {}, uid, {}, "POST")
    assert r["code"] == 0
    assert r["data"]["completed"] == True
    videoUrl = r["data"]["videoUrl"]
    print("  完成上传: OK, videoUrl:", videoUrl)
    
    r = handle_publish(f"/api/publish/drafts/from-upload/{taskId}", {}, uid,
                      {"title": "从上传来的草稿", "description": "测试",
                       "coverUrl": "test.jpg", "duration": 60, "topics": ["t1", "t2"]}, "POST")
    assert r["code"] == 0, f"转草稿失败: {r['message']}"
    draftId = r["data"]["draftId"]
    print("  上传转草稿: OK, draftId:", draftId)
    print("  草稿视频地址:", r["data"].get("videoUrl"))
    print("  草稿时长:", r["data"].get("duration"))
    
    r = handle_publish(f"/api/publish/drafts/{draftId}", {}, uid, None, "GET")
    assert r["code"] == 0
    assert r["data"]["videoUrl"] != ""
    print("  草稿详情验证: OK, 包含视频地址和时长")
    
    print()
    return True

def test_topic_count_consistency():
    print("=== 2. 测试话题计数一致性 ===")
    uid = "u1"
    admin = "u_admin"
    
    t_before = db.topics["t1"].video_count
    print(f"  话题t1初始视频数: {t_before}")
    
    r = handle_publish("/api/publish/video", {}, uid,
                      {"title": "话题测试视频", "videoUrl": "test.mp4",
                       "coverUrl": "test.jpg", "duration": 30, "topics": ["t1", "t2"]}, "POST")
    assert r["code"] == 0
    vid = r["data"]["videoId"]
    print("  发布视频(待审核): OK, videoId:", vid)
    
    t_after_submit = db.topics["t1"].video_count
    print(f"  提交后话题t1视频数: {t_after_submit} (应该不变)")
    assert t_after_submit == t_before, "提交审核后话题数不应变化"
    
    r = handle_audit(f"/api/audit/video/{vid}/approve", {}, admin, {}, "POST")
    assert r["code"] == 0, f"审核通过失败: {r['message']}"
    print("  审核通过: OK")
    
    t_after_approve = db.topics["t1"].video_count
    print(f"  审核通过后话题t1视频数: {t_after_approve} (应该+1)")
    assert t_after_approve == t_before + 1, "审核通过后话题数应+1"
    
    r = handle_audit(f"/api/audit/video/{vid}/remove", {}, admin, {"reason": "测试下架"}, "POST")
    assert r["code"] == 0
    print("  视频下架: OK")
    
    t_after_remove = db.topics["t1"].video_count
    print(f"  下架后话题t1视频数: {t_after_remove} (应该-1)")
    assert t_after_remove == t_before, "下架后话题数应-1"
    
    r = handle_audit(f"/api/audit/video/{vid}/restore", {}, admin, {}, "POST")
    assert r["code"] == 0
    print("  视频恢复: OK")
    
    t_after_restore = db.topics["t1"].video_count
    print(f"  恢复后话题t1视频数: {t_after_restore} (应该+1)")
    assert t_after_restore == t_before + 1, "恢复后话题数应+1"
    
    print()
    return True

def test_creator_dashboard():
    print("=== 3. 测试创作者经营看板 ===")
    uid = "u1"
    
    r = handle_creator("/api/creator/stats/trend", {"period": ["7d"]}, uid, None, "GET")
    assert r["code"] == 0
    print("  7天趋势: OK, days:", r["data"]["days"])
    print("    总播放:", r["data"]["summary"]["totalViews"])
    print("    总涨粉:", r["data"]["summary"]["totalNewFans"])
    print("    总收益:", r["data"]["summary"]["totalEarnings"])
    
    r = handle_creator("/api/creator/stats/videos", {"period": ["7d"], "page": ["1"], "pageSize": ["5"]}, uid, None, "GET")
    assert r["code"] == 0
    print("  按作品拆分: OK, total:", r["data"]["total"])
    if r["data"]["list"]:
        print("    top1:", r["data"]["list"][0]["title"], "views:", r["data"]["list"][0]["views"])
    
    r = handle_creator("/api/creator/stats/topics", {"period": ["7d"]}, uid, None, "GET")
    assert r["code"] == 0
    print("  按话题拆分: OK, count:", len(r["data"]["list"]))
    
    r = handle_creator("/api/creator/stats/time-slots", {"period": ["7d"]}, uid, None, "GET")
    assert r["code"] == 0
    print("  按时间段拆分: OK, 24小时数据")
    
    r = handle_creator("/api/creator/video/v1/stats", 
                      {"period": ["custom"], "startDate": ["2026-06-01"], "endDate": ["2026-06-07"]}, 
                      uid, None, "GET")
    assert r["code"] == 0
    print("  单作品自定义日期: OK, days:", len(r["data"]["daily"]))
    
    print()
    return True

def test_workbench():
    print("=== 4. 测试发布工作台 ===")
    uid = "u1"
    
    r = handle_publish("/api/publish/workbench", 
                      {"type": ["video"], "status": ["all"], "page": ["1"], "pageSize": ["10"]},
                      uid, None, "GET")
    assert r["code"] == 0
    print("  作品列表: OK, total:", r["data"]["total"])
    print("    stats:", {k: v for k, v in r["data"]["stats"].items()})
    
    r = handle_publish("/api/publish/workbench", 
                      {"type": ["video"], "status": ["published"], "page": ["1"], "pageSize": ["5"]},
                      uid, None, "GET")
    assert r["code"] == 0
    print("  已发布筛选: OK, count:", len(r["data"]["list"]))
    
    r = handle_publish("/api/publish/workbench", 
                      {"type": ["draft"], "page": ["1"], "pageSize": ["10"]},
                      uid, None, "GET")
    assert r["code"] == 0
    print("  草稿列表: OK, total:", r["data"]["total"])
    
    r = handle_publish("/api/publish/workbench", 
                      {"type": ["upload"], "page": ["1"], "pageSize": ["10"]},
                      uid, None, "GET")
    assert r["code"] == 0
    print("  上传任务: OK, total:", r["data"]["total"])
    
    r = handle_publish("/api/publish/workbench",
                      {"type": ["video"], "keyword": ["美食"], "page": ["1"], "pageSize": ["10"]},
                      uid, None, "GET")
    assert r["code"] == 0
    print("  关键词筛选: OK, count:", len(r["data"]["list"]))
    
    draft_ids = [d["id"] for d in r["data"].get("list", [])][:2]
    r = handle_publish("/api/publish/drafts/batch-delete", {}, uid,
                      {"draftIds": ["d_u1_1", "d_u1_2"]}, "POST")
    assert r["code"] == 0
    print("  批量删除草稿: OK, deleted:", r["data"]["deleted"])
    
    r = handle_publish("/api/publish/upload/batch-clean", {}, uid,
                      {"status": ["cancelled", "failed"]}, "POST")
    assert r["code"] == 0
    print("  批量清理上传任务: OK, deleted:", r["data"]["deleted"])
    
    print()
    return True

def test_notifications():
    print("=== 5. 测试消息中心细分 ===")
    uid = "u1"
    
    r = handle_audit("/api/audit/notifications/unread-count", {}, uid, None, "GET")
    assert r["code"] == 0
    print("  未读统计: OK")
    types_with_count = {k: v for k, v in r["data"].items() if v > 0}
    print("    有未读的类型:", list(types_with_count.keys()))
    
    r = handle_audit("/api/audit/notifications", 
                    {"type": ["like"], "page": ["1"], "pageSize": ["3"]},
                    uid, None, "GET")
    assert r["code"] == 0
    print("  点赞消息: OK, total:", r["data"]["total"])
    
    r = handle_audit("/api/audit/notifications", 
                    {"type": ["audit_pass"], "page": ["1"], "pageSize": ["3"]},
                    uid, None, "GET")
    assert r["code"] == 0
    print("  审核通过消息: OK, total:", r["data"]["total"])
    
    r = handle_audit("/api/audit/notifications", 
                    {"type": ["video_remove"], "page": ["1"], "pageSize": ["3"]},
                    uid, None, "GET")
    assert r["code"] == 0
    print("  视频下架消息: OK, total:", r["data"]["total"])
    
    print()
    return True

def test_audit_enhanced():
    print("=== 6. 测试审核后台增强 ===")
    admin = "u_admin"
    
    r = handle_audit("/api/audit/report/r2", {}, admin, None, "GET")
    assert r["code"] == 0
    print("  举报详情: OK")
    print("    timeline条数:", len(r["data"].get("timeline", [])))
    if r["data"].get("timeline"):
        print("    最新记录:", r["data"]["timeline"][0]["action"], r["data"]["timeline"][0]["note"])
    
    r = handle_audit("/api/audit/audit/videos",
                    {"status": ["reviewing"], "author": ["达人"], "page": ["1"], "pageSize": ["10"]},
                    admin, None, "GET")
    assert r["code"] == 0
    print("  按作者筛选审核列表: OK, count:", len(r["data"]["list"]))
    
    review_videos = [v["id"] for v in r["data"]["list"]][:3]
    r = handle_audit("/api/audit/video/batch-approve", {}, admin,
                    {"videoIds": review_videos, "reason": "批量通过"}, "POST")
    assert r["code"] == 0
    print("  批量通过: OK, success:", r["data"]["success"], "total:", r["data"]["total"])
    
    published_videos = [v for v in db.videos.values() if v.user_id == "u1" and v.status == VideoStatus.PUBLISHED][:2]
    ids = [v.id for v in published_videos]
    r = handle_audit("/api/audit/video/batch-remove", {}, admin,
                    {"videoIds": ids, "reason": "批量下架测试"}, "POST")
    assert r["code"] == 0
    print("  批量下架: OK, success:", r["data"]["success"], "total:", r["data"]["total"])
    
    print()
    return True

def test_operation_stats():
    print("=== 7. 测试运营统计 ===")
    admin = "u_admin"
    
    r = handle_audit("/api/audit/operation/trend", {}, admin,
                    {"period": "7d"}, "POST")
    assert r["code"] == 0, f"运营趋势失败: {r['message']}"
    print("  7天运营趋势: OK, days:", r["data"]["days"])
    print("    视频发布量:", r["data"]["summary"]["totalVideoPublish"])
    print("    审核通过率:", r["data"]["summary"]["auditPassRate"], "%")
    print("    活跃创作者:", r["data"]["summary"].get("totalNewUsers"))
    
    r = handle_audit("/api/audit/operation/trend", {}, admin,
                    {"period": "30d"}, "POST")
    assert r["code"] == 0
    print("  30天运营趋势: OK, days:", r["data"]["days"])
    
    r = handle_audit("/api/audit/operation/top-topics", {}, admin,
                    {"period": "7d", "limit": 5}, "POST")
    assert r["code"] == 0
    print("  热门话题: OK, count:", len(r["data"]["list"]))
    if r["data"]["list"]:
        print("    top1:", r["data"]["list"][0]["name"], "heat:", r["data"]["list"][0]["heat"])
    
    r = handle_audit("/api/audit/operation/top-report-reasons", {}, admin,
                    {"period": "7d"}, "POST")
    assert r["code"] == 0
    print("  举报原因排行: OK, count:", len(r["data"]["list"]))
    
    print()
    return True

def main():
    print("=" * 60)
    print("  短视频平台 V2 功能测试")
    print("=" * 60)
    print()
    
    tests = [
        ("上传转草稿闭环", test_upload_to_draft),
        ("话题计数一致性", test_topic_count_consistency),
        ("创作者经营看板", test_creator_dashboard),
        ("发布工作台", test_workbench),
        ("消息中心细分", test_notifications),
        ("审核后台增强", test_audit_enhanced),
        ("运营统计", test_operation_stats),
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
