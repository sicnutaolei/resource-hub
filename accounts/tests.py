from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

User = get_user_model()


class RegistrationTests(TestCase):
    def test_register_creates_user_and_logs_in(self):
        response = self.client.post(
            reverse("accounts:register"),
            {
                "username": "newbie",
                "nickname": "新来的",
                "email": "newbie@example.com",
                "password1": "str0ng-pass-2026",
                "password2": "str0ng-pass-2026",
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        user = User.objects.get(username="newbie")
        self.assertEqual(user.nickname, "新来的")
        self.assertIn("_auth_user_id", self.client.session)

    def test_register_blank_nickname_falls_back_to_username(self):
        self.client.post(
            reverse("accounts:register"),
            {
                "username": "silent",
                "nickname": "",
                "email": "silent@example.com",
                "password1": "str0ng-pass-2026",
                "password2": "str0ng-pass-2026",
            },
        )
        user = User.objects.get(username="silent")
        self.assertEqual(user.nickname, "silent")

    def test_duplicate_email_rejected(self):
        User.objects.create_user(username="a", email="dup@example.com", password="x")
        response = self.client.post(
            reverse("accounts:register"),
            {
                "username": "b",
                "nickname": "B",
                "email": "DUP@example.com",
                "password1": "str0ng-pass-2026",
                "password2": "str0ng-pass-2026",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username="b").exists())

    def test_password_mismatch_rejected(self):
        response = self.client.post(
            reverse("accounts:register"),
            {
                "username": "mismatch",
                "nickname": "",
                "email": "m@example.com",
                "password1": "str0ng-pass-2026",
                "password2": "another-pass-2026",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username="mismatch").exists())


class ProfileTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="tester", password="test12345", email="t@example.com", nickname="测试"
        )

    def test_profile_requires_login(self):
        response = self.client.get(reverse("accounts:profile"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response["Location"])

    def test_profile_renders_for_logged_in_user(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("accounts:profile"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "测试")

    def test_profile_edit_updates_nickname(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("accounts:profile_edit"),
            {"nickname": "新昵称", "email": "t@example.com", "bio": "你好"},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.nickname, "新昵称")
        self.assertEqual(self.user.bio, "你好")

    def test_password_change(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("accounts:password_change"),
            {
                "old_password": "test12345",
                "new_password1": "brand-new-pass-2026",
                "new_password2": "brand-new-pass-2026",
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("brand-new-pass-2026"))

    def test_logout_is_post_only(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse("accounts:logout")).status_code, 405)


class DisplayNameTests(TestCase):
    def test_display_name_and_initial(self):
        user = User.objects.create_user(username="zhang", password="x", nickname="张三")
        self.assertEqual(user.display_name, "张三")
        self.assertEqual(user.initial, "张")

    def test_anonymous_ish_user_without_nickname(self):
        user = User(username="abc")
        self.assertEqual(user.display_name, "abc")
        self.assertEqual(user.initial, "A")
