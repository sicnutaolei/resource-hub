from django.db import connection
from django.http import JsonResponse
from django.shortcuts import render

from resources.models import Category, Resource, UpdateLog


def about(request):
    """关于页：顺带展示站点数据，纯静态站也能有点内容。"""
    stats = {
        "resources": Resource.objects.filter(is_published=True).count(),
        "categories": Category.objects.count(),
        "logs": UpdateLog.objects.count(),
    }
    return render(
        request, "core/about.html", {"stats": stats, "page_title": "关于本站"}
    )


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
        "Disallow: /admin/",
        "Disallow: /accounts/",
        f"Sitemap: {request.build_absolute_uri('/')}",
    ]
    return JsonResponse("\n".join(lines), safe=False, content_type="text/plain")


def page_not_found(request, exception=None):
    return render(request, "404.html", status=404)


def server_error(request):
    return render(request, "500.html", status=500)
