"""
وحدة المراقبة - Monitoring Module
مراقبة الأجهزة، الإنترنت، محاولات الاختراق، وتغييرات الشبكة
"""
import asyncio
import logging
import time
from typing import List, Dict, Set, Optional, Callable
from datetime import datetime

from router.base import BaseRouter
from database.db import Database

logger = logging.getLogger(__name__)


class NetworkMonitor:
    """مراقب الشبكة الرئيسي"""

    def __init__(self, router: BaseRouter, db: Database, network_name: str = "حمد نت"):
        self.router = router
        self.db = db
        self.network_name = network_name
        self._known_macs: Set[str] = set()
        self._online_macs: Set[str] = set()
        self._previous_online: Set[str] = set()
        self._last_internet_up: bool = True
        self._alert_callback: Optional[Callable] = None
        self._running = False

    def set_alert_callback(self, callback: Callable):
        """تعيين دالة callback لإرسال التنبيهات عبر البوت"""
        self._alert_callback = callback

    async def _send_alert(self, alert_type: str, message: str, severity: str = "info",
                          device_mac: str = "", details: str = ""):
        """إرسال تنبيه وحفظه في قاعدة البيانات"""
        await self.db.add_alert(alert_type, message, severity, device_mac, details)
        if self._alert_callback:
            try:
                await self._alert_callback(alert_type, message, severity, device_mac)
            except Exception as e:
                logger.error(f"خطأ في إرسال التنبيه: {e}")

    async def initialize(self):
        """تهيئة المراقب بتحميل الأجهزة المعروفة"""
        devices = await self.db.get_all_devices()
        for d in devices:
            self._known_macs.add(d["mac"])
            if d["is_online"]:
                self._online_macs.add(d["mac"])
        self._previous_online = self._online_macs.copy()
        logger.info(f"تم تحميل {len(self._known_macs)} جهاز معروف")

    async def scan_devices(self) -> Dict:
        """فحص الأجهزة المتصلة بالشبكة"""
        result = {"new_devices": [], "left_devices": [], "current_online": [], "total_scanned": 0}

        try:
            # جلب من DHCP و ARP
            dhcp_devices = await self.router.get_dhcp_leases()
            arp_devices = await self.router.get_arp_table()
            wifi_clients = await self.router.get_wifi_clients()

            # دمج المصادر
            all_devices = {}
            for d in dhcp_devices:
                if d.mac:
                    all_devices[d.mac] = d
            for d in arp_devices:
                if d.mac and d.mac not in all_devices:
                    all_devices[d.mac] = d
            for d in wifi_clients:
                if d.mac and d.mac not in all_devices:
                    all_devices[d.mac] = d

            result["total_scanned"] = len(all_devices)
            current_macs = set(all_devices.keys())

            # تحديث قاعدة البيانات
            for mac, device in all_devices.items():
                await self.db.upsert_device(
                    mac=mac, ip=device.ip, hostname=device.hostname,
                    interface=device.interface, vendor=device.vendor
                )

            # كشف الأجهزة الجديدة
            truly_new = current_macs - self._known_macs
            for mac in truly_new:
                device = all_devices[mac]
                result["new_devices"].append({
                    "mac": mac, "ip": device.ip, "hostname": device.hostname,
                    "interface": device.interface, "vendor": device.vendor
                })
                is_known = mac in self._known_macs
                if not is_known:
                    await self._send_alert(
                        "new_device",
                        f"🔴 جهاز جديد متصل بالشبكة!\n"
                        f"📌 الاسم: {device.hostname or 'غير معروف'}\n"
                        f"🌐 IP: {device.ip}\n"
                        f"🔗 MAC: {mac}\n"
                        f"📡 الواجهة: {device.interface}\n"
                        f"🏭 الشركة: {device.vendor or 'غير معروفة'}",
                        "warning",
                        mac,
                        f"hostname={device.hostname}, ip={device.ip}"
                    )
                    await self.db.log_topology_change(
                        "new_device", mac,
                        f"جهاز جديد: {device.hostname or mac} ({device.ip})",
                        f"interface={device.interface}, vendor={device.vendor}"
                    )

            # كشف الأجهزة التي انفصلت
            left = self._previous_online - current_macs
            for mac in left:
                device_info = await self.db.get_device_by_mac(mac)
                if device_info and device_info.get("is_online"):
                    await self.db.set_device_offline(mac)
                    result["left_devices"].append({
                        "mac": mac,
                        "ip": device_info.get("ip", ""),
                        "hostname": device_info.get("hostname", "")
                    })
                    await self._send_alert(
                        "device_left",
                        f"🔵 جهاز انفصل عن الشبكة\n"
                        f"📌 الاسم: {device_info.get('hostname', 'غير معروف')}\n"
                        f"🌐 IP: {device_info.get('ip', '')}\n"
                        f"🔗 MAC: {mac}",
                        "info",
                        mac
                    )

            # تحديث الحالة
            self._known_macs = self._known_macs.union(current_macs)
            self._previous_online = current_macs.copy()
            self._online_macs = current_macs.copy()

            # جلب قائمة الأجهزة المتصلة
            result["current_online"] = [
                {"mac": mac, "ip": all_devices[mac].ip, "hostname": all_devices[mac].hostname}
                for mac in current_macs
            ]

        except Exception as e:
            logger.error(f"خطأ في فحص الأجهزة: {e}")
            await self.db.log_router_error("scan_error", str(e), "error")

        return result

    async def check_internet(self) -> Dict:
        """فحص اتصال الإنترنت"""
        result = {"is_up": True, "latency": 0, "wan_ip": "", "reason": ""}

        try:
            # فحص عبر ping من الراوتر
            ping_result = await self.router.ping("8.8.8.8", count=3)

            if ping_result.get("received", 0) > 0:
                result["is_up"] = True
                result["latency"] = ping_result.get("avg_latency", 0)
            else:
                result["is_up"] = False
                result["reason"] = "لا يستجيب للـ ping"

            # محاولة ثانية عبر DNS
            if not result["is_up"]:
                dns_ping = await self.router.ping("1.1.1.1", count=2)
                if dns_ping.get("received", 0) > 0:
                    result["is_up"] = True
                    result["latency"] = dns_ping.get("avg_latency", 0)
                    result["reason"] = ""

            # جلب WAN IP
            result["wan_ip"] = await self.router.get_wan_ip()

            # تسجيل الحالة
            await self.db.log_internet_status(
                result["is_up"], result["latency"], result["wan_ip"], result["reason"]
            )

            # تنبيه عند انقطاع الإنترنت
            if self._last_internet_up and not result["is_up"]:
                await self._send_alert(
                    "internet_down",
                    f"🚨 انقطاع الإنترنت!\n"
                    f"⏰ الوقت: {datetime.now().strftime('%H:%M:%S')}\n"
                    f"📋 السبب: {result['reason'] or 'غير محدد'}\n"
                    f"🌐 WAN IP الأخير: {result['wan_ip']}",
                    "critical"
                )
            elif not self._last_internet_up and result["is_up"]:
                await self._send_alert(
                    "internet_restored",
                    f"✅ عودة الإنترنت!\n"
                    f"⏰ الوقت: {datetime.now().strftime('%H:%M:%S')}\n"
                    f"📡 زمن الاستجابة: {result['latency']:.1f} ms",
                    "info"
                )

            self._last_internet_up = result["is_up"]

        except Exception as e:
            result["is_up"] = False
            result["reason"] = str(e)
            logger.error(f"خطأ في فحص الإنترنت: {e}")

        return result

    async def check_intrusions(self) -> List[Dict]:
        """فحص محاولات الاختراق من سجلات الراوتر"""
        intrusions = []

        try:
            logs = await self.router.get_firewall_logs(limit=100)

            for log_entry in logs:
                message = log_entry.get("message", "")
                topics = log_entry.get("topics", "")
                log_time = log_entry.get("time", "")

                # تحليل أنواع الهجمات
                attack_type = ""
                source_ip = ""
                target_port = 0
                protocol = ""

                if "drop" in message and "input" in topics:
                    attack_type = "محاولة وصول مباشر"
                    if "src=" in message:
                        source_ip = message.split("src=")[1].split()[0] if "src=" in message else ""
                    if "dst-port=" in message:
                        try:
                            target_port = int(message.split("dst-port=")[1].split()[0])
                        except (ValueError, IndexError):
                            pass
                    if "proto=" in message:
                        protocol = message.split("proto=")[1].split()[0] if "proto=" in message else ""

                elif "drop" in message and "forward" in topics:
                    attack_type = "محاولة تمرير محظورة"

                elif "reject" in message:
                    attack_type = "اتصال مرفوض"

                elif "login failure" in message.lower():
                    attack_type = "محاولة تسجيل دخول فاشلة"
                    if "from" in message:
                        source_ip = message.split("from")[-1].strip().split()[0]

                if attack_type:
                    intrusion = {
                        "time": log_time,
                        "source_ip": source_ip,
                        "target_port": target_port,
                        "protocol": protocol,
                        "attack_type": attack_type,
                        "message": message
                    }
                    intrusions.append(intrusion)

                    # تسجيل في قاعدة البيانات
                    await self.db.log_intrusion(
                        source_ip, target_port, protocol, attack_type, message
                    )

            # تنبيه إذا زادت محاولات الاختراق
            if len(intrusions) > 5:
                await self._send_alert(
                    "intrusion_spike",
                    f"🚨 تحذير: {len(intrusions)} محاولة اختراق في آخر فحص!\n"
                    f"أكثر المصادر: {', '.join(set(i['source_ip'] for i in intrusions if i['source_ip']))}",
                    "critical"
                )

        except Exception as e:
            logger.error(f"خطأ في فحص الاختراقات: {e}")

        return intrusions

    async def check_router_health(self) -> Dict:
        """فحص صحة الراوتر"""
        result = {"warnings": [], "errors": [], "stats": None}

        try:
            stats = await self.router.get_router_stats()
            result["stats"] = stats

            # فحص تحميل المعالج
            if stats.cpu_load > 90:
                result["warnings"].append(f"⚠️ تحميل المعالج مرتفع: {stats.cpu_load}%")
                await self._send_alert(
                    "high_cpu",
                    f"⚠️ تحميل المعالج مرتفع: {stats.cpu_load}%\n"
                    f"⏰ وقت التشغيل: {stats.uptime}",
                    "warning"
                )
                await self.db.log_router_error("high_cpu", f"CPU load: {stats.cpu_load}%", "warning")

            # فحص الذاكرة
            if stats.memory_usage > 90:
                result["warnings"].append(f"⚠️ استهلاك الذاكرة مرتفع: {stats.memory_usage}%")
                await self._send_alert(
                    "high_memory",
                    f"⚠️ استهلاك الذاكرة مرتفع: {stats.memory_usage}%\n"
                    f"💾 الحر: {stats.memory_free}",
                    "warning"
                )
                await self.db.log_router_error("high_memory", f"Memory: {stats.memory_usage}%", "warning")

            # فحص الحرارة
            if stats.temperature > 75:
                result["warnings"].append(f"🌡️ درجة الحرارة مرتفعة: {stats.temperature}°C")
                await self._send_alert(
                    "high_temp",
                    f"🌡️ درجة حرارة الراوتر مرتفعة: {stats.temperature}°C",
                    "warning"
                )

        except Exception as e:
            result["errors"].append(str(e))
            logger.error(f"خطأ في فحص صحة الراوتر: {e}")

        return result

    async def detect_topology_changes(self) -> List[Dict]:
        """كشف تغييرات طوبولوجيا الشبكة (مودم/سويتش جديد)"""
        changes = []

        try:
            interfaces = await self.router.get_interfaces()
            current_ifaces = {i.name: i for i in interfaces}

            # فحص واجهات جديدة أو متغيرة
            for iface in interfaces:
                # واجهة جديدة نشطة (قد تكون مودم/سويتش جديد)
                if iface.is_up and iface.type in ("ethernet", "bridge"):
                    # فحص إذا كان هناك تغير كبير في حركة المرور
                    # (قد يشير إلى جهاز شبكة جديد متصل)
                    pass

            # فحص أجهزة جديدة تعمل كجسر/سويتش
            dhcp_devices = await self.router.get_dhcp_leases()
            for d in dhcp_devices:
                # الأجهزة التي تحتوي كلمات تدل على أجهزة شبكة
                hostname_lower = (d.hostname or "").lower()
                if any(kw in hostname_lower for kw in ["switch", "hub", "router", "modem",
                                                         "ap-", "access-point", "repeater",
                                                         "switch", "hub", "مودم", "سويتش"]):
                    device = await self.db.get_device_by_mac(d.mac)
                    if device and not device.get("notes", "").startswith("[network-device]"):
                        change = {
                            "type": "network_device_detected",
                            "mac": d.mac,
                            "ip": d.ip,
                            "hostname": d.hostname,
                            "description": f"تم اكتشاف جهاز شبكة: {d.hostname} ({d.ip})"
                        }
                        changes.append(change)
                        await self.db.log_topology_change(
                            "network_device", d.mac,
                            change["description"],
                            f"hostname={d.hostname}, ip={d.ip}"
                        )
                        await self._send_alert(
                            "topology_change",
                            f"🔄 تغيير في طوبولوجيا الشبكة!\n"
                            f"📋 تم اكتشاف: {d.hostname}\n"
                            f"🌐 IP: {d.ip}\n"
                            f"🔗 MAC: {d.mac}\n"
                            f"⚠️ قد يكون مودم/سويتش/نقطة وصول جديدة",
                            "warning",
                            d.mac
                        )
                        await self.db.mark_device_known(d.mac, "[network-device] " + (d.hostname or ""))

        except Exception as e:
            logger.error(f"خطأ في كشف تغييرات الطوبولوجيا: {e}")

        return changes

    async def run_full_check(self) -> Dict:
        """تشغيل فحص شامل للشبكة"""
        results = {}
        results["devices"] = await self.scan_devices()
        results["internet"] = await self.check_internet()
        results["intrusions"] = await self.check_intrusions()
        results["health"] = await self.check_router_health()
        results["topology"] = await self.detect_topology_changes()
        return results
