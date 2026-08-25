# ============================================================
# 【已不用于标准部署】标准部署中前端 SPA 由后端 FastAPI 直接托管
# （FRONTEND_DIST_DIR=../web-ui/dist，单端口 8000），不再单独容器化前端。
# 本镜像仅保留供开发/CI 或历史参考。
# ============================================================
# 构建阶段
FROM node:20-alpine AS builder

WORKDIR /app

COPY package.json .
RUN npm install --registry=https://registry.npmmirror.com

COPY . .
RUN npm run build

# 运行阶段
FROM nginx:alpine

COPY --from=builder /app/dist /usr/share/nginx/html

# Nginx 配置（也可在运行时挂载）
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
