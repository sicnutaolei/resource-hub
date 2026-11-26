from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.core.exceptions import ValidationError


class AdminLoginForm(AuthenticationForm):
    """只允许管理员（is_staff / is_superuser）登录。"""

    error_messages = {
        "invalid_login": "用户名或密码不正确。",
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].widget.attrs.update(
            {"class": "input", "placeholder": "管理员用户名", "autofocus": True}
        )
        self.fields["password"].widget.attrs.update(
            {"class": "input", "placeholder": "密码"}
        )

    def confirm_login_allowed(self, user):
        if not user.is_active:
            raise ValidationError("账号已停用。", code="inactive")
        if not (user.is_staff or user.is_superuser):
            raise ValidationError("仅管理员账号可登录。", code="not_admin")