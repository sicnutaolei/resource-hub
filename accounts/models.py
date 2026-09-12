from django.contrib.auth.models import AbstractUser
from django.db import models
from django.urls import reverse

from core.validators import validate_image_upload


class User(AbstractUser):
    """
    自定义用户模型。

    项目从第一天就启用 AUTH_USER_MODEL，避免后期从 auth.User 迁移到自定义模型
    时产生的高风险数据迁移。
    """

    nickname = models.CharField("昵称", max_length=50, blank=True)
    avatar = models.ImageField(
        "头像",
        upload_to="avatars/%Y/%m/",
        blank=True,
        null=True,
        validators=[validate_image_upload],
    )
    bio = models.CharField("一句话简介", max_length=200, blank=True)

    class Meta:
        verbose_name = "用户"
        verbose_name_plural = "用户"
        ordering = ["-date_joined"]

    def __str__(self):
        return self.display_name

    def save(self, *args, **kwargs):
        if not self.nickname:
            self.nickname = self.username
        super().save(*args, **kwargs)

    @property
    def display_name(self) -> str:
        return self.nickname or self.username

    @property
    def initial(self) -> str:
        """用于无头像时的首字母色块。"""
        name = self.display_name.strip()
        return name[0].upper() if name else "?"

    def get_absolute_url(self):
        return reverse("accounts:profile")
