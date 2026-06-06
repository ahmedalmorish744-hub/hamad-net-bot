"""
إعدادات بوت حمد نت - Hamad Net Bot Configuration
"""
import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    # === إعدادات البوت ===
    BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
    ADMIN_CHAT_ID: int = int(os.getenv("ADMIN_CHAT_ID", "0"))
    NETWORK_NAME: str = os.getenv("NETWORK_NAME", "حمد نت")

    # === إعدادات الراوتر ===
    ROUTER_TYPE: str = os.getenv("ROUTER_TYPE", "mikrotik")  # mikrotik | openwrt
    ROUTER_HOST: str = os.getenv("ROUTER_HOST", "192.168.1.1")
    ROUTER_USER: str = os.getenv("ROUTER_USER", "admin")
    ROUTER_PASS: str = os.getenv("ROUTER_PASS", "")
    ROUTER_API_PORT: int = int(os.getenv("ROUTER_API_PORT", "8728"))
    ROUTER_SSH_PORT: int = int(os.getenv("ROUTER_SSH_PORT", "22"))

    # === إعدادات الشبكة ===
    NETWORK_SUBNET: str = os.getenv("NETWORK_SUBNET", "192.168.1.0/24")
    SCAN_INTERVAL: int = int(os.getenv("SCAN_INTERVAL", "60"))       # ثانية
    INTERNET_CHECK_INTERVAL: int = int(os.getenv("INTERNET_CHECK_INTERVAL", "30"))
    TRAFFIC_UPDATE_INTERVAL: int = int(os.getenv("TRAFFIC_UPDATE_INTERVAL", "300"))

    # === إعدادات الأمان ===
    MAX_LOGIN_ATTEMPTS: int = int(os.getenv("MAX_LOGIN_ATTEMPTS", "3"))
    ALERT_ON_NEW_DEVICE: bool = os.getenv("ALERT_ON_NEW_DEVICE", "true").lower() == "true"
    ALERT_ON_DEVICE_LEAVE: bool = os.getenv("ALERT_ON_DEVICE_LEAVE", "true").lower() == "true"
    ALERT_ON_INTRUSION: bool = os.getenv("ALERT_ON_INTRUSION", "true").lower() == "true"
    ALERT_ON_INTERNET_DOWN: bool = os.getenv("ALERT_ON_INTERNET_DOWN", "true").lower() == "true"
    ALERT_ON_TOPOLOGY_CHANGE: bool = os.getenv("ALERT_ON_TOPOLOGY_CHANGE", "true").lower() == "true"
    ALERT_ON_HIGH_CPU: bool = os.getenv("ALERT_ON_HIGH_CPU", "true").lower() == "true"
    CPU_THRESHOLD: int = int(os.getenv("CPU_THRESHOLD", "90"))

    # === مسار قاعدة البيانات ===
    DB_PATH: str = os.getenv("DB_PATH", "hamad_net.db")


config = Config()
