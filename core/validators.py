"""上传文件校验：体积上限与图片类型。

这里是 `settings.MAX_UPLOAD_SIZE_MB` 唯一真正生效的地方。注意不要把它当成
「可以随便调大的软配置」——它同时也是一道防止误传超大文件把磁盘写满的护栏。
"""

from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError

# 允许的图片扩展名。
# 刻意不放 svg：SVG 可以内嵌 <script>，而本站 media 与站点同源提供，
# 上传的 SVG 被浏览器直接打开时能执行脚本。封面图用 png/jpg/webp 足够。
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"}

_SIZE_UNITS = ("B", "KB", "MB", "GB", "TB")


def human_size(num_bytes: int) -> str:
    """把字节数格式化成人类可读的体积。"""
    value = float(num_bytes)
    for unit in _SIZE_UNITS:
        if value < 1024 or unit == _SIZE_UNITS[-1]:
            return f"{value:.0f} {unit}" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1024
    return f"{num_bytes} B"


def upload_size_limit() -> int:
    """当前生效的单文件上限（字节）。"""
    return int(settings.MAX_UPLOAD_SIZE_MB) * 1024 * 1024


def validate_upload_size(file):
    """拦截超过 MAX_UPLOAD_SIZE_MB 的上传。"""
    if file is None:
        return

    size = getattr(file, "size", None)
    if size is None:
        return

    limit = upload_size_limit()
    if size > limit:
        raise ValidationError(
            "文件体积 %(actual)s，超过上限 %(limit)s。"
            "大文件请改走网盘外链，不要直传服务器。",
            code="file_too_large",
            params={"actual": human_size(size), "limit": human_size(limit)},
        )


def validate_image_upload(file):
    """图片上传：先查体积，再查扩展名。"""
    validate_upload_size(file)

    if file is None:
        return

    suffix = Path(getattr(file, "name", "") or "").suffix.lower()
    if suffix and suffix not in IMAGE_EXTENSIONS:
        raise ValidationError(
            "只允许上传 %(allowed)s 格式的图片。",
            code="invalid_image_type",
            params={"allowed": "、".join(sorted(IMAGE_EXTENSIONS))},
        )
