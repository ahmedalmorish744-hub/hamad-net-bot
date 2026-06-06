"""
تكامل راوتر MikroTik - MikroTik RouterOS API Integration
يتصل بالراوتر عبر RouterOS API لتنفيذ جميع العمليات
"""
import asyncio
import logging
from typing import List, Dict, Optional
from .base import BaseRouter, DeviceInfo, RouterStats, InterfaceInfo

logger = logging.getLogger(__name__)

try:
    import librouteros
    from librouteros import connect as ros_connect
    from librouteros.query import Key
    HAS_LIBROUTEROS = True
except ImportError:
    HAS_LIBROUTEROS = False
    logger.warning("librouteros غير متوفر - سيتم استخدام وضع المحاكاة")


class MikroTikRouter(BaseRouter):
    def __init__(self, host: str, user: str, password: str, port: int = 8728):
        self.host = host
        self.user = user
        self.password = password
        self.port = port
        self._connection = None
        self._connected = False

    async def connect(self) -> bool:
        try:
            if not HAS_LIBROUTEROS:
                logger.info(f"وضع المحاكاة: الاتصال بـ MikroTik {self.host}")
                self._connected = True
                return True

            self._connection = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: ros_connect(
                    username=self.user,
                    password=self.password,
                    host=self.host,
                    port=self.port
                )
            )
            self._connected = True
            logger.info(f"تم الاتصال بـ MikroTik {self.host}")
            return True
        except Exception as e:
            logger.error(f"فشل الاتصال بـ MikroTik: {e}")
            self._connected = False
            return False

    async def disconnect(self):
        if self._connection:
            try:
                self._connection.close()
            except Exception:
                pass
        self._connected = False

    async def is_connected(self) -> bool:
        return self._connected

    async def _run_api(self, path, **kwargs):
        """تنفيذ أمر API بشكل متزامن في thread منفصل"""
        if not HAS_LIBROUTEROS or not self._connection:
            return []
        loop = asyncio.get_event_loop()

        def _exec():
            try:
                api = self._connection.path(path)
                if kwargs:
                    return list(api(**kwargs))
                return list(api)
            except Exception as e:
                logger.error(f"خطأ في API {path}: {e}")
                return []

        return await loop.run_in_executor(None, _exec)

    async def _run_api_cmd(self, path, command, **kwargs):
        """تنفيذ أمر API محدد"""
        if not HAS_LIBROUTEROS or not self._connection:
            return []
        loop = asyncio.get_event_loop()

        def _exec():
            try:
                api = self._connection.path(path)
                return list(api(command, **kwargs))
            except Exception as e:
                logger.error(f"خطأ في أمر API {path}/{command}: {e}")
                return []

        return await loop.run_in_executor(None, _exec)

    async def get_dhcp_leases(self) -> List[DeviceInfo]:
        """جلب عقود DHCP"""
        if not HAS_LIBROUTEROS or not self._connection:
            # بيانات تجريبية
            return [
                DeviceInfo(mac="AA:BB:CC:DD:EE:01", ip="192.168.1.100", hostname="Hamad-PC",
                          interface="bridge", vendor="Dell"),
                DeviceInfo(mac="AA:BB:CC:DD:EE:02", ip="192.168.1.101", hostname="iPhone-Hamad",
                          interface="wlan1", vendor="Apple"),
                DeviceInfo(mac="AA:BB:CC:DD:EE:03", ip="192.168.1.102", hostname="Samsung-TV",
                          interface="wlan1", vendor="Samsung"),
            ]

        try:
            leases = await self._run_api("/ip/dhcp-server/lease")
            devices = []
            for lease in leases:
                devices.append(DeviceInfo(
                    mac=lease.get("mac-address", ""),
                    ip=lease.get("address", ""),
                    hostname=lease.get("host-name", ""),
                    interface=lease.get("interface", ""),
                    vendor="",
                    is_online=lease.get("status", "") == "bound"
                ))
            return devices
        except Exception as e:
            logger.error(f"خطأ في جلب DHCP leases: {e}")
            return []

    async def get_arp_table(self) -> List[DeviceInfo]:
        """جلب جدول ARP"""
        if not HAS_LIBROUTEROS or not self._connection:
            return [
                DeviceInfo(mac="AA:BB:CC:DD:EE:01", ip="192.168.1.100", hostname="Hamad-PC",
                          interface="bridge"),
                DeviceInfo(mac="AA:BB:CC:DD:EE:02", ip="192.168.1.101", hostname="iPhone-Hamad",
                          interface="bridge"),
                DeviceInfo(mac="AA:BB:CC:DD:EE:03", ip="192.168.1.102", hostname="Samsung-TV",
                          interface="bridge"),
                DeviceInfo(mac="AA:BB:CC:DD:EE:04", ip="192.168.1.103", hostname="Unknown-Device",
                          interface="bridge"),
            ]

        try:
            arp_entries = await self._run_api("/ip/arp")
            devices = []
            for entry in arp_entries:
                if entry.get("mac-address"):
                    devices.append(DeviceInfo(
                        mac=entry.get("mac-address", ""),
                        ip=entry.get("address", ""),
                        interface=entry.get("interface", ""),
                        is_online=entry.get("complete", False)
                    ))
            return devices
        except Exception as e:
            logger.error(f"خطأ في جلب ARP table: {e}")
            return []

    async def get_interfaces(self) -> List[InterfaceInfo]:
        """جلب واجهات الشبكة"""
        if not HAS_LIBROUTEROS or not self._connection:
            return [
                InterfaceInfo(name="ether1", type="ethernet", is_up=True, rx_bytes=1024000,
                             tx_bytes=512000, mac="00:11:22:33:44:55"),
                InterfaceInfo(name="ether2", type="ethernet", is_up=True, rx_bytes=256000,
                             tx_bytes=128000, mac="00:11:22:33:44:56"),
                InterfaceInfo(name="wlan1", type="wireless", is_up=True, rx_bytes=2048000,
                             tx_bytes=1024000, mac="00:11:22:33:44:57"),
                InterfaceInfo(name="wlan2", type="wireless", is_up=True, rx_bytes=512000,
                             tx_bytes=256000, mac="00:11:22:33:44:58"),
            ]

        try:
            interfaces = await self._run_api("/interface")
            result = []
            for iface in interfaces:
                result.append(InterfaceInfo(
                    name=iface.get("name", ""),
                    type=iface.get("type", ""),
                    is_up=iface.get("running", False),
                    rx_bytes=iface.get("rx-byte", 0),
                    tx_bytes=iface.get("tx-byte", 0),
                    mac=iface.get("mac-address", "")
                ))
            return result
        except Exception as e:
            logger.error(f"خطأ في جلب interfaces: {e}")
            return []

    async def get_router_stats(self) -> RouterStats:
        """جلب إحصائيات الراوتر"""
        if not HAS_LIBROUTEROS or not self._connection:
            return RouterStats(
                uptime="15d 7h 32m",
                cpu_load=23.5,
                memory_usage=45.2,
                memory_total="256 MB",
                memory_free="140 MB",
                wan_ip="203.0.113.45",
                firmware_version="7.14.3",
                model="RB5009UG+S+IN",
                temperature=48.0,
                voltage=24.1
            )

        try:
            resource = await self._run_api("/system/resource")
            if resource:
                r = resource[0]
                return RouterStats(
                    uptime=r.get("uptime", ""),
                    cpu_load=float(r.get("cpu-load", 0)),
                    memory_usage=round(r.get("total-memory", 0) and
                                       (1 - r.get("free-memory", 0) / r.get("total-memory", 1)) * 100, 1),
                    memory_total=f"{r.get('total-memory', 0) // 1024 // 1024} MB",
                    memory_free=f"{r.get('free-memory', 0) // 1024 // 1024} MB",
                    firmware_version=r.get("version", ""),
                    model=r.get("board-name", ""),
                    temperature=float(r.get("cpu-temperature", 0)),
                )
            return RouterStats()
        except Exception as e:
            logger.error(f"خطأ في جلب router stats: {e}")
            return RouterStats()

    async def get_firewall_logs(self, limit: int = 50) -> List[Dict]:
        """جلب سجلات الجدار الناري"""
        if not HAS_LIBROUTEROS or not self._connection:
            import time
            return [
                {"time": "12:30:15", "topics": "firewall,input", "message": "input: drop src=10.0.0.5 dst=192.168.1.1 proto=tcp dst-port=23"},
                {"time": "12:28:03", "topics": "firewall,forward", "message": "forward: drop src=10.0.0.99 dst=45.33.32.156 proto=tcp dst-port=443"},
                {"time": "12:25:44", "topics": "firewall,input", "message": "input: reject src=172.16.0.1 dst=192.168.1.1 proto=udp dst-port=53"},
            ]

        try:
            logs = await self._run_api("/log", **{
                ".query": Key("topics").has("firewall"),
                ".proplist": ".id,time,topics,message"
            })
            result = []
            for log_entry in logs[:limit]:
                result.append({
                    "time": log_entry.get("time", ""),
                    "topics": log_entry.get("topics", ""),
                    "message": log_entry.get("message", "")
                })
            return result
        except Exception as e:
            logger.error(f"خطأ في جلب firewall logs: {e}")
            return []

    async def get_system_logs(self, limit: int = 50) -> List[Dict]:
        """جلب سجلات النظام"""
        if not HAS_LIBROUTEROS or not self._connection:
            return [
                {"time": "12:30:15", "topics": "system,error", "message": "login failure for user admin from 10.0.0.5"},
                {"time": "12:25:44", "topics": "system,warning", "message": "cpu load exceeds 90%"},
                {"time": "12:20:10", "topics": "dhcp", "message": "lease assigned 192.168.1.105 to AA:BB:CC:DD:EE:05"},
            ]

        try:
            logs = await self._run_api("/log")
            result = []
            for log_entry in logs[:limit]:
                result.append({
                    "time": log_entry.get("time", ""),
                    "topics": log_entry.get("topics", ""),
                    "message": log_entry.get("message", "")
                })
            return result
        except Exception as e:
            logger.error(f"خطأ في جلب system logs: {e}")
            return []

    async def block_device(self, mac: str, ip: str = "") -> bool:
        """حظر جهاز من الإنترنت عبر جدار ناري"""
        if not HAS_LIBROUTEROS or not self._connection:
            logger.info(f"[محاكاة] حظر الجهاز: {mac}")
            return True

        try:
            api = self._connection.path("/ip/firewall/filter")
            api.add(
                chain="forward",
                src_mac_address=mac,
                action="drop",
                comment=f"HamadNet-Blocked-{mac}"
            )
            logger.info(f"تم حظر الجهاز: {mac}")
            return True
        except Exception as e:
            logger.error(f"خطأ في حظر الجهاز {mac}: {e}")
            return False

    async def unblock_device(self, mac: str, ip: str = "") -> bool:
        """إلغاء حظر جهاز"""
        if not HAS_LIBROUTEROS or not self._connection:
            logger.info(f"[محاكاة] إلغاء حظر الجهاز: {mac}")
            return True

        try:
            api = self._connection.path("/ip/firewall/filter")
            comment_key = Key("comment")
            for rule in api.query(comment_key.has(f"HamadNet-Blocked-{mac}")):
                api.remove(rule[".id"])
            logger.info(f"تم إلغاء حظر الجهاز: {mac}")
            return True
        except Exception as e:
            logger.error(f"خطأ في إلغاء حظر الجهاز {mac}: {e}")
            return False

    async def block_wifi(self, mac: str) -> bool:
        """حظر جهاز من WiFi"""
        if not HAS_LIBROUTEROS or not self._connection:
            logger.info(f"[محاكاة] حظر WiFi: {mac}")
            return True

        try:
            api = self._connection.path("/interface/wireless/access-list")
            api.add(
                mac_address=mac,
                disabled="no",
                authentication="no",
                comment=f"HamadNet-WiFi-Blocked-{mac}"
            )
            return True
        except Exception as e:
            logger.error(f"خطأ في حظر WiFi {mac}: {e}")
            return False

    async def unblock_wifi(self, mac: str) -> bool:
        """إلغاء حظر WiFi"""
        if not HAS_LIBROUTEROS or not self._connection:
            logger.info(f"[محاكاة] إلغاء حظر WiFi: {mac}")
            return True

        try:
            api = self._connection.path("/interface/wireless/access-list")
            comment_key = Key("comment")
            for entry in api.query(comment_key.has(f"HamadNet-WiFi-Blocked-{mac}")):
                api.remove(entry[".id"])
            return True
        except Exception as e:
            logger.error(f"خطأ في إلغاء حظر WiFi {mac}: {e}")
            return False

    async def set_speed_limit(self, ip: str, download_kbps: int, upload_kbps: int) -> bool:
        """تحديد سرعة الجهاز عبر Simple Queue"""
        if not HAS_LIBROUTEROS or not self._connection:
            logger.info(f"[محاكاة] تحديد سرعة {ip}: {download_kbps}k/{upload_kbps}k")
            return True

        try:
            api = self._connection.path("/queue/simple")
            api.add(
                name=f"HamadNet-Limit-{ip}",
                target=f"{ip}/32",
                max_limit=f"{upload_kbps}k/{download_kbps}k",
                comment=f"HamadNet Speed Limit"
            )
            logger.info(f"تم تحديد سرعة {ip}: {download_kbps}k/{upload_kbps}k")
            return True
        except Exception as e:
            logger.error(f"خطأ في تحديد سرعة {ip}: {e}")
            return False

    async def remove_speed_limit(self, ip: str) -> bool:
        """إزالة تحديد السرعة"""
        if not HAS_LIBROUTEROS or not self._connection:
            logger.info(f"[محاكاة] إزالة تحديد سرعة: {ip}")
            return True

        try:
            api = self._connection.path("/queue/simple")
            name_key = Key("name")
            for queue in api.query(name_key == f"HamadNet-Limit-{ip}"):
                api.remove(queue[".id"])
            logger.info(f"تم إزالة تحديد سرعة {ip}")
            return True
        except Exception as e:
            logger.error(f"خطأ في إزالة تحديد سرعة {ip}: {e}")
            return False

    async def reboot_router(self) -> bool:
        """إعادة تشغيل الراوتر"""
        if not HAS_LIBROUTEROS or not self._connection:
            logger.info("[محاكاة] إعادة تشغيل الراوتر")
            return True

        try:
            await self._run_api_cmd("/system", "reboot")
            logger.info("تم إرسال أمر إعادة التشغيل")
            return True
        except Exception as e:
            logger.error(f"خطأ في إعادة تشغيل الراوتر: {e}")
            return False

    async def get_wan_ip(self) -> str:
        """جلب عنوان IP العام"""
        if not HAS_LIBROUTEROS or not self._connection:
            return "203.0.113.45"

        try:
            addrs = await self._run_api("/ip/address")
            for addr in addrs:
                iface = addr.get("interface", "")
                if "wan" in iface.lower() or "ether1" in iface.lower():
                    return addr.get("address", "").split("/")[0]
            return ""
        except Exception as e:
            logger.error(f"خطأ في جلب WAN IP: {e}")
            return ""

    async def ping(self, host: str, count: int = 4) -> Dict:
        """فحص اتصال بمضيف"""
        if not HAS_LIBROUTEROS or not self._connection:
            import random
            return {
                "host": host,
                "sent": count,
                "received": count,
                "packet_loss": 0,
                "avg_latency": round(random.uniform(5, 50), 1),
                "min_latency": round(random.uniform(1, 10), 1),
                "max_latency": round(random.uniform(20, 80), 1),
            }

        try:
            result = await self._run_api_cmd("/ping", "count", **{
                "address": host,
                "count": str(count)
            })
            if result:
                return {
                    "host": host,
                    "sent": count,
                    "received": result[-1].get("received", 0) if result else 0,
                    "packet_loss": result[-1].get("packet-loss", 100) if result else 100,
                    "avg_latency": result[-1].get("avg-rtt", 0) if result else 0,
                }
            return {"host": host, "sent": count, "received": 0, "packet_loss": 100, "avg_latency": 0}
        except Exception as e:
            logger.error(f"خطأ في ping {host}: {e}")
            return {"host": host, "error": str(e)}

    async def get_dhcp_leases_count(self) -> int:
        """عدد عقود DHCP النشطة"""
        if not HAS_LIBROUTEROS or not self._connection:
            return 4
        try:
            leases = await self._run_api("/ip/dhcp-server/lease")
            return len([l for l in leases if l.get("status") == "bound"])
        except Exception:
            return 0

    async def get_wifi_clients(self) -> List[DeviceInfo]:
        """جلب عملاء WiFi المتصلين"""
        if not HAS_LIBROUTEROS or not self._connection:
            return [
                DeviceInfo(mac="AA:BB:CC:DD:EE:02", ip="192.168.1.101",
                          hostname="iPhone-Hamad", interface="wlan1", vendor="Apple"),
                DeviceInfo(mac="AA:BB:CC:DD:EE:03", ip="192.168.1.102",
                          hostname="Samsung-TV", interface="wlan1", vendor="Samsung"),
            ]

        try:
            clients = []
            # جلب من registration-table للوايرلس
            reg = await self._run_api("/interface/wireless/registration-table")
            for entry in reg:
                clients.append(DeviceInfo(
                    mac=entry.get("mac-address", ""),
                    interface=entry.get("interface", ""),
                    is_online=True
                ))
            return clients
        except Exception as e:
            logger.error(f"خطأ في جلب WiFi clients: {e}")
            return []

    async def get_queue_list(self) -> List[Dict]:
        """جلب قائمة تحديد السرعة"""
        if not HAS_LIBROUTEROS or not self._connection:
            return [
                {"name": "HamadNet-Limit-192.168.1.105", "target": "192.168.1.105/32",
                 "max_limit": "1000k/2000k"}
            ]

        try:
            queues = await self._run_api("/queue/simple")
            result = []
            for q in queues:
                result.append({
                    "name": q.get("name", ""),
                    "target": q.get("target", ""),
                    "max_limit": q.get("max-limit", ""),
                })
            return result
        except Exception as e:
            logger.error(f"خطأ في جلب queue list: {e}")
            return []

    async def get_interface_traffic(self, interface: str = "ether1") -> Dict:
        """جلب حركة مرور واجهة"""
        if not HAS_LIBROUTEROS or not self._connection:
            return {"rx_byte": 1024000, "tx_byte": 512000, "rx_speed": "1.5 Mbps", "tx_speed": "0.8 Mbps"}

        try:
            ifaces = await self._run_api("/interface")
            for iface in ifaces:
                if iface.get("name") == interface:
                    return {
                        "rx_byte": iface.get("rx-byte", 0),
                        "tx_byte": iface.get("tx-byte", 0),
                    }
            return {}
        except Exception as e:
            logger.error(f"خطأ في جلب interface traffic: {e}")
            return {}
