"""
幂等地初始化 / 维护管理员账号。

规则：
- 系统里已经有超级管理员时，默认不创建、不重置、不打印密码（升级部署无需这一步）。
- 首次部署（无任何超级管理员）时创建管理员：优先用 ADMIN_PASSWORD，
  没有就用随机密码，并在终端打印一次；同时标记首次登录必须改密。
- 始终停用非管理员账号，保证只有管理员能保持登录。
"""

import os
import secrets

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import IntegrityError, transaction

PASSWORD_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789"
BANNER = "=" * 68


def generate_password(length: int = 16) -> str:
    return "".join(secrets.choice(PASSWORD_ALPHABET) for _ in range(length))


class Command(BaseCommand):
    help = "初始化管理员账号；首次部署会在终端打印一次默认密码。"

    def add_arguments(self, parser):
        parser.add_argument(
            "--update-password",
            action="store_true",
            help="管理员已存在时，用环境变量里的密码重置它（默认不动已有密码）",
        )
        parser.add_argument("--username", default=None, help="临时覆盖 ADMIN_USERNAME")
        parser.add_argument("--password", default=None, help="临时覆盖 ADMIN_PASSWORD")

    def handle(self, *args, **options):
        User = get_user_model()

        username = (
            options["username"] or os.environ.get("ADMIN_USERNAME", "admin")
        ).strip() or "admin"
        password = options["password"] or os.environ.get("ADMIN_PASSWORD", "")
        email = os.environ.get("ADMIN_EMAIL", "").strip()

        superusers = User.objects.filter(is_superuser=True)
        active_admins = superusers.filter(is_active=True)
        # 只把「可用的超级管理员」视为已初始化，避免唯一管理员被停用后彻底锁死后台。
        admin_exists = active_admins.exists()

        # 1) 停用所有非管理员账号（保留数据，只禁止登录）
        deactivated = User.objects.filter(
            is_staff=False, is_superuser=False, is_active=True
        ).update(is_active=False)
        if deactivated:
            self.stdout.write(
                self.style.WARNING(
                    f"已停用 {deactivated} 个非管理员账号（用户数据仍然保留）。"
                )
            )

        # 2) 已有管理员：默认什么都不做
        if admin_exists and not options["update_password"]:
            names = ", ".join(active_admins.values_list("username", flat=True)[:5])
            self.stdout.write(
                self.style.SUCCESS(
                    f"管理员已存在（{names}），跳过初始化，不会重置密码。"
                )
            )
            return

        # 3) 需要重置密码
        if admin_exists and options["update_password"]:
            if not password:
                self.stderr.write(
                    self.style.ERROR("未提供 ADMIN_PASSWORD，无法执行 --update-password。")
                )
                return
            admin = active_admins.filter(username=username).first() or active_admins.first()
            admin.set_password(password)
            admin.is_active = True
            admin.is_staff = True
            admin.is_superuser = True
            admin.must_change_password = True
            admin.save(
                update_fields=[
                    "password",
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "must_change_password",
                ]
            )
            self._print_credentials(admin.username, password, reset=True)
            return

        # 4) 首次部署：创建 / 提升管理员
        if not password:
            password = generate_password()
        if len(password) < 8:
            self.stderr.write(
                self.style.WARNING(
                    "ADMIN_PASSWORD 少于 8 位，建议改成长随机密码。"
                )
            )

        user = User.objects.filter(username=username).first()
        created = user is None
        try:
            with transaction.atomic():
                if created:
                    user = User.objects.create_superuser(
                        username=username, email=email, password=password
                    )
                else:
                    user.set_password(password)
                    user.is_active = True
                    user.is_staff = True
                    user.is_superuser = True
                if email:
                    user.email = email
                user.must_change_password = True
                user.nickname = user.nickname or "站长"
                user.save()
        except IntegrityError as exc:
            self.stderr.write(self.style.ERROR(f"创建管理员失败：{exc}"))
            return

        self._print_credentials(user.username, password, reset=not created)

    def _print_credentials(self, username: str, password: str, reset: bool = False):
        action = "管理员密码已重置" if reset else "管理员账号已创建"
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(BANNER))
        self.stdout.write(self.style.SUCCESS(f"  {action}"))
        self.stdout.write(self.style.SUCCESS(f"  用户名：{username}"))
        self.stdout.write(self.style.SUCCESS(f"  初始密码：{password}"))
        self.stdout.write(
            self.style.WARNING("  首次登录后必须修改密码；此密码只在本次日志中输出一次。")
        )
        self.stdout.write(self.style.SUCCESS(BANNER))
        self.stdout.write("")
        self.stdout.write(
            f"  站点：{settings.SITE_NAME}    后台入口：/manage/"
        )
        self.stdout.write("")