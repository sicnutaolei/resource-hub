"""
按环境变量幂等地创建 / 更新管理员账号。

设计要点：管理员密码只来自环境变量（ADMIN_PASSWORD），
仓库里只有 .env.example 中的占位符，真实密码永远不会进入版本库。
"""
import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import IntegrityError

DEFAULT_INSECURE_PASSWORD = "admin123"


class Command(BaseCommand):
    help = "根据 ADMIN_USERNAME / ADMIN_PASSWORD / ADMIN_EMAIL 创建或更新超级管理员。可重复执行。"

    def add_arguments(self, parser):
        parser.add_argument(
            "--update-password",
            action="store_true",
            help="即使账号已存在，也用环境变量里的密码重置它",
        )
        parser.add_argument(
            "--username", default=None, help="临时覆盖 ADMIN_USERNAME"
        )
        parser.add_argument(
            "--password", default=None, help="临时覆盖 ADMIN_PASSWORD（仅建议本地调试用）"
        )

    def handle(self, *args, **options):
        User = get_user_model()

        username = options["username"] or os.environ.get("ADMIN_USERNAME", "admin").strip()
        password = options["password"] or os.environ.get("ADMIN_PASSWORD", "")
        email = os.environ.get("ADMIN_EMAIL", "").strip()

        if not username:
            self.stderr.write(self.style.ERROR("ADMIN_USERNAME 为空，已跳过。"))
            return

        if not password:
            self.stderr.write(
                self.style.WARNING(
                    "未检测到 ADMIN_PASSWORD 环境变量。首次部署必须提供该变量，"
                    "否则管理员账号无法创建。"
                )
            )
            return

        user = User.objects.filter(username=username).first()

        if user is None:
            try:
                user = User.objects.create_superuser(
                    username=username, email=email, password=password
                )
            except IntegrityError as exc:
                self.stderr.write(self.style.ERROR(f"创建管理员失败：{exc}"))
                return
            user.nickname = "站长"
            user.save(update_fields=["nickname"])
            self.stdout.write(self.style.SUCCESS(f"已创建管理员账号：{username}"))
        else:
            updated_fields = []
            if not user.is_staff or not user.is_superuser:
                user.is_staff = True
                user.is_superuser = True
                updated_fields.append("is_staff")
                updated_fields.append("is_superuser")
            if email and user.email != email:
                user.email = email
                updated_fields.append("email")
            if options["update_password"]:
                user.set_password(password)
                updated_fields.append("password")
            if updated_fields:
                user.save(update_fields=list(dict.fromkeys(updated_fields)))
                self.stdout.write(
                    self.style.SUCCESS(
                        f"管理员 {username} 已更新：{', '.join(sorted(set(updated_fields)))}"
                    )
                )
            else:
                self.stdout.write(
                    f"管理员 {username} 已存在，未做修改"
                    "（如需重置密码请加 --update-password）。"
                )

        if password == DEFAULT_INSECURE_PASSWORD:
            self.stdout.write("")
            self.stdout.write(
                self.style.WARNING(
                    "⚠ 当前使用的是示例密码 admin123，任何人都能登录后台。"
                    "请立刻修改 .env 中的 ADMIN_PASSWORD，"
                    "然后执行：docker compose exec web python manage.py ensure_admin --update-password"
                )
            )
