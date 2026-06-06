import urllib.request
import json
import sys

def get(path, uid='u1'):
    req = urllib.request.Request(f'http://localhost:8000{path}',
                                 headers={'x-user-id': uid})
    return json.loads(urllib.request.urlopen(req, timeout=5).read())

def post(path, body, uid='u1'):
    data = json.dumps(body).encode()
    req = urllib.request.Request(f'http://localhost:8000{path}',
                                 data=data,
                                 headers={'Content-Type': 'application/json',
                                          'x-user-id': uid},
                                 method='POST')
    return json.loads(urllib.request.urlopen(req, timeout=5).read())

passed = 0
failed = 0

def test(name):
    print(f'\n[TEST] {name}')

def ok(msg='PASS'):
    global passed
    passed += 1
    print(f'  [OK] {msg}')

def fail(msg):
    global failed
    failed += 1
    print(f'  [FAIL] {msg}')

# 1. 发布工作台
test('发布工作台 stats')
r = get('/api/publish/workbench?type=video&status=all&page=1&pageSize=3')
stats = r['data']['stats']
print(f'  total={stats["total"]}, published={stats["published"]}, rejected={stats["rejected"]}')
if 'rejected' in stats and 'uploadFailed' in stats:
    ok('stats 字段完整')
else:
    fail('stats 字段缺失')

# 2. 按作品统计
test('按作品统计')
r = get('/api/creator/stats/videos?period=7d&page=1&pageSize=3')
s = r['data']['summary']
print(f'  totalVideos={s["totalVideos"]}, totalEarnings={s["totalEarnings"]}')
if 'totalEarnings' in s and r['data']['period'] == '7d':
    ok('7维度数据 + period 字段')
else:
    fail('字段缺失')

# 3. 按话题统计
test('按话题统计')
r = get('/api/creator/stats/topics?period=7d&page=1&pageSize=10')
s = r['data']['summary']
print(f'  total={r["data"]["total"]}, summary 字段数={len(s)}')
if 'totalEarnings' in s and len(r['data']['list']) > 0 and 'newFans' in r['data']['list'][0]:
    ok('7维度数据 + 分页')
else:
    fail('字段缺失')

# 4. 按时间段统计
test('按发布时间段统计')
r = get('/api/creator/stats/time-slots?period=7d')
print(f'  hours={len(r["data"]["hours"])}, summary 字段数={len(r["data"]["summary"])}')
if len(r['data']['hours']) == 24 and 'earnings' in r['data']:
    ok('24小时 + 7维度数据')
else:
    fail('字段缺失')

# 5. 消息中心
test('消息中心 - 多条件筛选')
r = get('/api/audit/notifications?type=all&page=1&pageSize=3')
print(f'  total={r["data"]["total"]}, unreadByType 类型数={len(r["data"]["unreadByType"])}')
if 'unreadByType' in r['data'] and len(r['data']['unreadByType']) >= 10:
    ok('11种类型 + 未读分类统计')
else:
    fail('字段缺失')

# 6. 热门话题排行
test('运营统计 - 热门话题排行')
r = post('/api/audit/operation/top-topics', {'period': '7d', 'limit': 3}, 'u_admin')
print(f'  list={len(r["data"]["list"])}, days={r["data"]["days"]}')
if 'periodViews' in r['data']['list'][0] and r['data']['days'] == 7:
    ok('按时间范围统计 + 7维度')
else:
    fail('字段缺失')

# 7. 举报原因排行
test('运营统计 - 举报原因排行')
r = post('/api/audit/operation/top-report-reasons', {'period': '30d'}, 'u_admin')
print(f'  total={r["data"]["total"]}, days={r["data"]["days"]}')
if r['data']['days'] == 30:
    ok('按时间范围统计')
else:
    fail('时间范围不对')

# 8. 导出明细
test('运营统计 - 视频导出明细')
r = get('/api/audit/operation/videos/export?status=all&page=1&pageSize=5', 'u_admin')
item = r['data']['list'][0]
print(f'  total={r["data"]["total"]}, 单条字段数={len(item)}')
if 'authorNickname' in item and 'topicNames' in item and 'rejectReason' in item:
    ok('完整字段 + 分页')
else:
    fail('字段缺失')

# 9. 被驳回作品 + 重新提交
test('被驳回作品重新提交')
r = get('/api/publish/workbench?type=video&status=rejected&page=1&pageSize=3')
print(f'  rejected total={r["data"]["total"]}')
if r['data']['list']:
    item = r['data']['list'][0]
    vid = item['id']
    reject_reason = item.get('rejectReason')
    print(f'  视频={vid}, 驳回原因={reject_reason}')
    if reject_reason:
        r2 = post(f'/api/publish/video/{vid}/resubmit', {
            'title': '修改后的标题',
            'description': '修改后的描述',
            'coverUrl': 'https://picsum.photos/seed/new/720/1280',
            'topics': ['t1']
        })
        print(f'  重新提交状态={r2["data"]["status"]}')
        if r2['data']['status'] == 'reviewing':
            ok('重新提交成功，状态变为 reviewing')
        else:
            fail('状态不对')
    else:
        fail('没有驳回原因')
else:
    print('  无被驳回作品，跳过')

# 10. 话题数据联动
test('话题数据联动 - 点赞')
r = get('/api/search/topic?keyword=美食')
if r['data']['list']:
    tid = r['data']['list'][0]['id']
    t1 = r['data']['list'][0]['likesCount']
    print(f'  话题={tid}, 点赞前={t1}')
    r2 = post('/api/interaction/video/v1/like', {})
    print(f'  点赞 v1: isLiked={r2["data"]["isLiked"]}')
    r3 = get('/api/search/topic?keyword=美食')
    t2 = r3['data']['list'][0]['likesCount']
    print(f'  点赞后={t2}')
    if t2 != t1:
        ok('话题点赞数联动变化')
    else:
        fail('话题点赞数未变化')
else:
    print('  没找到话题，跳过')

print(f'\n==========================')
print(f'结果: {passed} 通过, {failed} 失败')
print(f'==========================')
sys.exit(0 if failed == 0 else 1)
