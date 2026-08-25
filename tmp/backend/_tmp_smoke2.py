"""临时冒烟测试2：暂停/恢复 + 部署 + 评测链路"""
import json
import time
import urllib.request
import urllib.error

BASE = "http://127.0.0.1:8000/api"


def call(method, path, token=None, payload=None, timeout=60):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(BASE + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return {"code": 1, "http": e.code, "body": e.read().decode()[:300]}


token = call("POST", "/auth/login", payload={"username": "admin", "password": "admin123"})["data"]["accessToken"]
print("[1] login OK")

# --- 暂停/恢复 ---
tid = call("POST", "/train-tasks", token=token, payload={
    "name": "暂停测试", "taskType": "fine-tune", "subType": "LoRA微调",
    "baseModelName": "Qwen/Qwen2.5-7B-Instruct",
    "hyperParams": {"maxSteps": 300, "learningRate": 2e-5},
    "resourceConfig": {"gpuCount": 1},
})["data"]["id"]
call("POST", f"/train-tasks/{tid}/submit", token=token)
time.sleep(1.0)
r = call("POST", f"/train-tasks/{tid}/pause", token=token)
print("[2] pause ->", r.get("code"), r.get("message"))
time.sleep(1.5)
st = call("GET", f"/train-tasks/{tid}", token=token)["data"]["status"]
print("[3] status after pause:", st)
r = call("POST", f"/train-tasks/{tid}/resume", token=token)
print("[4] resume ->", r.get("code"), r.get("message"))
for _ in range(15):
    time.sleep(1)
    d = call("GET", f"/train-tasks/{tid}", token=token)["data"]
    if d["status"] in ("succeeded", "failed", "stopped"):
        break
print("[5] final status:", d["status"], "progress:", d["progress"], "output:", d["outputModelName"])

# --- 取消 ---
tid2 = call("POST", "/train-tasks", token=token, payload={
    "name": "取消测试", "taskType": "fine-tune", "subType": "LoRA微调",
    "baseModelName": "Qwen/Qwen2.5-7B-Instruct",
    "hyperParams": {"maxSteps": 300, "learningRate": 2e-5},
})["data"]["id"]
call("POST", f"/train-tasks/{tid2}/submit", token=token)
time.sleep(1.0)
r = call("POST", f"/train-tasks/{tid2}/cancel", token=token)
print("[6] cancel ->", r.get("code"), r.get("message"))
time.sleep(1.0)
st2 = call("GET", f"/train-tasks/{tid2}", token=token)["data"]["status"]
print("[7] status after cancel:", st2)

# --- 部署 ---
dep = call("POST", "/deployments", token=token, payload={
    "name": "部署测试", "modelName": "Qwen/Qwen2.5-7B-Instruct",
    "inferenceFramework": "vLLM", "accessPort": 8001,
    "params": {"gpuMemoryUtilization": 0.8},
})
print("[8] create deployment:", json.dumps(dep.get("data", dep), ensure_ascii=False)[:150])
dep_id = dep["data"]["id"]
r = call("POST", f"/deployments/{dep_id}/start", token=token)
print("[9] start ->", r.get("code"), json.dumps(r.get("data", {}), ensure_ascii=False)[:120])
time.sleep(1)
dd = call("GET", f"/deployments/{dep_id}", token=token)["data"]
print("[10] deployment status:", dd["status"], "endpoint:", dd["endpoint"])

# --- 评测 ---
ev = call("POST", "/evaluations", token=token, payload={
    "name": "评测测试", "scenes": ["code", "reasoning", "safety"],
})
print("[11] create eval:", json.dumps(ev.get("data", ev), ensure_ascii=False)[:150])
ev_id = ev["data"]["id"]
r = call("POST", f"/evaluations/{ev_id}/start", token=token)
print("[12] eval start ->", r.get("code"), json.dumps(r.get("data", {}), ensure_ascii=False)[:100])
for _ in range(5):
    time.sleep(1)
    ed = call("GET", f"/evaluations/{ev_id}", token=token)["data"]
    if ed["status"] in ("completed", "failed"):
        break
print("[13] eval status:", ed["status"], "score:", ed["score"], "reportUrl:", ed["reportUrl"])
rep = call("GET", f"/evaluations/{ev_id}/report", token=token)
print("[14] report:", json.dumps(rep.get("data", {}), ensure_ascii=False)[:300])
print("DONE")
