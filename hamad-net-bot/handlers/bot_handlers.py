"""
معالجات البوت الرئيسية - Main Bot Handlers
جميع معالجات أوامر وأزرار بوت حمد نت
"""
import asyncio
import logging
import time
from datetime import datetime
from typing import Optional

from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

from config import config
from router.mikrotik import MikroTikRouter
from router.base import BaseRouter
from database.db import Database, init_db
from monitoring.network_monitor import NetworkMonitor
from utils.keyboards import *
from utils.formatters import *

logger = logging.getLogger(__name__)


# ===== حالات المحادثة =====
class BotStates(StatesGroup):
    waiting_for_ping_host = State()
    waiting_for_block_mac = State()
    waiting_for_unblock_mac = State()
    waiting_for_limit_ip = State()
    waiting_for_limit_speed = State()
    waiting_for_unlimit_ip = State()
    waiting_for_device_search = State()


class HamadNetBot:
    """بوت حمد نت الرئيسي"""

    def __init__(self, bot: Bot):
        self.bot = bot
        self.router_api: BaseRouter = None
        self.db: Database = None
        self.monitor: NetworkMonitor = None
        self._router = Router()
        self._setup_handlers()
        self._last_alert_ts = 0

    def get_router(self) -> Router:
        return self._router

    async def initialize(self):
        """تهيئة البوت"""
        # إنشاء اتصال قاعدة البيانات
        self.db = Database(config.DB_PATH)
        await init_db(config.DB_PATH)

        # إنشاء اتصال الراوتر
        if config.ROUTER_TYPE == "mikrotik":
            self.router_api = MikroTikRouter(
                host=config.ROUTER_HOST,
                user=config.ROUTER_USER,
                password=config.ROUTER_PASS,
                port=config.ROUTER_API_PORT
            )
        else:
            # OpenWrt - يستخدم نفس وضع المحاكاة حالياً
            self.router_api = MikroTikRouter(
                host=config.ROUTER_HOST,
                user=config.ROUTER_USER,
                password=config.ROUTER_PASS,
            )

        # الاتصال بالراوتر
        connected = await self.router_api.connect()
        if connected:
            logger.info("تم الاتصال بالراوتر بنجاح")
        else:
            logger.warning("فشل الاتصال بالراوتر - سيتم استخدام وضع المحاكاة")

        # إنشاء المراقب
        self.monitor = NetworkMonitor(self.router_api, self.db, config.NETWORK_NAME)
        self.monitor.set_alert_callback(self._send_alert_to_admin)
        await self.monitor.initialize()

        logger.info("تم تهيئة بوت حمد نت بنجاح")

    async def _send_alert_to_admin(self, alert_type: str, message: str,
                                    severity: str = "info", device_mac: str = ""):
        """إرسال تنبيه للمدير عبر Telegram"""
        try:
            # منع الإرسال المتكرر (حد أدنى 5 ثواني بين التنبيهات)
            now = time.time()
            if now - self._last_alert_ts < 5:
                return
            self._last_alert_ts = now

            severity_emoji = {"info": "ℹ️", "warning": "⚠️", "critical": "🚨", "error": "❌"}
            emoji = severity_emoji.get(severity, "ℹ️")

            text = f"{emoji} <b>تنبيه - شبكة حمد نت</b>\n\n{message}"

            await self.bot.send_message(
                chat_id=config.ADMIN_CHAT_ID,
                text=text,
                parse_mode="HTML"
            )
        except Exception as e:
            logger.error(f"خطأ في إرسال التنبيه: {e}")

    def _is_admin(self, user_id: int) -> bool:
        """التحقق من أن المستخدم هو المدير"""
        return user_id == config.ADMIN_CHAT_ID

    def _setup_handlers(self):
        """إعداد جميع معالجات الأوامر والأزرار"""
        r = self._router

        # أوامر البوت
        r.message.register(self.cmd_start, CommandStart())
        r.message.register(self.cmd_menu, Command("menu"))
        r.message.register(self.cmd_status, Command("status"))
        r.message.register(self.cmd_devices, Command("devices"))
        r.message.register(self.cmd_internet, Command("internet"))
        r.message.register(self.cmd_reboot, Command("reboot"))
        r.message.register(self.cmd_scan, Command("scan"))
        r.message.register(self.cmd_ping, Command("ping"))
        r.message.register(self.cmd_alerts, Command("alerts"))
        r.message.register(self.cmd_errors, Command("errors"))
        r.message.register(self.cmd_intrusions, Command("intrusions"))

        # معالجات الأزرار التفاعلية
        r.callback_query.register(self.cb_main_menu, F.data == "main_menu")
        r.callback_query.register(self.cb_status, F.data == "status")
        r.callback_query.register(self.cb_devices, F.data == "devices")
        r.callback_query.register(self.cb_internet, F.data == "internet")
        r.callback_query.register(self.cb_security, F.data == "security")
        r.callback_query.register(self.cb_alerts, F.data == "alerts")
        r.callback_query.register(self.cb_diagnostics, F.data == "diagnostics")
        r.callback_query.register(self.cb_router, F.data == "router")
        r.callback_query.register(self.cb_control, F.data == "control")
        r.callback_query.register(self.cb_logs, F.data == "logs")
        r.callback_query.register(self.cb_settings, F.data == "settings")

        # أزرار الأجهزة
        r.callback_query.register(self.cb_devices_online, F.data == "devices_online")
        r.callback_query.register(self.cb_devices_offline, F.data == "devices_offline")
        r.callback_query.register(self.cb_devices_unknown, F.data == "devices_unknown")
        r.callback_query.register(self.cb_devices_blocked, F.data == "devices_blocked")
        r.callback_query.register(self.cb_devices_traffic, F.data == "devices_traffic")

        # أزرار تفاصيل جهاز
        r.callback_query.register(self.cb_device_detail, F.data.startswith("device:"))

        # أزرار التحكم بالأجهزة
        r.callback_query.register(self.cb_block_device, F.data.startswith("block:"))
        r.callback_query.register(self.cb_unblock_device, F.data.startswith("unblock:"))
        r.callback_query.register(self.cb_block_wifi, F.data.startswith("block_wifi:"))
        r.callback_query.register(self.cb_unblock_wifi, F.data.startswith("unblock_wifi:"))
        r.callback_query.register(self.cb_limit_device, F.data.startswith("limit:"))
        r.callback_query.register(self.cb_unlimit_device, F.data.startswith("unlimit:"))
        r.callback_query.register(self.cb_mark_known, F.data.startswith("mark_known:"))

        # أزرار الإنترنت
        r.callback_query.register(self.cb_internet_check, F.data == "internet_check")
        r.callback_query.register(self.cb_internet_outages, F.data == "internet_outages")
        r.callback_query.register(self.cb_wan_ip, F.data == "wan_ip")

        # أزرار الأمان
        r.callback_query.register(self.cb_intrusions, F.data == "intrusions")
        r.callback_query.register(self.cb_firewall, F.data == "firewall")
        r.callback_query.register(self.cb_suspicious, F.data == "suspicious")
        r.callback_query.register(self.cb_protection_status, F.data == "protection_status")

        # أزرار التشخيص
        r.callback_query.register(self.cb_diag_ping, F.data == "diag_ping")
        r.callback_query.register(self.cb_router_errors, F.data == "router_errors")
        r.callback_query.register(self.cb_topology_changes, F.data == "topology_changes")
        r.callback_query.register(self.cb_full_check, F.data == "full_check")

        # أزرار الراوتر
        r.callback_query.register(self.cb_router_stats, F.data == "router_stats")
        r.callback_query.register(self.cb_router_interfaces, F.data == "router_interfaces")
        r.callback_query.register(self.cb_system_logs, F.data == "system_logs")
        r.callback_query.register(self.cb_reboot_confirm, F.data == "reboot_confirm")
        r.callback_query.register(self.cb_reboot_execute, F.data == "reboot_yes")

        # أزرار السجلات
        r.callback_query.register(self.cb_firewall_logs, F.data == "firewall_logs")
        r.callback_query.register(self.cb_intrusion_logs, F.data == "intrusion_logs")
        r.callback_query.register(self.cb_change_logs, F.data == "change_logs")

        # أزرار التنبيهات
        r.callback_query.register(self.cb_alerts_unread, F.data == "alerts_unread")
        r.callback_query.register(self.cb_alerts_all, F.data == "alerts_all")
        r.callback_query.register(self.cb_alerts_mark_read, F.data == "alerts_mark_read")

        # حالات المحادثة
        r.message.register(self.process_ping_host, BotStates.waiting_for_ping_host)

    # ===== أوامر البوت =====

    async def cmd_start(self, message: Message, state: FSMContext):
        if not self._is_admin(message.from_user.id):
            await message.answer("⛔ غير مصرح لك باستخدام هذا البوت.")
            return

        await state.clear()
        welcome = (
            f"📡 <b>مرحباً بك في بوت شبكة حمد نت</b>\n\n"
            f"🛡️ بوت المراقبة والإدارة الشاملة لشبكتك\n"
            f"📱 تحكم بكل شيء من هنا\n\n"
            f"🔹 مراقبة الأجهزة المتصلة والمنفصلة\n"
            f"🔹 اكتشاف الأجهزة الجديدة والمشبوهة\n"
            f"🔹 تنبيهات فورية لأي تغيير\n"
            f"🔹 حظر وتحديد سرعة الأجهزة\n"
            f"🔹 مراقبة الإنترنت والانقطاعات\n"
            f"🔹 كشف محاولات الاختراق\n"
            f"🔹 تشخيص المشاكل وإصلاحها"
        )
        await message.answer(welcome, reply_markup=main_menu_kb(), parse_mode="HTML")

    async def cmd_menu(self, message: Message):
        if not self._is_admin(message.from_user.id):
            return
        await message.answer("📋 <b>القائمة الرئيسية - شبكة حمد نت</b>",
                            reply_markup=main_menu_kb(), parse_mode="HTML")

    async def cmd_status(self, message: Message):
        if not self._is_admin(message.from_user.id):
            return
        status_msg = await self._get_network_status_text()
        await message.answer(status_msg, reply_markup=main_menu_kb(), parse_mode="HTML")

    async def cmd_devices(self, message: Message):
        if not self._is_admin(message.from_user.id):
            return
        await message.answer("📱 <b>إدارة الأجهزة</b>",
                            reply_markup=devices_menu_kb(), parse_mode="HTML")

    async def cmd_internet(self, message: Message):
        if not self._is_admin(message.from_user.id):
            return
        internet = await self.monitor.check_internet()
        await message.answer(format_internet_status(internet),
                            reply_markup=internet_menu_kb(), parse_mode="HTML")

    async def cmd_reboot(self, message: Message):
        if not self._is_admin(message.from_user.id):
            return
        await message.answer(
            "🔄 <b>هل أنت متأكد من إعادة تشغيل الراوتر؟</b>",
            reply_markup=confirm_kb("إعادة التشغيل", "reboot_yes"),
            parse_mode="HTML"
        )

    async def cmd_scan(self, message: Message):
        if not self._is_admin(message.from_user.id):
            return
        wait_msg = await message.answer("🔍 جاري فحص الشبكة...")
        results = await self.monitor.run_full_check()
        status_msg = await self._get_network_status_text()
        await wait_msg.edit_text(status_msg, reply_markup=main_menu_kb(), parse_mode="HTML")

    async def cmd_ping(self, message: Message, state: FSMContext):
        if not self._is_admin(message.from_user.id):
            return
        await state.set_state(BotStates.waiting_for_ping_host)
        await message.answer(
            "🔍 أرسل عنوان المضيف لفحص الاتصال (مثل: google.com أو 8.8.8.8):",
            reply_markup=back_to_main_kb()
        )

    async def process_ping_host(self, message: Message, state: FSMContext):
        if not self._is_admin(message.from_user.id):
            return
        host = message.text.strip()
        await state.clear()

        wait_msg = await message.answer(f"🔍 جاري فحص {host}...")
        result = await self.router_api.ping(host)
        await wait_msg.edit_text(format_ping_result(result),
                                reply_markup=back_to_main_kb(), parse_mode="HTML")

    async def cmd_alerts(self, message: Message):
        if not self._is_admin(message.from_user.id):
            return
        await message.answer("🔔 <b>التنبيهات</b>",
                            reply_markup=alerts_menu_kb(), parse_mode="HTML")

    async def cmd_errors(self, message: Message):
        if not self._is_admin(message.from_user.id):
            return
        errors = await self.db.get_recent_errors(limit=10, unresolved_only=True)
        if not errors:
            await message.answer("✅ لا توجد أخطاء غير محلولة",
                                reply_markup=back_to_main_kb())
            return
        msg = "⚠️ <b>الأخطاء غير المحلولة</b>\n\n"
        for e in errors:
            msg += format_error(e) + "\n\n"
        await message.answer(msg, reply_markup=back_to_main_kb(), parse_mode="HTML")

    async def cmd_intrusions(self, message: Message):
        if not self._is_admin(message.from_user.id):
            return
        intrusions = await self.db.get_recent_intrusions(limit=10)
        if not intrusions:
            await message.answer("✅ لا توجد محاولات اختراق مسجلة",
                                reply_markup=back_to_main_kb())
            return
        msg = "🚨 <b>محاولات الاختراق الأخيرة</b>\n\n"
        for i in intrusions[:10]:
            msg += format_intrusion(i) + "\n\n"
        await message.answer(msg, reply_markup=back_to_main_kb(), parse_mode="HTML")

    # ===== معالجات الأزرار التفاعلية =====

    async def cb_main_menu(self, callback: CallbackQuery, state: FSMContext):
        await state.clear()
        await callback.message.edit_text(
            "📋 <b>القائمة الرئيسية - شبكة حمد نت</b>",
            reply_markup=main_menu_kb(), parse_mode="HTML"
        )

    async def cb_status(self, callback: CallbackQuery):
        await callback.answer("جاري تحميل الحالة...")
        status_msg = await self._get_network_status_text()
        await callback.message.edit_text(status_msg, reply_markup=main_menu_kb(), parse_mode="HTML")

    async def cb_devices(self, callback: CallbackQuery):
        await callback.message.edit_text(
            "📱 <b>إدارة الأجهزة</b>",
            reply_markup=devices_menu_kb(), parse_mode="HTML"
        )

    async def cb_internet(self, callback: CallbackQuery):
        await callback.answer("جاري فحص الإنترنت...")
        internet = await self.monitor.check_internet()
        await callback.message.edit_text(
            format_internet_status(internet),
            reply_markup=internet_menu_kb(), parse_mode="HTML"
        )

    async def cb_security(self, callback: CallbackQuery):
        await callback.message.edit_text(
            "🔒 <b>الأمان والحماية</b>",
            reply_markup=security_menu_kb(), parse_mode="HTML"
        )

    async def cb_alerts(self, callback: CallbackQuery):
        count = await self.db.get_unread_alerts_count()
        await callback.message.edit_text(
            f"🔔 <b>التنبيهات</b> ({count} غير مقروء)",
            reply_markup=alerts_menu_kb(), parse_mode="HTML"
        )

    async def cb_diagnostics(self, callback: CallbackQuery):
        await callback.message.edit_text(
            "🔧 <b>التشخيص والأدوات</b>",
            reply_markup=diagnostics_menu_kb(), parse_mode="HTML"
        )

    async def cb_router(self, callback: CallbackQuery):
        await callback.message.edit_text(
            "🖥️ <b>إدارة الراوتر</b>",
            reply_markup=router_menu_kb(), parse_mode="HTML"
        )

    async def cb_control(self, callback: CallbackQuery):
        await callback.message.edit_text(
            "🛡️ <b>التحكم بالشبكة</b>",
            reply_markup=control_menu_kb(), parse_mode="HTML"
        )

    async def cb_logs(self, callback: CallbackQuery):
        await callback.message.edit_text(
            "📋 <b>السجلات</b>",
            reply_markup=logs_menu_kb(), parse_mode="HTML"
        )

    async def cb_settings(self, callback: CallbackQuery):
        await callback.message.edit_text(
            "⚙️ <b>الإعدادات</b>",
            reply_markup=settings_menu_kb(), parse_mode="HTML"
        )

    # ===== أزرار الأجهزة =====

    async def cb_devices_online(self, callback: CallbackQuery):
        await callback.answer("جاري تحميل الأجهزة...")
        devices = await self.db.get_online_devices()
        msg = format_device_list(devices, "🟢 الأجهزة المتصلة")
        # إضافة أزرار لكل جهاز
        kb = self._build_device_list_kb(devices)
        await callback.message.edit_text(msg, reply_markup=kb, parse_mode="HTML")

    async def cb_devices_offline(self, callback: CallbackQuery):
        devices = await self.db.get_all_devices()
        offline = [d for d in devices if not d.get("is_online")]
        msg = format_device_list(offline, "🔴 الأجهزة المنفصلة")
        await callback.message.edit_text(msg, reply_markup=devices_menu_kb(), parse_mode="HTML")

    async def cb_devices_unknown(self, callback: CallbackQuery):
        devices = await self.db.get_unknown_devices()
        msg = format_device_list(devices, "❓ الأجهزة غير المعروفة")
        kb = self._build_device_list_kb(devices)
        await callback.message.edit_text(msg, reply_markup=kb, parse_mode="HTML")

    async def cb_devices_blocked(self, callback: CallbackQuery):
        devices = await self.db.get_blocked_devices()
        msg = format_device_list(devices, "🚫 الأجهزة المحظورة")
        await callback.message.edit_text(msg, reply_markup=devices_menu_kb(), parse_mode="HTML")

    async def cb_devices_traffic(self, callback: CallbackQuery):
        queues = await self.router_api.get_queue_list()
        if not queues:
            await callback.message.edit_text(
                "📊 <b>تحديد السرعة</b>\n\nلا توجد أجهزة بتحديد سرعة",
                reply_markup=devices_menu_kb(), parse_mode="HTML"
            )
            return
        msg = "📊 <b>الأجهزة ذات تحديد السرعة</b>\n\n"
        for q in queues:
            msg += f"🌐 {q.get('target', '')} | ⚡ {q.get('max_limit', '')}\n"
        await callback.message.edit_text(msg, reply_markup=devices_menu_kb(), parse_mode="HTML")

    # ===== تفاصيل جهاز =====

    async def cb_device_detail(self, callback: CallbackQuery):
        mac = callback.data.split(":", 1)[1]
        device = await self.db.get_device_by_mac(mac)
        if not device:
            await callback.answer("الجهاز غير موجود")
            return
        msg = format_device_detail(device)
        kb = device_actions_kb(
            mac=device["mac"],
            ip=device.get("ip", ""),
            is_online=device.get("is_online", False),
            is_blocked=device.get("is_blocked", False),
            has_speed_limit=bool(device.get("speed_limit"))
        )
        await callback.message.edit_text(msg, reply_markup=kb, parse_mode="HTML")

    # ===== التحكم بالأجهزة =====

    async def cb_block_device(self, callback: CallbackQuery):
        parts = callback.data.split(":")
        mac, ip = parts[1], parts[2] if len(parts) > 2 else ""
        success = await self.router_api.block_device(mac, ip)
        if success:
            await self.db.block_device(mac)
            await self.db.add_alert("device_blocked", f"تم حظر الجهاز {mac}", "info", mac)
            await callback.answer("✅ تم حظر الجهاز من الإنترنت")
        else:
            await callback.answer("❌ فشل حظر الجهاز")
        # تحديث العرض
        device = await self.db.get_device_by_mac(mac)
        if device:
            msg = format_device_detail(device)
            kb = device_actions_kb(mac, ip, device.get("is_online"), True,
                                  bool(device.get("speed_limit")))
            await callback.message.edit_text(msg, reply_markup=kb, parse_mode="HTML")

    async def cb_unblock_device(self, callback: CallbackQuery):
        parts = callback.data.split(":")
        mac, ip = parts[1], parts[2] if len(parts) > 2 else ""
        success = await self.router_api.unblock_device(mac, ip)
        if success:
            await self.db.unblock_device(mac)
            await self.db.add_alert("device_unblocked", f"تم إلغاء حظر الجهاز {mac}", "info", mac)
            await callback.answer("✅ تم إلغاء حظر الجهاز")
        else:
            await callback.answer("❌ فشل إلغاء الحظر")
        device = await self.db.get_device_by_mac(mac)
        if device:
            msg = format_device_detail(device)
            kb = device_actions_kb(mac, ip, device.get("is_online"), False,
                                  bool(device.get("speed_limit")))
            await callback.message.edit_text(msg, reply_markup=kb, parse_mode="HTML")

    async def cb_block_wifi(self, callback: CallbackQuery):
        parts = callback.data.split(":")
        mac, ip = parts[1], parts[2] if len(parts) > 2 else ""
        success = await self.router_api.block_wifi(mac)
        if success:
            await callback.answer("✅ تم حظر الجهاز من WiFi")
        else:
            await callback.answer("❌ فشل حظر WiFi")

    async def cb_unblock_wifi(self, callback: CallbackQuery):
        parts = callback.data.split(":")
        mac = parts[1]
        success = await self.router_api.unblock_wifi(mac)
        if success:
            await callback.answer("✅ تم إلغاء حظر WiFi")
        else:
            await callback.answer("❌ فشل إلغاء حظر WiFi")

    async def cb_limit_device(self, callback: CallbackQuery):
        parts = callback.data.split(":")
        mac, ip = parts[1], parts[2]
        dl, ul = int(parts[3]), int(parts[4])
        success = await self.router_api.set_speed_limit(ip, dl, ul)
        if success:
            await self.db.set_speed_limit(mac, f"{dl}k/{ul}k")
            await callback.answer(f"✅ تم تحديد السرعة: {dl//1000}M/{ul//1000}M")
        else:
            await callback.answer("❌ فشل تحديد السرعة")
        device = await self.db.get_device_by_mac(mac)
        if device:
            msg = format_device_detail(device)
            kb = device_actions_kb(mac, ip, device.get("is_online"),
                                  device.get("is_blocked"), True)
            await callback.message.edit_text(msg, reply_markup=kb, parse_mode="HTML")

    async def cb_unlimit_device(self, callback: CallbackQuery):
        parts = callback.data.split(":")
        mac, ip = parts[1], parts[2]
        success = await self.router_api.remove_speed_limit(ip)
        if success:
            await self.db.set_speed_limit(mac, "")
            await callback.answer("✅ تم إزالة تحديد السرعة")
        else:
            await callback.answer("❌ فشل إزالة تحديد السرعة")
        device = await self.db.get_device_by_mac(mac)
        if device:
            msg = format_device_detail(device)
            kb = device_actions_kb(mac, ip, device.get("is_online"),
                                  device.get("is_blocked"), False)
            await callback.message.edit_text(msg, reply_markup=kb, parse_mode="HTML")

    async def cb_mark_known(self, callback: CallbackQuery):
        mac = callback.data.split(":")[1]
        await self.db.mark_device_known(mac)
        await callback.answer("✅ تم تعليم الجهاز كمعروف")

    # ===== الإنترنت =====

    async def cb_internet_check(self, callback: CallbackQuery):
        await callback.answer("جاري فحص الإنترنت...")
        internet = await self.monitor.check_internet()
        await callback.message.edit_text(
            format_internet_status(internet),
            reply_markup=internet_menu_kb(), parse_mode="HTML"
        )

    async def cb_internet_outages(self, callback: CallbackQuery):
        outages = await self.db.get_internet_outages(hours=48)
        if not outages:
            await callback.message.edit_text(
                "✅ <b>لا توجد انقطاعات مسجلة في آخر 48 ساعة</b>",
                reply_markup=internet_menu_kb(), parse_mode="HTML"
            )
            return
        msg = "📉 <b>انقطاعات الإنترنت (آخر 48 ساعة)</b>\n\n"
        for o in outages[:10]:
            msg += (f"🔴 {format_timestamp(o.get('timestamp', 0))}\n"
                    f"   📋 {o.get('reason', 'غير محدد')}\n\n")
        await callback.message.edit_text(msg, reply_markup=internet_menu_kb(), parse_mode="HTML")

    async def cb_wan_ip(self, callback: CallbackQuery):
        wan_ip = await self.router_api.get_wan_ip()
        await callback.message.edit_text(
            f"🌐 <b>IP العام</b>\n\n{wan_ip or 'غير متوفر'}",
            reply_markup=internet_menu_kb(), parse_mode="HTML"
        )

    # ===== الأمان =====

    async def cb_security(self, callback: CallbackQuery):
        await callback.message.edit_text(
            "🔒 <b>الأمان والحماية</b>",
            reply_markup=security_menu_kb(), parse_mode="HTML"
        )

    async def cb_intrusions(self, callback: CallbackQuery):
        intrusions = await self.monitor.check_intrusions()
        if not intrusions:
            await callback.message.edit_text(
                "✅ <b>لا توجد محاولات اختراق</b>",
                reply_markup=security_menu_kb(), parse_mode="HTML"
            )
            return
        msg = "🚨 <b>محاولات الاختراق المكتشفة</b>\n\n"
        for i in intrusions[:10]:
            msg += format_intrusion(i) + "\n\n"
        await callback.message.edit_text(msg, reply_markup=security_menu_kb(), parse_mode="HTML")

    async def cb_firewall(self, callback: CallbackQuery):
        logs = await self.router_api.get_firewall_logs(limit=15)
        if not logs:
            await callback.message.edit_text(
                "🔥 <b>سجلات الجدار الناري</b>\n\nلا توجد سجلات",
                reply_markup=security_menu_kb(), parse_mode="HTML"
            )
            return
        msg = "🔥 <b>سجلات الجدار الناري</b>\n\n"
        for log in logs[:15]:
            msg += f"⏰ {log.get('time', '')} | {log.get('message', '')}\n"
        await callback.message.edit_text(msg, reply_markup=security_menu_kb(), parse_mode="HTML")

    async def cb_suspicious(self, callback: CallbackQuery):
        unknown = await self.db.get_unknown_devices()
        if not unknown:
            await callback.message.edit_text(
                "✅ <b>لا توجد أجهزة مشبوهة</b>",
                reply_markup=security_menu_kb(), parse_mode="HTML"
            )
            return
        msg = format_device_list(unknown, "❓ الأجهزة المشبوهة/غير المعروفة")
        kb = self._build_device_list_kb(unknown)
        await callback.message.edit_text(msg, reply_markup=kb, parse_mode="HTML")

    async def cb_protection_status(self, callback: CallbackQuery):
        stats = await self.db.get_network_stats()
        intrusions_24h = stats.get("intrusions_24h", 0)
        blocked = stats.get("blocked_devices", 0)
        unknown = stats.get("unknown_devices", 0)

        # تقييم مستوى الحماية
        if intrusions_24h > 10 or unknown > 5:
            level = "🔴 ضعيف"
        elif intrusions_24h > 3 or unknown > 2:
            level = "🟡 متوسط"
        else:
            level = "🟢 جيد"

        msg = f"""🛡️ <b>حالة الحماية - شبكة حمد نت</b>

📊 <b>مستوى الحماية:</b> {level}

🚨 محاولات اختراق (24س): {intrusions_24h}
🚫 أجهزة محظورة: {blocked}
❓ أجهزة غير معروفة: {unknown}
✅ أجهزة معروفة: {stats.get('online_devices', 0) - unknown}
"""
        await callback.message.edit_text(msg, reply_markup=security_menu_kb(), parse_mode="HTML")

    # ===== التشخيص =====

    async def cb_diag_ping(self, callback: CallbackQuery, state: FSMContext):
        await state.set_state(BotStates.waiting_for_ping_host)
        await callback.message.edit_text(
            "🔍 أرسل عنوان المضيف لفحص الاتصال (مثل: google.com أو 8.8.8.8):",
            reply_markup=back_to_main_kb()
        )

    async def cb_router_errors(self, callback: CallbackQuery):
        errors = await self.db.get_recent_errors(limit=10, unresolved_only=True)
        if not errors:
            await callback.message.edit_text(
                "✅ <b>لا توجد أخطاء غير محلولة</b>",
                reply_markup=diagnostics_menu_kb(), parse_mode="HTML"
            )
            return
        msg = "⚠️ <b>أخطاء الراوتر غير المحلولة</b>\n\n"
        for e in errors:
            msg += format_error(e) + "\n\n"
        await callback.message.edit_text(msg, reply_markup=diagnostics_menu_kb(), parse_mode="HTML")

    async def cb_topology_changes(self, callback: CallbackQuery):
        changes = await self.db.get_recent_topology_changes(limit=10)
        if not changes:
            await callback.message.edit_text(
                "✅ <b>لا توجد تغييرات في طوبولوجيا الشبكة</b>",
                reply_markup=diagnostics_menu_kb(), parse_mode="HTML"
            )
            return
        msg = "🔄 <b>تغييرات طوبولوجيا الشبكة</b>\n\n"
        for c in changes[:10]:
            msg += format_topology_change(c) + "\n\n"
        await callback.message.edit_text(msg, reply_markup=diagnostics_menu_kb(), parse_mode="HTML")

    async def cb_full_check(self, callback: CallbackQuery):
        await callback.answer("جاري الفحص الشامل...")
        results = await self.monitor.run_full_check()
        status_msg = await self._get_network_status_text()

        new = len(results["devices"]["new_devices"])
        left = len(results["devices"]["left_devices"])
        intrusions = len(results["intrusions"])
        warnings = len(results["health"]["warnings"])
        topo = len(results["topology"])

        summary = f"\n\n📊 <b>ملخص الفحص الشامل:</b>\n"
        if new:
            summary += f"🔴 أجهزة جديدة: {new}\n"
        if left:
            summary += f"🔵 أجهزة انفصلت: {left}\n"
        if intrusions:
            summary += f"🚨 محاولات اختراق: {intrusions}\n"
        if warnings:
            summary += f"⚠️ تحذيرات: {warnings}\n"
        if topo:
            summary += f"🔄 تغييرات شبكة: {topo}\n"
        if not any([new, left, intrusions, warnings, topo]):
            summary += "✅ كل شيء طبيعي\n"

        await callback.message.edit_text(
            status_msg + summary,
            reply_markup=main_menu_kb(), parse_mode="HTML"
        )

    # ===== الراوتر =====

    async def cb_router_stats(self, callback: CallbackQuery):
        stats = await self.router_api.get_router_stats()
        await callback.message.edit_text(
            format_router_stats(stats),
            reply_markup=router_menu_kb(), parse_mode="HTML"
        )

    async def cb_router_interfaces(self, callback: CallbackQuery):
        interfaces = await self.router_api.get_interfaces()
        if not interfaces:
            await callback.message.edit_text(
                "🔌 <b>الواجهات</b>\n\nغير متوفر",
                reply_markup=router_menu_kb(), parse_mode="HTML"
            )
            return
        msg = "🔌 <b>واجهات الراوتر</b>\n\n"
        for iface in interfaces:
            status = "🟢" if iface.is_up else "🔴"
            msg += (f"{status} <b>{iface.name}</b> ({iface.type})\n"
                    f"   📥 RX: {format_bytes(iface.rx_bytes)} | 📤 TX: {format_bytes(iface.tx_bytes)}\n\n")
        await callback.message.edit_text(msg, reply_markup=router_menu_kb(), parse_mode="HTML")

    async def cb_system_logs(self, callback: CallbackQuery):
        logs = await self.router_api.get_system_logs(limit=15)
        if not logs:
            await callback.message.edit_text(
                "📋 <b>سجلات النظام</b>\n\nغير متوفر",
                reply_markup=router_menu_kb(), parse_mode="HTML"
            )
            return
        msg = "📋 <b>سجلات النظام</b>\n\n"
        for log in logs[:15]:
            msg += f"⏰ {log.get('time', '')} [{log.get('topics', '')}] {log.get('message', '')}\n"
        if len(msg) > 4000:
            msg = msg[:4000] + "..."
        await callback.message.edit_text(msg, reply_markup=router_menu_kb(), parse_mode="HTML")

    async def cb_reboot_confirm(self, callback: CallbackQuery):
        await callback.message.edit_text(
            "🔄 <b>هل أنت متأكد من إعادة تشغيل الراوتر؟</b>\n\n"
            "⚠️ سيتم قطع الإنترنت عن جميع الأجهزة مؤقتاً.",
            reply_markup=confirm_kb("إعادة التشغيل", "reboot_yes"),
            parse_mode="HTML"
        )

    async def cb_reboot_execute(self, callback: CallbackQuery):
        await callback.answer("جاري إعادة التشغيل...")
        success = await self.router_api.reboot_router()
        if success:
            await self.db.add_alert("reboot", "تم إعادة تشغيل الراوتر يدوياً", "warning")
            await callback.message.edit_text(
                "✅ <b>تم إرسال أمر إعادة التشغيل</b>\n\n"
                "⏳ سيحتاج الراوتر 1-2 دقيقة للعودة.",
                reply_markup=main_menu_kb(), parse_mode="HTML"
            )
        else:
            await callback.message.edit_text(
                "❌ <b>فشل إعادة التشغيل</b>",
                reply_markup=main_menu_kb(), parse_mode="HTML"
            )

    # ===== السجلات =====

    async def cb_firewall_logs(self, callback: CallbackQuery):
        logs = await self.router_api.get_firewall_logs(limit=20)
        if not logs:
            await callback.message.edit_text(
                "🔥 <b>سجلات الجدار الناري</b>\n\nلا توجد سجلات",
                reply_markup=logs_menu_kb(), parse_mode="HTML"
            )
            return
        msg = "🔥 <b>سجلات الجدار الناري</b>\n\n"
        for log in logs[:20]:
            msg += f"⏰ {log.get('time', '')} | {log.get('message', '')}\n"
        if len(msg) > 4000:
            msg = msg[:4000] + "..."
        await callback.message.edit_text(msg, reply_markup=logs_menu_kb(), parse_mode="HTML")

    async def cb_intrusion_logs(self, callback: CallbackQuery):
        intrusions = await self.db.get_recent_intrusions(limit=15)
        if not intrusions:
            await callback.message.edit_text(
                "🚨 <b>سجلات الاختراقات</b>\n\nلا توجد سجلات",
                reply_markup=logs_menu_kb(), parse_mode="HTML"
            )
            return
        msg = "🚨 <b>سجلات محاولات الاختراق</b>\n\n"
        for i in intrusions[:15]:
            msg += format_intrusion(i) + "\n"
        if len(msg) > 4000:
            msg = msg[:4000] + "..."
        await callback.message.edit_text(msg, reply_markup=logs_menu_kb(), parse_mode="HTML")

    async def cb_change_logs(self, callback: CallbackQuery):
        changes = await self.db.get_recent_topology_changes(limit=15)
        if not changes:
            await callback.message.edit_text(
                "🔄 <b>سجلات التغييرات</b>\n\nلا توجد سجلات",
                reply_markup=logs_menu_kb(), parse_mode="HTML"
            )
            return
        msg = "🔄 <b>سجلات تغييرات الشبكة</b>\n\n"
        for c in changes[:15]:
            msg += format_topology_change(c) + "\n"
        await callback.message.edit_text(msg, reply_markup=logs_menu_kb(), parse_mode="HTML")

    # ===== التنبيهات =====

    async def cb_alerts_unread(self, callback: CallbackQuery):
        alerts = await self.db.get_recent_alerts(limit=15, unread_only=True)
        if not alerts:
            await callback.message.edit_text(
                "✅ <b>لا توجد تنبيهات غير مقروءة</b>",
                reply_markup=alerts_menu_kb(), parse_mode="HTML"
            )
            return
        msg = "🔔 <b>التنبيهات غير المقروءة</b>\n\n"
        for a in alerts[:10]:
            msg += format_alert(a) + "\n\n"
        if len(msg) > 4000:
            msg = msg[:4000] + "..."
        await callback.message.edit_text(msg, reply_markup=alerts_menu_kb(), parse_mode="HTML")

    async def cb_alerts_all(self, callback: CallbackQuery):
        alerts = await self.db.get_recent_alerts(limit=20)
        if not alerts:
            await callback.message.edit_text(
                "📋 <b>لا توجد تنبيهات</b>",
                reply_markup=alerts_menu_kb(), parse_mode="HTML"
            )
            return
        msg = "📋 <b>جميع التنبيهات</b>\n\n"
        for a in alerts[:15]:
            msg += format_alert(a) + "\n\n"
        if len(msg) > 4000:
            msg = msg[:4000] + "..."
        await callback.message.edit_text(msg, reply_markup=alerts_menu_kb(), parse_mode="HTML")

    async def cb_alerts_mark_read(self, callback: CallbackQuery):
        await self.db.mark_alerts_read()
        await callback.answer("✅ تم تحديد الكل كمقروء")

    # ===== الدوال المساعدة =====

    async def _get_network_status_text(self) -> str:
        """جلب نص حالة الشبكة"""
        stats = await self.db.get_network_stats()
        router_stats = await self.router_api.get_router_stats()
        internet = await self.monitor.check_internet()
        return format_network_status(stats, router_stats, internet)

    def _build_device_list_kb(self, devices: list) -> InlineKeyboardMarkup:
        """بناء لوحة أزرار لقائمة أجهزة"""
        buttons = []
        for d in devices[:10]:
            mac = d.get("mac", "")
            hostname = d.get("hostname") or "غير معروف"
            ip = d.get("ip", "")
            status = "🟢" if d.get("is_online") else "🔴"
            buttons.append([
                InlineKeyboardButton(
                    text=f"{status} {hostname} ({ip})",
                    callback_data=f"device:{mac}"
                )
            ])
        buttons.append([InlineKeyboardButton(text="🔙 قائمة الأجهزة", callback_data="devices")])
        return InlineKeyboardMarkup(inline_keyboard=buttons)
