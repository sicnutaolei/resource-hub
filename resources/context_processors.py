from django.conf import settings
from django.db.models import Count, Q

from .models import Category, Tag


def site_context(request):
    """全站通用上下文：站点信息 + 侧栏分类 + 热门标签。"""
    context = {
        "site_name": settings.SITE_NAME,
        "site_subtitle": settings.SITE_SUBTITLE,
        "site_footer": settings.SITE_FOOTER,
    }

    # 后台页面不需要这些数据，省掉两次查询
    if request.path.startswith("/admin/"):
        context["nav_categories"] = []
        context["nav_tags"] = []
        return context

    context["nav_categories"] = (
        Category.objects.annotate(
            total=Count("resources", filter=Q(resources__is_published=True))
        ).order_by("order", "id")
    )
    context["nav_tags"] = (
        Tag.objects.annotate(
            total=Count("resources", filter=Q(resources__is_published=True))
        )
        .filter(total__gt=0)
        .order_by("-total", "name")[:24]
    )
    return context
