"""临时脚本：修复 train_task_logs/metrics 的 seq 列（去 AUTO_INCREMENT、去唯一索引）"""
import asyncio
from sqlalchemy import text
from app.core.database import engine

TABLES = ["train_task_logs", "train_task_metrics"]


async def main():
    async with engine.begin() as conn:
        for table in TABLES:
            # 1) 若为 AUTO_INCREMENT，先去掉
            extra = (
                await conn.execute(text(
                    "SELECT EXTRA FROM information_schema.COLUMNS "
                    "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = :t AND COLUMN_NAME = 'seq'"
                ), {"t": table})
            ).scalar() or ""
            print(f"[{table}] seq EXTRA: {extra}")
            if "auto_increment" in extra:
                await conn.execute(text(f"ALTER TABLE {table} MODIFY COLUMN seq BIGINT NULL"))
                print(f"  -> drop auto_increment")

            # 2) 删除包含 seq 的索引
            idx = (
                await conn.execute(text(
                    "SELECT INDEX_NAME FROM information_schema.STATISTICS "
                    "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = :t "
                    "GROUP BY INDEX_NAME "
                    "HAVING GROUP_CONCAT(COLUMN_NAME ORDER BY SEQ_IN_INDEX) = 'seq'"
                ), {"t": table})
            ).all()
            print(f"[{table}] seq 索引: {[r[0] for r in idx]}")
            for row in idx:
                await conn.execute(text(f"ALTER TABLE {table} DROP INDEX `{row[0]}`"))
                print(f"  -> drop index {row[0]}")
    print("DONE")


asyncio.run(main())
