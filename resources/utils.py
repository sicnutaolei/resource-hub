"""
外链状态检测。

只用标准库 urllib，不引入 requests，保持依赖最小。
注意：本检测只能判断「链接能否访问」，网盘分享过期后部分平台仍返回 200，
因此结果仅供管理员参考，不能作为唯一判断依据。
"""
import urllib.error
import urllib.request

from django.conf import settings
from django.utils import timezone

from .models import DownloadLink

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

OK = "ok"
BROKEN = "broken"
SKIPPED = "skipped"

STATUS_LABEL = {
    OK: "可达",
    BROKEN: "疑似失效",
    SKIPPED: "已跳过",
}


def _request(url: str, method: str, timeout: int = 8, extra_headers=None):
    headers = {"User-Agent": USER_AGENT, "Accept": "*/*"}
    if extra_headers:
        headers.update(extra_headers)
    request = urllib.request.Request(url, method=method, headers=headers)
    return urllib.request.urlopen(request, timeout=timeout)


def probe_url(url: str, timeout: int = 8):
    """返回 (status, detail)。status 取 OK / BROKEN / SKIPPED。"""
    url = (url or "").strip()
    if not url:
        return SKIPPED, "无外链地址"

    if not url.lower().startswith(("http://", "https://")):
        return SKIPPED, "非 http(s) 链接"

    # 先 HEAD，成本最低
    try:
        with _request(url, "HEAD", timeout) as response:
            return OK, f"HTTP {response.status}"
    except urllib.error.HTTPError as exc:
        if exc.code in (403, 405, 406, 501):
            # 部分站点禁用 HEAD，退化为只取 1 字节的 GET
            try:
                with _request(url, "GET", timeout, {"Range": "bytes=0-0"}) as response:
                    return OK, f"HTTP {response.status}"
            except urllib.error.HTTPError as inner:
                return _classify_http_error(inner)
            except Exception as inner:  # noqa: BLE001
                return BROKEN, f"{type(inner).__name__}: {inner}"
        return _classify_http_error(exc)
    except urllib.error.URLError as exc:
        return BROKEN, f"网络错误：{exc.reason}"
    except Exception as exc:  # noqa: BLE001
        return BROKEN, f"{type(exc).__name__}: {exc}"


def _classify_http_error(exc: urllib.error.HTTPError):
    if exc.code in (404, 410, 451):
        return BROKEN, f"HTTP {exc.code}（资源不存在）"
    if exc.code >= 500:
        return BROKEN, f"HTTP {exc.code}（服务端异常）"
    # 401/403/429 更可能是防盗链或限流，不判定为失效
    return OK, f"HTTP {exc.code}（疑似防盗链/限流）"


def check_links(links, timeout=None, apply=False):
    """
    逐个检测外链。

    apply=False（默认）只出报告不改库；apply=True 才写回 is_broken / last_checked_at。
    返回结果列表，元素为 dict。
    """
    timeout = timeout or settings.EXTERNAL_LINK_CHECK_TIMEOUT
    now = timezone.now()
    results = []
    changed = []

    for link in links:
        if link.link_type == DownloadLink.EXTERNAL:
            status, detail = probe_url(link.url, timeout=timeout)
        else:
            status, detail = SKIPPED, "本地文件，无需检测"

        results.append(
            {
                "id": link.pk,
                "resource": link.resource.title,
                "label": link.label,
                "url": link.url or "（本地文件）",
                "status": status,
                "detail": detail,
            }
        )

        if apply and status in (OK, BROKEN):
            link.is_broken = status == BROKEN
            link.last_checked_at = now
            changed.append(link)

    if apply and changed:
        DownloadLink.objects.bulk_update(
            changed, ["is_broken", "last_checked_at"], batch_size=200
        )

    return results
