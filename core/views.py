from django.db import connection
from django.http import JsonResponse
from django.shortcuts import render

from resources.models import Category, DownloadLink, Resource, Tag


def about(request):
    """关于页：README 风格的站点简介。"""
    stats = {
        "software": Resource.objects.filter(is_public=True).count(),
        "libraries": Category.objects.count(),
        "tags": Tag.objects.count(),
        "downloads": DownloadLink.objects.filter(
            resource__is_public=True, is_active=True
        ).count(),
    }
    return render(request, "core/about.html", {"stats": stats})


def healthz(request):
    """健康检查：容器编排 / 监控用。"""
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except Exception as exc:  # noqa: BLE001
        return JsonResponse(
            {"status": "error", "database": str(exc)}, status=503
        )
    return JsonResponse({"status": "ok", "database": "ok"})


def robots_txt(request):
    lines = [
        "User-agent: *",
        "Disallow: /manage/",
        "Disallow: /accounts/",
        f"Sitemap: {request.build_absolute_uri('/')}",
    ]
    return JsonResponse("\n".join(lines), safe=False, content_type="text/plain")


def page_not_found(request, exception=None):
    return render(request, "404.html", status=404)


def server_error(request):
    return render(request, "500.html", status=500)