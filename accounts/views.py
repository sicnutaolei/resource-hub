from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import (
    LoginView,
    LogoutView,
    PasswordChangeView,
)
from django.shortcuts import redirect, render
from django.urls import reverse_lazy

from .forms import LoginForm, ProfileForm, RegisterForm, StyledPasswordChangeForm


class SiteLoginView(LoginView):
    template_name = "accounts/login.html"
    authentication_form = LoginForm
    redirect_authenticated_user = True

    def form_valid(self, form):
        messages.success(self.request, f"欢迎回来，{form.get_user().display_name}")
        return super().form_valid(form)


class SiteLogoutView(LogoutView):
    next_page = reverse_lazy("resources:home")


class SitePasswordChangeView(PasswordChangeView):
    template_name = "accounts/password_change.html"
    form_class = StyledPasswordChangeForm
    success_url = reverse_lazy("accounts:profile")

    def form_valid(self, form):
        messages.success(self.request, "密码已更新。")
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, "密码修改失败，请检查下方提示。")
        return super().form_invalid(form)


def register(request):
    """注册即登录，避免多一步操作。"""
    if request.user.is_authenticated:
        return redirect("resources:home")

    if request.method == "POST":
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, "注册成功，欢迎加入！")
            return redirect("resources:home")
        messages.error(request, "注册信息有误，请检查下方提示。")
    else:
        form = RegisterForm()

    return render(request, "accounts/register.html", {"form": form})


@login_required
def profile(request):
    from resources.models import Comment, Favorite

    favorite_list = (
        Favorite.objects.filter(user=request.user)
        .select_related("resource", "resource__category")
        .prefetch_related("resource__tags")
        .order_by("-created_at")
    )
    comment_list = (
        Comment.objects.filter(user=request.user)
        .select_related("resource")
        .order_by("-created_at")
    )

    return render(
        request,
        "accounts/profile.html",
        {
            "favorite_list": favorite_list,
            "comment_list": comment_list,
            "tab": request.GET.get("tab", "favorites"),
        },
    )


@login_required
def profile_edit(request):
    if request.method == "POST":
        form = ProfileForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "资料已保存。")
            return redirect("accounts:profile")
        messages.error(request, "保存失败，请检查下方提示。")
    else:
        form = ProfileForm(instance=request.user)

    return render(request, "accounts/profile_edit.html", {"form": form})
