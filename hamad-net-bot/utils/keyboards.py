"""
باني لوحات المفاتيح - Keyboard Builders
بناء الأزرار التفاعلية للبوت
"""
from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton
)
from typing import List, Optional


def main_menu_kb() -> InlineKeyboardMarkup:
    """القائمة الرئيسية"""
    buttons = [
        [
            InlineKeyboardButton(text="📊 حالة الشبكة", callback_data="status"),
            InlineKeyboardButton(text="📱 الأجهزة", callback_data="devices"),
        ],
        [
            InlineKeyboardButton(text="🌐 حالة الإنترنت", callback_data="internet"),
            InlineKeyboardButton(text="🔒 الأمان", callback_data="security"),
        ],
        [
            InlineKeyboardButton(text="⚠️ التنبيهات", callback_data="alerts"),
            InlineKeyboardButton(text="🔧 التشخيص", callback_data="diagnostics"),
        ],
        [
            InlineKeyboardButton(text="📡 الراوتر", callback_data="router"),
            InlineKeyboardButton(text="🛡️ التحكم", callback_data="control"),
        ],
        [
            InlineKeyboardButton(text="📋 السجلات", callback_data="logs"),
            InlineKeyboardButton(text="⚙️ الإعدادات", callback_data="settings"),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def devices_menu_kb() -> InlineKeyboardMarkup:
    """قائمة الأجهزة"""
    buttons = [
        [
            InlineKeyboardButton(text="🟢 الأجهزة المتصلة", callback_data="devices_online"),
            InlineKeyboardButton(text="🔴 المنفصلة", callback_data="devices_offline"),
        ],
        [
            InlineKeyboardButton(text="❓ أجهزة غير معروفة", callback_data="devices_unknown"),
            InlineKeyboardButton(text="🚫 المحظورة", callback_data="devices_blocked"),
        ],
        [
            InlineKeyboardButton(text="📊 استهلاك الباندويث", callback_data="devices_traffic"),
        ],
        [
            InlineKeyboardButton(text="🔙 القائمة الرئيسية", callback_data="main_menu"),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def device_actions_kb(mac: str, ip: str, is_online: bool = True,
                      is_blocked: bool = False, has_speed_limit: bool = False) -> InlineKeyboardMarkup:
    """أزرار إجراءات جهاز محدد"""
    buttons = []

    if is_online:
        if is_blocked:
            buttons.append([
                InlineKeyboardButton(text="✅ إلغاء حظر الإنترنت",
                                    callback_data=f"unblock:{mac}:{ip}"),
            ])
        else:
            buttons.append([
                InlineKeyboardButton(text="🚫 حظر الإنترنت",
                                    callback_data=f"block:{mac}:{ip}"),
                InlineKeyboardButton(text="📵 حظر WiFi",
                                    callback_data=f"block_wifi:{mac}:{ip}"),
            ])

        if has_speed_limit:
            buttons.append([
                InlineKeyboardButton(text="❌ إزالة تحديد السرعة",
                                    callback_data=f"unlimit:{mac}:{ip}"),
            ])
        else:
            buttons.append([
                InlineKeyboardButton(
                    text="⚡ 1M",
                    callback_data=f"limit:{mac}:{ip}:1000:1000"
                ),
                InlineKeyboardButton(
                    text="⚡ 2M",
                    callback_data=f"limit:{mac}:{ip}:2000:2000"
                ),
                InlineKeyboardButton(
                    text="⚡ 5M",
                    callback_data=f"limit:{mac}:{ip}:5000:5000"
                ),
            ])
            buttons.append([
                InlineKeyboardButton(
                    text="⚡ 10M",
                    callback_data=f"limit:{mac}:{ip}:10000:10000"
                ),
                InlineKeyboardButton(
                    text="⚡ 25M",
                    callback_data=f"limit:{mac}:{ip}:25000:25000"
                ),
                InlineKeyboardButton(
                    text="⚡ 50M",
                    callback_data=f"limit:{mac}:{ip}:50000:50000"
                ),
            ])

    buttons.append([
        InlineKeyboardButton(text="✅ تعليم كمعروف",
                            callback_data=f"mark_known:{mac}"),
    ])
    buttons.append([
        InlineKeyboardButton(text="🔙 قائمة الأجهزة", callback_data="devices"),
    ])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def security_menu_kb() -> InlineKeyboardMarkup:
    """قائمة الأمان"""
    buttons = [
        [
            InlineKeyboardButton(text="🚨 محاولات الاختراق", callback_data="intrusions"),
            InlineKeyboardButton(text="🔥 الجدار الناري", callback_data="firewall"),
        ],
        [
            InlineKeyboardButton(text="❓ أجهزة مشبوهة", callback_data="suspicious"),
            InlineKeyboardButton(text="🛡️ حالة الحماية", callback_data="protection_status"),
        ],
        [
            InlineKeyboardButton(text="🔙 القائمة الرئيسية", callback_data="main_menu"),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def internet_menu_kb() -> InlineKeyboardMarkup:
    """قائمة الإنترنت"""
    buttons = [
        [
            InlineKeyboardButton(text="📡 فحص الاتصال", callback_data="internet_check"),
            InlineKeyboardButton(text="📉 انقطاعات سابقة", callback_data="internet_outages"),
        ],
        [
            InlineKeyboardButton(text="🌐 IP العام", callback_data="wan_ip"),
            InlineKeyboardButton(text="⚡ اختبار السرعة", callback_data="speedtest"),
        ],
        [
            InlineKeyboardButton(text="🔙 القائمة الرئيسية", callback_data="main_menu"),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def diagnostics_menu_kb() -> InlineKeyboardMarkup:
    """قائمة التشخيص"""
    buttons = [
        [
            InlineKeyboardButton(text="🔍 Ping", callback_data="diag_ping"),
            InlineKeyboardButton(text="📍 Traceroute", callback_data="diag_traceroute"),
        ],
        [
            InlineKeyboardButton(text="⚠️ أخطاء الراوتر", callback_data="router_errors"),
            InlineKeyboardButton(text="🔄 تغييرات الشبكة", callback_data="topology_changes"),
        ],
        [
            InlineKeyboardButton(text="🩺 فحص شامل", callback_data="full_check"),
        ],
        [
            InlineKeyboardButton(text="🔙 القائمة الرئيسية", callback_data="main_menu"),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def router_menu_kb() -> InlineKeyboardMarkup:
    """قائمة الراوتر"""
    buttons = [
        [
            InlineKeyboardButton(text="📊 إحصائيات", callback_data="router_stats"),
            InlineKeyboardButton(text="🔌 الواجهات", callback_data="router_interfaces"),
        ],
        [
            InlineKeyboardButton(text="📋 سجلات النظام", callback_data="system_logs"),
            InlineKeyboardButton(text="🔄 إعادة تشغيل", callback_data="reboot_confirm"),
        ],
        [
            InlineKeyboardButton(text="🔙 القائمة الرئيسية", callback_data="main_menu"),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def control_menu_kb() -> InlineKeyboardMarkup:
    """قائمة التحكم"""
    buttons = [
        [
            InlineKeyboardButton(text="🚫 حظر جهاز", callback_data="control_block"),
            InlineKeyboardButton(text="✅ إلغاء حظر", callback_data="control_unblock"),
        ],
        [
            InlineKeyboardButton(text="⚡ تحديد سرعة", callback_data="control_limit"),
            InlineKeyboardButton(text="❌ إزالة تحديد", callback_data="control_unlimit"),
        ],
        [
            InlineKeyboardButton(text="🔄 إعادة تشغيل الراوتر", callback_data="reboot_confirm"),
        ],
        [
            InlineKeyboardButton(text="🔙 القائمة الرئيسية", callback_data="main_menu"),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def confirm_kb(action: str, callback_yes: str, callback_no: str = "main_menu") -> InlineKeyboardMarkup:
    """لوحة تأكيد"""
    buttons = [
        [
            InlineKeyboardButton(text=f"✅ نعم - {action}", callback_data=callback_yes),
            InlineKeyboardButton(text="❌ إلغاء", callback_data=callback_no),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def alerts_menu_kb() -> InlineKeyboardMarkup:
    """قائمة التنبيهات"""
    buttons = [
        [
            InlineKeyboardButton(text="🔔 تنبيهات غير مقروءة", callback_data="alerts_unread"),
            InlineKeyboardButton(text="📋 كل التنبيهات", callback_data="alerts_all"),
        ],
        [
            InlineKeyboardButton(text="✅ تحديد الكل كمقروء", callback_data="alerts_mark_read"),
        ],
        [
            InlineKeyboardButton(text="🔙 القائمة الرئيسية", callback_data="main_menu"),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def logs_menu_kb() -> InlineKeyboardMarkup:
    """قائمة السجلات"""
    buttons = [
        [
            InlineKeyboardButton(text="🔥 سجلات الجدار الناري", callback_data="firewall_logs"),
            InlineKeyboardButton(text="📋 سجلات النظام", callback_data="system_logs"),
        ],
        [
            InlineKeyboardButton(text="🚨 سجلات الاختراقات", callback_data="intrusion_logs"),
            InlineKeyboardButton(text="🔄 سجلات التغييرات", callback_data="change_logs"),
        ],
        [
            InlineKeyboardButton(text="🔙 القائمة الرئيسية", callback_data="main_menu"),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def settings_menu_kb() -> InlineKeyboardMarkup:
    """قائمة الإعدادات"""
    buttons = [
        [
            InlineKeyboardButton(text="🔔 إعدادات التنبيهات", callback_data="settings_alerts"),
            InlineKeyboardButton(text="⏱️ فترات الفحص", callback_data="settings_intervals"),
        ],
        [
            InlineKeyboardButton(text="🔙 القائمة الرئيسية", callback_data="main_menu"),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def back_to_main_kb() -> InlineKeyboardMarkup:
    """زر العودة للقائمة الرئيسية"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 القائمة الرئيسية", callback_data="main_menu")]
    ])
