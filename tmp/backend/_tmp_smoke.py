"""临时冒烟测试：训练任务提交链路"""
import json
import time
import urllib.request
import urllib.error

BASE = "http://127.0.0.1:8000/api"


def call(method, path, token=None, payload=None):
    url = BASE + path
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        return {"code": 1, "error": e.code, "body": body}


# 1. 登录
login = call("POST", "/auth/login", payload={"username": "admin", "password": "admin123"})
token = login["data"]["accessToken"]
print("[1] login OK, user:", login["data"]["user"]["username"])

# 2. 创建训练任务
task_payload = {
    "name": "冒烟测试-SFT",
    "taskType": "fine-tune",
    "subType": "LoRA微调",
    "baseModelName": "Qwen/Qwen2.5-7B-Instruct",
    "hyperParams": {"learningRate": 2e-5, "epochs": 1, "maxSteps": 40, "batchSize": 4},
    "resourceConfig": {"gpuCount": 1, "memory": 32},
    "description": "自动冒烟测试任务",
}
created = call("POST", "/train-tasks", token=token, payload=task_payload)
print("[2] create task:", json.dumps(created.get("data", created), ensure_ascii=False)[:200])
task_id = created["data"]["id"]

# 3. 提交任务
submitted = call("POST", f"/train-tasks/{task_id}/submit", token=token)
print("[3] submit:", json.dumps(submitted.get("data", submitted), ensure_ascii=False))

# 4. 轮询日志 / 指标 / 状态
for i in range(10):
    time.sleep(2)
    detail = call("GET", f"/train-tasks/{task_id}", token=token)
    d = detail.get("data", {})
    logs = call("GET", f"/train-tasks/{task_id}/logs?tail=20", token=token)
    metrics = call("GET", f"/train-tasks/{task_id}/metrics", token=token)
    log_rows = logs.get("data", [])
    status = d.get("status")
    progress = d.get("progress")
    print(f"[4.{i}] status={status} progress={progress} logs={len(log_rows)} metrics={len(metrics.get('data', []))} engineCommand={'yes' if d.get('engineCommand') else 'no'}")
    if status in ("succeeded", "failed", "stopped"):
        break

# 5. 打印最后几条日志
logs = call("GET", f"/train-tasks/{task_id}/logs?tail=8", token=token)
print("[5] last logs:")
for row in logs.get("data", []):
    print("   ", row.get("time"), f"[{row.get('level')}]", row.get("message"))

# 6. 打印指标
metrics = call("GET", f"/train-tasks/{task_id}/metrics", token=token)
print("[6] metrics sample:", json.dumps(metrics.get("data", [])[:3], ensure_ascii=False))
print("DONE")
