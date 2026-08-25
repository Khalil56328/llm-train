-- ============================================================
-- LLM 训推平台 · MySQL 初始化脚本（建库 + 应用用户）
-- 使用场景：
--   1. docker-compose：自动挂载到 /docker-entrypoint-initdb.d/，首次启动自动执行
--   2. ModelScope Notebook（无 Docker）：手动执行
--        sudo mysql < deploy/mysql/init.sql
-- 建表由后端启动时自动完成（main.py lifespan create_all + sync_schema），此处无需建表
-- ============================================================
CREATE DATABASE IF NOT EXISTS llm_train
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

-- 应用账号（与 backend/.env 中 DATABASE_URL 保持一致）
CREATE USER IF NOT EXISTS 'llm_train'@'%' IDENTIFIED BY 'llm_train_2026';
GRANT ALL PRIVILEGES ON llm_train.* TO 'llm_train'@'%';
FLUSH PRIVILEGES;
