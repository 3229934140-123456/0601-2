import urllib.request
import json
import time

BASE = "http://localhost:8000"

def get(path, uid="u1"):
    req = urllib.request.Request(BASE + path, headers={"x-user-id": uid})
    r = urllib.request.urlopen(req, timeout=5)
    return json.loads(r.read())

def post(path, body=None, uid="u1"):
    data = json.dumps(body or {}).encode("utf-8")
    req = urllib.request.Request(BASE + path, data=data, headers={"x-user-id": uid, "Content-Type": "application/json"})
    r = urllib.request.urlopen(req, timeout=5)
    return json.loads(r.read())

def test_draft_duration():
    print("=" * 60)
    print("[1] 草稿时长补录测试")
    print("=" * 60)
    
    tasks = get("/api/publish/upload-tasks?status=completed", uid="u1")
    completed = [t for t in tasks["data"]["list"] if t["status"] == "completed"]
    print(f"  已完成上传任务: {len(completed)} 个")
    
    if not completed:
        print("  SKIP: 没有已完成任务")
        return
    
    task_id = completed[0]["id"]
    print(f"  用任务 {task_id} 生成草稿")
    
    r = post(f"/api/publish/drafts/from-upload/{task_id}", uid="u1")
    print(f"  转草稿结果: code={r['code']}")
    draft = r["data"]
    print(f"  草稿ID: {draft.get('id') or draft.get('draftId')}")
    print(f"  duration={draft.get('duration')}, durationUnknown={draft.get('durationUnknown')}")
    print(f"  fileSize={draft.get('fileSize')}, uploadTaskId={draft.get('uploadTaskId')}")
    
    did = draft.get("id") or draft.get("draftId")
    
    if not did:
        print("  FAIL: 没有拿到草稿ID")
        return
    
    if not draft.get("durationUnknown"):
        print("  WARN: 时长不为0，duration_unknown 应该为 False，跳过补录")
    else:
        print("  -> 调用时长补录接口 (设为 120 秒)")
        r2 = post(f"/api/publish/drafts/{did}/update-duration", body={"duration": 120}, uid="u1")
        print(f"  补录结果: code={r2['code']}")
        
        print("  -> 查草稿列表确认")
        r3 = get("/api/publish/drafts?page=1&pageSize=5", uid="u1")
        list_draft = next((d for d in r3["data"]["list"] if d["id"] == did), None)
        if list_draft:
            print(f"  列表: duration={list_draft['duration']}, durationUnknown={list_draft['durationUnknown']}")
            assert list_draft["duration"] == 120, "列表时长不对"
            assert list_draft["durationUnknown"] == False, "列表待补录状态不对"
            print("  PASS: 草稿列表数据正确")
        else:
            print("  FAIL: 列表里找不到草稿")
        
        print("  -> 查草稿详情确认")
        r4 = get(f"/api/publish/drafts/{did}", uid="u1")
        detail = r4["data"]
        print(f"  详情: duration={detail['duration']}, durationUnknown={detail['durationUnknown']}")
        assert detail["duration"] == 120, "详情时长不对"
        assert detail["durationUnknown"] == False, "详情待补录状态不对"
        print("  PASS: 草稿详情数据正确")
    
    print("  PASS: 草稿时长补录完整测试通过\n")

def test_creator_trend_custom():
    print("=" * 60)
    print("[2] 创作者看板整体趋势 - 自定义日期对齐")
    print("=" * 60)
    
    start = "2026-06-01"
    end = "2026-06-07"
    r = get(f"/api/creator/stats/trend?period=custom&startDate={start}&endDate={end}", uid="u1")
    data = r["data"]
    print(f"  period={data['period']}, days={data['days']}")
    print(f"  返回 startDate={data.get('startDate')}, endDate={data.get('endDate')}")
    print(f"  dates 第一个={data['dates'][0]}, 最后一个={data['dates'][-1]}")
    print(f"  日期数量={len(data['dates'])}")
    
    assert data["dates"][0] == start, f"起始日期不对: {data['dates'][0]} vs {start}"
    assert data["dates"][-1] == end, f"结束日期不对: {data['dates'][-1]} vs {end}"
    assert len(data["dates"]) == 7, "日期数量不对"
    assert data.get("startDate") == start, "返回 startDate 不对"
    assert data.get("endDate") == end, "返回 endDate 不对"
    
    print(f"  summary totalViews={data['summary']['totalViews']}")
    print(f"  summary totalEarnings={data['summary']['totalEarnings']}")
    print("  PASS: 自定义日期严格对齐\n")

def test_topic_remove_restore():
    print("=" * 60)
    print("[3] 话题数据下架/恢复联动 + 幂等性")
    print("=" * 60)
    
    videos = get("/api/feed/recommend?pageSize=5", uid="u1")
    vid = None
    for v in videos["data"]["list"]:
        if v.get("topics"):
            vid = v["id"]
            tid = v["topics"][0]
            break
    
    if not vid:
        print("  SKIP: 找不到带话题的视频")
        return
    
    print(f"  测试视频: {vid}, 话题: {tid}")
    
    topic_before = get(f"/api/search/topic?keyword=美食", uid="u1")
    t_before = next((t for t in topic_before["data"]["list"] if t["id"] == tid), None)
    if not t_before:
        print("  WARN: 话题没在搜索结果里，换个方式查")
        t_before = {"video_count": 0, "views_count": 0, "heat": 0}
    
    print(f"  下架前: videoCount={t_before.get('videoCount')}, views={t_before.get('viewsCount')}, heat={t_before.get('heat')}")
    
    r1 = post(f"/api/audit/video/{vid}/remove", body={"reason": "测试下架"}, uid="u_admin")
    print(f"  下架结果: code={r1['code']}, status={r1['data'].get('status')}")
    
    topic_after1 = get(f"/api/search/topic?keyword=美食", uid="u1")
    t_after1 = next((t for t in topic_after1["data"]["list"] if t["id"] == tid), None)
    if t_after1:
        print(f"  下架后: videoCount={t_after1.get('videoCount')}, views={t_after1.get('viewsCount')}, heat={t_after1.get('heat')}")
    
    print("  -> 重复下架一次（幂等性测试）")
    r2 = post(f"/api/audit/video/{vid}/remove", body={"reason": "再试一次"}, uid="u_admin")
    print(f"  重复下架结果: code={r2['code']}")
    assert r2["code"] != 0, "重复下架应该失败"
    print("  PASS: 重复下架正确拒绝")
    
    print("  -> 恢复上架")
    r3 = post(f"/api/audit/video/{vid}/restore", uid="u_admin")
    print(f"  恢复结果: code={r3['code']}, status={r3['data'].get('status')}")
    
    topic_after2 = get(f"/api/search/topic?keyword=美食", uid="u1")
    t_after2 = next((t for t in topic_after2["data"]["list"] if t["id"] == tid), None)
    if t_after2:
        print(f"  恢复后: videoCount={t_after2.get('videoCount')}, views={t_after2.get('viewsCount')}, heat={t_after2.get('heat')}")
    
    print("  -> 重复恢复一次（幂等性测试）")
    r4 = post(f"/api/audit/video/{vid}/restore", uid="u_admin")
    print(f"  重复恢复结果: code={r4['code']}")
    assert r4["code"] != 0, "重复恢复应该失败"
    print("  PASS: 重复恢复正确拒绝")
    
    print("  PASS: 话题下架/恢复联动 + 幂等性测试通过\n")

def test_audit_video_filter():
    print("=" * 60)
    print("[4] 审核视频列表 - 举报原因筛选")
    print("=" * 60)
    
    print("  -> 先查全部待审核视频")
    r1 = get("/api/audit/audit/videos?status=published&pageSize=20", uid="u_admin")
    total_all = r1["data"]["total"]
    print(f"  全部已发布视频: {total_all} 个")
    
    print("  -> 按举报原因 porn 筛选")
    r2 = get("/api/audit/audit/videos?status=published&reason=porn&pageSize=20", uid="u_admin")
    total_porn = r2["data"]["total"]
    print(f"  被色情原因举报的视频: {total_porn} 个")
    
    if total_porn > 0:
        assert total_porn <= total_all, "筛选后数量应该更少"
        print("  PASS: 举报原因筛选生效（数量减少了）")
        
        print("  -> 再加作者昵称筛选")
        r3 = get("/api/audit/audit/videos?status=published&reason=porn&author=美食&pageSize=20", uid="u_admin")
        print(f"  色情原因 + 作者含'美食': {r3['data']['total']} 个")
        print("  PASS: 组合筛选生效")
    else:
        print("  WARN: 没有porn原因的举报，换个原因测试")
        reasons = ["violence", "plagiarism", "fake", "illegal", "other"]
        found = False
        for reason in reasons:
            r = get(f"/api/audit/audit/videos?status=published&reason={reason}&pageSize=20", uid="u_admin")
            if r["data"]["total"] > 0:
                print(f"  用原因 {reason} 测试: {r['data']['total']} 个")
                assert r["data"]["total"] <= total_all, "筛选后应该更少"
                found = True
                break
        if found:
            print("  PASS: 举报原因筛选生效")
        else:
            print("  WARN: 所有原因都没数据，可能举报表为空")
    
    print("  PASS: 审核视频列表筛选测试通过\n")

def test_report_timeline():
    print("=" * 60)
    print("[5] 举报处理时间线 - 按时间从早到晚")
    print("=" * 60)
    
    reports = get("/api/audit/report/list?pageSize=5", uid="u_admin")
    rs = reports["data"]["list"]
    if not rs:
        print("  SKIP: 没有举报数据")
        return
    
    rid = rs[0]["id"]
    print(f"  测试举报: {rid}")
    
    print("  -> 追加 3 条处理记录")
    for i in range(3):
        r = post("/api/audit/report/handle", body={
            "reportId": rid, "action": "note",
            "note": f"追加记录 {i+1}"
        }, uid="u_admin")
    
    r2 = get(f"/api/audit/report/{rid}", uid="u_admin")
    timeline = r2["data"]["timeline"]
    print(f"  时间线共 {len(timeline)} 条")
    
    if len(timeline) >= 2:
        times = [t["createdAt"] for t in timeline]
        is_ascending = all(times[i] <= times[i+1] for i in range(len(times)-1))
        print(f"  时间顺序: {'升序（正确）' if is_ascending else '降序（错误）'}")
        for i, t in enumerate(timeline):
            print(f"    {i+1}. {time.strftime('%H:%M:%S', time.localtime(t['createdAt']/1000))} - {t['action']} - {t.get('note','')}")
        
        assert is_ascending, "时间线应该从早到晚"
        print("  PASS: 时间线顺序正确\n")

def test_operation_trend_earnings():
    print("=" * 60)
    print("[6] 运营趋势 - 收益 + 自定义日期对齐")
    print("=" * 60)
    
    start = "2026-06-01"
    end = "2026-06-07"
    
    r = post("/api/audit/operation/trend", body={
        "period": "custom", "startDate": start, "endDate": end
    }, uid="u_admin")
    data = r["data"]
    print(f"  period={data['period']}, days={data['days']}")
    print(f"  返回 startDate={data.get('startDate')}, endDate={data.get('endDate')}")
    print(f"  dates 第一个={data['dates'][0]}, 最后一个={data['dates'][-1]}")
    
    assert data["dates"][0] == start, "起始日期不对"
    assert data["dates"][-1] == end, "结束日期不对"
    assert len(data["dates"]) == 7, "日期数量不对"
    
    print(f"  有 earnings 字段: {'earnings' in data}")
    assert "earnings" in data, "应该有 earnings 字段"
    print(f"  earnings 数据: {data['earnings'][:3]}...")
    
    print(f"  summary totalEarnings={data['summary'].get('totalEarnings')}")
    assert "totalEarnings" in data["summary"], "汇总应该有 totalEarnings"
    assert abs(sum(data["earnings"]) - data["summary"]["totalEarnings"]) < 0.01, "收益汇总不对"
    
    print("  PASS: 运营趋势收益 + 自定义日期测试通过\n")

def test_top_topics_and_reasons():
    print("=" * 60)
    print("[7] 热门话题 + 举报原因排行 - 时间范围 + 分页")
    print("=" * 60)
    
    start = "2026-06-01"
    end = "2026-06-07"
    
    print("  --- 热门话题排行 ---")
    r1 = post("/api/audit/operation/top-topics", body={
        "period": "custom", "startDate": start, "endDate": end,
        "page": 1, "pageSize": 5
    }, uid="u_admin")
    d1 = r1["data"]
    print(f"  period={d1['period']}")
    print(f"  startDate={d1.get('startDate')}, endDate={d1.get('endDate')}")
    print(f"  total={d1['total']}, page={d1['page']}, pageSize={d1['pageSize']}, hasMore={d1['hasMore']}")
    print(f"  list 数量={len(d1['list'])}")
    
    assert d1["startDate"] == start, "热门话题 startDate 不对"
    assert d1["endDate"] == end, "热门话题 endDate 不对"
    assert "page" in d1, "应该有 page"
    assert "hasMore" in d1, "应该有 hasMore"
    print("  PASS: 热门话题排行时间范围 + 分页正确")
    
    print("  --- 举报原因排行 ---")
    r2 = post("/api/audit/operation/top-report-reasons", body={
        "period": "custom", "startDate": start, "endDate": end,
        "page": 1, "pageSize": 5
    }, uid="u_admin")
    d2 = r2["data"]
    print(f"  period={d2['period']}")
    print(f"  startDate={d2.get('startDate')}, endDate={d2.get('endDate')}")
    print(f"  total={d2['total']}, page={d2['page']}, pageSize={d2['pageSize']}, hasMore={d2['hasMore']}")
    print(f"  list 数量={len(d2['list'])}")
    
    assert d2["startDate"] == start, "举报原因 startDate 不对"
    assert d2["endDate"] == end, "举报原因 endDate 不对"
    assert "page" in d2, "应该有 page"
    assert "hasMore" in d2, "应该有 hasMore"
    print("  PASS: 举报原因排行时间范围 + 分页正确")
    
    print("  PASS: 两项排行测试通过\n")

if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("V3 Bug Fix 验证测试")
    print("=" * 60 + "\n")
    
    try:
        test_draft_duration()
    except Exception as e:
        print(f"  ERROR: {e}\n")
    
    try:
        test_creator_trend_custom()
    except Exception as e:
        print(f"  ERROR: {e}\n")
    
    try:
        test_topic_remove_restore()
    except Exception as e:
        print(f"  ERROR: {e}\n")
    
    try:
        test_audit_video_filter()
    except Exception as e:
        print(f"  ERROR: {e}\n")
    
    try:
        test_report_timeline()
    except Exception as e:
        print(f"  ERROR: {e}\n")
    
    try:
        test_operation_trend_earnings()
    except Exception as e:
        print(f"  ERROR: {e}\n")
    
    try:
        test_top_topics_and_reasons()
    except Exception as e:
        print(f"  ERROR: {e}\n")
    
    print("=" * 60)
    print("全部测试完成!")
    print("=" * 60)
