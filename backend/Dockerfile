# ============================================================
# 【已不用于标准部署】标准部署中整个项目（前端 + API + Worker）直接运行在
# GPU 宿主机上（deploy/notebook/README.md 路径 A / deploy/ubuntu/README.md 路径 C），
# 无需容器。本镜像仅保留供开发/CI 或历史参考，真实训练/推理须在 GPU 宿主机执行。
# ============================================================
FROM python:3.10-slim

WORKDIR /app

# 系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev && \
    rm -rf /var/lib/apt/lists/*

# Python 依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 应用代码
COPY . .

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
