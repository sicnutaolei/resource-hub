from django.conf import settings
from django.core.cache import cache
from django.db.models import Count, Q

from .models import Resource, Tag

FILTER_TAGS_CACHE_KEY = "filter_tags"


def is_admin(user) -> bool:
    return bool(
        user
        and user.is_authenticated
        and (user.is_staff or user.is_superuser)
    )


def visible_resources(user):
    """未登录/非管理员只能看到公开软件；管理员可见全部。"""
    queryset = Resource.objects.all()
    if not is_admin(user):
        queryset = queryset.filter(is_public=True)
    return queryset


def filter_tags(user=None, limit: int = 30):
    """首页横向筛选标签，固定取 Tag 表。

    匿名只统计公开软件；管理员统计全部。结果缓存，TTL 很短，
    Tag/Resource 变更时通过 signals 主动失效。
    """
    include_private = is_admin(user)
    key = f"{FILTER_TAGS_CACHE_KEY}:{'all' if include_private else 'public'}"
    cached = cache.get(key)
    if cached is not None:
        return cached

    queryset = Tag.objects.all()
    if include_private:
        queryset = queryset.annotate(total=Count("resources"))
    else:
        queryset = queryset.annotate(
            total=Count("resources", filter=Q(resources__is_public=True))
        )
    queryset = queryset.filter(total__gt=0).order_by("-total", "name")[:limit]
    data = list(queryset.values("id", "name", "slug", "total"))
    cache.set(key, data, settings.FILTER_TAGS_CACHE_TTL)
    return data


def invalidate_filter_tags():
    cache.delete_many(
        [
            f"{FILTER_TAGS_CACHE_KEY}:public",
            f"{FILTER_TAGS_CACHE_KEY}:all",
        ]
    )