#!/bin/sh
# 容器启动脚本：迁移 → 建管理员 → 收集静态文件 → 启动 gunicorn
set -e

PORT="${PORT:-8082}"
WORKERS="${GUNICORN_WORKERS:-3}"
TIMEOUT="${GUNICORN_TIMEOUT:-60}"

echo "[1/4] 应用数据库迁移…"
python manage.py migrate --noinput

echo "[2/4] 同步管理员账号（读取 ADMIN_USERNAME / ADMIN_PASSWORD）…"
python manage.py ensure_admin

echo "[3/4] 收集静态文件…"
python manage.py collectstatic --noinput --clear >/dev/null

echo "[4/4] 启动 gunicorn：0.0.0.0:${PORT}，workers=${WORKERS}"
exec gunicorn config.wsgi:application \
    --bind "0.0.0.0:${PORT}" \
    --workers "${WORKERS}" \
    --timeout "${TIMEOUT}" \
    --access-logfile - \
    --error-logfile -
