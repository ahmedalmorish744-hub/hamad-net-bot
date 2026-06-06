"""
وحدة التنبيهات والإشعارات - Notification Handler
"""
import asyncio
import logging
from typing import Dict, List, Optional
from datetime import datetime

from telegram import Bot, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.constants import ParseMode

import config

logger = logging.getLogger(__name__)


class NotificationHandler:
    """إرسال التنبيهات والإشعارات عبر تليجرام"""

    def __init__(self, bot: Bot):
        self.bot = bot
        self.last_notifications: Dict[str, datetime] = {}
        self.notification_cooldown = 30  # ثانية بين التنبيهات المتكررة

    async def send_to_all(self, text: str, reply_markup=None, parse_mode=ParseMode.HTML):
        """إرسال رسالة لجميع المستخدمين المرخصين"""
        for chat_id in config.AUTHORIZED_CHAT_IDS:
            try:
                await self.bot.send_message(
                    chat_id=chat_id,
                    text=text,
                    reply_markup=reply_markup,
                    parse_mode=parse_mode,
                )
            except Exception as e:
                logger.error(f"خطأ في إرسال تنبيه لـ {chat_id}: {e}")

    def _can_send(self, notification_type: str) -> bool:
        """التحقق من عدم الإرسال المتكرر"""
        now = datetime.now()
        last = self.last_notifications.get(notification_type)
        if last and (now - last).total_seconds() < self.notification_cooldown:
            return False
        self.last_notifications[notification_type] = now
        return True

    # === تنبيهات الأجهزة ===

    async def notify_new_device(self, device: Dict):
        """تنبيه بجهاز جديد"""
        if not config.ALERT_ON_NEW_DEVICE:
            return
        if not self._can_send('new_device'):
            return

        mac = device.get('mac', '')
        ip = device.get('ip', '')
        hostname = device.get('hostname', '')
        vendor = device.get('vendor', '')
        unauthorized = device.get('unauthorized', False)

        emoji = "🚨" if unauthorized else "📱"
        status = "⚠️ <b>غير مرخص!</b>" if unauthorized else "✅"

        text = (
            f"{emoji} <b>جهاز جديد على شبكة حمد نت</b>\n\n"
            f"📋 الحالة: {status}\n"
            f"📛 الاسم: <code>{hostname or 'غير معروف'}</code>\n"
            f"🌐 IP: <code>{ip}</code>\n"
            f"🔗 MAC: <code>{mac}</code>\n"
            f"🏭 الشركة: {vendor}\n"
            f"🕐 الوقت: {datetime.now().strftime('%H:%M:%S - %Y/%m/%d')}\n"
        )

        keyboard = None
        if unauthorized:
            keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("✅ ترخيص", callback_data=f"auth_{mac}"),
                    InlineKeyboardButton("🚫 حظر", callback_data=f"block_{mac}"),
                ],
                [
                    InlineKeyboardButton("📋 التفاصيل", callback_data=f"detail_{mac}"),
                ],
            ])

        await self.send_to_all(text, reply_markup=keyboard)

    async def notify_device_left(self, device: Dict):
        """تنبيه بمغادرة جهاز"""
        if not config.ALERT_ON_DEVICE_LEAVE:
            return
        if not self._can_send('device_left'):
            return

        mac = device.get('mac_address', device.get('mac', ''))
        ip = device.get('ip_address', device.get('ip', ''))
        hostname = device.get('hostname', device.get('nickname', ''))

        text = (
            f"📤 <b>جهاز غادر الشبكة</b>\n\n"
            f"📛 الاسم: <code>{hostname or 'غير معروف'}</code>\n"
            f"🌐 IP: <code>{ip}</code>\n"
            f"🔗 MAC: <code>{mac}</code>\n"
            f"🕐 الوقت: {datetime.now().strftime('%H:%M:%S - %Y/%m/%d')}\n"
        )

        await self.send_to_all(text)

    # === تنبيهات الأمن ===

    async def notify_intrusion_attempt(self, attempt: Dict):
        """تنبيه بمحاولة اختراق"""
        if not config.ALERT_ON_INTRUSION:
            return
        if not self._can_send('intrusion'):
            return

        attack_type = attempt.get('type', 'unknown')
        source_ip = attempt.get('source_ip', '')
        source_mac = attempt.get('source_mac', '')
        description = attempt.get('description', '')
        severity = attempt.get('severity', 'high')

        severity_emoji = {
            'critical': '🔴',
            'high': '🟠',
            'medium': '🟡',
            'low': '🔵',
        }.get(severity, '⚪')

        type_names = {
            'brute_force': 'هجوم القوة الغاشمة',
            'port_scan': 'فحص المنافذ',
            'access_denied': 'وصول مرفوض',
            'firewall_drop': 'حظر جدار ناري',
            'intrusion': 'محاولة اختراق',
            'attack': 'هجوم',
            'ddos': 'هجوم DDoS',
            'flood': 'هجوم فيضاني',
            'mac_spoofing': 'انتحال MAC',
            'connection_refused': 'اتصال مرفوض',
        }

        text = (
            f"🚨 <b>تنبيه أمني - شبكة حمد نت</b>\n\n"
            f"{severity_emoji} المستوى: <b>{severity.upper()}</b>\n"
            f"⚡ النوع: <b>{type_names.get(attack_type, attack_type)}</b>\n"
            f"📝 الوصف: {description}\n"
        )

        if source_ip:
            text += f"🌐 IP المصدر: <code>{source_ip}</code>\n"
        if source_mac:
            text += f"🔗 MAC المصدر: <code>{source_mac}</code>\n"

        text += f"🕐 الوقت: {datetime.now().strftime('%H:%M:%S - %Y/%m/%d')}\n"

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("🚫 حظر", callback_data=f"block_{source_mac or source_ip}"),
                InlineKeyboardButton("🔍 تفاصيل", callback_data=f"detail_{source_mac or source_ip}"),
            ],
            [
                InlineKeyboardButton("✅ تجاهل", callback_data=f"ignore_{source_mac or source_ip}"),
            ],
        ])

        await self.send_to_all(text, reply_markup=keyboard)

    # === تنبيهات الانقطاع ===

    async def notify_outage(self, outage_info: Dict):
        """تنبيه بانقطاع الإنترنت"""
        if not config.ALERT_ON_OUTAGE:
            return
        if not self._can_send('outage'):
            return

        outage_type = outage_info.get('type', 'unknown')
        description = outage_info.get('description', '')
        affected_area = outage_info.get('affected_area', '')

        type_names = {
            'local_network': 'انقطاع محلي',
            'wan_down': 'انقطاع WAN',
            'internet_down': 'انقطاع الإنترنت',
            'dns_issue': 'مشكلة DNS',
            'partial_outage': 'انقطاع جزئي',
            'high_latency': 'بطء شديد',
        }

        text = (
            f"🔴 <b>انقطاع الإنترنت - شبكة حمد نت</b>\n\n"
            f"⚡ النوع: <b>{type_names.get(outage_type, outage_type)}</b>\n"
            f"📝 السبب: {description}\n"
            f"📍 المنطقة المتأثرة: {affected_area}\n"
            f"🕐 بداية الانقطاع: {datetime.now().strftime('%H:%M:%S - %Y/%m/%d')}\n"
        )

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("🔍 تشخيص", callback_data="diag_outage"),
                InlineKeyboardButton("📡 تتبع المسار", callback_data="trace_route"),
            ],
        ])

        await self.send_to_all(text, reply_markup=keyboard)

    async def notify_outage_resolved(self, duration: float, diagnosis: str):
        """تنبيه باستعادة الاتصال"""
        hours = int(duration // 3600)
        minutes = int((duration % 3600) // 60)
        seconds = int(duration % 60)

        duration_text = ""
        if hours > 0:
            duration_text += f"{hours} ساعة "
        if minutes > 0:
            duration_text += f"{minutes} دقيقة "
        duration_text += f"{seconds} ثانية"

        text = (
            f"🟢 <b>تم استعادة الإنترنت - شبكة حمد نت</b>\n\n"
            f"⏱️ مدة الانقطاع: <b>{duration_text}</b>\n"
            f"📝 السبب: {diagnosis}\n"
            f"🕐 وقت الاستعادة: {datetime.now().strftime('%H:%M:%S - %Y/%m/%d')}\n"
        )

        await self.send_to_all(text)

    # === تنبيهات التغييرات ===

    async def notify_config_change(self, change: Dict):
        """تنبيه بتغيير في التهيئة"""
        if not config.ALERT_ON_CONFIG_CHANGE:
            return
        if not self._can_send('config_change'):
            return

        change_type = change.get('type', 'unknown')
        description = change.get('description', '')

        type_names = {
            'new_network_device': 'جهاز شبكة جديد',
            'interface_up': 'واجهة شبكة نشطة',
            'interface_down': 'واجهة شبكة معطلة',
            'dhcp_change': 'تغيير في DHCP',
            'firewall_change': 'تغيير في الجدار الناري',
            'route_change': 'تغيير في التوجيه',
        }

        text = (
            f"⚙️ <b>تغيير في شبكة حمد نت</b>\n\n"
            f"📌 النوع: <b>{type_names.get(change_type, change_type)}</b>\n"
            f"📝 التفاصيل: {description}\n"
            f"🕐 الوقت: {datetime.now().strftime('%H:%M:%S - %Y/%m/%d')}\n"
        )

        await self.send_to_all(text)

    async def notify_high_bandwidth(self, device_mac: str, speed: float):
        """تنبيه باستخدام باندويث مرتفع"""
        if not config.ALERT_ON_HIGH_BANDWIDTH:
            return
        if not self._can_send(f'bw_{device_mac}'):
            return

        text = (
            f"📊 <b>استخدام باندويث مرتفع - شبكة حمد نت</b>\n\n"
            f"🔗 MAC: <code>{device_mac}</code>\n"
            f"📈 السرعة: <b>{speed:.1f} Mbps</b>\n"
            f"🕐 الوقت: {datetime.now().strftime('%H:%M:%S - %Y/%m/%d')}\n"
        )

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("🚫 تحديد السرعة", callback_data=f"limit_{device_mac}"),
                InlineKeyboardButton("⛔ حظر", callback_data=f"block_{device_mac}"),
            ],
        ])

        await self.send_to_all(text, reply_markup=keyboard)

    async def notify_unauthorized_device(self, device: Dict):
        """تنبيه بجهاز غير مرخص"""
        mac = device.get('mac', '')
        ip = device.get('ip', '')
        hostname = device.get('hostname', '')

        text = (
            f"⚠️ <b>جهاز غير مرخص - شبكة حمد نت</b>\n\n"
            f"📛 الاسم: <code>{hostname or 'غير معروف'}</code>\n"
            f"🌐 IP: <code>{ip}</code>\n"
            f"🔗 MAC: <code>{mac}</code>\n"
        )

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ ترخيص", callback_data=f"auth_{mac}"),
                InlineKeyboardButton("🚫 حظر", callback_data=f"block_{mac}"),
            ],
        ])

        await self.send_to_all(text, reply_markup=keyboard)
