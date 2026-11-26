from django.conf import settings
from django.contrib import messages
from django.contrib.auth import logout
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.http import urlencode


class AdminAccessMiddleware:
    """两条硬约束：

    1. 只有管理员可以保持登录态；其他账号的旧会话会被立刻注销。
    2. 自动创建的管理员首次登录必须先改密码，改完才能进入后台。
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)

        if user is not None and user.is_authenticated:
            if not (user.is_staff or user.is_superuser):
                logout(request)
                if request.path != reverse("accounts:login"):
                    query = urlencode({"next": request.get_full_path()})
                    return redirect(f"{reverse('accounts:login')}?{query}")
            elif getattr(user, "must_change_password", False):
                allowed = {
                    reverse("accounts:login"),
                    reverse("accounts:logout"),
                    reverse("manage:account"),
                    reverse("core:healthz"),
                }
                is_asset = request.path.startswith(
                    settings.STATIC_URL
                ) or request.path.startswith(settings.MEDIA_URL)
                if request.path not in allowed and not is_asset:
                    messages.info(request, "首次登录请先修改默认密码。")
                    return redirect("manage:account")

        return self.get_response(request)