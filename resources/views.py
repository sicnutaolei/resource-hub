import logging
import os
from pathlib import Path

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from .forms import CommentForm
from .models import Category, DownloadLink, Favorite, Resource, Tag, UpdateLog

logger = logging.getLogger(__name__)

SORT_OPTIONS = {
    "updated": ("最近更新", ("-is_pinned", "-updated_at")),
    "newest": ("最新收录", ("-created_at",)),
    "hot": ("最多浏览", ("-views", "-updated_at")),
}


def _base_resource_queryset():
    """
    列表页统一走这个 queryset。

    关键点：tags 是多对多（反向外键），必须用 prefetch_related，
    select_related 对 M2M 无效，会退化成 N+1 查询。
    """
    return (
        Resource.objects.filter(is_published=True)
        .select_related("category")
        .prefetch_related("tags")
        .annotate(comment_total=Count("comments", filter=Q(comments__is_active=True), distinct=True))
    )


def home(request):
    pinned = list(
        _base_resource_queryset().filter(is_pinned=True).order_by("-updated_at")[:6]
    )
    pinned_ids = [item.pk for item in pinned]

    # 注意：annotate(Count(...)) 会清掉 Meta.ordering，
    # 这里必须显式 order_by，否则分页结果不稳定并触发 UnorderedObjectListWarning
    latest_qs = (
        _base_resource_queryset().exclude(pk__in=pinned_ids).order_by("-updated_at")
    )
    paginator = Paginator(latest_qs, settings.PAGE_SIZE)
    page_obj = paginator.get_page(request.GET.get("page"))

    recent_logs = (
        UpdateLog.objects.select_related("resource", "resource__category")
        .filter(resource__is_published=True)
        .order_by("-created_at")[:8]
    )

    stats = {
        "resources": Resource.objects.filter(is_published=True).count(),
        "categories": Category.objects.count(),
        "logs": UpdateLog.objects.count(),
    }

    return render(
        request,
        "resources/home.html",
        {
            "pinned_resources": pinned,
            "page_obj": page_obj,
            "recent_logs": recent_logs,
            "stats": stats,
            "page_title": "首页",
        },
    )


def resource_list(request):
    """分类页 / 标签页 / 搜索结果页共用。"""
    queryset = _base_resource_queryset()

    category = None
    tag = None
    query = (request.GET.get("q") or "").strip()

    category_key = request.GET.get("category") or ""
    if category_key:
        lookup = {"pk": int(category_key)} if category_key.isdigit() else {"slug": category_key}
        category = get_object_or_404(Category, **lookup)

    tag_key = request.GET.get("tag") or ""
    if tag_key:
        lookup = {"pk": int(tag_key)} if tag_key.isdigit() else {"slug": tag_key}
        tag = get_object_or_404(Tag, **lookup)

    if category:
        queryset = queryset.filter(category=category)
    if tag:
        queryset = queryset.filter(tags=tag)
    if query:
        queryset = queryset.filter(
            Q(title__icontains=query)
            | Q(summary__icontains=query)
            | Q(description__icontains=query)
            | Q(version__icontains=query)
            | Q(tags__name__icontains=query)
        ).distinct()

    sort = request.GET.get("sort") or "updated"
    if sort not in SORT_OPTIONS:
        sort = "updated"
    queryset = queryset.order_by(*SORT_OPTIONS[sort][1])

    paginator = Paginator(queryset, settings.PAGE_SIZE)
    page_obj = paginator.get_page(request.GET.get("page"))

    if category:
        page_title = f"分类：{category.name}"
    elif tag:
        page_title = f"标签：{tag.name}"
    elif query:
        page_title = f"搜索：{query}"
    else:
        page_title = "全部资源"

    return render(
        request,
        "resources/list.html",
        {
            "page_obj": page_obj,
            "category": category,
            "tag": tag,
            "query": query,
            "sort": sort,
            "sort_options": SORT_OPTIONS,
            "page_title": page_title,
            "total_count": paginator.count,
        },
    )


def _resolve_resource(key: str):
    queryset = (
        Resource.objects.filter(is_published=True)
        .select_related("category")
        .prefetch_related("tags", "links")
    )
    lookup = {"pk": int(key)} if key.isdigit() else {"slug": key}
    return queryset.filter(**lookup).first()


def resource_detail(request, key):
    resource = _resolve_resource(key)
    if resource is None:
        raise Http404("资源不存在或未发布")

    resource.bump_views()
    resource.views += 1  # 让当前页面显示的数字与数据库一致

    comments = resource.comments.filter(is_active=True).select_related("user")

    related = (
        Resource.objects.filter(is_published=True)
        .exclude(pk=resource.pk)
        .select_related("category")
        .prefetch_related("tags")
    )
    if resource.category_id:
        related = related.filter(category_id=resource.category_id)
    related = list(related.order_by("-updated_at")[:4])
    if len(related) < 4:
        extra = (
            Resource.objects.filter(is_published=True, tags__in=resource.tags.all())
            .exclude(pk__in=[resource.pk] + [item.pk for item in related])
            .select_related("category")
            .prefetch_related("tags")
            .distinct()
            .order_by("-updated_at")[: 4 - len(related)]
        )
        related.extend(extra)

    is_favorited = False
    if request.user.is_authenticated:
        is_favorited = Favorite.objects.filter(
            user=request.user, resource=resource
        ).exists()

    return render(
        request,
        "resources/detail.html",
        {
            "resource": resource,
            "local_links": resource.local_links,
            "external_links": resource.external_links,
            "logs": resource.logs.all(),
            "comments": comments,
            "comment_form": CommentForm(),
            "is_favorited": is_favorited,
            "related": related,
            "page_title": resource.title,
        },
    )


def category_detail(request, key):
    lookup = {"pk": int(key)} if str(key).isdigit() else {"slug": key}
    category = get_object_or_404(Category, **lookup)
    return redirect(f"{reverse('resources:list')}?category={category.slug or category.pk}")


def tag_detail(request, key):
    lookup = {"pk": int(key)} if str(key).isdigit() else {"slug": key}
    tag = get_object_or_404(Tag, **lookup)
    return redirect(f"{reverse('resources:list')}?tag={tag.slug or tag.pk}")


def changelog(request):
    queryset = (
        UpdateLog.objects.select_related("resource", "resource__category")
        .filter(resource__is_published=True)
        .order_by("-created_at")
    )
    paginator = Paginator(queryset, settings.PAGE_SIZE * 2)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(
        request,
        "resources/changelog.html",
        {"page_obj": page_obj, "page_title": "资源更新日志"},
    )


def tag_cloud(request):
    tags = (
        Tag.objects.annotate(
            total=Count("resources", filter=Q(resources__is_published=True))
        )
        .filter(total__gt=0)
        .order_by("-total", "name")
    )
    categories = Category.objects.annotate(
        total=Count("resources", filter=Q(resources__is_published=True))
    ).order_by("order", "id")

    return render(
        request,
        "resources/tags.html",
        {"tags": tags, "categories": categories, "page_title": "标签与分类"},
    )


def download_local(request, pk):
    """本地文件下载：校验路径必须落在 MEDIA_ROOT 内，防目录穿越。"""
    link = get_object_or_404(
        DownloadLink.objects.select_related("resource"),
        pk=pk,
        link_type=DownloadLink.LOCAL,
        is_active=True,
        resource__is_published=True,
    )

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


@require_POST
@login_required
def toggle_favorite(request, pk):
    resource = get_object_or_404(Resource, pk=pk, is_published=True)
    favorite, created = Favorite.objects.get_or_create(
        user=request.user, resource=resource
    )
    if not created:
        favorite.delete()

    favorited = created
    total = Favorite.objects.filter(resource=resource).count()

    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse(
            {
                "ok": True,
                "favorited": favorited,
                "total": total,
                "message": "已加入收藏" if favorited else "已取消收藏",
            }
        )

    messages.success(request, "已加入收藏" if favorited else "已取消收藏")
    next_url = request.POST.get("next") or request.META.get("HTTP_REFERER") or "/"
    if not url_has_allowed_host_and_scheme(
        next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        next_url = "/"
    return redirect(next_url)


@require_POST
@login_required
def comment_create(request, pk):
    resource = get_object_or_404(Resource, pk=pk, is_published=True)
    form = CommentForm(request.POST)

    if form.is_valid():
        comment = form.save(commit=False)
        comment.resource = resource
        comment.user = request.user
        comment.save()
        messages.success(request, "评论已发布。")
    else:
        for errors in form.errors.values():
            for error in errors:
                messages.error(request, error)

    return redirect(f"{resource.get_absolute_url()}#comments")
