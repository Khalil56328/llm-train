"""临时调试：检查 dataset_files / dataset_versions 表结构与 ORM 差异"""
import asyncio
from sqlalchemy import text
from app.core.database import engine


async def main():
    async with engine.connect() as conn:
        for table in ["datasets", "dataset_files", "dataset_versions"]:
            r = await conn.execute(text(f"SHOW CREATE TABLE `{table}`"))
            row = r.first()
            print(f"\n========== {table} ==========")
            print(row[1])


asyncio.run(main())
