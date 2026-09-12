from django import forms
from django.contrib.auth.forms import (
    AuthenticationForm,
    PasswordChangeForm,
    UserCreationForm,
)

from .models import User


class RegisterForm(UserCreationForm):
    """注册表单：用户名 + 昵称 + 邮箱 + 密码。"""

    nickname = forms.CharField(
        label="昵称",
        max_length=50,
        required=False,
        widget=forms.TextInput(attrs={"placeholder": "留空则与用户名相同"}),
    )
    email = forms.EmailField(
        label="邮箱",
        required=True,
        widget=forms.EmailInput(attrs={"placeholder": "用于找回密码，不会公开"}),
    )

    class Meta:
        model = User
        fields = ("username", "nickname", "email")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        placeholders = {
            "username": "3-150 个字符，字母/数字/下划线",
            "password1": "至少 8 位，不要纯数字",
            "password2": "再次输入密码",
        }
        for name, field in self.fields.items():
            css = "input"
            if name in ("password1", "password2"):
                css = "input"
            field.widget.attrs.setdefault("class", css)
            if name in placeholders:
                field.widget.attrs.setdefault("placeholder", placeholders[name])
        self.fields["username"].help_text = ""

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("该邮箱已被注册。")
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        user.nickname = self.cleaned_data.get("nickname") or user.username
        if commit:
            user.save()
        return user


class LoginForm(AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].widget.attrs.update(
            {"class": "input", "placeholder": "用户名", "autofocus": True}
        )
        self.fields["password"].widget.attrs.update(
            {"class": "input", "placeholder": "密码"}
        )


class ProfileForm(forms.ModelForm):
    """个人中心：改昵称、简介、头像。"""

    class Meta:
        model = User
        fields = ("nickname", "email", "bio", "avatar")
        widgets = {
            "nickname": forms.TextInput(attrs={"class": "input"}),
            "email": forms.EmailInput(attrs={"class": "input"}),
            "bio": forms.TextInput(
                attrs={"class": "input", "placeholder": "最多 200 字"}
            ),
            "avatar": forms.ClearableFileInput(attrs={"class": "input", "accept": "image/*"}),
        }

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if (
            User.objects.filter(email__iexact=email)
            .exclude(pk=self.instance.pk)
            .exists()
        ):
            raise forms.ValidationError("该邮箱已被其他账号使用。")
        return email

    def clean_avatar(self):
        avatar = self.cleaned_data.get("avatar")
        if avatar and getattr(avatar, "size", 0) > 2 * 1024 * 1024:
            raise forms.ValidationError("头像请控制在 2MB 以内。")
        return avatar


class StyledPasswordChangeForm(PasswordChangeForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "input")
