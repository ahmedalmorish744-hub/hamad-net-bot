"""
وحدة فحص الشبكة - Network Scanner Module
لاكتشاف الأجهزة ورصد التغييرات
"""
import asyncio
import subprocess
import re
import logging
from typing import List, Dict, Optional
from datetime import datetime

import config
from utils.database import Database

logger = logging.getLogger(__name__)


class NetworkScanner:
    """فحص الشبكة واكتشاف الأجهزة"""

    def __init__(self, db: Database, router=None):
        self.db = db
        self.router = router
        self.previous_devices: Dict[str, Dict] = {}
        self._load_previous_devices()

    def _load_previous_devices(self):
        """تحميل الأجهزة المعروفة مسبقاً"""
        devices = self.db.get_all_devices()
        for d in devices:
            self.previous_devices[d['mac_address']] = d

    async def full_scan(self) -> Dict:
        """فحص شامل للشبكة - يُرجع التغييرات المكتشفة"""
        changes = {
            'new_devices': [],
            'left_devices': [],
            'changed_devices': [],
        }

        # 1. جلب الأجهزة من الراوتر
        router_devices = {}
        if self.router:
            try:
                # DHCP Leases
                leases = await self.router.get_dhcp_leases()
                for lease in leases:
                    mac = lease.get('mac', '').upper()
                    if mac:
                        router_devices[mac] = {
                            'mac': mac,
                            'ip': lease.get('ip', ''),
                            'hostname': lease.get('hostname', ''),
                            'status': lease.get('status', ''),
                            'source': 'dhcp',
                        }

                # ARP Table
                arp = await self.router.get_arp_table()
                for entry in arp:
                    mac = entry.get('mac', '').upper()
                    if mac and mac not in router_devices:
                        router_devices[mac] = {
                            'mac': mac,
                            'ip': entry.get('ip', ''),
                            'hostname': '',
                            'status': entry.get('status', ''),
                            'source': 'arp',
                        }
            except Exception as e:
                logger.error(f"خطأ في جلب بيانات الراوتر: {e}")

        # 2. فحص ARP المحلي
        local_arp = self._scan_local_arp()
        for mac, info in local_arp.items():
            if mac not in router_devices:
                router_devices[mac] = info

        # 3. فحص NMAP (إذا كان متوفراً)
        nmap_devices = await self._nmap_scan()
        for mac, info in nmap_devices.items():
            if mac not in router_devices:
                router_devices[mac] = info

        # 4. مقارنة مع الحالة السابقة
        current_macs = set(router_devices.keys())
        previous_macs = set(self.previous_devices.keys())

        # أجهزة جديدة
        new_macs = current_macs - previous_macs
        for mac in new_macs:
            device = router_devices[mac]
            is_new = self.db.add_or_update_device(
                mac=mac,
                ip=device.get('ip', ''),
                hostname=device.get('hostname', ''),
                device_type=self._guess_device_type(device),
                vendor=device.get('vendor', 'غير معروف'),
            )
            if is_new or not self.previous_devices.get(mac, {}).get('is_online', False):
                changes['new_devices'].append(device)
                self.db.log_connection_event(
                    mac=mac, ip=device.get('ip', ''),
                    event_type='connect', details=f"اسم: {device.get('hostname', 'غير معروف')}"
                )
                # التحقق من الترخيص
                db_device = self.db.get_device_by_mac(mac)
                if db_device and not db_device.get('is_authorized', False):
                    changes['new_devices'][-1]['unauthorized'] = True

        # أجهزة غادرت
        left_macs = previous_macs - current_macs
        for mac in left_macs:
            if self.previous_devices[mac].get('is_online', False):
                self.db.set_device_offline(mac)
                changes['left_devices'].append(self.previous_devices[mac])
                self.db.log_connection_event(
                    mac=mac,
                    ip=self.previous_devices[mac].get('ip_address', ''),
                    event_type='disconnect',
                )

        # أجهزة تغيرت (IP أو اسم المضيف)
        for mac in current_macs & previous_macs:
            new_device = router_devices[mac]
            old_device = self.previous_devices[mac]
            
            changes_list = []
            if new_device.get('ip') != old_device.get('ip_address'):
                changes_list.append(f"IP: {old_device.get('ip_address')} → {new_device.get('ip')}")
            if new_device.get('hostname') != old_device.get('hostname'):
                changes_list.append(f"اسم: {old_device.get('hostname')} → {new_device.get('hostname')}")
            
            if changes_list:
                self.db.add_or_update_device(
                    mac=mac, ip=new_device.get('ip', ''),
                    hostname=new_device.get('hostname', ''),
                )
                changes['changed_devices'].append({
                    'mac': mac,
                    'changes': changes_list,
                })
            else:
                # تحديث آخر ظهور فقط
                self.db.add_or_update_device(
                    mac=mac, ip=new_device.get('ip', ''),
                    hostname=new_device.get('hostname', ''),
                )

        # تحديث الحالة السابقة
        self.previous_devices = {}
        for mac, device in router_devices.items():
            self.previous_devices[mac] = {
                'mac_address': mac,
                'ip_address': device.get('ip', ''),
                'hostname': device.get('hostname', ''),
                'is_online': True,
                'is_authorized': self.previous_devices.get(mac, {}).get('is_authorized', False),
            }

        return changes

    def _scan_local_arp(self) -> Dict[str, Dict]:
        """فحص جدول ARP المحلي"""
        devices = {}
        try:
            result = subprocess.run(
                ['arp', '-a'],
                capture_output=True, text=True, timeout=10
            )
            for line in result.stdout.strip().split('\n'):
                match = re.search(r'\((\d+\.\d+\.\d+\.\d+)\)\s+at\s+([0-9a-fA-F:]+)', line)
                if match:
                    ip = match.group(1)
                    mac = match.group(2).upper()
                    if mac != '00:00:00:00:00:00':
                        devices[mac] = {
                            'mac': mac, 'ip': ip,
                            'hostname': '', 'source': 'local_arp',
                        }
        except Exception as e:
            logger.debug(f"فشل فحص ARP المحلي: {e}")
        return devices

    async def _nmap_scan(self) -> Dict[str, Dict]:
        """فحص الشبكة باستخدام nmap"""
        devices = {}
        try:
            result = subprocess.run(
                ['nmap', '-sn', '-n', config.NETWORK_SUBNET],
                capture_output=True, text=True, timeout=120
            )
            current_ip = None
            for line in result.stdout.split('\n'):
                ip_match = re.search(r'Nmap scan report for (\d+\.\d+\.\d+\.\d+)', line)
                if ip_match:
                    current_ip = ip_match.group(1)
                mac_match = re.search(r'MAC Address: ([0-9A-F:]+)\s+\((.+?)\)', line)
                if mac_match and current_ip:
                    mac = mac_match.group(1).upper()
                    vendor = mac_match.group(2)
                    devices[mac] = {
                        'mac': mac, 'ip': current_ip,
                        'hostname': '', 'vendor': vendor,
                        'source': 'nmap',
                    }
                    current_ip = None
        except FileNotFoundError:
            logger.debug("nmap غير مثبت")
        except Exception as e:
            logger.debug(f"فشل فحص nmap: {e}")
        return devices

    def _guess_device_type(self, device: Dict) -> str:
        """تخمين نوع الجهاز"""
        hostname = device.get('hostname', '').lower()
        vendor = device.get('vendor', '').lower()
        mac = device.get('mac', '')

        if 'router' in hostname or 'mikrotik' in hostname or 'openwrt' in hostname:
            return 'router'
        elif 'switch' in hostname:
            return 'switch'
        elif 'ap' in hostname or 'wifi' in hostname or 'wlan' in hostname:
            return 'access_point'
        elif 'phone' in hostname or 'galaxy' in hostname or 'iphone' in hostname:
            return 'phone'
        elif 'pc' in hostname or 'desktop' in hostname or 'windows' in hostname:
            return 'computer'
        elif 'android' in hostname:
            return 'phone'
        elif any(x in vendor for x in ['samsung', 'apple', 'huawei', 'xiaomi', 'oppo', 'oneplus', 'honor']):
            return 'phone'
        elif any(x in vendor for x in ['mikrotik', 'tp-link', 'ubiquiti', 'netgear', 'cisco']):
            return 'network_device'
        elif 'dell' in vendor or 'lenovo' in vendor or 'hp' in vendor:
            return 'computer'
        elif 'raspberry' in vendor:
            return 'server'
        else:
            return 'unknown'

    async def ping_check(self, hosts: List[str]) -> Dict[str, bool]:
        """فحص اتصال مجموعة عناوين"""
        results = {}
        for host in hosts:
            try:
                result = subprocess.run(
                    ['ping', '-c', '1', '-W', '3', host],
                    capture_output=True, timeout=5
                )
                results[host] = result.returncode == 0
            except:
                results[host] = False
        return results

    async def detect_network_changes(self) -> List[Dict]:
        """كشف التغييرات في بنية الشبكة (مودم/سويتش جديد)"""
        changes = []
        
        if not self.router:
            return changes

        try:
            # فحص الواجهات الجديدة
            interfaces = await self.router.get_interfaces()
            for iface in interfaces:
                if iface.get('link_downs', 0) > 0 and iface.get('running'):
                    # واجهة كانت معطلة وأصبحت نشطة - قد يكون جهاز جديد
                    changes.append({
                        'type': 'interface_up',
                        'description': f"الواجهة {iface['name']} أصبحت نشطة",
                        'interface': iface['name'],
                        'timestamp': datetime.now().isoformat(),
                    })

            # فحص DHCP Leases الجديدة (أجهزة شبكة)
            leases = await self.router.get_dhcp_leases_with_vendor()
            for lease in leases:
                vendor = lease.get('vendor', '').lower()
                if any(x in vendor for x in ['tp-link', 'mikrotik', 'cisco', 'netgear', 'ubiquiti', 'd-link']):
                    device = self.db.get_device_by_mac(lease['mac'])
                    if device and device.get('device_type') != 'network_device':
                        self.db.add_or_update_device(
                            mac=lease['mac'], ip=lease['ip'],
                            hostname=lease.get('hostname', ''),
                            device_type='network_device', vendor=vendor,
                        )
                        changes.append({
                            'type': 'new_network_device',
                            'description': f"جهاز شبكة جديد: {lease.get('hostname', lease['mac'])} ({vendor})",
                            'mac': lease['mac'],
                            'ip': lease['ip'],
                            'vendor': vendor,
                            'timestamp': datetime.now().isoformat(),
                        })

        except Exception as e:
            logger.error(f"خطأ في كشف تغييرات الشبكة: {e}")

        return changes

    async def get_device_details(self, ip: str) -> Optional[Dict]:
        """الحصول على تفاصيل جهاز بالـ IP"""
        try:
            result = subprocess.run(
                ['nmap', '-sV', '-O', '--top-ports', '100', ip],
                capture_output=True, text=True, timeout=60
            )
            return {'ip': ip, 'scan_result': result.stdout}
        except:
            return None
