import urllib.request
import json

BASE = 'http://localhost:8000'
H = {'Content-Type': 'application/json', 'x-user-id': 'u1'}
H_ADMIN = {'Content-Type': 'application/json', 'x-user-id': 'u_admin'}

def get(path, headers=H):
    req = urllib.request.Request(BASE + path, headers=headers)
    return json.loads(urllib.request.urlopen(req).read().decode())

def post(path, body, headers=H):
    data = json.dumps(body).encode()
    req = urllib.request.Request(BASE + path, data=data, headers=headers, method='POST')
    return json.loads(urllib.request.urlopen(req).read().decode())

print("=" * 50)
print("  HTTP 接口测试 V2")
print("=" * 50)
print()

passed = 0
total = 0

def test(name, fn):
    global passed, total
    total += 1
    try:
        result = fn()
        if result:
            passed += 1
            print(f"[PASS] {name}")
        else:
            print(f"[FAIL] {name}")
    except Exception as e:
        print(f"[FAIL] {name}: {e}")
    print()

def test_1():
    r = get('/api/publish/workbench?type=video&status=all&page=1&pageSize=5')
    assert r['code'] == 0
    print(f"  total: {r['data']['total']}")
    print(f"  stats keys: {list(r['data']['stats'].keys())}")
    return True
test("发布工作台", test_1)

def test_2():
    r = get('/api/publish/workbench?type=draft&page=1&pageSize=10')
    assert r['code'] == 0
    print(f"  草稿数: {r['data']['total']}")
    return True
test("工作台-草稿", test_2)

def test_3():
    r = get('/api/publish/workbench?type=upload&page=1&pageSize=10')
    assert r['code'] == 0
    print(f"  上传任务数: {r['data']['total']}")
    return True
test("工作台-上传任务", test_3)

def test_4():
    r = get('/api/creator/stats/videos?period=7d&page=1&pageSize=3')
    assert r['code'] == 0
    print(f"  total: {r['data']['total']}")
    if r['data']['list']:
        print(f"  top1: {r['data']['list'][0]['title']} views={r['data']['list'][0]['views']}")
    return True
test("创作者-作品统计", test_4)

def test_5():
    r = get('/api/creator/stats/topics?period=7d')
    assert r['code'] == 0
    print(f"  话题数: {len(r['data']['list'])}")
    return True
test("创作者-话题统计", test_5)

def test_6():
    r = get('/api/creator/stats/time-slots?period=7d')
    assert r['code'] == 0
    print(f"  24小时数据: {len(r['data']['views'])}个点")
    return True
test("创作者-时间段统计", test_6)

def test_7():
    r = get('/api/audit/notifications/unread-count')
    assert r['code'] == 0
    types_with_count = {k: v for k, v in r['data'].items() if v > 0}
    print(f"  有未读的类型: {list(types_with_count.keys())}")
    return True
test("消息未读统计(12种类型)", test_7)

def test_8():
    r = post('/api/publish/drafts/batch-delete', {'draftIds': []})
    assert r['code'] == 0
    print(f"  deleted: {r['data']['deleted']}")
    return True
test("批量删除草稿", test_8)

def test_9():
    r = post('/api/publish/upload/batch-clean', {'status': ['cancelled', 'failed']})
    assert r['code'] == 0
    print(f"  deleted: {r['data']['deleted']}")
    return True
test("批量清理上传任务", test_9)

def test_10():
    r = get('/api/audit/report/r2', H_ADMIN)
    assert r['code'] == 0
    print(f"  timeline条数: {len(r['data'].get('timeline', []))}")
    return True
test("举报详情-处理时间线", test_10)

def test_11():
    r = get('/api/audit/audit/videos?status=reviewing&page=1&pageSize=5', H_ADMIN)
    assert r['code'] == 0
    print(f"  待审核数: {r['data']['total']}")
    return True
test("审核视频列表", test_11)

def test_12():
    r = post('/api/audit/operation/trend', {'period': '7d'}, H_ADMIN)
    assert r['code'] == 0
    print(f"  days: {r['data']['days']}")
    print(f"  发布量: {r['data']['summary']['totalVideoPublish']}")
    print(f"  通过率: {r['data']['summary']['auditPassRate']}%")
    return True
test("运营统计-趋势", test_12)

def test_13():
    r = post('/api/audit/operation/top-topics', {'limit': 5}, H_ADMIN)
    assert r['code'] == 0
    print(f"  count: {len(r['data']['list'])}")
    if r['data']['list']:
        print(f"  top1: {r['data']['list'][0]['name']}")
    return True
test("运营统计-热门话题", test_13)

def test_14():
    r = post('/api/audit/operation/top-report-reasons', {}, H_ADMIN)
    assert r['code'] == 0
    print(f"  count: {len(r['data']['list'])}")
    return True
test("运营统计-举报原因排行", test_14)

print("=" * 50)
print(f"  结果: {passed}/{total} 通过")
print("=" * 50)
