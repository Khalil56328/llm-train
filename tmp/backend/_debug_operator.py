"""临时脚本：给 operators 表补上 ORM 模型缺失的列"""
import asyncio
import sys

sys.path.insert(0, r"d:\work\project\20260806\model_train\backend")

from sqlalchemy import text
from app.core.database import engine


async def main():
    async with engine.begin() as conn:
        # 检查列是否已存在
        r = await conn.execute(text(
            "SELECT COLUMN_NAME FROM information_schema.COLUMNS "
            "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'operators' "
            "AND COLUMN_NAME IN ('training_framework','training_method')"
        ))
        existing = [row[0] for row in r.fetchall()]
        print("已存在列:", existing)

        adds = []
        if "training_framework" not in existing:
            adds.append("ADD COLUMN `training_framework` varchar(50) DEFAULT NULL COMMENT '训练框架' AFTER `type`")
        if "training_method" not in existing:
            adds.append("ADD COLUMN `training_method` varchar(50) DEFAULT NULL COMMENT '训练方法' AFTER `training_framework`")

        if adds:
            sql = f"ALTER TABLE `operators` {', '.join(adds)}"
            await conn.execute(text(sql))
            print("执行成功:", sql)
        else:
            print("无需变更")

        # 验证
        r = await conn.execute(text(
            "SELECT COLUMN_NAME FROM information_schema.COLUMNS "
            "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'operators' ORDER BY ORDINAL_POSITION"
        ))
        print("当前列:", [row[0] for row in r.fetchall()])


asyncio.run(main())
