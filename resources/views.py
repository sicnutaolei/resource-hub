import logging
import os
from pathlib import Path

from django.conf import settings
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import FileResponse, Http404, HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from .models import DownloadLink, Resource, Tag
from .selectors import filter_tags, is_admin, visible_resources

logger = logging.getLogger(__name__)

PAGE_SIZE_CHOICES = tuple(getattr(settings, "PAGE_SIZE_CHOICES", (20, 24, 30)))


def _parse_page_size(raw) -> int:
    try:
        size = int(raw)
    except (TypeError, ValueError):
        return settings.PAGE_SIZE
    return size if size in PAGE_SIZE_CHOICES else settings.PAGE_SIZE


def _selected_tag(tag_key: str):
    tag_key = (tag_key or "").strip()
    if not tag_key:
        return None
    if tag_key.isdigit():
        return Tag.objects.filter(pk=int(tag_key)).first()
    return Tag.objects.filter(slug=tag_key).first()


def home(request):
    """首页：公开软件网格，搜索 / 标签 / 分页全部服务端查询。"""
    query = (request.GET.get("q") or "").strip()
    tag_key = request.GET.get("tag") or ""
    page_size = _parse_page_size(request.GET.get("size"))

    queryset = (
        visible_resources(request.user)
        .select_related("category")
        .prefetch_related("tags")
    )

    if query:
        queryset = queryset.filter(
            Q(title__icontains=query)
            | Q(summary__icontains=query)
            | Q(description__icontains=query)
            | Q(tags__name__icontains=query)
        ).distinct()

    selected_tag = _selected_tag(tag_key)
    if tag_key:
        if selected_tag is None:
            queryset = queryset.none()
        else:
            queryset = queryset.filter(tags=selected_tag)

    queryset = queryset.order_by("-updated_at")
    paginator = Paginator(queryset, page_size)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(
        request,
        "resources/home.html",
        {
            "page_obj": page_obj,
            "query": query,
            "selected_tag": selected_tag,
            "tag_filters": filter_tags(request.user),
            "page_size": page_size,
            "page_size_choices": PAGE_SIZE_CHOICES,
            "total_count": paginator.count,
            "is_admin_user": is_admin(request.user),
        },
    )


def resource_detail(request, key):
    queryset = (
        Resource.objects.select_related("category")
        .prefetch_related("tags", "links", "logs")
    )
    if not is_admin(request.user):
        queryset = queryset.filter(is_public=True)

    lookup = {"pk": int(key)} if str(key).isdigit() else {"slug": key}
    resource = queryset.filter(**lookup).first()
    if resource is None:
        raise Http404("软件不存在或未公开")

    resource.bump_views()
    resource.views += 1

    links = [link for link in resource.links.all() if link.is_active]

    return render(
        request,
        "resources/detail.html",
        {
            "resource": resource,
            "local_links": [
                link for link in links if link.link_type == DownloadLink.LOCAL
            ],
            "external_links": [
                link for link in links if link.link_type == DownloadLink.EXTERNAL
            ],
            "logs": list(resource.logs.all()),
            "is_admin_user": is_admin(request.user),
        },
    )


def download(request, pk):
    """统一下载入口：本地文件直接返回，外链校验后 302 跳转。

    未登录访客只能下载公开软件的链接；非公开软件统一 404，避免泄露存在性。
    """
    link = get_object_or_404(
        DownloadLink.objects.select_related("resource"),
        pk=pk,
        is_active=True,
    )

    if not link.resource.is_public and not is_admin(request.user):
        raise Http404("软件不存在或未公开")

    if link.link_type == DownloadLink.LOCAL:
        if not link.file:
            raise Http404("文件不存在")

        media_root = Path(settings.MEDIA_ROOT).resolve()
        try:
            file_path = Path(link.file.path).resolve(strict=True)
        except (FileNotFoundError, OSError):
            logger.warning("本地文件缺失：link=%s path=%s", pk, link.file.name)
            raise Http404("文件已丢失，请联系管理员")

        if os.path.commonpath([str(file_path), str(media_root)]) != str(media_root):
            logger.error("检测到越界文件路径：%s", file_path)
            raise Http404("非法文件路径")

        link.bump_downloads()
        response = FileResponse(
            open(file_path, "rb"), as_attachment=True, filename=file_path.name
        )
        response["X-Content-Type-Options"] = "nosniff"
        return response

    if not link.url.lower().startswith(("http://", "https://")):
        raise Http404("外链地址无效")

    link.bump_downloads()
    response = HttpResponseRedirect(link.url)
    response["X-Robots-Tag"] = "noindex, nofollow"
    return response


# ---------------------------- 旧链接兼容 ----------------------------
def legacy_list(request):
    query = request.GET.urlencode()
    target = reverse("resources:home")
    return redirect(f"{target}?{query}" if query else target)


def legacy_category(request, key):
    return redirect("resources:home")


def legacy_tag(request, key):
    tag = _selected_tag(str(key))
    if tag is None:
        return redirect("resources:home")
    return redirect(f"{reverse('resources:home')}?tag={tag.pk}")


def legacy_home(request):
    return redirect("resources:home")