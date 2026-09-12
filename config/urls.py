from django.conf import settings
from django.contrib import admin
from django.urls import include, path, re_path
from django.views.static import serve

from core import views as core_views

admin.site.site_header = f"{settings.SITE_NAME} 管理后台"
admin.site.site_title = f"{settings.SITE_NAME} 管理后台"
admin.site.index_title = "站点管理"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("accounts.urls")),
    path("", include("resources.urls")),
    path("", include("core.urls")),
]

# 媒体文件（封面图 + 本地小文件）的访问方式：
# - DEBUG=True 或 SERVE_MEDIA=True：由 Django 直接返回，部署简单，
#   适合「几百资源 + 几个用户」的规模。
# - 若用 nginx / 飞牛网关托管 /media/，把 SERVE_MEDIA 设为 False 走代理，
#   吞吐更好。详见 README。
if settings.DEBUG or getattr(settings, "SERVE_MEDIA", True):
    urlpatterns += [
        re_path(
            r"^media/(?P<path>.*)$",
            serve,
            {"document_root": settings.MEDIA_ROOT},
            name="media",
        )
    ]

handler404 = "core.views.page_not_found"
handler500 = "core.views.server_error"
