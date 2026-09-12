from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify

from core.validators import human_size, validate_image_upload, validate_upload_size


def unique_slugify(instance, value: str, slug_field: str = "slug") -> str:
    """
    生成不冲突的 slug。

    中文标题经 slugify 后通常为空，此时返回空串，
    由 get_absolute_url 回退到 /r/<pk>/ 形式的 URL。
    """
    base = slugify(value)[:120]
    if not base:
        return ""

    model = instance.__class__
    candidate = base
    index = 1
    while (
        model.objects.filter(**{slug_field: candidate})
        .exclude(pk=instance.pk)
        .exists()
    ):
        index += 1
        candidate = f"{base}-{index}"
    return candidate


class Category(models.Model):
    name = models.CharField("分类名", max_length=50, unique=True)
    slug = models.SlugField("URL 标识", max_length=60, blank=True, db_index=True)
    description = models.CharField("描述", max_length=200, blank=True)
    order = models.IntegerField("排序", default=100, help_text="数字越小越靠前")
    created_at = models.DateTimeField("创建时间", auto_now_add=True)

    class Meta:
        verbose_name = "分类"
        verbose_name_plural = "分类"
        ordering = ["order", "id"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slugify(self, self.name)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        key = self.slug or self.pk
        return reverse("resources:category", args=[key])


class Tag(models.Model):
    name = models.CharField("标签名", max_length=40, unique=True)
    slug = models.SlugField("URL 标识", max_length=60, blank=True, db_index=True)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)

    class Meta:
        verbose_name = "标签"
        verbose_name_plural = "标签"
        ordering = ["name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slugify(self, self.name)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        key = self.slug or self.pk
        return reverse("resources:tag", args=[key])


class Resource(models.Model):
    """资源条目：软件名 / 版本 / 说明，关联多个下载链接与更新日志。"""

    title = models.CharField("资源名称", max_length=150)
    slug = models.SlugField(
        "URL 标识",
        max_length=140,
        blank=True,
        db_index=True,
        help_text="留空自动生成；中文标题自动生成会为空，此时 URL 使用数字 ID",
    )
    category = models.ForeignKey(
        Category,
        verbose_name="分类",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="resources",
    )
    tags = models.ManyToManyField(
        Tag, verbose_name="标签", blank=True, related_name="resources"
    )

    summary = models.CharField(
        "卡片摘要",
        max_length=200,
        blank=True,
        help_text="列表页展示的一句话介绍，留空则自动截取简介前 60 字",
    )
    description = models.TextField(
        "详细介绍", blank=True, help_text="支持换行；建议写软件简介、本版特点"
    )
    version = models.CharField("当前版本", max_length=60, blank=True)
    cover_image = models.ImageField(
        "封面图",
        upload_to="covers/%Y/%m/",
        blank=True,
        null=True,
        validators=[validate_image_upload],
    )

    is_published = models.BooleanField("已发布", default=True)
    is_pinned = models.BooleanField("首页置顶", default=False)
    views = models.PositiveIntegerField("浏览量", default=0)

    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        verbose_name = "资源"
        verbose_name_plural = "资源"
        ordering = ["-is_pinned", "-updated_at"]
        indexes = [
            models.Index(fields=["-updated_at"]),
            models.Index(fields=["is_published", "-is_pinned", "-updated_at"]),
        ]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slugify(self, self.title)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        key = self.slug or self.pk
        return reverse("resources:detail", args=[key])

    @property
    def display_summary(self) -> str:
        if self.summary:
            return self.summary
        text = " ".join(self.description.split())
        return text[:60] + ("…" if len(text) > 60 else "")

    @property
    def local_links(self):
        return [link for link in self.links.all() if link.link_type == DownloadLink.LOCAL]

    @property
    def external_links(self):
        return [
            link for link in self.links.all() if link.link_type == DownloadLink.EXTERNAL
        ]

    @property
    def has_local_file(self) -> bool:
        return any(link.link_type == DownloadLink.LOCAL for link in self.links.all())

    @property
    def latest_log(self):
        return self.logs.first()

    def bump_views(self):
        """用 F 表达式自增，避免读改写竞态。"""
        Resource.objects.filter(pk=self.pk).update(views=models.F("views") + 1)


class DownloadLink(models.Model):
    """一个下载入口：要么是本地文件，要么是外部网盘链接。"""

    LOCAL = "local"
    EXTERNAL = "external"
    LINK_TYPE_CHOICES = [
        (LOCAL, "本地文件（服务器磁盘）"),
        (EXTERNAL, "外部链接（网盘）"),
    ]

    resource = models.ForeignKey(
        Resource, verbose_name="所属资源", on_delete=models.CASCADE, related_name="links"
    )
    label = models.CharField(
        "按钮名称", max_length=50, help_text="例如：本地下载 / 百度网盘 / 蓝奏云"
    )
    link_type = models.CharField(
        "链接类型", max_length=20, choices=LINK_TYPE_CHOICES, default=EXTERNAL
    )
    file = models.FileField(
        "本地文件",
        upload_to="files/%Y/%m/",
        blank=True,
        null=True,
        help_text="link_type=本地文件 时必填",
        validators=[validate_upload_size],
    )
    url = models.URLField(
        "外链地址",
        blank=True,
        help_text="link_type=外部链接 时必填，包含 https:// 前缀",
    )
    extract_code = models.CharField(
        "提取码", max_length=30, blank=True, help_text="网盘提取码，可留空"
    )
    file_size = models.BigIntegerField("文件大小（字节）", null=True, blank=True)
    order = models.IntegerField("排序", default=10, help_text="数字越小越靠前")
    is_active = models.BooleanField("启用", default=True)
    is_broken = models.BooleanField(
        "外链疑似失效", default=False, help_text="由「检查外链状态」任务自动标记"
    )
    last_checked_at = models.DateTimeField("最后检测时间", null=True, blank=True)
    downloads = models.PositiveIntegerField("下载次数", default=0)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)

    class Meta:
        verbose_name = "下载链接"
        verbose_name_plural = "下载链接"
        ordering = ["order", "id"]

    def __str__(self):
        return f"{self.resource.title} · {self.label}"

    def clean(self):
        from django.core.exceptions import ValidationError

        if self.link_type == self.LOCAL and not self.file:
            raise ValidationError({"file": "选择「本地文件」时必须上传文件。"})
        if self.link_type == self.EXTERNAL and not self.url:
            raise ValidationError({"url": "选择「外部链接」时必须填写外链地址。"})

    def save(self, *args, **kwargs):
        if self.link_type == self.LOCAL and self.file and not self.file_size:
            try:
                self.file_size = self.file.size
            except (OSError, ValueError):
                self.file_size = None
        if self.link_type == self.EXTERNAL:
            self.file = None
        super().save(*args, **kwargs)

    @property
    def size_display(self) -> str:
        return human_size(self.file_size) if self.file_size else ""

    def bump_downloads(self):
        DownloadLink.objects.filter(pk=self.pk).update(
            downloads=models.F("downloads") + 1
        )


class UpdateLog(models.Model):
    """资源更新日志：某资源在某个版本改了什么。"""

    resource = models.ForeignKey(
        Resource, verbose_name="所属资源", on_delete=models.CASCADE, related_name="logs"
    )
    version = models.CharField("版本号", max_length=60)
    content = models.TextField("更新内容", help_text="一条一行，或用换行分隔多条")
    created_at = models.DateTimeField("记录时间", default=timezone.now)

    class Meta:
        verbose_name = "更新日志"
        verbose_name_plural = "更新日志"
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return f"{self.resource.title} {self.version}"

    @property
    def lines(self):
        return [line.strip(" ·-\t") for line in self.content.splitlines() if line.strip()]


class Comment(models.Model):
    """资源评论：登录用户可见、可发。"""

    resource = models.ForeignKey(
        Resource,
        verbose_name="所属资源",
        on_delete=models.CASCADE,
        related_name="comments",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="评论者",
        on_delete=models.CASCADE,
        related_name="comments",
    )
    content = models.TextField("评论内容", max_length=1000)
    is_active = models.BooleanField("显示", default=True)
    created_at = models.DateTimeField("评论时间", auto_now_add=True)

    class Meta:
        verbose_name = "评论"
        verbose_name_plural = "评论"
        ordering = ["created_at"]
        indexes = [models.Index(fields=["resource", "-created_at"])]

    def __str__(self):
        return f"{self.user.display_name}：{self.content[:20]}"


class Favorite(models.Model):
    """收藏：注册用户的唯一动机来源。"""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="用户",
        on_delete=models.CASCADE,
        related_name="favorites",
    )
    resource = models.ForeignKey(
        Resource,
        verbose_name="资源",
        on_delete=models.CASCADE,
        related_name="favorited_by",
    )
    created_at = models.DateTimeField("收藏时间", auto_now_add=True)

    class Meta:
        verbose_name = "收藏"
        verbose_name_plural = "收藏"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "resource"], name="uniq_favorite_user_resource"
            )
        ]

    def __str__(self):
        return f"{self.user.display_name} 收藏了 {self.resource.title}"
