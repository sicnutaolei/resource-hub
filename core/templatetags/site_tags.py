from django import template

register = template.Library()


@register.simple_tag(takes_context=True)
def url_with(context, **kwargs):
    """在当前 URL 基础上替换部分查询参数，其余参数原样保留。

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
    """当前视图匹配任一 url name 时返回 css_class。"""
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