#!/bin/sh
# 容器启动脚本：备份 → 迁移 → 管理员 → 默认设置 → 静态文件 → gunicorn
set -e

PORT="${PORT:-8082}"
WORKERS="${GUNICORN_WORKERS:-3}"
TIMEOUT="${GUNICORN_TIMEOUT:-60}"

echo "[1/6] 迁移前备份数据库…"
python manage.py backup_db

echo "[2/6] 应用数据库迁移…"
python manage.py migrate --noinput

echo "[3/6] 初始化 / 检查管理员账号…"
python manage.py ensure_admin

echo "[4/6] 写入默认站点设置…"
python manage.py init_site

echo "[5/6] 收集静态文件…"
python manage.py collectstatic --noinput --clear >/dev/null

echo "[6/6] 启动 gunicorn：0.0.0.0:${PORT}，workers=${WORKERS}"
exec gunicorn config.wsgi:application \
    --bind "0.0.0.0:${PORT}" \
    --workers "${WORKERS}" \
    --timeout "${TIMEOUT}" \
    --access-logfile - \
    --error-logfile -