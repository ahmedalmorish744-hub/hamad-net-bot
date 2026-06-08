"""
إعدادات بوت حمد نت - Hamad Net Bot Configuration
"""
import os
from dotenv import load_dotenv

load_dotenv()

# === إعدادات التليجرام ===
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")

# معرف صاحب البوت الرئيسي - له الصلاحية المطلقة (يُقرأ من متغيرات البيئة)
SOLE_OWNER_ID = int(os.getenv("SOLE_OWNER_ID", "0")) if os.getenv("SOLE_OWNER_ID", "") else 0

# معرف الأدمن الرئيسي - له الصلاحية الكاملة
ADMIN_ID = int(os.getenv("ADMIN_ID", "0")) if os.getenv("ADMIN_ID", "") else 0

# مستخدمون مصرح لهم إضافيون (يمكنهم استخدام البوت لكن ليس صلاحيات الأدمن الكاملة)
AUTHORIZED_USERS = [
    int(x) for x in os.getenv("AUTHORIZED_USERS", "").split(",") if x.strip()
]

# جميع المعرفات المصرح لها (الأدمن + المستخدمون الإضافيون)
AUTHORIZED_CHAT_IDS = []
if ADMIN_ID:
    AUTHORIZED_CHAT_IDS.append(ADMIN_ID)
AUTHORIZED_CHAT_IDS.extend(AUTHORIZED_USERS)

# معرفات الأدمن فقط (للأوامر الحساسة)
ADMIN_CHAT_IDS = [ADMIN_ID] if ADMIN_ID else []

# === إعدادات الراوتر الرئيسي ===
ROUTER_TYPE = os.getenv("ROUTER_TYPE", "mikrotik")  # mikrotik أو openwrt

# إعدادات MikroTik
MIKROTIK_HOST = os.getenv("MIKROTIK_HOST", "192.168.1.1")
MIKROTIK_USER = os.getenv("MIKROTIK_USER", "admin")
MIKROTIK_PASSWORD = os.getenv("MIKROTIK_PASSWORD", "")
MIKROTIK_PORT = int(os.getenv("MIKROTIK_PORT", "8728"))

# إعدادات OpenWrt
OPENWRT_HOST = os.getenv("OPENWRT_HOST", "192.168.1.1")
OPENWRT_USER = os.getenv("OPENWRT_USER", "root")
OPENWRT_PASSWORD = os.getenv("OPENWRT_PASSWORD", "")
OPENWRT_PORT = int(os.getenv("OPENWRT_PORT", "22"))

# === إعدادات الشبكة ===
NETWORK_SUBNET = os.getenv("NETWORK_SUBNET", "192.168.1.0/24")
NETWORK_GATEWAY = os.getenv("NETWORK_GATEWAY", "192.168.1.1")
NETWORK_NAME = os.getenv("NETWORK_NAME", "حمد نت")

# === إعدادات المراقبة ===
SCAN_INTERVAL = int(os.getenv("SCAN_INTERVAL", "300"))        # فحص الشبكة كل 5 دقائق
PING_INTERVAL = int(os.getenv("PING_INTERVAL", "60"))         # فحص الاتصال كل دقيقة
SECURITY_CHECK_INTERVAL = int(os.getenv("SECURITY_CHECK_INTERVAL", "120"))  # فحص أمني كل دقيقتين
BANDWIDTH_MONITOR_INTERVAL = int(os.getenv("BANDWIDTH_MONITOR_INTERVAL", "30"))  # مراقبة الباندويث كل 30 ثانية

# === إعدادات التنبيهات ===
ALERT_ON_NEW_DEVICE = os.getenv("ALERT_ON_NEW_DEVICE", "true").lower() == "true"
ALERT_ON_DEVICE_LEAVE = os.getenv("ALERT_ON_DEVICE_LEAVE", "true").lower() == "true"
ALERT_ON_INTRUSION = os.getenv("ALERT_ON_INTRUSION", "true").lower() == "true"
ALERT_ON_OUTAGE = os.getenv("ALERT_ON_OUTAGE", "true").lower() == "true"
ALERT_ON_CONFIG_CHANGE = os.getenv("ALERT_ON_CONFIG_CHANGE", "true").lower() == "true"
ALERT_ON_HIGH_BANDWIDTH = os.getenv("ALERT_ON_HIGH_BANDWIDTH", "true").lower() == "true"
HIGH_BANDWIDTH_THRESHOLD = int(os.getenv("HIGH_BANDWIDTH_THRESHOLD", "100"))  # Mbps

# === إعدادات قاعدة البيانات ===
DATABASE_PATH = os.getenv("DATABASE_PATH", "data/hamad_net.db")

# === إعدادات Starlink ===
STARLINK_ENABLED = os.getenv("STARLINK_ENABLED", "false").lower() == "true"
STARLINK_IP = os.getenv("STARLINK_IP", "192.168.100.1")  # Dishy IP

# === إعدادات متقدمة ===
MAX_LOG_ENTRIES = int(os.getenv("MAX_LOG_ENTRIES", "1000"))
AUTO_BLOCK_INTRUSION = os.getenv("AUTO_BLOCK_INTRUSION", "false").lower() == "true"
NOTIFICATION_LANGUAGE = os.getenv("NOTIFICATION_LANGUAGE", "ar")  # ar أو en
