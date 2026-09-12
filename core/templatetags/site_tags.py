from django import template
from django.utils.html import format_html
from django.utils.safestring import mark_safe

register = template.Library()


@register.simple_tag(takes_context=True)
def url_with(context, **kwargs):
    """
    在当前 URL 的基础上替换部分查询参数，其余参数原样保留。

    用法：
        {% url_with sort='hot' page='' %}   排序并回到第一页
        {% url_with page=page_obj.next_page_number %}
    传入空字符串表示删除该参数。
    """
    request = context.get("request")
    if request is None:
        return ""

    params = request.GET.copy()
    for key, value in kwargs.items():
        if value is None or value == "":
            params.pop(key, None)
        else:
            params[key] = value

    query = params.urlencode()
    return f"{request.path}?{query}" if query else request.path


@register.simple_tag(takes_context=True)
def is_active(context, *url_names, css_class="active"):
    """
    当前视图匹配任一 url name 时返回 css_class。

    同时接受带命名空间和不带命名空间的写法：
        {% is_active 'home' %}
        {% is_active 'resources:home' %}
    """
    request = context.get("request")
    if request is None:
        return ""
    match = request.resolver_match
    if match is None:
        return ""

    candidates = {match.url_name}
    if match.namespace:
        candidates.add(f"{match.namespace}:{match.url_name}")
    return css_class if candidates.intersection(url_names) else ""


@register.filter
def cover_style(resource):
    """给没有封面图的卡片生成一个稳定的渐变色块样式（同一资源颜色固定）。"""
    palette = [
        ("#4B45C6", "#7B6CF6"),
        ("#1F7A6B", "#3FB49B"),
        ("#B5462F", "#E2624B"),
        ("#8A5A00", "#D9A22E"),
        ("#31547A", "#5B8DC4"),
        ("#7A3163", "#C05A9B"),
    ]
    seed = (resource.pk or 0) + len(resource.title or "")
    start, end = palette[seed % len(palette)]
    return format_html("--cover-a:{};--cover-b:{};", start, end)


@register.filter
def first_char(resource):
    title = (resource.title or "?").strip()
    return title[0] if title else "?"


@register.filter
def stars(count):
    """把数字渲染成 ★ 串，最多 5 颗，用于简单的热度展示。"""
    try:
        count = int(count)
    except (TypeError, ValueError):
        count = 0
    level = min(5, max(1, count // 20 + 1)) if count else 1
    return mark_safe("".join("★" if index < level else "☆" for index in range(5)))


@register.filter
def truncate_middle(value, length=28):
    text = str(value or "")
    length = int(length)
    if len(text) <= length:
        return text
    head = (length - 1) // 2
    tail = length - head - 1
    return f"{text[:head]}…{text[-tail:]}"
