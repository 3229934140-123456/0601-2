import urllib.request
import urllib.parse
import json
import sys

BASE_URL = "http://localhost:8000"


def get(path, headers=None):
    req = urllib.request.Request(BASE_URL + path, headers=headers or {})
    resp = urllib.request.urlopen(req)
    return json.loads(resp.read().decode())


def post(path, body=None, headers=None):
    data = json.dumps(body or {}).encode("utf-8")
    h = {"Content-Type": "application/json"}
    if headers:
        h.update(headers)
    req = urllib.request.Request(BASE_URL + path, data=data, headers=h, method="POST")
    resp = urllib.request.urlopen(req)
    return json.loads(resp.read().decode())


def run_test(name, fn):
    try:
        result = fn()
        code = result.get("code", -1)
        status = "PASS" if code == 0 else "FAIL"
        print("[%s] - %s" % (status, name))
        return code == 0
    except Exception as e:
        print("[FAIL] - %s: %s" % (name, e))
        return False


def main():
    print("=" * 50)
    print("  Short Video Backend - API Test")
    print("=" * 50)
    print()

    passed = 0
    total = 0
    user_h = {"x-user-id": "u1"}

    tests = [
        ("Home", lambda: get("/")),
        ("Recommend videos", lambda: get("/api/video/recommend?page=1&pageSize=5")),
        ("Video detail", lambda: get("/api/video/v1")),
        ("Hot ranking", lambda: get("/api/video/hot/ranking?type=hot&limit=5")),
        ("Following feed", lambda: get("/api/video/following")),
        ("User profile", lambda: get("/api/account/profile", user_h)),
        ("User homepage", lambda: get("/api/account/u2", user_h)),
        ("User videos", lambda: get("/api/account/u1/videos?page=1&pageSize=5")),
        ("Like video", lambda: post("/api/interaction/video/v10/like", headers=user_h)),
        ("Collect video", lambda: post("/api/interaction/video/v10/collect", headers=user_h)),
        ("Comment list", lambda: get("/api/interaction/video/v1/comments?page=1&pageSize=5")),
        ("Post comment", lambda: post("/api/interaction/video/v1/comments", {"content": "test"}, user_h)),
        ("Send danmaku", lambda: post("/api/interaction/video/v1/danmakus", {"content": "666", "timestamp": 10}, user_h)),
        ("Follow user", lambda: post("/api/interaction/user/u6/follow", headers=user_h)),
        ("Search video", lambda: get("/api/search/video?keyword=food&page=1&pageSize=5")),
        ("Search user", lambda: get("/api/search/user?keyword=da")),
        ("Hot words", lambda: get("/api/search/hot/words")),
        ("Hot videos", lambda: get("/api/search/hot/videos?limit=5")),
        ("Creator overview", lambda: get("/api/creator/overview", user_h)),
        ("Creator earnings", lambda: get("/api/creator/earnings", user_h)),
        ("Draft list", lambda: get("/api/publish/drafts", user_h)),
        ("Topic suggest", lambda: get("/api/publish/topics/suggest?keyword=food")),
        ("Notifications", lambda: get("/api/audit/notifications?page=1&pageSize=5", user_h)),
        ("Unread count", lambda: get("/api/audit/notifications/unread-count", user_h)),
        ("Report video", lambda: post("/api/audit/report/video", {"videoId": "v3", "reason": "other", "description": "test"}, user_h)),
    ]

    for name, fn in tests:
        total += 1
        if run_test(name, fn):
            passed += 1

    print()
    print("=" * 50)
    print("  Result: %d/%d passed" % (passed, total))
    print("=" * 50)
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
