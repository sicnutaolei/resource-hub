from django.conf import settings as django_settings
from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from core.models import SiteSetting
from resources.models import Category, DownloadLink, Resource, Tag

from .decorators import admin_required
from .forms import (
    DownloadLinkFormSet,
    LibraryForm,
    SiteSettingsForm,
    SoftwareForm,
    StyledPasswordChangeForm,
    TagForm,
    UpdateLogFormSet,
)

PAGE_SIZE = 20


@admin_required
def index(request):
    counts = {
        "software": Resource.objects.count(),
        "public": Resource.objects.filter(is_public=True).count(),
        "private": Resource.objects.filter(is_public=False).count(),
        "libraries": Category.objects.count(),
        "tags": Tag.objects.count(),
        "broken_links": DownloadLink.objects.filter(
            link_type=DownloadLink.EXTERNAL, is_broken=True, is_active=True
        ).count(),
    }
    recent = (
        Resource.objects.select_related("category")
        .prefetch_related("tags")
        .order_by("-updated_at")[:6]
    )
    return render(request, "manage/index.html", {"counts": counts, "recent": recent})


# ---------------------------- 软件 ----------------------------
@admin_required
def software_list(request):
    query = (request.GET.get("q") or "").strip()
    visibility = request.GET.get("visibility") or ""
    if visibility not in ("public", "private"):
        visibility = ""
    library_raw = request.GET.get("library") or ""
    library_id = int(library_raw) if library_raw.isdigit() else None

    queryset = (
        Resource.objects.select_related("category")
        .prefetch_related("tags")
        .annotate(link_total=Count("links"))
    )
    if query:
        queryset = queryset.filter(
            Q(title__icontains=query)
            | Q(summary__icontains=query)
            | Q(description__icontains=query)
            | Q(version__icontains=query)
            | Q(tags__name__icontains=query)
        ).distinct()
    if visibility == "public":
        queryset = queryset.filter(is_public=True)
    elif visibility == "private":
        queryset = queryset.filter(is_public=False)
    if library_id:
        queryset = queryset.filter(category_id=library_id)

    queryset = queryset.order_by("-updated_at")
    page_obj = Paginator(queryset, PAGE_SIZE).get_page(request.GET.get("page"))

    libraries = Category.objects.annotate(
        total=Count("resources")
    ).order_by("order", "id")
    selected_library = (
        libraries.filter(pk=library_id).first() if library_id else None
    )

    return render(
        request,
        "manage/software_list.html",
        {
            "page_obj": page_obj,
            "query": query,
            "visibility": visibility,
            "libraries": libraries,
            "selected_library": selected_library,
            "total_count": page_obj.paginator.count,
        },
    )


def _software_form(request, instance, template, title):
    if request.method == "POST":
        form = SoftwareForm(request.POST, request.FILES, instance=instance)
        link_formset = DownloadLinkFormSet(
            request.POST, request.FILES, instance=instance, prefix="links"
        )
        log_formset = UpdateLogFormSet(
            request.POST, request.FILES, instance=instance, prefix="logs"
        )

        if form.is_valid() and link_formset.is_valid() and log_formset.is_valid():
            with transaction.atomic():
                resource = form.save()
                link_formset.instance = resource
                link_formset.save()
                log_formset.instance = resource
                log_formset.save()
            messages.success(request, f"软件「{resource.title}」已保存。")
            return redirect("manage:software_list")

        messages.error(request, "保存失败，请检查标红的字段。")
    else:
        form = SoftwareForm(instance=instance)
        link_formset = DownloadLinkFormSet(instance=instance, prefix="links")
        log_formset = UpdateLogFormSet(instance=instance, prefix="logs")

    return render(
        request,
        template,
        {
            "form": form,
            "link_formset": link_formset,
            "log_formset": log_formset,
            "form_title": title,
            "is_create": not instance.pk,
        },
    )


@admin_required
def software_create(request):
    return _software_form(request, Resource(), "manage/software_form.html", "新增软件")


@admin_required
def software_edit(request, pk):
    resource = get_object_or_404(Resource, pk=pk)
    return _software_form(
        request, resource, "manage/software_form.html", f"编辑：{resource.title}"
    )


@admin_required
@require_POST
def software_delete(request, pk):
    resource = get_object_or_404(Resource, pk=pk)
    title = resource.title
    resource.delete()
    messages.success(request, f"软件「{title}」已删除。")
    return redirect("manage:software_list")


# ---------------------------- 资源库 ----------------------------
@admin_required
def library_list(request):
    libraries = Category.objects.annotate(total=Count("resources")).order_by(
        "order", "id"
    )
    return render(request, "manage/library_list.html", {"libraries": libraries})


@admin_required
def library_create(request):
    form = LibraryForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        library = form.save()
        messages.success(request, f"资源库「{library.name}」已创建。")
        return redirect("manage:library_list")
    return render(
        request,
        "manage/library_form.html",
        {"form": form, "form_title": "新增资源库"},
    )


@admin_required
def library_edit(request, pk):
    library = get_object_or_404(Category, pk=pk)
    form = LibraryForm(request.POST or None, instance=library)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "资源库已保存。")
        return redirect("manage:library_list")
    return render(
        request,
        "manage/library_form.html",
        {"form": form, "form_title": f"编辑资源库：{library.name}"},
    )


@admin_required
@require_POST
def library_delete(request, pk):
    library = get_object_or_404(Category, pk=pk)
    if library.resources.exists():
        messages.error(request, "该资源库下还有软件，请先移动软件后再删除。")
        return redirect("manage:library_list")
    name = library.name
    library.delete()
    messages.success(request, f"资源库「{name}」已删除。")
    return redirect("manage:library_list")


# ---------------------------- 标签 ----------------------------
@admin_required
def tag_list(request):
    tags = Tag.objects.annotate(total=Count("resources")).order_by("-total", "name")
    return render(request, "manage/tag_list.html", {"tags": tags})


@admin_required
def tag_create(request):
    form = TagForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        tag = form.save()
        messages.success(request, f"标签「{tag.name}」已创建。")
        return redirect("manage:tag_list")
    return render(
        request, "manage/tag_form.html", {"form": form, "form_title": "新增标签"}
    )


@admin_required
def tag_edit(request, pk):
    tag = get_object_or_404(Tag, pk=pk)
    form = TagForm(request.POST or None, instance=tag)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "标签已保存。")
        return redirect("manage:tag_list")
    return render(
        request,
        "manage/tag_form.html",
        {"form": form, "form_title": f"编辑标签：{tag.name}"},
    )


@admin_required
@require_POST
def tag_delete(request, pk):
    tag = get_object_or_404(Tag, pk=pk)
    if tag.resources.exists():
        messages.error(request, "该标签仍被软件使用，先解除关联后再删除。")
        return redirect("manage:tag_list")
    name = tag.name
    tag.delete()
    messages.success(request, f"标签「{name}」已删除。")
    return redirect("manage:tag_list")


# ---------------------------- 站点设置 / 账号 ----------------------------
@admin_required
def site_settings(request):
    initial = {
        "site_name": SiteSetting.get("site_name", django_settings.SITE_NAME),
        "homepage_slogan": SiteSetting.get(
            "homepage_slogan", django_settings.SITE_SLOGAN
        ),
    }
    form = SiteSettingsForm(request.POST or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        SiteSetting.set("site_name", form.cleaned_data["site_name"])
        SiteSetting.set("homepage_slogan", form.cleaned_data["homepage_slogan"])
        messages.success(request, "站点设置已保存，首页已生效。")
        return redirect("manage:settings")
    return render(request, "manage/settings.html", {"form": form, "initial": initial})


@admin_required
def account(request):
    user = request.user
    form = StyledPasswordChangeForm(user=user, data=request.POST or None)

    if request.method == "POST" and form.is_valid():
        form.save()
        user.must_change_password = False
        user.save(update_fields=["must_change_password"])
        update_session_auth_hash(request, user)
        messages.success(request, "密码已更新。")
        return redirect("manage:index")

    return render(
        request,
        "manage/account.html",
        {
            "form": form,
            "forced": user.must_change_password,
        },
    )