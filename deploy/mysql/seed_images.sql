-- ============================================================
-- LLM 训推平台 · 初始化宿主机环境镜像记录
--
-- 用途：向 docker_images 表插入一条与宿主机一致的镜像记录
--       （ModelScope Notebook 环境镜像：
--         ubuntu22.04-cuda12.8.1-py312-torch2.10.0-1.39.0）
--
-- 何时需要执行：
--   1. 全新部署：无需手动执行 —— 后端启动时 image_service.seed_defaults()
--      会在 docker_images 表为空时自动写入默认镜像（已含本记录）；
--   2. 已有数据库（后端已启动、表已存在、但种子数据是旧版占位地址）：
--      手动执行本脚本补插 / 更新本记录；
--   3. 表不存在时执行会报错：请先启动后端完成建表（main.py lifespan create_all）。
--
-- 用法：
--   ModelScope Notebook / 宿主机直跑 MySQL：
--     sudo mysql llm_train < deploy/mysql/seed_images.sql
--   Docker 编排（mysql 容器内）：
--     docker exec -i llm-train-mysql mysql -ullm_train -pllm_train_2026 llm_train \
--       < deploy/mysql/seed_images.sql
--
-- 幂等：docker_images.name 为唯一键，重复执行不会产生重复记录，
--       且会更新已存在记录的 address / resource_type / description。
-- ============================================================

INSERT INTO docker_images (id, name, address, resource_type, description, created_at, updated_at)
SELECT
    REPLACE(UUID(), '-', ''),                      -- 与应用端 uuid4().hex 同格式（32 位十六进制）
    'ModelScope 宿主机环境镜像',
    'ubuntu22.04-cuda12.8.1-py312-torch2.10.0-1.39.0',
    'GPU',
    '魔搭 Notebook 宿主机实际运行环境（Ubuntu 22.04 / CUDA 12.8.1 / Python 3.12 / torch 2.10.0）；TRAIN_CONTAINER_RUNTIME=local 时训练/推理直接在此环境执行',
    NOW(),
    NOW()
WHERE NOT EXISTS (
    SELECT 1 FROM docker_images WHERE name = 'ModelScope 宿主机环境镜像'
);
