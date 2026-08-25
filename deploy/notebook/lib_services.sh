#!/usr/bin/env bash
# ============================================================
# LLM 训推平台 · 依赖服务启动辅助函数（MySQL / Redis）
# 由 init_env.sh / start.sh source 使用；要求调用方已设置 $SUDO
# 依赖服务默认由本机 apt 安装（systemd 完整环境 / sysvinit / 无 systemd 容器兜底）。
# 若 3306/6379 端口已有服务在监听（外部已部署 / 云厂商预装 / 残留实例），
# 自动视为已提供：跳过本机拉起与初始化，避免端口冲突与重复安装。
# ============================================================

# 探测 127.0.0.1:3306 是否已有 MySQL 监听（外部/已运行 MySQL 场景，
# 此时本机无 socket，service/systemctl/mysqld_safe 均不应再启动本机实例）
mysql_port_alive() {
  if timeout 2 bash -c 'exec 3<>/dev/tcp/127.0.0.1/3306' 2>/dev/null; then
    return 0
  fi
  return 1
}

# 探测 127.0.0.1:6379 是否已有 Redis 监听（外部/已运行 Redis 场景）
redis_port_alive() {
  if timeout 2 bash -c 'exec 3<>/dev/tcp/127.0.0.1/6379' 2>/dev/null; then
    return 0
  fi
  return 1
}

# 启动 MySQL（成功返回 0；失败返回 1）
start_mysql() {
  # 0) 端口已有服务（外部/已运行 MySQL）：直接视为已就绪，绝不拉起本机实例
  if mysql_port_alive; then
    return 0
  fi
  # 1) 系统服务优先
  if $SUDO service mysql start 2>/dev/null; then
    return 0
  fi
  if $SUDO systemctl start mysql 2>/dev/null; then
    return 0
  fi
  # 2) 容器兜底：手动拉起 mysqld（需补齐 socket 目录；数据目录缺失时先初始化）
  echo "    [WARN] service/systemctl 无法启动 MySQL，改用 mysqld_safe 手动启动"
  $SUDO mkdir -p /var/run/mysqld || true
  $SUDO chown mysql:mysql /var/run/mysqld || true
  # 数据目录未初始化（apt 安装时静默失败 / 目录损坏的常见表现）则先初始化
  if [ ! -d /var/lib/mysql/mysql ]; then
    echo "    [WARN] MySQL 数据目录未初始化，执行 mysqld --initialize-insecure ..."
    $SUDO mysqld --initialize-insecure --user=mysql || return 1
  fi
  # 已在运行则跳过启动
  if $SUDO mysqladmin ping --silent 2>/dev/null; then
    return 0
  fi
  $SUDO bash -c 'nohup mysqld_safe --user=mysql >/tmp/mysqld_safe.log 2>&1 &'
  return 0
}

# 等待 MySQL 就绪（参数：超时秒数，默认 60；就绪返回 0）
# 本机 socket 与 TCP 端口（外部/已运行 MySQL）任一可达即视为就绪
wait_mysql() {
  local timeout="${1:-60}"
  local i
  for i in $(seq 1 "$timeout"); do
    if mysql_port_alive || $SUDO mysqladmin ping --silent 2>/dev/null; then
      return 0
    fi
    sleep 1
  done
  return 1
}

# 执行建库建用户脚本（deploy/mysql/init.sql，幂等）
# 优先本机 root socket（apt 安装）；失败回退 TCP root（外部/已运行 MySQL 的常见
# root 密码）。docker 容器等外部 MySQL 首次启动通常已自动执行 init.sql，
# 此处仅为幂等兜底，失败只告警不阻断。
mysql_init_db() {
  local sql_file="$1"
  if $SUDO mysql < "$sql_file" 2>/dev/null; then
    return 0
  fi
  for pw in "" "root123456"; do
    if mysql -h 127.0.0.1 -u root ${pw:+-p"$pw"} < "$sql_file" 2>/dev/null; then
      return 0
    fi
  done
  echo "    [WARN] 无法执行 $sql_file（本机 socket 与 TCP root 均失败）；"
  echo "           请确认 MySQL 已就绪且 root 可访问（本机 apt 装的可直接 sudo mysql）"
  return 1
}

# 启动 Redis（成功返回 0；失败返回 1）
start_redis() {
  # 0) 端口已有服务（外部/已运行 Redis）：直接视为已就绪
  if redis_port_alive; then
    return 0
  fi
  if $SUDO service redis-server start 2>/dev/null; then
    return 0
  fi
  if $SUDO systemctl start redis-server 2>/dev/null; then
    return 0
  fi
  echo "    [WARN] service/systemctl 无法启动 Redis，改用 redis-server --daemonize yes 手动启动"
  if $SUDO redis-server --daemonize yes 2>/dev/null; then
    return 0
  fi
  # 部分 Redis 版本拒绝以 root 运行：补齐 pidfile 目录后降权为 redis 用户再试
  if [ -n "$SUDO" ]; then
    $SUDO mkdir -p /run/redis || true
    $SUDO chown redis:redis /run/redis || true
    $SUDO -u redis redis-server /etc/redis/redis.conf --daemonize yes 2>/dev/null || true
  fi
}

# 探测 Redis 是否存活（存活返回 0）：先查端口（外部/已运行），再查本机 redis-cli
redis_alive() {
  if redis_port_alive; then
    return 0
  fi
  redis-cli ping 2>/dev/null | grep -q PONG
}
