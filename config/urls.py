from django.conf import settings
from django.urls import include, path, re_path
from django.views.generic import RedirectView
from django.views.static import serve

urlpatterns = [
    # 旧的 Django admin 已整体移除；仅保留一个入口跳转到新后台，避免旧书签 404。
    # 权限/组管理等 /admin/... 子路径不再注册，访问会直接 404。
    path("admin/", RedirectView.as_view(url="/manage/", permanent=False)),
    path("accounts/", include("accounts.urls")),
    path("manage/", include("dashboard.urls")),
    path("", include("resources.urls")),
    path("", include("core.urls")),
]

# 媒体文件（封面图 + 本地小文件）的访问方式：
# - DEBUG=True 或 SERVE_MEDIA=True：由 Django 直接返回，部署简单，
#   适合「几百资源 + 几个管理员」的规模。
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