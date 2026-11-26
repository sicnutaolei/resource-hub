from django.conf import settings
from django.contrib import messages
from django.contrib.auth.views import LoginView, LogoutView
from django.urls import reverse_lazy

from core.models import SiteSetting

from .forms import AdminLoginForm


class SiteLoginView(LoginView):
    template_name = "accounts/login.html"
    authentication_form = AdminLoginForm
    redirect_authenticated_user = True

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Django LoginView 会把 django.contrib.sites 的 site_name 塞进来；
        # 未安装 sites 时它就是主机名，会覆盖站点设置里的名称。
        context["site_name"] = SiteSetting.get("site_name", settings.SITE_NAME)
        return context

    def form_valid(self, form):
        messages.success(self.request, f"欢迎回来，{form.get_user().display_name}")
        return super().form_valid(form)


class SiteLogoutView(LogoutView):
    next_page = reverse_lazy("resources:home")