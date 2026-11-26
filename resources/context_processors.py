from django.conf import settings

from core.models import SiteSetting


def site_context(request):
    """全站通用上下文：站点名称与首页 slogan（均可在后台修改）。"""
    return {
        "site_name": SiteSetting.get("site_name", settings.SITE_NAME),
        "site_slogan": SiteSetting.get("homepage_slogan", settings.SITE_SLOGAN),
    }