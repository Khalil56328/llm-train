"""临时脚本：验证训练任务列表 API 按 task_type 过滤（用后即删）"""
import urllib.request
import json

BASE = "http://localhost:8000/api"


def post(path, data):
    req = urllib.request.Request(
        BASE + path,
        data=json.dumps(data).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read().decode("utf-8"))


def get(path, token):
    req = urllib.request.Request(
        BASE + path,
        headers={"Authorization": f"Bearer {token}"},
        method="GET",
    )
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read().decode("utf-8"))


def main():
    login = post("/auth/login", {"username": "admin", "password": "admin123"})
    print("LOGIN RESP:", json.dumps(login, ensure_ascii=False)[:300])
    token = login["data"].get("access_token") or login["data"].get("token") or login["data"].get("accessToken")
    print("LOGIN OK")

    # 不带类型（应返回全部）
    all_res = get("/train-tasks?pageIndex=1&pageSize=20", token)
    print("ALL total:", all_res["data"]["total"])
    for t in all_res["data"]["list"]:
        print("  ALL:", t["taskType"], "|", t["name"], "|", t["status"])

    # 按 taskType 过滤（前端驼峰参数）
    for tt in ["pretrain", "scene", "alignment", "compression", "fine-tune"]:
        res = get(f"/train-tasks?pageIndex=1&pageSize=20&taskType={tt}", token)
        names = [t["name"] for t in res["data"]["list"]]
        types = {t["taskType"] for t in res["data"]["list"]}
        print(f"taskType={tt}: total={res['data']['total']} types={types} names={names}")

    # 兼容蛇形 task_type 参数
    res = get("/train-tasks?pageIndex=1&pageSize=20&task_type=compression", token)
    print("task_type=compression total:", res["data"]["total"], [t["name"] for t in res["data"]["list"]])


main()
