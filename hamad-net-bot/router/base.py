"""
طبقة التجريد للراوتر - Router Abstraction Layer
يدعم MikroTik RouterOS و OpenWrt
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class DeviceInfo:
    mac: str
    ip: str
    hostname: str = ""
    interface: str = ""
    vendor: str = ""
    is_online: bool = True


@dataclass
class RouterStats:
    uptime: str = ""
    cpu_load: float = 0.0
    memory_usage: float = 0.0
    memory_total: str = ""
    memory_free: str = ""
    wan_ip: str = ""
    firmware_version: str = ""
    model: str = ""
    temperature: float = 0.0
    voltage: float = 0.0


@dataclass
class InterfaceInfo:
    name: str
    type: str = ""
    is_up: bool = False
    rx_bytes: int = 0
    tx_bytes: int = 0
    rx_speed: str = ""
    tx_speed: str = ""
    mac: str = ""


class BaseRouter(ABC):
    """الواجهة الأساسية لأي راوتر"""

    @abstractmethod
    async def connect(self) -> bool:
        """الاتصال بالراوتر"""
        pass

    @abstractmethod
    async def disconnect(self):
        """قطع الاتصال بالراوتر"""
        pass

    @abstractmethod
    async def is_connected(self) -> bool:
        """هل الراوتر متصل؟"""
        pass

    @abstractmethod
    async def get_dhcp_leases(self) -> List[DeviceInfo]:
        """جلب عقود DHCP"""
        pass

    @abstractmethod
    async def get_arp_table(self) -> List[DeviceInfo]:
        """جلب جدول ARP"""
        pass

    @abstractmethod
    async def get_interfaces(self) -> List[InterfaceInfo]:
        """جلب واجهات الشبكة"""
        pass

    @abstractmethod
    async def get_router_stats(self) -> RouterStats:
        """جلب إحصائيات الراوتر"""
        pass

    @abstractmethod
    async def get_firewall_logs(self, limit: int = 50) -> List[Dict]:
        """جلب سجلات الجدار الناري"""
        pass

    @abstractmethod
    async def get_system_logs(self, limit: int = 50) -> List[Dict]:
        """جلب سجلات النظام"""
        pass

    @abstractmethod
    async def block_device(self, mac: str, ip: str = "") -> bool:
        """حظر جهاز من الإنترنت"""
        pass

    @abstractmethod
    async def unblock_device(self, mac: str, ip: str = "") -> bool:
        """إلغاء حظر جهاز"""
        pass

    @abstractmethod
    async def block_wifi(self, mac: str) -> bool:
        """حظر جهاز من WiFi"""
        pass

    @abstractmethod
    async def unblock_wifi(self, mac: str) -> bool:
        """إلغاء حظر WiFi"""
        pass

    @abstractmethod
    async def set_speed_limit(self, ip: str, download_kbps: int, upload_kbps: int) -> bool:
        """تحديد سرعة التحميل والتنزيل لجهاز"""
        pass

    @abstractmethod
    async def remove_speed_limit(self, ip: str) -> bool:
        """إزالة تحديد السرعة"""
        pass

    @abstractmethod
    async def reboot_router(self) -> bool:
        """إعادة تشغيل الراوتر"""
        pass

    @abstractmethod
    async def get_wan_ip(self) -> str:
        """جلب عنوان IP العام"""
        pass

    @abstractmethod
    async def ping(self, host: str, count: int = 4) -> Dict:
        """فحص اتصال بمضيف"""
        pass

    @abstractmethod
    async def get_dhcp_leases_count(self) -> int:
        """عدد عقود DHCP النشطة"""
        pass

    @abstractmethod
    async def get_wifi_clients(self) -> List[DeviceInfo]:
        """جلب عملاء WiFi المتصلين"""
        pass

    @abstractmethod
    async def get_queue_list(self) -> List[Dict]:
        """جلب قائمة تحديد السرعة"""
        pass

    @abstractmethod
    async def get_interface_traffic(self, interface: str = "ether1") -> Dict:
        """جلب حركة مرور واجهة"""
        pass
