"""灌入演示数据，用于本地预览界面效果。

生产环境（DEBUG=False）默认拒绝执行，必须显式加 --force 才会写入。
"""

from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from resources.models import (
    Category,
    Comment,
    DownloadLink,
    Favorite,
    Resource,
    Tag,
    UpdateLog,
)

CATEGORIES = [
    ("工具软件", "日常必备的小工具与系统增强", 1),
    ("图像影音", "看图、剪辑、转码与播放", 2),
    ("系统优化", "清理、卸载、驱动与硬件检测", 3),
    ("开发工具", "编辑器、终端与命令行利器", 4),
]

TAGS = [
    "绿色版", "便携", "免安装", "开源", "免费", "无广告",
    "Win11", "轻量", "中文", "命令行", "跨平台", "离线可用",
]

RESOURCES = [
    {
        "title": "Notepad-- 文本编辑器",
        "category": "工具软件",
        "tags": ["开源", "轻量", "便携", "中文"],
        "summary": "国产开源文本编辑器，专治超大文件卡顿，替代 Notepad++ 的顺手选择。",
        "description": (
            "打开几百 MB 的日志文件不卡顿，这点比大多数编辑器都强。\n"
            "内置十六进制查看、列编辑、正则替换，常用功能一个不缺。\n"
            "自带便携模式，解压即用，配置文件跟着程序目录走，换机器直接拷走。"
        ),
        "version": "3.5.2",
        "pinned": True,
        "views": 1284,
        "links": [
            ("本地直链下载", "local", "notepad--v3.5.2-portable.zip", 48 * 1024 * 1024),
            ("蓝奏云（提取码 8x2k）", "external", "https://wwi.lanzoup.com/b0example1", "8x2k"),
            ("百度网盘", "external", "https://pan.baidu.com/s/1example2", "tool"),
        ],
        "logs": [
            ("3.5.2", "修复超长行折行时的卡顿\n新增 JSON 格式化快捷键 Ctrl+Alt+J"),
            ("3.5.0", "重构语法高亮引擎，大文件内存占用降低约 40%"),
        ],
        "comments": ["打开 800MB 的 nginx 日志确实不卡，给站长点赞。"],
    },
    {
        "title": "PotPlayer 影音播放器",
        "category": "图像影音",
        "tags": ["无广告", "中文", "Win11", "离线可用"],
        "summary": "解码能力最全的本地播放器，几乎什么格式都能放，零广告零捆绑。",
        "description": (
            "H.265 / AV1 / VP9 硬解全支持，老机器也能流畅播 4K。\n"
            "自带倍速播放与字幕匹配，追剧看片都够用。\n"
            "安装时记得取消勾选捆绑的额外组件，本包已做净化处理。"
        ),
        "version": "240618",
        "pinned": True,
        "views": 2156,
        "links": [
            ("本地直链下载", "local", "PotPlayer-240618-x64.exe", 112 * 1024 * 1024),
            ("阿里云盘", "external", "https://www.alipan.com/s/example3", ""),
        ],
        "logs": [("240618", "更新内置解码器\n修复部分 MKV 字幕不同步的问题")],
        "comments": ["终于找到没广告的版本了，谢谢站长。", "4K 硬解没问题，CPU 占用很低。"],
    },
    {
        "title": "Geek Uninstaller 卸载工具",
        "category": "系统优化",
        "tags": ["绿色版", "免安装", "轻量", "无广告"],
        "summary": "单文件卸载神器，能连残留注册表一起清干净，比系统自带的好用太多。",
        "description": (
            "绿色单文件，两 MB 不到，放在 U 盘里随时能掏出来用。\n"
            "卸载完会自动扫描残留文件和注册表项，一键清理。\n"
            "支持强制卸载那些在控制面板里删不掉的流氓软件。"
        ),
        "version": "1.5.2",
        "views": 968,
        "links": [("本地直链下载", "local", "geek-uninstaller-1.5.2.zip", 6 * 1024 * 1024)],
        "logs": [("1.5.2", "卸载残留扫描速度提升\n支持 Windows 11 24H2")],
        "comments": [],
    },
    {
        "title": "Rufus 启动盘制作工具",
        "category": "工具软件",
        "tags": ["免安装", "开源", "轻量", "中文"],
        "summary": "刻录 U 盘启动盘的老牌工具，装系统前必备，三秒写好一个盘。",
        "description": (
            "支持 Windows / Linux 镜像，也支持直接下载官方 ISO。\n"
            "能绕过 Windows 11 的 TPM 和联网要求，老电脑装 win11 靠它。\n"
            "免安装单文件，体积不到 1.5MB。"
        ),
        "version": "4.5",
        "views": 742,
        "links": [
            ("本地直链下载", "local", "rufus-4.5p.exe", 1500 * 1024),
            ("官网直接下载", "external", "https://rufus.ie/zh/", ""),
        ],
        "logs": [("4.5", "新增对 Windows 11 24H2 的绕过选项")],
        "comments": ["做启动盘一直在用这个，稳定。", "绕过 TPM 那个选项太实用了。"],
    },
    {
        "title": "Everything 文件搜索",
        "category": "工具软件",
        "tags": ["免费", "轻量", "中文", "便携"],
        "summary": "秒级搜遍全盘文件的索引工具，用过就回不去了。",
        "description": (
            "基于 NTFS 索引，百万文件也能瞬间出结果。\n"
            "支持正则与通配符，还能按大小、时间、类型组合筛选。\n"
            "便携版可以直接放在 U 盘里给别人的电脑用。"
        ),
        "version": "1.4.1",
        "views": 1533,
        "links": [
            ("本地直链下载", "local", "Everything-1.4.1.1024.x64.zip", 2 * 1024 * 1024),
            ("百度网盘", "external", "https://pan.baidu.com/s/1example5", "evry"),
        ],
        "logs": [("1.4.1", "修复长时间运行后索引偶尔失效的问题")],
        "comments": ["这个真的无敌，装系统第一件事就是装它。"],
    },
    {
        "title": "ShareX 截图与录屏",
        "category": "图像影音",
        "tags": ["开源", "免费", "无广告", "Win11"],
        "summary": "截图、录屏、OCR、上传一条龙，功能多到有点过剩。",
        "description": (
            "区域截图后可以直接标注、加马赛克、生成 GIF。\n"
            "录屏支持指定窗口，输出体积控制得不错。\n"
            "内置 OCR 能直接提取截图里的文字，识别中文效果可以。"
        ),
        "version": "16.1.0",
        "views": 611,
        "links": [
            ("本地直链下载", "local", "ShareX-16.1.0-setup.exe", 9 * 1024 * 1024),
            ("GitHub Release", "external", "https://github.com/ShareX/ShareX/releases", ""),
        ],
        "logs": [("16.1.0", "OCR 引擎升级\n新增窗口录制模式")],
        "comments": [],
    },
    {
        "title": "Windows Terminal 终端",
        "category": "开发工具",
        "tags": ["开源", "免费", "命令行", "Win11", "中文"],
        "summary": "微软官方多标签终端，把 PowerShell、WSL、CMD 都装进一个窗口。",
        "description": (
            "多标签 + 分屏，开一堆终端也不乱。\n"
            "GPU 加速渲染，滚动长日志非常顺滑。\n"
            "完全可配置的字体、配色与快捷键，配合 WSL 体验最好。"
        ),
        "version": "1.21",
        "views": 489,
        "links": [
            ("微软商店", "external", "https://apps.microsoft.com/detail/9n0dx20hk701", ""),
            ("本地直链下载", "local", "WindowsTerminal-1.21.msixbundle", 32 * 1024 * 1024),
        ],
        "logs": [("1.21", "新增标签页恢复功能\n提升大文件输出时的渲染性能")],
        "comments": ["配合 WSL 用了一阵，确实比 cmd 舒服太多。"],
    },
    {
        "title": "7-Zip 压缩解压",
        "category": "工具软件",
        "tags": ["开源", "免费", "中文", "离线可用", "轻量"],
        "summary": "压缩率最高的老牌工具，开源免费，没有任何广告和弹窗。",
        "description": (
            "7z 格式压缩率目前仍是第一梯队，比 zip 省不少空间。\n"
            "支持解压 RAR、ISO、DMG 等几十种格式。\n"
            "右键菜单集成清爽，卸载也干净。"
        ),
        "version": "24.08",
        "views": 1102,
        "links": [
            ("本地直链下载", "local", "7z2408-x64.exe", 1600 * 1024),
            ("官网直接下载", "external", "https://www.7-zip.org/", ""),
        ],
        "logs": [("24.08", "修复解压特定 RAR5 压缩包时崩溃的问题")],
        "comments": ["免费无广告，一直用这个。"],
    },
    {
        "title": "Dism++ 系统维护",
        "category": "系统优化",
        "tags": ["绿色版", "便携", "中文", "无广告"],
        "summary": "图形化 DISM 工具，清理系统垃圾、管理启动项、优化体积都好用。",
        "description": (
            "空间回收能清掉 Windows 更新残留，动辄释放几个 G。\n"
            "启动项管理比任务管理器详细，能看到计划任务。\n"
            "还能直接编辑系统镜像，做无人值守安装盘。"
        ),
        "version": "10.1.1002.2",
        "views": 877,
        "links": [
            ("本地直链下载", "local", "Dism++10.1.1002.2.zip", 4 * 1024 * 1024),
            ("蓝奏云（提取码 dsim）", "external", "https://wwi.lanzoup.com/b0example9", "dsim"),
        ],
        "logs": [("10.1.1002.2", "支持 Windows 11 24H2 镜像\n修复清理后偶发的组件损坏")],
        "comments": [],
    },
    {
        "title": "HWiNFO 硬件检测",
        "category": "系统优化",
        "tags": ["免费", "中文", "Win11", "便携"],
        "summary": "硬件信息检测最全的工具，温度、电压、风扇转速都能实时看。",
        "description": (
            "CPU 各核心频率、功耗、温度逐项可查，超频调试用它。\n"
            "传感器面板可以常驻桌面，随时盯硬件状态。\n"
            "也支持生成报告，二手验机时很好用。"
        ),
        "version": "7.68",
        "views": 534,
        "links": [
            ("本地直链下载", "local", "hwinfo-7.68-portable.zip", 12 * 1024 * 1024),
            ("官网直接下载", "external", "https://www.hwinfo.com/download/", ""),
        ],
        "logs": [("7.68", "新增对 Intel Arrow Lake 的传感器支持")],
        "comments": [],
    },
    {
        "title": "VS Code 代码编辑器",
        "category": "开发工具",
        "tags": ["免费", "中文", "跨平台", "开源"],
        "summary": "插件生态最庞大的编辑器，前端到嵌入式都能凑合写。",
        "description": (
            "内置 Git、调试、终端，开箱就够用。\n"
            "远程开发插件可以直接编辑服务器和容器的代码。\n"
            "扩展市场插件几十万，几乎任何语言都有支持。"
        ),
        "version": "1.93",
        "views": 1290,
        "links": [
            ("本地直链下载", "local", "VSCodeUserSetup-x64-1.93.exe", 98 * 1024 * 1024),
            ("官网直接下载", "external", "https://code.visualstudio.com/", ""),
        ],
        "logs": [("1.93", "提升大项目下的文件搜索速度\n修复中文输入法候选框错位")],
        "comments": ["远程开发那套确实方便，服务器上直接改代码。"],
    },
    {
        "title": "Bulk Crap Uninstaller 批量卸载",
        "category": "系统优化",
        "tags": ["开源", "免费", "便携", "无广告"],
        "summary": "一次勾选几十个软件批量卸载，还能静默清理残留，装机必备。",
        "description": (
            "支持多选批量卸载，装的软件多的时候能省很多时间。\n"
            "能识别那些不在控制面板里显示的隐藏程序。\n"
            "卸载前会先做一次还原点，出问题能退回来。"
        ),
        "version": "5.8.3",
        "views": 412,
        "links": [
            ("本地直链下载", "local", "BCUninstaller_5.8.3_portable.zip", 18 * 1024 * 1024),
            (
                "GitHub Release",
                "external",
                "https://github.com/Klocman/Bulk-Crap-Uninstaller/releases",
                "",
            ),
        ],
        "logs": [("5.8.3", "提升对 MSIX 应用包的识别率")],
        "comments": [],
    },
]


class Command(BaseCommand):
    help = "灌入演示资源数据，用于本地预览界面效果"

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="即使 DEBUG=False（生产环境）也强制执行",
        )
        parser.add_argument(
            "--reset",
            action="store_true",
            help="先清空已有的资源、分类、标签再灌入",
        )

    def handle(self, *args, **options):
        if not settings.DEBUG and not options["force"]:
            raise CommandError(
                "当前 DEBUG=False，看起来是生产环境。\n"
                "灌入演示数据会污染真实数据，已拒绝执行。\n"
                "确实需要的话请加 --force。"
            )

        if options["reset"]:
            count = Resource.objects.count()
            Favorite.objects.all().delete()
            Resource.objects.all().delete()
            Category.objects.all().delete()
            Tag.objects.all().delete()
            self.stdout.write(self.style.WARNING(f"已清空 {count} 条旧资源"))

        demo_user, created = get_user_model().objects.get_or_create(
            username="demo",
            defaults={"nickname": "路过的网友", "bio": "只是来看看有没有好用的工具。"},
        )
        if created:
            demo_user.set_password("demo12345")
            demo_user.save()

        category_map = {
            name: Category.objects.get_or_create(
                name=name, defaults={"description": desc, "order": order}
            )[0]
            for name, desc, order in CATEGORIES
        }
        tag_map = {name: Tag.objects.get_or_create(name=name)[0] for name in TAGS}

        now = timezone.now()
        created_count = 0

        for index, data in enumerate(RESOURCES):
            if Resource.objects.filter(title=data["title"]).exists():
                continue

            resource = Resource.objects.create(
                title=data["title"],
                category=category_map[data["category"]],
                summary=data["summary"],
                description=data["description"],
                version=data["version"],
                is_pinned=data.get("pinned", False),
                is_published=True,
                views=data.get("views", 0),
            )
            # 错开时间，避免列表页所有条目时间一致
            Resource.objects.filter(pk=resource.pk).update(
                updated_at=now - timedelta(days=index, hours=index * 3),
                created_at=now - timedelta(days=index + 3, hours=index * 3),
            )
            resource.refresh_from_db()
            resource.tags.set([tag_map[t] for t in data["tags"]])

            for label, link_type, target, extra in data["links"]:
                if link_type == "local":
                    link = DownloadLink(
                        resource=resource,
                        label=label,
                        link_type=DownloadLink.LOCAL,
                        file_size=extra,
                    )
                    link.file.save(
                        target, ContentFile(b"demo placeholder file\n"), save=False
                    )
                    link.save()
                else:
                    DownloadLink.objects.create(
                        resource=resource,
                        label=label,
                        link_type=DownloadLink.EXTERNAL,
                        url=target,
                        extract_code=extra,
                    )

            for offset, (version, content) in enumerate(data["logs"]):
                log = UpdateLog.objects.create(
                    resource=resource, version=version, content=content
                )
                UpdateLog.objects.filter(pk=log.pk).update(
                    created_at=now - timedelta(days=index + offset * 5)
                )

            for text in data["comments"]:
                Comment.objects.create(resource=resource, user=demo_user, content=text)

            Favorite.objects.get_or_create(user=demo_user, resource=resource)
            created_count += 1

        # 人为造一条「疑似失效」外链，用于验证前端徽标样式
        broken = DownloadLink.objects.filter(
            link_type=DownloadLink.EXTERNAL, resource__title="PotPlayer 影音播放器"
        ).first()
        if broken:
            broken.is_broken = True
            broken.last_checked_at = now
            broken.save(update_fields=["is_broken", "last_checked_at"])

        self.stdout.write(self.style.SUCCESS(f"演示数据就绪：新增 {created_count} 条资源"))
        self.stdout.write(
            f"资源 {Resource.objects.count()} / 分类 {Category.objects.count()} / "
            f"标签 {Tag.objects.count()} / 下载链接 {DownloadLink.objects.count()} / "
            f"更新日志 {UpdateLog.objects.count()} / 评论 {Comment.objects.count()}"
        )
        self.stdout.write(f"演示账号：demo / demo12345")
