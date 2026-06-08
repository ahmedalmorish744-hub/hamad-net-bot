"""
وحدة التنبيهات والإشعارات - Notification Handler (ثنائية اللغة: عربي + إنجليزي)
كل إشعار يعرض بالعربية ثم تحته الترجمة الإنجليزية
مع توضيح سبب المشكلة ونوعها
"""
import asyncio
import logging
from typing import Dict, List, Optional
from datetime import datetime

from telegram import Bot, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.constants import ParseMode

import config

logger = logging.getLogger(__name__)


# ==========================================
# قواميس الترجمة - Translation Dictionaries
# ==========================================

# أنواع المشاكل وأسبابها - Problem Types & Causes
CAUSE_TRANSLATIONS = {
    'local_network': {
        'ar': 'انقطاع محلي في الشبكة',
        'en': 'Local Network Outage',
        'cause_ar': 'الراوتر أو البوابة (Gateway) غير قابل للوصول - قد تكون المشكلة في كابل الشبكة، أو الراوتر معلق، أو إعدادات الشبكة المحلية خاطئة',
        'cause_en': 'Router/Gateway is unreachable — possible causes: network cable disconnected, router frozen, or misconfigured local network settings',
        'fix_ar': '🔧 الحل: أعد تشغيل الراوتر، تحقق من الكابلات، تأكد من إعدادات IP',
        'fix_en': '🔧 Fix: Reboot the router, check cables, verify IP settings',
    },
    'wan_down': {
        'ar': 'انقطاع واجهة WAN',
        'en': 'WAN Interface Down',
        'cause_ar': 'كابل الإنترنت مفصول أو واجهة WAN معطلة - مشكلة من مزود خدمة الإنترنت (ISP) أو كابل الألياف البصرية / Starlink غير متصل',
        'cause_en': 'Internet cable disconnected or WAN interface is down — ISP issue or fiber/Starlink link is down',
        'fix_ar': '🔧 الحل: تحقق من كابل الإنترنت، اتصل بمزود الخدمة، أعد تشغيل مودم ISP',
        'fix_en': '🔧 Fix: Check internet cable, contact ISP, reboot ISP modem',
    },
    'internet_down': {
        'ar': 'انقطاع الإنترنت بالكامل',
        'en': 'Complete Internet Outage',
        'cause_ar': 'لا يوجد اتصال بالإنترنت على الإطلاق - مشكلة من مزود الخدمة (ISP) أو انقطاع Starlink أو عطل في خط البيانات',
        'cause_en': 'No internet connectivity at all — ISP outage, Starlink disconnection, or data line failure',
        'fix_ar': '🔧 الحل: اتصل بمزود الخدمة، تحقق من حالة Starlink، انتظر استعادة الخدمة',
        'fix_en': '🔧 Fix: Contact ISP, check Starlink status, wait for service restoration',
    },
    'dns_issue': {
        'ar': 'مشكلة في نظام أسماء النطاقات (DNS)',
        'en': 'DNS (Domain Name System) Issue',
        'cause_ar': 'الإنترنت يعمل لكن لا يمكن ترجمة أسماء المواقع إلى عناوين IP - خوادم DNS لا تستجيب أو تم تغييرها',
        'cause_en': 'Internet works but domain names cannot be resolved to IP addresses — DNS servers not responding or misconfigured',
        'fix_ar': '🔧 الحل: غيّر خوادم DNS إلى 8.8.8.8 و 1.1.1.1، أعد تشغيل خدمة DNS في الراوتر',
        'fix_en': '🔧 Fix: Change DNS servers to 8.8.8.8 and 1.1.1.1, restart DNS service on router',
    },
    'partial_outage': {
        'ar': 'انقطاع جزئي - بعض الخدمات لا تعمل',
        'en': 'Partial Outage — Some Services Unavailable',
        'cause_ar': 'بعض المواقع أو الخدمات لا تعمل بينما أخرى تعمل - قد يكون حجب من ISP أو مشكلة في بروكسي أو جدار ناري يمنع بعض الاتصالات',
        'cause_en': 'Some websites/services work while others don\'t — possible ISP blocking, proxy issues, or firewall blocking specific connections',
        'fix_ar': '🔧 الحل: تحقق من إعدادات الجدار الناري، جرّب VPN، تحقق من إعدادات البروكسي',
        'fix_en': '🔧 Fix: Check firewall settings, try VPN, verify proxy configuration',
    },
    'high_latency': {
        'ar': 'بطء شديد في الاتصال',
        'en': 'High Latency / Slow Connection',
        'cause_ar': 'الاتصال موجود لكن بطيء جداً - ازدحام في الشبكة، مشكلة في Starlink (حالة الطقس أو عوائق)، أو استهلاك مفرط للباندويث من أحد الأجهزة',
        'cause_en': 'Connection exists but extremely slow — network congestion, Starlink weather/obstruction issues, or excessive bandwidth usage by a device',
        'fix_ar': '🔧 الحل: تحقق من استهلاك الباندويث، تحقق من حالة Starlink، أعد تشغيل الراوتر',
        'fix_en': '🔧 Fix: Check bandwidth usage, verify Starlink status, reboot router',
    },
    'unknown': {
        'ar': 'مشكلة غير محددة',
        'en': 'Unidentified Issue',
        'cause_ar': 'لم يتم تحديد سبب المشكلة تلقائياً - يحتاج فحص يدوي',
        'cause_en': 'Could not automatically determine the cause — manual investigation needed',
        'fix_ar': '🔧 الحل: استخدم أمر التشخيص /internet أو تتبع المسار /trace',
        'fix_en': '🔧 Fix: Use /internet diagnostics or /trace route command',
    },
}

# أنواع الهجمات - Attack Types
ATTACK_TRANSLATIONS = {
    'brute_force': {
        'ar': 'هجوم القوة الغاشمة (Brute Force)',
        'en': 'Brute Force Attack',
        'desc_ar': 'محاولة تخمين كلمات المرور بشكل متكرر للوصول غير المصرح به إلى النظام',
        'desc_en': 'Repeated password guessing attempts to gain unauthorized system access',
    },
    'port_scan': {
        'ar': 'فحص المنافذ (Port Scanning)',
        'en': 'Port Scanning',
        'desc_ar': 'شخص أو برنامج يفحص المنافذ المفتوحة على الراوتر ل寻找 نقاط الضعف',
        'desc_en': 'Someone or a program scanning open ports on the router to find vulnerabilities',
    },
    'access_denied': {
        'ar': 'وصول مرفوض',
        'en': 'Access Denied',
        'desc_ar': 'محاولة وصول إلى مورد محظور أو غير مصرح به',
        'desc_en': 'Attempted access to a blocked or unauthorized resource',
    },
    'firewall_drop': {
        'ar': 'حظر من الجدار الناري (Firewall Drop)',
        'en': 'Firewall Drop',
        'desc_ar': 'الجدار الناري حظر اتصال مشبوه - محاولة اتصال من عنوان غير مصرح به',
        'desc_en': 'Firewall blocked a suspicious connection — connection attempt from unauthorized address',
    },
    'intrusion': {
        'ar': 'محاولة اختراق (Intrusion Attempt)',
        'en': 'Intrusion Attempt',
        'desc_ar': 'محاولة اختراق نشطة للشبكة - شخص يحاول الدخول إلى النظام بدون تصريح',
        'desc_en': 'Active intrusion attempt on the network — someone trying to break into the system without authorization',
    },
    'attack': {
        'ar': 'هجوم على الشبكة (Network Attack)',
        'en': 'Network Attack',
        'desc_ar': 'هجوم نشط على الشبكة - قد يكون محاولة تعطيل أو اختراق',
        'desc_en': 'Active attack on the network — could be disruption or penetration attempt',
    },
    'ddos': {
        'ar': 'هجوم الحرمان من الخدمة الموزع (DDoS)',
        'en': 'Distributed Denial of Service (DDoS)',
        'desc_ar': 'هجوم يغرق الشبكة بآلاف الطلبات لتعطيلها - يتسبب في بطء شديد أو انقطاع كامل',
        'desc_en': 'Attack flooding the network with thousands of requests to disable it — causes extreme slowness or complete outage',
    },
    'flood': {
        'ar': 'هجوم فيضاني (Flood Attack)',
        'en': 'Flood Attack',
        'desc_ar': 'إرسال كم هائل من الحزم إلى الشبكة لتعطيلها أو إغراقها',
        'desc_en': 'Sending massive amounts of packets to the network to disable or overwhelm it',
    },
    'mac_spoofing': {
        'ar': 'انتحال عنوان MAC (MAC Spoofing)',
        'en': 'MAC Address Spoofing',
        'desc_ar': 'جهاز يستخدم عنوان MAC مزيف لانتحال شخصية جهاز آخر مرخص - محاولة تجاوز الحماية',
        'desc_en': 'Device using a fake MAC address to impersonate another authorized device — attempting to bypass security',
    },
    'connection_refused': {
        'ar': 'اتصال مرفوض (Connection Refused)',
        'en': 'Connection Refused',
        'desc_ar': 'محاولة اتصال بمنفذ أو خدمة مغلقة - قد يكون فحص أو محاولة وصول',
        'desc_en': 'Connection attempt to a closed port or service — could be scanning or access attempt',
    },
    'unauthorized_device': {
        'ar': 'جهاز غير مرخص (Unauthorized Device)',
        'en': 'Unauthorized Device',
        'desc_ar': 'جهاز غير معروف يتصل بالشبكة بدون إذن - قد يكون متسلل أو جهاز ضيف',
        'desc_en': 'Unknown device connecting to the network without permission — could be intruder or guest device',
    },
    'auto_block': {
        'ar': 'حظر تلقائي (Auto Block)',
        'en': 'Automatic Block',
        'desc_ar': 'تم حظر الجهاز تلقائياً بسبب نشاط مشبوه أو محاولة اختراق',
        'desc_en': 'Device automatically blocked due to suspicious activity or intrusion attempt',
    },
    'open_service': {
        'ar': 'خدمة مفتوحة للعالم (Open Service)',
        'en': 'Publicly Exposed Service',
        'desc_ar': 'خدمة على الراوتر مفتوحة للإنترنت بالكامل - يمكن لأي شخص في العالم الوصول إليها',
        'desc_en': 'Router service exposed to the entire internet — anyone in the world can access it',
    },
    'dns_open': {
        'ar': 'خادم DNS مفتوح (Open DNS Resolver)',
        'en': 'Open DNS Resolver',
        'desc_ar': 'خادم DNS يسمح لأي شخص باستخدامه - يمكن استغلاله في هجمات DNS Amplification لتعطيل شبكات أخرى',
        'desc_en': 'DNS server allows anyone to use it — can be exploited in DNS Amplification attacks to disable other networks',
    },
}

# أنواع تغييرات الشبكة - Network Change Types
CHANGE_TRANSLATIONS = {
    'new_network_device': {
        'ar': 'جهاز شبكة جديد (مودم/سويتش/نقطة وصول)',
        'en': 'New Network Device (Modem/Switch/Access Point)',
    },
    'interface_up': {
        'ar': 'واجهة شبكة أصبحت نشطة',
        'en': 'Network Interface Became Active',
    },
    'interface_down': {
        'ar': 'واجهة شبكة أصبحت معطلة',
        'en': 'Network Interface Went Down',
    },
    'dhcp_change': {
        'ar': 'تغيير في إعدادات DHCP',
        'en': 'DHCP Configuration Change',
    },
    'firewall_change': {
        'ar': 'تغيير في قواعد الجدار الناري',
        'en': 'Firewall Rules Change',
    },
    'route_change': {
        'ar': 'تغيير في جدول التوجيه',
        'en': 'Routing Table Change',
    },
}

# أنواع الأجهزة - Device Types
DEVICE_TYPE_TRANSLATIONS = {
    'router': {'ar': 'راوتر', 'en': 'Router'},
    'switch': {'ar': 'سويتش', 'en': 'Switch'},
    'access_point': {'ar': 'نقطة وصول لاسلكية', 'en': 'Wireless Access Point'},
    'phone': {'ar': 'هاتف', 'en': 'Phone'},
    'computer': {'ar': 'حاسوب', 'en': 'Computer'},
    'server': {'ar': 'خادم', 'en': 'Server'},
    'network_device': {'ar': 'جهاز شبكة', 'en': 'Network Device'},
    'tv': {'ar': 'تلفزيون ذكي', 'en': 'Smart TV'},
    'printer': {'ar': 'طابعة', 'en': 'Printer'},
    'camera': {'ar': 'كاميرا مراقبة', 'en': 'Surveillance Camera'},
    'iot': {'ar': 'جهاز إنترنت الأشياء', 'en': 'IoT Device'},
    'unknown': {'ar': 'غير معروف', 'en': 'Unknown'},
}


class NotificationHandler:
    """إرسال التنبيهات والإشعارات عبر تليجرام - ثنائية اللغة"""

    def __init__(self, bot: Bot):
        self.bot = bot
        self.last_notifications: Dict[str, datetime] = {}
        self.notification_cooldown = 30

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

    @staticmethod
    def _bilingual(ar_text: str, en_text: str) -> str:
        """تنسيق النص ثنائي اللغة"""
        return f"{ar_text}\n┄┄┄┄┄┄┄┄┄┄┄┄┄┄\n🌐 {en_text}"

    # ==========================================
    # تنبيهات الأجهزة
    # ==========================================

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

        # العربية
        ar_status = "⚠️ غير مرخص!" if unauthorized else "✅"
        ar_text = (
            f"{emoji} <b>جهاز جديد على شبكة حمد نت</b>\n\n"
            f"📋 الحالة: {ar_status}\n"
            f"📛 الاسم: <code>{hostname or 'غير معروف'}</code>\n"
            f"🌐 IP: <code>{ip}</code>\n"
            f"🔗 MAC: <code>{mac}</code>\n"
            f"🏭 الشركة: {vendor}\n"
            f"🕐 الوقت: {datetime.now().strftime('%H:%M:%S - %Y/%m/%d')}"
        )

        # الإنجليزية
        en_status = "⚠️ UNAUTHORIZED!" if unauthorized else "✅"
        en_text = (
            f"<b>New Device on Hamad Net</b>\n"
            f"Status: {en_status}\n"
            f"Name: <code>{hostname or 'Unknown'}</code>\n"
            f"IP: <code>{ip}</code>\n"
            f"MAC: <code>{mac}</code>\n"
            f"Vendor: {vendor}\n"
            f"Time: {datetime.now().strftime('%H:%M:%S - %Y/%m/%d')}"
        )

        text = self._bilingual(ar_text, en_text)

        keyboard = None
        if unauthorized:
            keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("✅ ترخيص / Authorize", callback_data=f"auth_{mac}"),
                    InlineKeyboardButton("🚫 حظر / Block", callback_data=f"block_{mac}"),
                ],
                [
                    InlineKeyboardButton("📋 التفاصيل / Details", callback_data=f"detail_{mac}"),
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

        ar_text = (
            f"📤 <b>جهاز غادر شبكة حمد نت</b>\n\n"
            f"📛 الاسم: <code>{hostname or 'غير معروف'}</code>\n"
            f"🌐 IP: <code>{ip}</code>\n"
            f"🔗 MAC: <code>{mac}</code>\n"
            f"🕐 الوقت: {datetime.now().strftime('%H:%M:%S - %Y/%m/%d')}"
        )

        en_text = (
            f"<b>Device Left Hamad Net</b>\n"
            f"Name: <code>{hostname or 'Unknown'}</code>\n"
            f"IP: <code>{ip}</code>\n"
            f"MAC: <code>{mac}</code>\n"
            f"Time: {datetime.now().strftime('%H:%M:%S - %Y/%m/%d')}"
        )

        text = self._bilingual(ar_text, en_text)
        await self.send_to_all(text)

    # ==========================================
    # تنبيهات الأمن
    # ==========================================

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
            'critical': '🔴', 'high': '🟠', 'medium': '🟡', 'low': '🔵',
        }.get(severity, '⚪')

        severity_ar = {'critical': 'حرج', 'high': 'عالي', 'medium': 'متوسط', 'low': 'منخفض'}.get(severity, severity)
        severity_en = {'critical': 'CRITICAL', 'high': 'HIGH', 'medium': 'MEDIUM', 'low': 'LOW'}.get(severity, severity.upper())

        attack_info = ATTACK_TRANSLATIONS.get(attack_type, {
            'ar': attack_type, 'en': attack_type,
            'desc_ar': 'نشاط مشبوه غير محدد', 'desc_en': 'Unidentified suspicious activity',
        })

        # العربية
        ar_text = (
            f"🚨 <b>تنبيه أمني - شبكة حمد نت</b>\n\n"
            f"{severity_emoji} مستوى الخطورة: <b>{severity_ar}</b>\n"
            f"⚡ نوع الهجوم: <b>{attack_info['ar']}</b>\n"
            f"📝 طبيعة الخطر: {attack_info['desc_ar']}\n"
        )
        if source_ip:
            ar_text += f"🌐 عنوان IP المهاجم: <code>{source_ip}</code>\n"
        if source_mac:
            ar_text += f"🔗 عنوان MAC: <code>{source_mac}</code>\n"
        ar_text += f"🕐 الوقت: {datetime.now().strftime('%H:%M:%S - %Y/%m/%d')}"

        # الإنجليزية
        en_text = (
            f"<b>Security Alert — Hamad Net</b>\n"
            f"Severity: <b>{severity_en}</b>\n"
            f"Attack Type: <b>{attack_info['en']}</b>\n"
            f"Threat Description: {attack_info['desc_en']}\n"
        )
        if source_ip:
            en_text += f"Attacker IP: <code>{source_ip}</code>\n"
        if source_mac:
            en_text += f"Attacker MAC: <code>{source_mac}</code>\n"
        en_text += f"Time: {datetime.now().strftime('%H:%M:%S - %Y/%m/%d')}"

        text = self._bilingual(ar_text, en_text)

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("🚫 حظر / Block", callback_data=f"block_{source_mac or source_ip}"),
                InlineKeyboardButton("🔍 تفاصيل / Details", callback_data=f"detail_{source_mac or source_ip}"),
            ],
            [
                InlineKeyboardButton("✅ تجاهل / Dismiss", callback_data=f"ignore_{source_mac or source_ip}"),
            ],
        ])

        await self.send_to_all(text, reply_markup=keyboard)

    # ==========================================
    # تنبيهات الانقطاع
    # ==========================================

    async def notify_outage(self, outage_info: Dict):
        """تنبيه بانقطاع الإنترنت - مع السبب والحل"""
        if not config.ALERT_ON_OUTAGE:
            return
        if not self._can_send('outage'):
            return

        outage_type = outage_info.get('type', 'unknown')
        affected_area = outage_info.get('affected_area', '')

        cause_info = CAUSE_TRANSLATIONS.get(outage_type, CAUSE_TRANSLATIONS['unknown'])

        # العربية
        ar_text = (
            f"🔴 <b>انقطاع الإنترنت - شبكة حمد نت</b>\n\n"
            f"⚡ نوع المشكلة: <b>{cause_info['ar']}</b>\n"
            f"🔍 سبب العطل:\n   {cause_info['cause_ar']}\n\n"
            f"📍 المنطقة المتأثرة: {affected_area}\n"
            f"🕐 بداية الانقطاع: {datetime.now().strftime('%H:%M:%S - %Y/%m/%d')}\n\n"
            f"{cause_info['fix_ar']}"
        )

        # الإنجليزية
        en_text = (
            f"<b>Internet Outage — Hamad Net</b>\n"
            f"Problem Type: <b>{cause_info['en']}</b>\n"
            f"Root Cause:\n   {cause_info['cause_en']}\n\n"
            f"Affected Area: {affected_area}\n"
            f"Outage Started: {datetime.now().strftime('%H:%M:%S - %Y/%m/%d')}\n\n"
            f"{cause_info['fix_en']}"
        )

        text = self._bilingual(ar_text, en_text)

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("🔍 تشخيص / Diagnose", callback_data="diag_outage"),
                InlineKeyboardButton("📡 تتبع / Trace", callback_data="trace_route"),
            ],
        ])

        await self.send_to_all(text, reply_markup=keyboard)

    async def notify_outage_resolved(self, duration: float, diagnosis: str):
        """تنبيه باستعادة الاتصال"""
        hours = int(duration // 3600)
        minutes = int((duration % 3600) // 60)
        seconds = int(duration % 60)

        ar_duration = ""
        en_duration = ""
        if hours > 0:
            ar_duration += f"{hours} ساعة و "
            en_duration += f"{hours}h "
        if minutes > 0:
            ar_duration += f"{minutes} دقيقة و "
            en_duration += f"{minutes}m "
        ar_duration += f"{seconds} ثانية"
        en_duration += f"{seconds}s"

        # العربية
        ar_text = (
            f"🟢 <b>تم استعادة الإنترنت - شبكة حمد نت</b>\n\n"
            f"⏱️ مدة الانقطاع: <b>{ar_duration}</b>\n"
            f"📝 السبب: {diagnosis}\n"
            f"🕐 وقت الاستعادة: {datetime.now().strftime('%H:%M:%S - %Y/%m/%d')}"
        )

        # الإنجليزية
        en_text = (
            f"<b>Internet Restored — Hamad Net</b>\n"
            f"Outage Duration: <b>{en_duration}</b>\n"
            f"Cause: {diagnosis}\n"
            f"Restored At: {datetime.now().strftime('%H:%M:%S - %Y/%m/%d')}"
        )

        text = self._bilingual(ar_text, en_text)
        await self.send_to_all(text)

    # ==========================================
    # تنبيهات التغييرات
    # ==========================================

    async def notify_config_change(self, change: Dict):
        """تنبيه بتغيير في بنية الشبكة"""
        if not config.ALERT_ON_CONFIG_CHANGE:
            return
        if not self._can_send('config_change'):
            return

        change_type = change.get('type', 'unknown')
        description = change.get('description', '')

        change_info = CHANGE_TRANSLATIONS.get(change_type, {
            'ar': change_type, 'en': change_type,
        })

        # العربية
        ar_text = (
            f"⚙️ <b>تغيير في شبكة حمد نت</b>\n\n"
            f"📌 نوع التغيير: <b>{change_info['ar']}</b>\n"
            f"📝 التفاصيل: {description}\n"
            f"🕐 الوقت: {datetime.now().strftime('%H:%M:%S - %Y/%m/%d')}"
        )

        # الإنجليزية
        en_text = (
            f"<b>Network Change — Hamad Net</b>\n"
            f"Change Type: <b>{change_info['en']}</b>\n"
            f"Details: {description}\n"
            f"Time: {datetime.now().strftime('%H:%M:%S - %Y/%m/%d')}"
        )

        text = self._bilingual(ar_text, en_text)
        await self.send_to_all(text)

    # ==========================================
    # تنبيهات الباندويث
    # ==========================================

    async def notify_high_bandwidth(self, device_mac: str, speed: float):
        """تنبيه باستخدام باندويث مرتفع"""
        if not config.ALERT_ON_HIGH_BANDWIDTH:
            return
        if not self._can_send(f'bw_{device_mac}'):
            return

        # العربية
        ar_text = (
            f"📊 <b>استخدام باندويث مرتفع - شبكة حمد نت</b>\n\n"
            f"🔗 MAC: <code>{device_mac}</code>\n"
            f"📈 السرعة: <b>{speed:.1f} Mbps</b>\n"
            f"⚠️ هذا الجهاز يستهلك كمية كبيرة من الإنترنت مما قد يبطئ الشبكة للآخرين\n"
            f"🕐 الوقت: {datetime.now().strftime('%H:%M:%S - %Y/%m/%d')}"
        )

        # الإنجليزية
        en_text = (
            f"<b>High Bandwidth Usage — Hamad Net</b>\n"
            f"MAC: <code>{device_mac}</code>\n"
            f"Speed: <b>{speed:.1f} Mbps</b>\n"
            f"⚠️ This device is consuming excessive bandwidth which may slow down the network for others\n"
            f"Time: {datetime.now().strftime('%H:%M:%S - %Y/%m/%d')}"
        )

        text = self._bilingual(ar_text, en_text)

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("⚡ تحديد السرعة / Limit", callback_data=f"limit_{device_mac}"),
                InlineKeyboardButton("⛔ حظر / Block", callback_data=f"block_{device_mac}"),
            ],
        ])

        await self.send_to_all(text, reply_markup=keyboard)

    # ==========================================
    # تنبيهات الأجهزة غير المرخصة
    # ==========================================

    async def notify_unauthorized_device(self, device: Dict):
        """تنبيه بجهاز غير مرخص"""
        mac = device.get('mac', '')
        ip = device.get('ip', '')
        hostname = device.get('hostname', '')
        vendor = device.get('vendor', '')

        # العربية
        ar_text = (
            f"⚠️ <b>جهاز غير مرخص على شبكة حمد نت</b>\n\n"
            f"📛 الاسم: <code>{hostname or 'غير معروف'}</code>\n"
            f"🌐 IP: <code>{ip}</code>\n"
            f"🔗 MAC: <code>{mac}</code>\n"
            f"🏭 الشركة: {vendor or 'غير معروف'}\n"
            f"⚠️ هذا الجهاز متصل بالشبكة بدون إذن - قد يكون متسلل أو ضيف\n"
            f"🕐 الوقت: {datetime.now().strftime('%H:%M:%S - %Y/%m/%d')}"
        )

        # الإنجليزية
        en_text = (
            f"<b>Unauthorized Device on Hamad Net</b>\n"
            f"Name: <code>{hostname or 'Unknown'}</code>\n"
            f"IP: <code>{ip}</code>\n"
            f"MAC: <code>{mac}</code>\n"
            f"Vendor: {vendor or 'Unknown'}\n"
            f"⚠️ This device is connected without permission — could be intruder or guest\n"
            f"Time: {datetime.now().strftime('%H:%M:%S - %Y/%m/%d')}"
        )

        text = self._bilingual(ar_text, en_text)

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ ترخيص / Authorize", callback_data=f"auth_{mac}"),
                InlineKeyboardButton("🚫 حظر / Block", callback_data=f"block_{mac}"),
            ],
        ])

        await self.send_to_all(text, reply_markup=keyboard)

    # ==========================================
    # تنبيه ثغرة أمنية (خدمة مفتوحة / DNS مفتوح)
    # ==========================================

    async def notify_vulnerability(self, vuln_type: str, description_ar: str, description_en: str,
                                    severity: str = 'high', extra_info: str = ''):
        """تنبيه بثغرة أمنية"""
        if not self._can_send(f'vuln_{vuln_type}'):
            return

        severity_emoji = {'critical': '🔴', 'high': '🟠', 'medium': '🟡', 'low': '🔵'}.get(severity, '⚪')
        severity_ar = {'critical': 'حرج', 'high': 'عالي', 'medium': 'متوسط', 'low': 'منخفض'}.get(severity, severity)
        severity_en = {'critical': 'CRITICAL', 'high': 'HIGH', 'medium': 'MEDIUM', 'low': 'LOW'}.get(severity, severity.upper())

        ar_text = (
            f"🔓 <b>ثغرة أمنية - شبكة حمد نت</b>\n\n"
            f"{severity_emoji} مستوى الخطورة: <b>{severity_ar}</b>\n"
            f"📝 الوصف: {description_ar}\n"
        )
        if extra_info:
            ar_text += f"📋 معلومات إضافية: {extra_info}\n"
        ar_text += f"🕐 الوقت: {datetime.now().strftime('%H:%M:%S - %Y/%m/%d')}"

        en_text = (
            f"<b>Security Vulnerability — Hamad Net</b>\n"
            f"Severity: <b>{severity_en}</b>\n"
            f"Description: {description_en}\n"
        )
        if extra_info:
            en_text += f"Additional Info: {extra_info}\n"
        en_text += f"Time: {datetime.now().strftime('%H:%M:%S - %Y/%m/%d')}"

        text = self._bilingual(ar_text, en_text)
        await self.send_to_all(text)

    # ==========================================
    # تنبيه حظر تلقائي
    # ==========================================

    async def notify_auto_block(self, mac: str, ip: str, reason: str, attack_type: str):
        """تنبيه بالحظر التلقائي"""
        attack_info = ATTACK_TRANSLATIONS.get(attack_type, {
            'ar': attack_type, 'en': attack_type,
            'desc_ar': reason, 'desc_en': reason,
        })

        ar_text = (
            f"🔒 <b>حظر تلقائي - شبكة حمد نت</b>\n\n"
            f"🚫 تم حظر الجهاز تلقائياً بسبب نشاط مشبوه\n"
            f"⚡ السبب: <b>{attack_info['ar']}</b>\n"
            f"📝 التفاصيل: {attack_info['desc_ar']}\n"
        )
        if mac:
            ar_text += f"🔗 MAC: <code>{mac}</code>\n"
        if ip:
            ar_text += f"🌐 IP: <code>{ip}</code>\n"
        ar_text += f"🕐 الوقت: {datetime.now().strftime('%H:%M:%S - %Y/%m/%d')}"

        en_text = (
            f"<b>Auto Block — Hamad Net</b>\n"
            f"Device automatically blocked due to suspicious activity\n"
            f"Reason: <b>{attack_info['en']}</b>\n"
            f"Details: {attack_info['desc_en']}\n"
        )
        if mac:
            en_text += f"MAC: <code>{mac}</code>\n"
        if ip:
            en_text += f"IP: <code>{ip}</code>\n"
        en_text += f"Time: {datetime.now().strftime('%H:%M:%S - %Y/%m/%d')}"

        text = self._bilingual(ar_text, en_text)

        if mac:
            keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("🔓 إلغاء الحظر / Unblock", callback_data=f"unblock_{mac}"),
                ],
            ])
            await self.send_to_all(text, reply_markup=keyboard)
        else:
            await self.send_to_all(text)
