from __future__ import annotations

APP_DISPLAY_NAME = "秋招进程台账"
APP_VERSION = "1.1.1"
ORGANIZATION_NAME = "PersonalTools"
APPLICATION_NAME = "AutumnRecruitmentLedger"

APPLICATION_STATUSES: tuple[str, ...] = (
    "待投递",
    "已投递",
    "简历筛选中",
    "笔试",
    "一面结束",
    "二面结束",
    "三面结束",
    "HR面结束",
    "Offer沟通中",
    "已有Offer",
    "已拒绝",
    "已放弃",
)

APPLICATION_CHANNELS: tuple[str, ...] = (
    "公司官网",
    "校园招聘",
    "内推",
    "Boss直聘",
    "猎聘",
    "智联招聘",
    "前程无忧",
    "微信公众号",
    "招聘会",
    "其他",
)

INTERVIEW_STATUSES: frozenset[str] = frozenset(
    {"笔试", "一面结束", "二面结束", "三面结束", "HR面结束", "Offer沟通中"}
)

STATUS_COLORS: dict[str, str] = {
    "待投递": "#E5E7EB",
    "已投递": "#DBEAFE",
    "简历筛选中": "#BFDBFE",
    "笔试": "#FFEDD5",
    "一面结束": "#FED7AA",
    "二面结束": "#FED7AA",
    "三面结束": "#FDBA74",
    "HR面结束": "#FDBA74",
    "Offer沟通中": "#D1FAE5",
    "已有Offer": "#A7F3D0",
    "已拒绝": "#FEE2E2",
    "已放弃": "#E5E7EB",
}

DATE_FORMAT = "yyyy-MM-dd"
ISO_DATE_FORMAT = "%Y-%m-%d"
TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"
MAX_AUTO_BACKUPS = 30
