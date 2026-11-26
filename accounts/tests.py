import os
from io import StringIO
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from core.models import SiteSetting

User = get_user_model()


class DisplayNameTests(TestCase):
    def test_display_name_and_initial(self):
        user = User.objects.create_user(username="zhang", password="x", nickname="张三")
        self.assertEqual(user.display_name, "张三")
        self.assertEqual(user.initial, "张")

    def test_anonymous_ish_user_without_nickname(self):
        user = User(username="abc")
        self.assertEqual(user.display_name, "abc")
        self.assertEqual(user.initial, "A")


class AdminOnlyLoginTests(TestCase):
    def test_staff_login_redirects_to_dashboard(self):
        User.objects.create_superuser(
            username="admin", email="a@example.com", password="Str0ngPass!2026"
        )
        response = self.client.post(
            reverse("accounts:login"),
            {"username": "admin", "password": "Str0ngPass!2026"},
            follow=False,
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], reverse("manage:index"))
        self.assertIn("_auth_user_id", self.client.session)

    def test_normal_user_cannot_login(self):
        User.objects.create_user(username="normal", password="Str0ngPass!2026")
        response = self.client.post(
            reverse("accounts:login"),
            {"username": "normal", "password": "Str0ngPass!2026"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "仅管理员账号可登录")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_inactive_admin_cannot_login(self):
        admin = User.objects.create_superuser(
            username="admin", email="a@example.com", password="Str0ngPass!2026"
        )
        admin.is_active = False
        admin.save(update_fields=["is_active"])
        response = self.client.post(
            reverse("accounts:login"),
            {"username": "admin", "password": "Str0ngPass!2026"},
        )
        self.assertEqual(response.status_code, 200)
        # 停用账号在 Django 的 authenticate 阶段就返回 None，
        # 统一显示「用户名或密码不正确」而不是泄露账号状态。
        self.assertContains(response, "用户名或密码不正确")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_registration_routes_are_gone(self):
        self.assertEqual(self.client.get("/accounts/register/").status_code, 404)
        response = self.client.post(
            "/accounts/register/",
            {
                "username": "newbie",
                "email": "n@example.com",
                "password1": "Str0ngPass!2026",
                "password2": "Str0ngPass!2026",
            },
        )
        self.assertEqual(response.status_code, 404)
        self.assertFalse(User.objects.filter(username="newbie").exists())

    def test_login_page_uses_site_name_and_has_no_register_link(self):
        response = self.client.get(reverse("accounts:login"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, settings.SITE_NAME)
        self.assertNotContains(response, "testserver")
        self.assertNotContains(response, "/accounts/register/")

    def test_logout_is_post_only(self):
        admin = User.objects.create_superuser(
            username="admin", email="a@example.com", password="Str0ngPass!2026"
        )
        self.client.force_login(admin)
        self.assertEqual(self.client.get(reverse("accounts:logout")).status_code, 405)
        self.assertEqual(self.client.post(reverse("accounts:logout")).status_code, 302)

    def test_non_staff_session_is_logged_out_by_middleware(self):
        user = User.objects.create_user(username="normal", password="Str0ngPass!2026")
        self.client.force_login(user)
        response = self.client.get(reverse("resources:home"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("accounts:login"), response["Location"])
        self.assertNotIn("_auth_user_id", self.client.session)


class ForcedPasswordChangeTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            username="admin", email="a@example.com", password="Str0ngPass!2026"
        )
        self.admin.must_change_password = True
        self.admin.save(update_fields=["must_change_password"])
        self.client.force_login(self.admin)

    def test_dashboard_redirects_to_account(self):
        response = self.client.get(reverse("manage:index"))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], reverse("manage:account"))

    def test_account_page_shows_forced_notice(self):
        response = self.client.get(reverse("manage:account"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "首次登录请先修改默认密码")

    def test_password_change_clears_flag(self):
        response = self.client.post(
            reverse("manage:account"),
            {
                "old_password": "Str0ngPass!2026",
                "new_password1": "BrandNewPass!2026",
                "new_password2": "BrandNewPass!2026",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], reverse("manage:index"))
        self.admin.refresh_from_db()
        self.assertFalse(self.admin.must_change_password)
        self.assertTrue(self.admin.check_password("BrandNewPass!2026"))


class EnsureAdminCommandTests(TestCase):
    @patch.dict(
        os.environ,
        {
            "ADMIN_USERNAME": "admin",
            "ADMIN_PASSWORD": "Str0ngPass!2026",
            "ADMIN_EMAIL": "admin@example.com",
        },
        clear=False,
    )
    def test_creates_admin_when_missing_and_deactivates_normal_users(self):
        User.objects.create_user(username="normal", password="whatever-123")
        out = StringIO()
        call_command("ensure_admin", stdout=out)

        admin = User.objects.get(username="admin")
        self.assertTrue(admin.is_superuser)
        self.assertTrue(admin.is_staff)
        self.assertTrue(admin.must_change_password)
        self.assertTrue(admin.check_password("Str0ngPass!2026"))
        self.assertIn("初始密码", out.getvalue())

        normal = User.objects.get(username="normal")
        self.assertFalse(normal.is_active)

    @patch.dict(
        os.environ,
        {"ADMIN_USERNAME": "admin", "ADMIN_PASSWORD": "NewPass!2026"},
        clear=False,
    )
    def test_does_not_reset_existing_admin_by_default(self):
        User.objects.create_superuser(
            username="admin", email="a@example.com", password="OldPass!2026"
        )
        out = StringIO()
        call_command("ensure_admin", stdout=out)

        admin = User.objects.get(username="admin")
        self.assertTrue(admin.check_password("OldPass!2026"))
        self.assertFalse(admin.must_change_password)
        self.assertNotIn("初始密码", out.getvalue())

    @patch.dict(
        os.environ,
        {"ADMIN_USERNAME": "admin", "ADMIN_PASSWORD": "NewPass!2026"},
        clear=False,
    )
    def test_update_password_flag_resets_existing_admin(self):
        User.objects.create_superuser(
            username="admin", email="a@example.com", password="OldPass!2026"
        )
        out = StringIO()
        call_command("ensure_admin", "--update-password", stdout=out)

        admin = User.objects.get(username="admin")
        self.assertTrue(admin.check_password("NewPass!2026"))
        self.assertTrue(admin.must_change_password)
        self.assertIn("初始密码", out.getvalue())


class InitSiteCommandTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_creates_default_settings(self):
        call_command("init_site", stdout=StringIO())
        self.assertEqual(SiteSetting.get("site_name"), settings.SITE_NAME)
        self.assertEqual(SiteSetting.get("homepage_slogan"), settings.SITE_SLOGAN)

    def test_does_not_overwrite_existing_settings(self):
        SiteSetting.set("homepage_slogan", "自定义口号")
        call_command("init_site", stdout=StringIO())
        self.assertEqual(SiteSetting.get("homepage_slogan"), "自定义口号")