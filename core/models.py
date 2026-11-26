from django.conf import settings
from django.core.cache import cache
from django.db import models


class SiteSetting(models.Model):
    """键值形式的站点配置。

    目前使用两个键：
      - site_name       站点名称（标题、页头、页脚）
      - homepage_slogan 首页 slogan

    读取走本地缓存，后台保存时立即失效；多 worker 进程下靠短 TTL 兜底。
    模板输出默认自动转义，不需要也不应该使用 |safe。
    """

    key = models.CharField("配置键", max_length=100, unique=True)
    value = models.TextField("配置值", blank=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        verbose_name = "站点设置"
        verbose_name_plural = "站点设置"
        ordering = ["key"]

    def __str__(self):
        return self.key

    @classmethod
    def cache_key(cls, key: str) -> str:
        return f"site_setting:{key}"

    @classmethod
    def get(cls, key: str, default: str = "") -> str:
        cache_key = cls.cache_key(key)
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        row = cls.objects.filter(key=key).values_list("value", flat=True).first()
        value = row if row is not None else default
        cache.set(cache_key, value, getattr(settings, "SITE_SETTING_CACHE_TTL", 300))
        return value

    @classmethod
    def set(cls, key: str, value: str) -> "SiteSetting":
        obj, _ = cls.objects.update_or_create(key=key, defaults={"value": value})
        cache.delete(cls.cache_key(key))
        return obj