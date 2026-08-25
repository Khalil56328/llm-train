"""数据库结构同步工具

`Base.metadata.create_all` 只会创建不存在的表，不会为已存在的表补充新列。
本模块用于在启动时幂等地为已存在的表：
  1. 补齐 ORM 中定义但数据库缺失的列（ADD COLUMN）；
  2. 对字符串列做“只扩不缩”的加宽同步（MODIFY COLUMN，VARCHAR 长度只增不减，
     例如 train_tasks.operator_version 从 VARCHAR(20) 加宽到 VARCHAR(36)，
     用于修复存算子版本 UUID 时的 1406 Data too long 错误）。
"""
from sqlalchemy import text
from sqlalchemy.inspection import inspect
from sqlalchemy import String, Text

from app.core.database import engine, Base


def _collect_changes(sync_conn) -> list:
    """收集需要执行的 DDL 语句：(action, table_name, col_name, ddl)。"""
    insp = inspect(sync_conn)
    changes = []
    for table_name, table in Base.metadata.tables.items():
        if not insp.has_table(table_name):
            # 新表由 create_all 创建，跳过
            continue
        existing = {c["name"]: c for c in insp.get_columns(table_name)}
        for col_name, col in table.columns.items():
            if col_name not in existing:
                # 构造 ADD COLUMN 语句
                col_type = col.type.compile(dialect=engine.dialect)
                nullable = "" if col.nullable else " NOT NULL"
                default = ""
                if col.default is not None and col.default.is_scalar:
                    v = col.default.arg
                    if isinstance(v, str):
                        default = f" DEFAULT '{v}'"
                    elif isinstance(v, bool):
                        default = f" DEFAULT {1 if v else 0}"
                    elif isinstance(v, (int, float)):
                        default = f" DEFAULT {v}"
                ddl = f"ALTER TABLE {table_name} ADD COLUMN {col_name} {col_type}{nullable}{default}"
                changes.append(("add", table_name, col_name, ddl))
                continue

            # 字符串列“只扩不缩”：ORM 长度 > 库中长度时才加宽（注意 Text 是 String 的子类，需排除）
            if isinstance(col.type, String) and not isinstance(col.type, Text):
                old_type = existing[col_name]["type"]
                if isinstance(old_type, String) and not isinstance(old_type, Text):
                    new_len = getattr(col.type, "length", None)
                    old_len = getattr(old_type, "length", None)
                    if new_len and old_len and new_len > old_len:
                        nullable = "" if col.nullable else " NOT NULL"
                        comment = ""
                        if getattr(col, "comment", None):
                            comment = f" COMMENT '{col.comment}'"
                        ddl = (
                            f"ALTER TABLE {table_name} MODIFY COLUMN {col_name} "
                            f"VARCHAR({new_len}){nullable}{comment}"
                        )
                        changes.append(("widen", table_name, col_name, ddl))
    return changes


async def sync_schema() -> None:
    """补齐缺失列 + 加宽字符串列（幂等，且只会加宽不会缩窄）。"""
    async with engine.begin() as conn:
        changes = await conn.run_sync(_collect_changes)
        for action, table_name, col_name, ddl in changes:
            await conn.execute(text(ddl))
            verb = "added column" if action == "add" else "widened column"
            print(f"[SCHEMA] {verb} {table_name}.{col_name}")
