"""
بوت حمد نت - القلب الرئيسي
Hamad Net Bot - Main Bot
بوت تليجرام لإدارة ومراقبة شبكة حمد نت
"""
import asyncio
import logging
import os
import signal
import sys
from datetime import datetime
from typing import Optional

from telegram import (
    Update, InlineKeyboardMarkup, InlineKeyboardButton,
    BotCommand, BotCommandScopeChat,
)
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes,
)
from telegram.constants import ParseMode

import config
from utils.database import Database
from modules.router import create_router, RouterBase
from modules.scanner import NetworkScanner
from modules.security import SecurityMonitor
from modules.monitor import InternetMonitor
from modules.notifications import NotificationHandler

# إعداد السجلات
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# المتغيرات العامة
db: Optional[Database] = None
router: Optional[RouterBase] = None
scanner: Optional[NetworkScanner] = None
security: Optional[SecurityMonitor] = None
monitor: Optional[InternetMonitor] = None
notifier: Optional[NotificationHandler] = None


def is_authorized(update: Update) -> bool:
    """التحقق من صلاحية المستخدم"""
    chat_id = update.effective_chat.id if update.effective_chat else 0
    if not config.AUTHORIZED_CHAT_IDS:
        return True  # إذا لم يتم تحديد معرفات، يُسمح للجميع
    return chat_id in config.AUTHORIZED_CHAT_IDS


def get_emoji_status(is_online: bool) -> str:
    return "🟢" if is_online else "🔴"


def format_device_type(device_type: str) -> str:
    """ترجمة نوع الجهاز"""
    types = {
        'router': '🔓 راوتر',
        'switch': '🔀 سويتش',
        'access_point': '📡 نقطة وصول',
        'phone': '📱 هاتف',
        'computer': '💻 حاسوب',
        'server': '🖥️ خادم',
        'network_device': '🌐 جهاز شبكة',
        'tv': '📺 تلفزيون',
        'printer': '🖨️ طابعة',
        'camera': '📷 كاميرا',
        'iot': '🔌 إنترنت الأشياء',
        'unknown': '❓ غير معروف',
    }
    return types.get(device_type, '❓ غير معروف')


# ==========================================
# أوامر البوت
# ==========================================

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """أمر البدء"""
    if not is_authorized(update):
        await update.message.reply_text("⛔ غير مصرح لك باستخدام هذا البوت.")
        return

    text = (
        f"🏠 <b>مرحباً بك في بوت حمد نت</b>\n\n"
        f"🛡️ بوت إدارة ومراقبة شبكة حمد نت\n"
        f"يمكنك من خلال هذا البوت:\n\n"
        f"📱 مراقبة جميع الأجهزة المتصلة\n"
        f"🔒 كشف محاولات الاختراق\n"
        f"📡 معرفة حالة الإنترنت\n"
        f"⚙️ التحكم بالراوتر والأجهزة\n"
        f"📊 متابعة استهلاك الباندويث\n"
        f"🔧 إصلاح المشاكل عن بُعد\n\n"
        f"استخدم الأزرار أدناه أو اكتب /help لعرض الأوامر"
    )

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📊 لوحة التحكم", callback_data="dashboard"),
            InlineKeyboardButton("📱 الأجهزة", callback_data="devices"),
        ],
        [
            InlineKeyboardButton("🔒 الأمان", callback_data="security"),
            InlineKeyboardButton("📡 الإنترنت", callback_data="internet"),
        ],
        [
            InlineKeyboardButton("⚙️ الإعدادات", callback_data="settings"),
            InlineKeyboardButton("❓ المساعدة", callback_data="help"),
        ],
    ])

    await update.message.reply_text(text, reply_markup=keyboard, parse_mode=ParseMode.HTML)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض المساعدة"""
    if not is_authorized(update):
        return

    text = (
        "📖 <b>دليل استخدام بوت حمد نت</b>\n\n"
        "📱 <b>مراقبة الأجهزة:</b>\n"
        "/devices - عرض جميع الأجهزة\n"
        "/online - الأجهزة المتصلة فقط\n"
        "/offline - الأجهزة غير المتصلة\n"
        "/unauthorized - الأجهزة غير المرخصة\n\n"
        "🔒 <b>الأمان:</b>\n"
        "/security - فحص أمني شامل\n"
        "/alerts - التنبيهات غير المعالجة\n"
        "/block [MAC] - حظر جهاز\n"
        "/unblock [MAC] - إلغاء حظر\n\n"
        "📡 <b>الإنترنت:</b>\n"
        "/internet - حالة الاتصال\n"
        "/outages - سجل الانقطاعات\n"
        "/trace - تتبع المسار\n"
        "/dns - حالة DNS\n\n"
        "📊 <b>الإحصائيات:</b>\n"
        "/dashboard - لوحة التحكم\n"
        "/bandwidth - استهلاك الباندويث\n"
        "/topusers - أكبر المستخدمين\n\n"
        "⚙️ <b>التحكم:</b>\n"
        "/router - معلومات الراوتر\n"
        "/reboot - إعادة تشغيل الراوتر\n"
        "/scan - فحص الشبكة الآن\n"
        "/limit [IP] [DL] [UL] - تحديد سرعة\n\n"
        "🔧 <b>الصيانة:</b>\n"
        "/logs - سجلات النظام\n"
        "/changes - التغييرات الأخيرة\n"
        "/resolve [ID] - معالجة تنبيه\n"
    )

    await update.message.reply_text(text, parse_mode=ParseMode.HTML)


async def dashboard_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """لوحة التحكم الرئيسية"""
    if not is_authorized(update):
        return

    await _send_dashboard(update)


async def _send_dashboard(update_or_query, is_query: bool = False):
    """إرسال لوحة التحكم"""
    summary = db.get_network_summary()

    # حالة الإنترنت
    internet_status = "🟢 متصل" if monitor and monitor.is_online else "🔴 غير متصل"

    # حالة الأمان
    sec_summary = {}
    if security:
        sec_summary = await security.get_security_summary()

    # معلومات الراوتر
    router_info = ""
    if router and router.connected:
        try:
            info = await router.get_system_info()
            cpu = info.get('cpu_load', 0)
            mem = await router.get_memory_usage()
            uptime = info.get('uptime', 'غير معروف')

            cpu_emoji = "🟢" if cpu < 50 else "🟡" if cpu < 80 else "🔴"
            mem_emoji = "🟢" if mem.get('usage_percent', 0) < 70 else "🟡" if mem.get('usage_percent', 0) < 90 else "🔴"

            router_info = (
                f"\n\n🖥️ <b>الراوتر:</b>\n"
                f"   الاسم: {info.get('identity', 'غير معروف')}\n"
                f"   الموديل: {info.get('model', 'غير معروف')}\n"
                f"   {cpu_emoji} المعالج: {cpu}%\n"
                f"   {mem_emoji} الذاكرة: {mem.get('usage_percent', 0)}%\n"
                f"   ⏱️ وقت التشغيل: {uptime}"
            )
        except:
            router_info = "\n\n🖥️ الراوتر: ⚠️ لا يمكن جلب المعلومات"

    sec_status = sec_summary.get('status', 'غير معروف')
    sec_count = sec_summary.get('total_alerts', 0)

    text = (
        f"🏠 <b>لوحة تحكم شبكة حمد نت</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📡 الإنترنت: <b>{internet_status}</b>\n"
        f"🛡️ الأمان: <b>{sec_status}</b> ({sec_count} تنبيه)\n\n"
        f"📱 <b>الأجهزة:</b>\n"
        f"   🟢 متصل: <b>{summary['online_devices']}</b>\n"
        f"   🔴 غير متصل: <b>{summary['offline_devices']}</b>\n"
        f"   ✅ مرخص: <b>{summary['authorized_devices']}</b>\n"
        f"   ⚠️ غير مرخص: <b>{summary['unauthorized_devices']}</b>\n"
        f"   📊 الإجمالي: <b>{summary['total_devices']}</b>"
        f"{router_info}\n\n"
        f"🕐 آخر تحديث: {datetime.now().strftime('%H:%M:%S')}"
    )

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📱 الأجهزة", callback_data="devices"),
            InlineKeyboardButton("🔒 الأمان", callback_data="security"),
        ],
        [
            InlineKeyboardButton("📡 الإنترنت", callback_data="internet"),
            InlineKeyboardButton("📊 الباندويث", callback_data="bandwidth"),
        ],
        [
            InlineKeyboardButton("🔄 تحديث", callback_data="dashboard"),
            InlineKeyboardButton("⚙️ الإعدادات", callback_data="settings"),
        ],
    ])

    if is_query:
        await update_or_query.edit_message_text(text, reply_markup=keyboard, parse_mode=ParseMode.HTML)
    else:
        await update_or_query.message.reply_text(text, reply_markup=keyboard, parse_mode=ParseMode.HTML)


# === أوامر الأجهزة ===

async def devices_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض جميع الأجهزة"""
    if not is_authorized(update):
        return

    await _send_devices_list(update, show_all=True)


async def online_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض الأجهزة المتصلة"""
    if not is_authorized(update):
        return

    await _send_devices_list(update, online_only=True)


async def offline_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض الأجهزة غير المتصلة"""
    if not is_authorized(update):
        return

    await _send_devices_list(update, online_only=False, offline_only=True)


async def unauthorized_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض الأجهزة غير المرخصة"""
    if not is_authorized(update):
        return

    devices = db.get_all_devices()
    unauth = [d for d in devices if not d.get('is_authorized', False)]

    if not unauth:
        await update.message.reply_text("✅ لا توجد أجهزة غير مرخصة.")
        return

    text = f"⚠️ <b>الأجهزة غير المرخصة ({len(unauth)})</b>\n\n"
    for i, d in enumerate(unauth[:20], 1):
        status = "🟢" if d.get('is_online') else "🔴"
        name = d.get('nickname') or d.get('hostname') or 'غير معروف'
        text += (
            f"{i}. {status} <code>{name}</code>\n"
            f"   🌐 {d['ip_address']} | 🔗 {d['mac_address']}\n"
        )

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🚫 حظر الكل", callback_data="block_all_unauth")],
    ])

    await update.message.reply_text(text, reply_markup=keyboard, parse_mode=ParseMode.HTML)


async def _send_devices_list(update, show_all: bool = True, online_only: bool = False,
                               offline_only: bool = False):
    """إرسال قائمة الأجهزة"""
    if online_only:
        devices = db.get_all_devices(online_only=True)
        title = "🟢 الأجهزة المتصلة"
    elif offline_only:
        all_dev = db.get_all_devices()
        devices = [d for d in all_dev if not d.get('is_online', False)]
        title = "🔴 الأجهزة غير المتصلة"
    else:
        devices = db.get_all_devices()
        title = "📱 جميع الأجهزة"

    if not devices:
        await update.message.reply_text("لا توجد أجهزة مسجلة.")
        return

    # تقسيم إلى صفحات
    per_page = 10
    page = 0
    total_pages = (len(devices) + per_page - 1) // per_page

    text = f"<b>{title}</b> ({len(devices)} جهاز)\n\n"
    
    page_devices = devices[page * per_page:(page + 1) * per_page]
    for i, d in enumerate(page * per_page + 1 + (i for i in range(len(page_devices))), 1):
        pass  # Will be rewritten below

    for i, d in enumerate(page_devices, 1):
        status = "🟢" if d.get('is_online') else "🔴"
        auth = "✅" if d.get('is_authorized') else "⚠️"
        blocked = "🚫" if d.get('blocked') else ""
        name = d.get('nickname') or d.get('hostname') or 'غير معروف'
        dtype = format_device_type(d.get('device_type', 'unknown'))
        
        text += (
            f"{i}. {status}{auth}{blocked} <code>{name}</code>\n"
            f"   🌐 {d['ip_address']} | {dtype}\n"
            f"   🔗 {d['mac_address']}\n"
        )

    text += f"\n📄 صفحة {page + 1} من {total_pages}"

    keyboard_buttons = []
    for d in page_devices:
        name = d.get('nickname') or d.get('hostname') or d['mac_address'][:8]
        keyboard_buttons.append(
            InlineKeyboardButton(f"{name}", callback_data=f"detail_{d['mac_address']}")
        )

    # ترتيب الأزرار في صفوف
    kb_rows = [keyboard_buttons[i:i + 2] for i in range(0, len(keyboard_buttons), 2)]
    kb_rows.append([
        InlineKeyboardButton("🔄 تحديث", callback_data="devices" if show_all else "online_devs"),
        InlineKeyboardButton("🏠 الرئيسية", callback_data="dashboard"),
    ])

    await update.message.reply_text(
        text, reply_markup=InlineKeyboardMarkup(kb_rows), parse_mode=ParseMode.HTML
    )


# === أوامر الأمان ===

async def security_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """فحص أمني شامل"""
    if not is_authorized(update):
        return

    msg = await update.message.reply_text("🔍 جاري الفحص الأمني...")

    result = await security.full_security_check()

    status_emoji = {
        'secure': '🟢 آمن',
        'caution': '🔵 انتباه',
        'warning': '🟡 تحذير',
        'danger': '🔴 خطر',
    }

    text = (
        f"🛡️ <b>تقرير الأمان - شبكة حمد نت</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"الحالة العامة: <b>{status_emoji.get(result['overall_status'], '⚪')}</b>\n\n"
    )

    if result['unauthorized_devices']:
        text += f"⚠️ أجهزة غير مرخصة: <b>{len(result['unauthorized_devices'])}</b>\n"
        for d in result['unauthorized_devices'][:5]:
            text += f"   • {d.get('description', '')}\n"

    if result['intrusion_attempts']:
        text += f"\n🚨 محاولات اختراق: <b>{len(result['intrusion_attempts'])}</b>\n"
        for a in result['intrusion_attempts'][:5]:
            text += f"   • [{a.get('severity', '').upper()}] {a.get('description', '')}\n"

    if result['suspicious_activity']:
        text += f"\n⚠️ نشاط مشبوه: <b>{len(result['suspicious_activity'])}</b>\n"
        for s in result['suspicious_activity'][:5]:
            text += f"   • {s.get('description', '')}\n"

    if result['firewall_issues']:
        text += f"\n🔥 مشاكل الجدار الناري: <b>{len(result['firewall_issues'])}</b>\n"
        for f in result['firewall_issues'][:5]:
            text += f"   • {f.get('description', '')}\n"

    if result['vulnerabilities']:
        text += f"\n🔓 ثغرات: <b>{len(result['vulnerabilities'])}</b>\n"
        for v in result['vulnerabilities'][:5]:
            text += f"   • [{v.get('severity', '').upper()}] {v.get('description', '')}\n"

    if result['overall_status'] == 'secure':
        text += "\n✅ الشبكة في حالة آمنة!"

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📋 التنبيهات", callback_data="alerts"),
            InlineKeyboardButton("🔄 إعادة الفحص", callback_data="security"),
        ],
        [InlineKeyboardButton("🏠 الرئيسية", callback_data="dashboard")],
    ])

    await msg.edit_text(text, reply_markup=keyboard, parse_mode=ParseMode.HTML)


async def alerts_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض التنبيهات"""
    if not is_authorized(update):
        return

    alerts = db.get_unresolved_alerts()

    if not alerts:
        await update.message.reply_text("✅ لا توجد تنبيهات غير معالجة.")
        return

    text = f"🔔 <b>التنبيهات غير المعالجة ({len(alerts)})</b>\n\n"

    for i, alert in enumerate(alerts[:15], 1):
        severity_emoji = {
            'critical': '🔴', 'high': '🟠', 'medium': '🟡', 'low': '🔵', 'info': 'ℹ️'
        }.get(alert.get('severity', ''), '⚪')

        text += (
            f"{i}. {severity_emoji} [{alert.get('alert_type', '')}] {alert.get('description', '')[:80]}\n"
            f"   🕐 {alert.get('timestamp', '')[:19]}\n"
        )

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ معالجة الكل", callback_data="resolve_all"),
            InlineKeyboardButton("🏠 الرئيسية", callback_data="dashboard"),
        ],
    ])

    await update.message.reply_text(text, reply_markup=keyboard, parse_mode=ParseMode.HTML)


async def block_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """حظر جهاز /block MAC"""
    if not is_authorized(update):
        return

    if not context.args:
        await update.message.reply_text("⚠️ الاستخدام: /block [MAC Address]\nمثال: /block AA:BB:CC:DD:EE:FF")
        return

    mac = context.args[0].upper()
    success = await security.block_device(mac)

    if success:
        await update.message.reply_text(f"🚫 تم حظر الجهاز {mac} بنجاح.")
        db.log_command(
            update.effective_chat.id, update.effective_user.id,
            update.effective_user.username, "block", mac, "success"
        )
    else:
        await update.message.reply_text(f"❌ فشل حظر الجهاز {mac}.")


async def unblock_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """إلغاء حظر جهاز /unblock MAC"""
    if not is_authorized(update):
        return

    if not context.args:
        await update.message.reply_text("⚠️ الاستخدام: /unblock [MAC Address]\nمثال: /unblock AA:BB:CC:DD:EE:FF")
        return

    mac = context.args[0].upper()
    success = await security.unblock_device(mac)

    if success:
        await update.message.reply_text(f"✅ تم إلغاء حظر الجهاز {mac}.")
    else:
        await update.message.reply_text(f"❌ فشل إلغاء حظر الجهاز {mac}.")


# === أوامر الإنترنت ===

async def internet_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """حالة الإنترنت"""
    if not is_authorized(update):
        return

    msg = await update.message.reply_text("📡 جاري فحص الاتصال...")

    result = await monitor.check_internet()

    status = "🟢 متصل" if result.get('online') else "🔴 غير متصل"

    text = (
        f"📡 <b>حالة الإنترنت - شبكة حمد نت</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"الحالة: <b>{status}</b>\n\n"
        f"📊 <b>التأخير:</b>\n"
    )

    for name, latency in result.get('latency', {}).items():
        if latency >= 0:
            lat_emoji = "🟢" if latency < 50 else "🟡" if latency < 150 else "🔴"
            text += f"   {lat_emoji} {name}: {latency:.1f} ms\n"
        else:
            text += f"   ❌ {name}: غير قابل للوصول\n"

    text += (
        f"\n🔍 <b>التشخيص:</b>\n"
        f"   Gateway: {'✅' if result.get('gateway_reachable') else '❌'}\n"
        f"   DNS: {'✅' if result.get('dns_working') else '❌'}\n"
        f"   HTTP: {'✅' if result.get('http_working') else '❌'}\n"
        f"   WAN: {'✅' if result.get('wan_interface_up') else '❌'}\n"
    )

    if result.get('diagnosis'):
        text += f"\n📝 التشخيص: {result['diagnosis']}"

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔍 تشخيص", callback_data="diag_internet"),
            InlineKeyboardButton("📡 تتبع المسار", callback_data="trace_route"),
        ],
        [
            InlineKeyboardButton("📊 الباندويث", callback_data="bandwidth"),
            InlineKeyboardButton("🏠 الرئيسية", callback_data="dashboard"),
        ],
    ])

    await msg.edit_text(text, reply_markup=keyboard, parse_mode=ParseMode.HTML)


async def outages_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """سجل الانقطاعات"""
    if not is_authorized(update):
        return

    outages = db.get_recent_outages(20)

    if not outages:
        await update.message.reply_text("✅ لا توجد انقطاعات مسجلة.")
        return

    text = f"📋 <b>سجل الانقطاعات</b>\n\n"

    for i, o in enumerate(outages, 1):
        status = "🔴" if not o.get('resolved') else "🟢"
        duration = o.get('duration_seconds')
        if duration:
            mins = int(duration // 60)
            secs = int(duration % 60)
            dur_text = f"{mins} دقيقة و {secs} ثانية"
        else:
            dur_text = "مستمر"

        text += (
            f"{i}. {status} {o.get('outage_type', '')} - {o.get('affected_area', '')}\n"
            f"   🕐 {o.get('start_time', '')[:19]} | ⏱️ {dur_text}\n"
        )

    await update.message.reply_text(text, parse_mode=ParseMode.HTML)


async def trace_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تتبع المسار"""
    if not is_authorized(update):
        return

    target = context.args[0] if context.args else '8.8.8.8'
    msg = await update.message.reply_text(f"📡 جاري تتبع المسار إلى {target}...")

    hops = await monitor.trace_route(target)

    if not hops:
        await msg.edit_text("❌ فشل تتبع المسار. تأكد من تثبيت traceroute.")
        return

    text = f"🗺️ <b>تتبع المسار إلى {target}</b>\n\n"
    for hop in hops:
        if 'raw' in hop:
            text += f"{hop['raw']}\n"
        elif hop.get('ip'):
            lat = hop.get('latency', '')
            text += f"  {hop.get('hop', '?'):>2}. {hop['ip']:>15}  {lat} ms\n"

    await msg.edit_text(text, parse_mode=ParseMode.HTML)


async def dns_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """حالة DNS"""
    if not is_authorized(update):
        return

    result = await monitor.get_dns_info()

    text = "🌐 <b>حالة DNS - شبكة حمد نت</b>\n\n"

    if result.get('servers'):
        text += "📡 خوادم DNS:\n"
        for s in result['servers']:
            text += f"   • {s}\n"

    if result.get('allow_remote') is not None:
        text += f"\n🔓 السماح بالطلبات البعيدة: {'⚠️ نعم' if result['allow_remote'] else '✅ لا'}"

    if result.get('cache_size'):
        text += f"\n💾 حجم الذاكرة المؤقتة: {result.get('cache_used', '0')}/{result['cache_size']}"

    if result.get('test'):
        text += "\n\n🧪 اختبار DNS:\n"
        for name, working in result['test'].items():
            text += f"   {'✅' if working else '❌'} {name}\n"

    await update.message.reply_text(text, parse_mode=ParseMode.HTML)


# === أوامر الإحصائيات ===

async def bandwidth_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """استهلاك الباندويث"""
    if not is_authorized(update):
        return

    stats = await monitor.get_bandwidth_stats()

    text = (
        f"📊 <b>استهلاك الباندويث - شبكة حمد نت</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
    )

    if stats.get('interfaces'):
        text += "📡 واجهات الشبكة:\n"
        for iface in stats['interfaces']:
            text += (
                f"   🔹 {iface['name']} ({iface.get('type', '')})\n"
                f"      ⬇️ {iface.get('download_speed_formatted', '0')}\n"
                f"      ⬆️ {iface.get('upload_speed_formatted', '0')}\n"
            )

    if stats.get('total_download_formatted'):
        text += (
            f"\n📦 الإجمالي:\n"
            f"   ⬇️ التحميل: {stats['total_download_formatted']}\n"
            f"   ⬆️ الرفع: {stats['total_upload_formatted']}\n"
        )

    if stats.get('top_users'):
        text += "\n🏆 أكبر المستخدمين (24 ساعة):\n"
        for i, user in enumerate(stats['top_users'], 1):
            dl = user.get('total_download', 0)
            ul = user.get('total_upload', 0)
            text += f"   {i}. {user.get('mac_address', '')[:17]} - ⬇️{dl/1024/1024:.1f}MB ⬆️{ul/1024/1024:.1f}MB\n"

    await update.message.reply_text(text, parse_mode=ParseMode.HTML)


async def topusers_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """أكبر مستخدمي الباندويث"""
    if not is_authorized(update):
        return

    users = db.get_top_bandwidth_users(hours=24, limit=10)

    if not users:
        await update.message.reply_text("لا توجد بيانات استخدام.")
        return

    text = "🏆 <b>أكبر مستخدمي الباندويث (24 ساعة)</b>\n\n"
    for i, u in enumerate(users, 1):
        dl = u.get('total_download', 0)
        ul = u.get('total_upload', 0)
        total = dl + ul
        name = u.get('mac_address', '')
        device = db.get_device_by_mac(u.get('mac_address', ''))
        if device:
            name = device.get('nickname') or device.get('hostname') or name

        text += (
            f"{i}. <code>{name}</code>\n"
            f"   ⬇️ {dl/1024/1024:.1f} MB | ⬆️ {ul/1024/1024:.1f} MB | 📊 {total/1024/1024:.1f} MB\n"
        )

    await update.message.reply_text(text, parse_mode=ParseMode.HTML)


# === أوامر التحكم ===

async def router_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معلومات الراوتر"""
    if not is_authorized(update):
        return

    if not router or not router.connected:
        await update.message.reply_text("❌ غير متصل بالراوتر.")
        return

    try:
        info = await router.get_system_info()
        mem = await router.get_memory_usage()

        text = (
            f"🖥️ <b>معلومات الراوتر - شبكة حمد نت</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"📛 الاسم: <b>{info.get('identity', 'غير معروف')}</b>\n"
            f"📦 الموديل: {info.get('model', 'غير معروف')}\n"
            f"🔧 الإصدار: {info.get('version', 'غير معروف')}\n"
            f"💾 البرنامج الثابت: {info.get('firmware', 'غير معروف')}\n"
            f"⚙️ المعالج: {info.get('cpu', 'غير معروف')} ({info.get('cpu_count', 1)} نواة)\n"
            f"📊 تحميل المعالج: {info.get('cpu_load', 0)}%\n"
            f"🧠 الذاكرة: {mem.get('used_mb', 0)}/{mem.get('total_mb', 0)} MB ({mem.get('usage_percent', 0)}%)\n"
            f"⏱️ وقت التشغيل: {info.get('uptime', 'غير معروف')}\n"
            f"🏗️ البنية: {info.get('architecture', 'غير معروف')}\n"
        )

        if info.get('routerboard_model'):
            text += (
                f"\n🔌 RouterBoard:\n"
                f"   الموديل: {info['routerboard_model']}\n"
                f"   الرقم التسلسلي: {info.get('serial_number', 'غير معروف')}\n"
            )

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("🔄 إعادة تشغيل", callback_data="confirm_reboot"),
                InlineKeyboardButton("📋 السجلات", callback_data="logs"),
            ],
            [InlineKeyboardButton("🏠 الرئيسية", callback_data="dashboard")],
        ])

        await update.message.reply_text(text, reply_markup=keyboard, parse_mode=ParseMode.HTML)

    except Exception as e:
        await update.message.reply_text(f"❌ خطأ في جلب معلومات الراوتر: {e}")


async def reboot_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """إعادة تشغيل الراوتر"""
    if not is_authorized(update):
        return

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ نعم، أعد التشغيل", callback_data="do_reboot"),
            InlineKeyboardButton("❌ إلغاء", callback_data="dashboard"),
        ],
    ])

    await update.message.reply_text(
        "⚠️ <b>هل أنت متأكد من إعادة تشغيل الراوتر؟</b>\n"
        "سيؤدي ذلك إلى انقطاع الإنترنت مؤقتاً.",
        reply_markup=keyboard, parse_mode=ParseMode.HTML
    )


async def scan_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """فحص الشبكة الآن"""
    if not is_authorized(update):
        return

    msg = await update.message.reply_text("🔍 جاري فحص الشبكة...")

    changes = await scanner.full_scan()
    net_changes = await scanner.detect_network_changes()

    text = "🔍 <b>نتائج فحص الشبكة</b>\n\n"

    if changes['new_devices']:
        text += f"📱 أجهزة جديدة: <b>{len(changes['new_devices'])}</b>\n"
        for d in changes['new_devices'][:5]:
            name = d.get('hostname', d.get('mac', ''))
            text += f"   • {name} ({d.get('ip', '')})\n"

    if changes['left_devices']:
        text += f"\n📤 أجهزة غادرت: <b>{len(changes['left_devices'])}</b>\n"

    if changes['changed_devices']:
        text += f"\n🔄 أجهزة تغيرت: <b>{len(changes['changed_devices'])}</b>\n"

    if net_changes:
        text += f"\n⚙️ تغييرات في الشبكة: <b>{len(net_changes)}</b>\n"
        for c in net_changes[:5]:
            text += f"   • {c.get('description', '')}\n"

    if not any([changes['new_devices'], changes['left_devices'], changes['changed_devices'], net_changes]):
        text += "✅ لا توجد تغييرات جديدة."

    await msg.edit_text(text, parse_mode=ParseMode.HTML)


async def limit_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تحديد سرعة جهاز /limit IP DL UL"""
    if not is_authorized(update):
        return

    if len(context.args) < 3:
        await update.message.reply_text(
            "⚠️ الاستخدام: /limit [IP] [تحميل] [رفع]\n"
            "مثال: /limit 192.168.1.100 10M 5M\n"
            "الوحدات: K (كيلو), M (ميجا), G (جيجا)"
        )
        return

    ip, dl, ul = context.args[0], context.args[1], context.args[2]

    if not router or not router.connected:
        await update.message.reply_text("❌ غير متصل بالراوتر.")
        return

    success = await router.set_bandwidth_limit(ip, dl, ul)
    if success:
        await update.message.reply_text(f"✅ تم تحديد سرعة {ip}: ⬇️{dl} ⬆️{ul}")
    else:
        await update.message.reply_text(f"❌ فشل تحديد السرعة.")


# === أوامر الصيانة ===

async def logs_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """سجلات النظام"""
    if not is_authorized(update):
        return

    if not router or not router.connected:
        await update.message.reply_text("❌ غير متصل بالراوتر.")
        return

    logs = await router.get_system_logs()

    if not logs:
        await update.message.reply_text("لا توجد سجلات.")
        return

    text = "📋 <b>سجلات النظام (آخر 20)</b>\n\n"
    for log in logs[-20:]:
        text += f"[{log.get('time', '')}] {log.get('message', '')[:100]}\n"

    # تقسيم إذا كان طويلاً
    if len(text) > 4000:
        text = text[:4000] + "\n... (مقتطع)"

    await update.message.reply_text(text, parse_mode=ParseMode.HTML)


async def changes_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """التغييرات الأخيرة"""
    if not is_authorized(update):
        return

    changes = db.get_recent_config_changes(20)
    connections = db.get_recent_connections(20)

    text = "📝 <b>آخر التغييرات والأحداث</b>\n\n"

    if changes:
        text += "⚙️ <b>تغييرات التهيئة:</b>\n"
        for c in changes[:10]:
            text += f"   • [{c.get('change_type', '')}] {c.get('description', '')[:60]}\n"

    if connections:
        text += "\n📱 <b>أحداث الاتصال:</b>\n"
        for c in connections[:10]:
            event = "🟢 دخول" if c.get('event_type') == 'connect' else "🔴 خروج"
            name = c.get('nickname') or c.get('hostname') or c.get('mac_address', '')[:8]
            text += f"   {event} {name} ({c.get('ip_address', '')})\n"

    await update.message.reply_text(text, parse_mode=ParseMode.HTML)


async def resolve_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة تنبيه /resolve ID"""
    if not is_authorized(update):
        return

    if not context.args:
        await update.message.reply_text("⚠️ الاستخدام: /resolve [رقم التنبيه]")
        return

    try:
        alert_id = int(context.args[0])
        db.resolve_alert(alert_id, resolved_by=str(update.effective_user.username or update.effective_user.id))
        await update.message.reply_text(f"✅ تم معالجة التنبيه #{alert_id}.")
    except ValueError:
        await update.message.reply_text("❌ رقم التنبيه غير صالح.")


# ==========================================
# معالجة الأزرار (Callback Queries)
# ==========================================

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة الضغط على الأزرار"""
    query = update.callback_query
    await query.answer()

    if not is_authorized(update):
        await query.answer("⛔ غير مصرح", show_alert=True)
        return

    data = query.data

    # === التنقل الرئيسي ===
    if data == "dashboard":
        await _send_dashboard(query, is_query=True)

    elif data == "devices":
        devices = db.get_all_devices()
        text = f"📱 <b>جميع الأجهزة ({len(devices)})</b>\n\n"
        for i, d in enumerate(devices[:20], 1):
            status = "🟢" if d.get('is_online') else "🔴"
            auth = "✅" if d.get('is_authorized') else "⚠️"
            name = d.get('nickname') or d.get('hostname') or 'غير معروف'
            text += f"{i}. {status}{auth} <code>{name}</code> - {d['ip_address']}\n"

        kb = [[InlineKeyboardButton("🏠 الرئيسية", callback_data="dashboard")]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.HTML)

    elif data == "security":
        await query.edit_message_text("🔍 جاري الفحص الأمني...")
        result = await security.full_security_check()
        status_emoji = {'secure': '🟢', 'caution': '🔵', 'warning': '🟡', 'danger': '🔴'}
        status = status_emoji.get(result['overall_status'], '⚪')

        text = (
            f"🛡️ <b>الحالة الأمنية: {status} {result['overall_status'].upper()}</b>\n\n"
            f"⚠️ أجهزة غير مرخصة: {len(result.get('unauthorized_devices', []))}\n"
            f"🚨 محاولات اختراق: {len(result.get('intrusion_attempts', []))}\n"
            f"🔍 نشاط مشبوه: {len(result.get('suspicious_activity', []))}\n"
            f"🔥 مشاكل الجدار الناري: {len(result.get('firewall_issues', []))}\n"
            f"🔓 ثغرات: {len(result.get('vulnerabilities', []))}\n"
        )

        kb = [
            [InlineKeyboardButton("📋 التنبيهات", callback_data="alerts"),
             InlineKeyboardButton("🔄 إعادة الفحص", callback_data="security")],
            [InlineKeyboardButton("🏠 الرئيسية", callback_data="dashboard")],
        ]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.HTML)

    elif data == "internet":
        result = await monitor.check_internet()
        status = "🟢 متصل" if result.get('online') else "🔴 غير متصل"

        text = (
            f"📡 <b>حالة الإنترنت: {status}</b>\n\n"
        )
        for name, latency in result.get('latency', {}).items():
            if latency >= 0:
                text += f"   {name}: {latency:.1f} ms\n"
            else:
                text += f"   {name}: ❌\n"

        kb = [
            [InlineKeyboardButton("🔍 تشخيص", callback_data="diag_internet"),
             InlineKeyboardButton("📡 تتبع", callback_data="trace_route")],
            [InlineKeyboardButton("🏠 الرئيسية", callback_data="dashboard")],
        ]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.HTML)

    elif data == "bandwidth":
        stats = await monitor.get_bandwidth_stats()
        text = "📊 <b>استهلاك الباندويث</b>\n\n"
        for iface in stats.get('interfaces', []):
            text += (
                f"🔹 {iface['name']}\n"
                f"   ⬇️ {iface.get('download_speed_formatted', '0')}\n"
                f"   ⬆️ {iface.get('upload_speed_formatted', '0')}\n\n"
            )
        kb = [[InlineKeyboardButton("🏠 الرئيسية", callback_data="dashboard")]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.HTML)

    elif data == "alerts":
        alerts = db.get_unresolved_alerts()
        if not alerts:
            await query.edit_message_text("✅ لا توجد تنبيهات.", reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("🏠 الرئيسية", callback_data="dashboard")]]
            ))
            return

        text = f"🔔 <b>التنبيهات ({len(alerts)})</b>\n\n"
        for i, a in enumerate(alerts[:10], 1):
            sev = {'critical': '🔴', 'high': '🟠', 'medium': '🟡', 'low': '🔵'}.get(a.get('severity', ''), '⚪')
            text += f"{i}. {sev} {a.get('description', '')[:60]}\n"

        kb = [
            [InlineKeyboardButton("✅ معالجة الكل", callback_data="resolve_all")],
            [InlineKeyboardButton("🏠 الرئيسية", callback_data="dashboard")],
        ]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.HTML)

    elif data == "settings":
        text = (
            "⚙️ <b>إعدادات بوت حمد نت</b>\n\n"
            f"📡 نوع الراوتر: {config.ROUTER_TYPE}\n"
            f"🌐 الشبكة: {config.NETWORK_SUBNET}\n"
            f"⏱️ فترة الفحص: {config.SCAN_INTERVAL} ثانية\n"
            f"🔒 حظر تلقائي: {'✅' if config.AUTO_BLOCK_INTRUSION else '❌'}\n"
            f"🛰️ Starlink: {'✅' if config.STARLINK_ENABLED else '❌'}\n\n"
            f"📱 تنبيهات:\n"
            f"   جهاز جديد: {'✅' if config.ALERT_ON_NEW_DEVICE else '❌'}\n"
            f"   مغادرة جهاز: {'✅' if config.ALERT_ON_DEVICE_LEAVE else '❌'}\n"
            f"   اختراق: {'✅' if config.ALERT_ON_INTRUSION else '❌'}\n"
            f"   انقطاع: {'✅' if config.ALERT_ON_OUTAGE else '❌'}\n"
            f"   تغييرات: {'✅' if config.ALERT_ON_CONFIG_CHANGE else '❌'}\n"
        )
        kb = [
            [InlineKeyboardButton("🔄 فحص الآن", callback_data="scan_now")],
            [InlineKeyboardButton("🏠 الرئيسية", callback_data="dashboard")],
        ]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.HTML)

    elif data == "help":
        text = (
            "📖 <b>التعليمات</b>\n\n"
            "استخدم الأوامر التالية أو الأزرار:\n\n"
            "/dashboard - لوحة التحكم\n"
            "/devices - الأجهزة\n"
            "/security - الأمان\n"
            "/internet - الإنترنت\n"
            "/bandwidth - الباندويث\n"
            "/scan - فحص الشبكة\n"
            "/help - المساعدة\n"
        )
        kb = [[InlineKeyboardButton("🏠 الرئيسية", callback_data="dashboard")]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.HTML)

    # === أزرار الإجراءات ===
    elif data.startswith("detail_"):
        mac = data.replace("detail_", "")
        device = db.get_device_by_mac(mac)
        if not device:
            await query.answer("الجهاز غير موجود", show_alert=True)
            return

        name = device.get('nickname') or device.get('hostname') or 'غير معروف'
        dtype = format_device_type(device.get('device_type', 'unknown'))
        status = "🟢 متصل" if device.get('is_online') else "🔴 غير متصل"
        auth = "✅ مرخص" if device.get('is_authorized') else "⚠️ غير مرخص"
        blocked = "🚫 محظور" if device.get('blocked') else ""

        text = (
            f"📱 <b>تفاصيل الجهاز</b>\n\n"
            f"📛 الاسم: <code>{name}</code>\n"
            f"🌐 IP: <code>{device['ip_address']}</code>\n"
            f"🔗 MAC: <code>{device['mac_address']}</code>\n"
            f"📋 النوع: {dtype}\n"
            f"🏭 الشركة: {device.get('vendor', 'غير معروف')}\n"
            f"📊 الحالة: {status} {blocked}\n"
            f"🔐 الترخيص: {auth}\n"
            f"🕐 أول ظهور: {device.get('first_seen', '')[:19]}\n"
            f"🕐 آخر ظهور: {device.get('last_seen', '')[:19]}\n"
        )

        if device.get('notes'):
            text += f"📝 ملاحظات: {device['notes']}\n"

        kb = [
            [
                InlineKeyboardButton("✅ ترخيص" if not device.get('is_authorized') else "❌ إلغاء ترخيص",
                                     callback_data=f"auth_{mac}"),
                InlineKeyboardButton("🚫 حظر" if not device.get('blocked') else "✅ إلغاء حظر",
                                     callback_data=f"block_{mac}"),
            ],
            [
                InlineKeyboardButton("📝 تسمية", callback_data=f"nick_{mac}"),
                InlineKeyboardButton("📊 السرعة", callback_data=f"speed_{mac}"),
            ],
            [InlineKeyboardButton("🔙 العودة", callback_data="devices")],
        ]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.HTML)

    elif data.startswith("auth_"):
        mac = data.replace("auth_", "")
        device = db.get_device_by_mac(mac)
        if device:
            new_auth = not device.get('is_authorized', False)
            db.authorize_device(mac, new_auth)
            action = "ترخيص" if new_auth else "إلغاء ترخيص"
            await query.answer(f"✅ تم {action} الجهاز", show_alert=True)
            # Refresh detail view
            update.callback_query.data = f"detail_{mac}"
            await button_handler(update, context)

    elif data.startswith("block_"):
        identifier = data.replace("block_", "")
        if ":" in identifier:  # MAC address
            success = await security.block_device(identifier)
            if success:
                await query.answer("🚫 تم حظر الجهاز", show_alert=True)
            else:
                await query.answer("❌ فشل الحظر", show_alert=True)
        else:
            await query.answer("⚠️ يجب استخدام MAC Address للحظر", show_alert=True)

    elif data.startswith("nick_"):
        mac = data.replace("nick_", "")
        context.user_data['pending_nickname_mac'] = mac
        await query.edit_message_text(
            "📝 أرسل الاسم المستعار للجهاز:\n"
            f"MAC: <code>{mac}</code>",
            parse_mode=ParseMode.HTML
        )

    elif data.startswith("speed_"):
        mac = data.replace("speed_", "")
        device = db.get_device_by_mac(mac)
        if device and device.get('ip_address'):
            ip = device['ip_address']
            keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("1M/1M", callback_data=f"ratelimit_{ip}_1M_1M"),
                    InlineKeyboardButton("5M/5M", callback_data=f"ratelimit_{ip}_5M_5M"),
                ],
                [
                    InlineKeyboardButton("10M/10M", callback_data=f"ratelimit_{ip}_10M_10M"),
                    InlineKeyboardButton("20M/20M", callback_data=f"ratelimit_{ip}_20M_20M"),
                ],
                [
                    InlineKeyboardButton("🚫 إزالة التحديد", callback_data=f"removelimit_{ip}"),
                ],
                [InlineKeyboardButton("🔙 العودة", callback_data=f"detail_{mac}")],
            ])
            await query.edit_message_text(
                f"⚡ <b>تحديد سرعة الجهاز {ip}</b>\n\nاختر السرعة:",
                reply_markup=keyboard, parse_mode=ParseMode.HTML
            )
        else:
            await query.answer("لا يمكن تحديد السرعة", show_alert=True)

    elif data.startswith("ratelimit_"):
        parts = data.replace("ratelimit_", "").split("_")
        if len(parts) >= 3:
            ip, dl, ul = parts[0], parts[1], parts[2]
            success = await router.set_bandwidth_limit(ip, dl, ul)
            if success:
                await query.answer(f"✅ تم تحديد السرعة: ⬇️{dl} ⬆️{ul}", show_alert=True)
            else:
                await query.answer("❌ فشل تحديد السرعة", show_alert=True)

    elif data.startswith("removelimit_"):
        ip = data.replace("removelimit_", "")
        success = await router.remove_bandwidth_limit(ip)
        if success:
            await query.answer("✅ تم إزالة تحديد السرعة", show_alert=True)
        else:
            await query.answer("❌ فشل إزالة التحديد", show_alert=True)

    elif data == "confirm_reboot":
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ نعم، أعد التشغيل", callback_data="do_reboot")],
            [InlineKeyboardButton("❌ إلغاء", callback_data="dashboard")],
        ])
        await query.edit_message_text(
            "⚠️ <b>هل أنت متأكد؟</b>\nسيتم إعادة تشغيل الراوتر.",
            reply_markup=keyboard, parse_mode=ParseMode.HTML
        )

    elif data == "do_reboot":
        await query.edit_message_text("🔄 جاري إعادة تشغيل الراوتر...")
        success = await router.reboot()
        if success:
            await query.edit_message_text("✅ تم إرسال أمر إعادة التشغيل. انتظر دقيقة ثم تحقق.")
        else:
            await query.edit_message_text("❌ فشل إعادة التشغيل.")

    elif data == "diag_internet":
        await query.edit_message_text("🔍 جاري التشخيص...")
        result = await monitor.check_internet()
        text = f"🔍 <b>تشخيص الإنترنت</b>\n\n"
        text += f"Gateway: {'✅' if result.get('gateway_reachable') else '❌'}\n"
        text += f"DNS: {'✅' if result.get('dns_working') else '❌'}\n"
        text += f"HTTP: {'✅' if result.get('http_working') else '❌'}\n"
        text += f"WAN: {'✅' if result.get('wan_interface_up') else '❌'}\n"
        if result.get('diagnosis'):
            text += f"\n📝 {result['diagnosis']}"

        kb = [[InlineKeyboardButton("🏠 الرئيسية", callback_data="dashboard")]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.HTML)

    elif data == "trace_route":
        await query.edit_message_text("📡 جاري تتبع المسار...")
        hops = await monitor.trace_route()
        text = "🗺️ <b>تتبع المسار</b>\n\n"
        for hop in hops[:15]:
            if 'raw' in hop:
                text += f"{hop['raw']}\n"
        kb = [[InlineKeyboardButton("🏠 الرئيسية", callback_data="dashboard")]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.HTML)

    elif data == "diag_outage":
        result = await monitor.check_internet()
        text = f"🔍 <b>تشخيص الانقطاع</b>\n\n"
        text += f"Gateway: {'✅' if result.get('gateway_reachable') else '❌'}\n"
        text += f"DNS: {'✅' if result.get('dns_working') else '❌'}\n"
        text += f"WAN: {'✅' if result.get('wan_interface_up') else '❌'}\n"
        if result.get('diagnosis'):
            text += f"\n📝 {result['diagnosis']}"
        kb = [[InlineKeyboardButton("🏠 الرئيسية", callback_data="dashboard")]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.HTML)

    elif data == "resolve_all":
        alerts = db.get_unresolved_alerts()
        for a in alerts:
            db.resolve_alert(a['id'], resolved_by="bot_button")
        await query.answer(f"✅ تم معالجة {len(alerts)} تنبيه", show_alert=True)

    elif data == "block_all_unauth":
        devices = db.get_all_devices(online_only=True)
        unauth = [d for d in devices if not d.get('is_authorized', False)]
        count = 0
        for d in unauth:
            success = await security.block_device(d['mac_address'])
            if success:
                count += 1
        await query.answer(f"🚫 تم حظر {count} جهاز غير مرخص", show_alert=True)

    elif data == "scan_now":
        await query.edit_message_text("🔍 جاري فحص الشبكة...")
        changes = await scanner.full_scan()
        text = "✅ تم الفحص\n\n"
        if changes['new_devices']:
            text += f"📱 أجهزة جديدة: {len(changes['new_devices'])}\n"
        if changes['left_devices']:
            text += f"📤 أجهزة غادرت: {len(changes['left_devices'])}\n"
        if not any([changes['new_devices'], changes['left_devices']]):
            text += "لا توجد تغييرات."
        kb = [[InlineKeyboardButton("🏠 الرئيسية", callback_data="dashboard")]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.HTML)

    elif data == "logs":
        if router and router.connected:
            logs = await router.get_system_logs()
            text = "📋 <b>السجلات</b>\n\n"
            for log in logs[-15:]:
                text += f"[{log.get('time', '')}] {log.get('message', '')[:80]}\n"
            if len(text) > 4000:
                text = text[:4000]
        else:
            text = "❌ غير متصل بالراوتر"
        kb = [[InlineKeyboardButton("🏠 الرئيسية", callback_data="dashboard")]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.HTML)

    elif data.startswith("ignore_"):
        await query.answer("تم التجاهل", show_alert=False)

    elif data == "online_devs":
        devices = db.get_all_devices(online_only=True)
        text = f"🟢 <b>الأجهزة المتصلة ({len(devices)})</b>\n\n"
        for i, d in enumerate(devices[:20], 1):
            name = d.get('nickname') or d.get('hostname') or 'غير معروف'
            text += f"{i}. ✅ <code>{name}</code> - {d['ip_address']}\n"
        kb = [[InlineKeyboardButton("🏠 الرئيسية", callback_data="dashboard")]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.HTML)


# === معالجة الرسائل النصية ===

async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة الرسائل النصية"""
    if not is_authorized(update):
        return

    # معالجة إدخال الاسم المستعار
    if 'pending_nickname_mac' in context.user_data:
        mac = context.user_data['pending_nickname_mac']
        nickname = update.message.text
        db.set_device_nickname(mac, nickname)
        del context.user_data['pending_nickname_mac']
        await update.message.reply_text(f"✅ تم تعيين الاسم المستعار: <code>{nickname}</code>", parse_mode=ParseMode.HTML)
        return

    # رسالة افتراضية
    await update.message.reply_text(
        "🤖 استخدم الأوامر أو الأزرار للتفاعل.\n"
        "اضغط /help لعرض الأوامر المتاحة."
    )


# ==========================================
# المهام الدورية
# ==========================================

async def periodic_network_scan(context: ContextTypes.DEFAULT_TYPE):
    """فحص دوري للشبكة"""
    try:
        changes = await scanner.full_scan()

        # تنبيهات الأجهزة الجديدة
        for device in changes.get('new_devices', []):
            await notifier.notify_new_device(device)

        # تنبيهات مغادرة الأجهزة
        for device in changes.get('left_devices', []):
            await notifier.notify_device_left(device)

        # كشف تغييرات الشبكة
        net_changes = await scanner.detect_network_changes()
        for change in net_changes:
            await notifier.notify_config_change(change)
            db.log_config_change(
                change_type=change.get('type', ''),
                description=change.get('description', ''),
            )

    except Exception as e:
        logger.error(f"خطأ في الفحص الدوري: {e}")


async def periodic_internet_check(context: ContextTypes.DEFAULT_TYPE):
    """فحص دوري للإنترنت"""
    try:
        result = await monitor.check_internet()

        if result.get('outage_detected'):
            await notifier.notify_outage({
                'type': result.get('outage_type', 'unknown'),
                'description': result.get('diagnosis', 'انقطاع الإنترنت'),
                'affected_area': 'جميع المستخدمين',
            })

        elif result.get('outage_end'):
            duration = result.get('outage_duration', 0)
            diagnosis = result.get('diagnosis', 'تم الاستعادة')
            await notifier.notify_outage_resolved(duration, diagnosis)

    except Exception as e:
        logger.error(f"خطأ في فحص الإنترنت الدوري: {e}")


async def periodic_security_check(context: ContextTypes.DEFAULT_TYPE):
    """فحص أمني دوري"""
    try:
        result = await security.full_security_check()

        # تنبيهات الاختراقات
        for attempt in result.get('intrusion_attempts', []):
            await notifier.notify_intrusion_attempt(attempt)

        # تنبيهات الأجهزة غير المرخصة
        for device in result.get('unauthorized_devices', []):
            if not db.get_device_by_mac(device.get('mac', '')):
                await notifier.notify_unauthorized_device(device)

    except Exception as e:
        logger.error(f"خطأ في الفحص الأمني الدوري: {e}")


async def periodic_bandwidth_monitor(context: ContextTypes.DEFAULT_TYPE):
    """مراقبة الباندويث الدورية"""
    try:
        stats = await monitor.get_bandwidth_stats()
        for iface in stats.get('interfaces', []):
            dl_speed = iface.get('download_speed', 0)
            ul_speed = iface.get('upload_speed', 0)
            total_speed = (dl_speed + ul_speed) * 8 / 1_000_000  # تحويل إلى Mbps

            if total_speed > config.HIGH_BANDWIDTH_THRESHOLD:
                await notifier.notify_high_bandwidth(iface['name'], total_speed)

        # تسجيل الباندويث
        devices = db.get_all_devices(online_only=True)
        for d in devices:
            db.log_bandwidth(
                mac=d['mac_address'], ip=d['ip_address'],
                dl_bytes=0, ul_bytes=0,
                dl_speed=0, ul_speed=0,
            )

    except Exception as e:
        logger.error(f"خطأ في مراقبة الباندويث: {e}")


async def periodic_cleanup(context: ContextTypes.DEFAULT_TYPE):
    """تنظيف دوري"""
    try:
        db.cleanup_old_records(config.MAX_LOG_ENTRIES)
    except Exception as e:
        logger.error(f"خطأ في التنظيف الدوري: {e}")


# ==========================================
# تشغيل البوت
# ==========================================

async def post_init(application: Application):
    """تهيئة بعد بدء البوت"""
    global db, router, scanner, security, monitor, notifier

    # إنشاء قاعدة البيانات
    db = Database(config.DATABASE_PATH)

    # إنشاء اتصال الراوتر
    router = create_router()
    try:
        connected = await router.connect()
        if connected:
            logger.info("✅ تم الاتصال بالراوتر بنجاح")
        else:
            logger.warning("⚠️ لم يتم الاتصال بالراوتر - سيعمل البوت بوضع محدود")
    except Exception as e:
        logger.warning(f"⚠️ فشل الاتصال بالراوتر: {e} - سيعمل البوت بوضع محدود")

    # إنشاء الوحدات
    scanner = NetworkScanner(db, router)
    security = SecurityMonitor(db, router)
    monitor = InternetMonitor(db, router)
    notifier = NotificationHandler(application.bot)

    # إعداد المهام الدورية
    job_queue = application.job_queue

    # فحص الشبكة
    job_queue.run_repeating(
        periodic_network_scan,
        interval=config.SCAN_INTERVAL,
        first=10,
        name="network_scan",
    )

    # فحص الإنترنت
    job_queue.run_repeating(
        periodic_internet_check,
        interval=config.PING_INTERVAL,
        first=5,
        name="internet_check",
    )

    # الفحص الأمني
    job_queue.run_repeating(
        periodic_security_check,
        interval=config.SECURITY_CHECK_INTERVAL,
        first=30,
        name="security_check",
    )

    # مراقبة الباندويث
    job_queue.run_repeating(
        periodic_bandwidth_monitor,
        interval=config.BANDWIDTH_MONITOR_INTERVAL,
        first=15,
        name="bandwidth_monitor",
    )

    # تنظيف
    job_queue.run_repeating(
        periodic_cleanup,
        interval=3600,  # كل ساعة
        first=60,
        name="cleanup",
    )

    # تسجيل أوامر البوت
    if config.AUTHORIZED_CHAT_IDS:
        commands = [
            BotCommand("start", "🏠 الرئيسية"),
            BotCommand("dashboard", "📊 لوحة التحكم"),
            BotCommand("devices", "📱 الأجهزة"),
            BotCommand("online", "🟢 الأجهزة المتصلة"),
            BotCommand("security", "🔒 الفحص الأمني"),
            BotCommand("internet", "📡 حالة الإنترنت"),
            BotCommand("bandwidth", "📊 الباندويث"),
            BotCommand("scan", "🔍 فحص الشبكة"),
            BotCommand("alerts", "🔔 التنبيهات"),
            BotCommand("router", "🖥️ الراوتر"),
            BotCommand("help", "❓ المساعدة"),
        ]
        for chat_id in config.AUTHORIZED_CHAT_IDS:
            try:
                await application.bot.set_my_commands(commands, BotCommandScopeChat(chat_id))
            except:
                pass

    logger.info("🚀 بوت حمد نت جاهز للعمل!")


def main():
    """تشغيل البوت الرئيسي"""
    if not config.TELEGRAM_BOT_TOKEN:
        print("❌ يجب تعيين TELEGRAM_BOT_TOKEN في ملف .env")
        sys.exit(1)

    # إنشاء التطبيق
    application = Application.builder().token(config.TELEGRAM_BOT_TOKEN).post_init(post_init).build()

    # تسجيل الأوامر
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("dashboard", dashboard_command))
    application.add_handler(CommandHandler("devices", devices_command))
    application.add_handler(CommandHandler("online", online_command))
    application.add_handler(CommandHandler("offline", offline_command))
    application.add_handler(CommandHandler("unauthorized", unauthorized_command))
    application.add_handler(CommandHandler("security", security_command))
    application.add_handler(CommandHandler("alerts", alerts_command))
    application.add_handler(CommandHandler("block", block_command))
    application.add_handler(CommandHandler("unblock", unblock_command))
    application.add_handler(CommandHandler("internet", internet_command))
    application.add_handler(CommandHandler("outages", outages_command))
    application.add_handler(CommandHandler("trace", trace_command))
    application.add_handler(CommandHandler("dns", dns_command))
    application.add_handler(CommandHandler("bandwidth", bandwidth_command))
    application.add_handler(CommandHandler("topusers", topusers_command))
    application.add_handler(CommandHandler("router", router_command))
    application.add_handler(CommandHandler("reboot", reboot_command))
    application.add_handler(CommandHandler("scan", scan_command))
    application.add_handler(CommandHandler("limit", limit_command))
    application.add_handler(CommandHandler("logs", logs_command))
    application.add_handler(CommandHandler("changes", changes_command))
    application.add_handler(CommandHandler("resolve", resolve_command))

    # معالجة الأزرار
    application.add_handler(CallbackQueryHandler(button_handler))

    # معالجة الرسائل النصية
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))

    # تشغيل البوت
    logger.info("🚀 بدء تشغيل بوت حمد نت...")
    application.run_polling(drop_pending_updates=True)


if __name__ == '__main__':
    main()
