import sys
sys.path.insert(0, '.')

from app.database import db
from app.models import *
from server import handle_publish, handle_creator, handle_audit

def test_publish_routes():
    uid = "u1"
    
    test_paths = [
        ("/api/publish/workbench", "GET", "发布工作台"),
        ("/api/publish/drafts", "GET", "草稿列表"),
        ("/api/publish/upload/list", "GET", "上传列表"),
        ("/api/publish/drafts/batch-delete", "POST", "批量删除草稿"),
        ("/api/publish/upload/batch-clean", "POST", "批量清理上传"),
        ("/api/creator/stats/videos", "GET", "作品统计"),
        ("/api/creator/stats/topics", "GET", "话题统计"),
        ("/api/creator/stats/time-slots", "GET", "时间段统计"),
    ]
    
    for path, method, name in test_paths:
        try:
            if method == "GET":
                r = handle_publish(path, {}, uid, None, "GET") if "publish" in path else handle_creator(path, {}, uid, None, "GET")
            else:
                r = handle_publish(path, {}, uid, {}, "POST")
            if r is None:
                print(f"[FAIL] {name}: 返回 None (404)")
            else:
                print(f"[OK] {name}: code={r['code']}")
        except Exception as e:
            print(f"[ERR] {name}: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    test_publish_routes()
