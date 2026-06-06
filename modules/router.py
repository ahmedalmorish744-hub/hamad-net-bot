"""
وحدة الاتصال بالراوتر - Router Connection Module
يدعم MikroTik RouterOS و OpenWrt
"""
import asyncio
import logging
from typing import Dict, List, Optional, Any
from abc import ABC, abstractmethod

import config

logger = logging.getLogger(__name__)


class RouterBase(ABC):
    """فئة أساسية للاتصال بالراوتر"""

    @abstractmethod
    async def connect(self) -> bool:
        pass

    @abstractmethod
    async def disconnect(self):
        pass

    @abstractmethod
    async def get_dhcp_leases(self) -> List[Dict]:
        pass

    @abstractmethod
    async def get_arp_table(self) -> List[Dict]:
        pass

    @abstractmethod
    async def get_interfaces(self) -> List[Dict]:
        pass

    @abstractmethod
    async def get_interface_traffic(self) -> List[Dict]:
        pass

    @abstractmethod
    async def get_system_info(self) -> Dict:
        pass

    @abstractmethod
    async def get_firewall_rules(self) -> List[Dict]:
        pass

    @abstractmethod
    async def block_device(self, mac: str, comment: str = "") -> bool:
        pass

    @abstractmethod
    async def unblock_device(self, mac: str) -> bool:
        pass

    @abstractmethod
    async def get_dhcp_leases_with_vendor(self) -> List[Dict]:
        pass

    @abstractmethod
    async def get_system_logs(self) -> List[Dict]:
        pass

    @abstractmethod
    async def get_routing_table(self) -> List[Dict]:
        pass

    @abstractmethod
    async def ping(self, host: str, count: int = 4) -> Dict:
        pass

    @abstractmethod
    async def reboot(self) -> bool:
        pass

    @abstractmethod
    async def get_cpu_load(self) -> float:
        pass

    @abstractmethod
    async def get_memory_usage(self) -> Dict:
        pass

    @abstractmethod
    async def get_uptime(self) -> str:
        pass

    @abstractmethod
    async def add_dhcp_lease(self, mac: str, ip: str, hostname: str = "") -> bool:
        pass

    @abstractmethod
    async def set_bandwidth_limit(self, ip: str, download: str, upload: str) -> bool:
        pass

    @abstractmethod
    async def remove_bandwidth_limit(self, ip: str) -> bool:
        pass


class MikroTikRouter(RouterBase):
    """الاتصال براوتر MikroTik عبر API"""

    def __init__(self):
        self.api = None
        self.connected = False

    async def connect(self) -> bool:
        try:
            from routeros_api import RouterOsApi
            self.api = RouterOsApi(
                config.MIKROTIK_HOST,
                username=config.MIKROTIK_USER,
                password=config.MIKROTIK_PASSWORD,
                port=config.MIKROTIK_PORT
            )
            self.api.connect()
            self.connected = True
            logger.info("تم الاتصال براوتر MikroTik بنجاح")
            return True
        except Exception as e:
            logger.error(f"فشل الاتصال بـ MikroTik: {e}")
            self.connected = False
            return False

    async def disconnect(self):
        if self.api:
            try:
                self.api.close()
            except:
                pass
            self.connected = False

    def _ensure_connection(self):
        if not self.connected:
            raise ConnectionError("غير متصل بالراوتر")

    async def get_dhcp_leases(self) -> List[Dict]:
        self._ensure_connection()
        try:
            leases = self.api.get_resource('/ip/dhcp-server/lease').get()
            return [{
                'mac': l.get('mac-address', '').upper(),
                'ip': l.get('address', ''),
                'hostname': l.get('host-name', ''),
                'status': 'bound' if l.get('status') == 'bound' else 'waiting',
                'server': l.get('server', ''),
                'comment': l.get('comment', ''),
            } for l in leases]
        except Exception as e:
            logger.error(f"خطأ في جلب DHCP leases: {e}")
            return []

    async def get_arp_table(self) -> List[Dict]:
        self._ensure_connection()
        try:
            arp = self.api.get_resource('/ip/arp').get()
            return [{
                'mac': a.get('mac-address', '').upper(),
                'ip': a.get('address', ''),
                'interface': a.get('interface', ''),
                'status': 'reachable' if a.get('complete') == 'true' else 'unreachable',
            } for a in arp if a.get('mac-address')]
        except Exception as e:
            logger.error(f"خطأ في جلب ARP table: {e}")
            return []

    async def get_interfaces(self) -> List[Dict]:
        self._ensure_connection()
        try:
            interfaces = self.api.get_resource('/interface').get()
            return [{
                'name': i.get('name', ''),
                'type': i.get('type', ''),
                'running': i.get('running') == 'true',
                'enabled': i.get('disabled') != 'true',
                'mac': i.get('mac-address', ''),
                'tx_bytes': int(i.get('tx-byte', 0)),
                'rx_bytes': int(i.get('rx-byte', 0)),
                'link_downs': int(i.get('link-downs', 0)),
                'comment': i.get('comment', ''),
            } for i in interfaces]
        except Exception as e:
            logger.error(f"خطأ في جلب الواجهات: {e}")
            return []

    async def get_interface_traffic(self) -> List[Dict]:
        self._ensure_connection()
        try:
            interfaces = self.api.get_resource('/interface').get()
            result = []
            for i in interfaces:
                if i.get('running') == 'true' and i.get('type') in ['ether', 'wlan', 'bridge', 'vlan']:
                    result.append({
                        'name': i.get('name', ''),
                        'tx_bytes': int(i.get('tx-byte', 0)),
                        'rx_bytes': int(i.get('rx-byte', 0)),
                        'tx_speed': int(i.get('tx-byte', 0)),  # سيتم حساب السرعة من الفرق
                        'rx_speed': int(i.get('rx-byte', 0)),
                        'type': i.get('type', ''),
                    })
            return result
        except Exception as e:
            logger.error(f"خطأ في جلب بيانات المرور: {e}")
            return []

    async def get_system_info(self) -> Dict:
        self._ensure_connection()
        try:
            identity = self.api.get_resource('/system/identity').get()[0]
            resource = self.api.get_resource('/system/resource').get()[0]
            routerboard = self.api.get_resource('/system/routerboard').get()
            
            info = {
                'identity': identity.get('name', 'Unknown'),
                'model': resource.get('board-name', 'Unknown'),
                'version': resource.get('version', 'Unknown'),
                'firmware': resource.get('firmware', 'Unknown'),
                'cpu': resource.get('cpu', 'Unknown'),
                'cpu_count': int(resource.get('cpu-count', 1)),
                'cpu_load': float(resource.get('cpu-load', 0)),
                'uptime': resource.get('uptime', 'Unknown'),
                'total_memory': int(resource.get('total-memory', 0)),
                'free_memory': int(resource.get('free-memory', 0)),
                'architecture': resource.get('architecture-name', 'Unknown'),
            }
            
            if routerboard:
                info['routerboard_model'] = routerboard[0].get('model', '')
                info['serial_number'] = routerboard[0].get('serial-number', '')
            
            return info
        except Exception as e:
            logger.error(f"خطأ في جلب معلومات النظام: {e}")
            return {}

    async def get_firewall_rules(self) -> List[Dict]:
        self._ensure_connection()
        try:
            rules = self.api.get_resource('/ip/firewall/filter').get()
            return [{
                'chain': r.get('chain', ''),
                'action': r.get('action', ''),
                'src_address': r.get('src-address', ''),
                'dst_address': r.get('dst-address', ''),
                'src_mac': r.get('src-mac-address', ''),
                'protocol': r.get('protocol', ''),
                'dst_port': r.get('dst-port', ''),
                'comment': r.get('comment', ''),
                'disabled': r.get('disabled') == 'true',
                'bytes': int(r.get('bytes', 0)),
                'packets': int(r.get('packets', 0)),
            } for r in rules]
        except Exception as e:
            logger.error(f"خطأ في جلب قواعد الجدار الناري: {e}")
            return []

    async def block_device(self, mac: str, comment: str = "محظور بواسطة بوت حمد نت") -> bool:
        self._ensure_connection()
        try:
            self.api.get_resource('/ip/firewall/filter').add(
                chain='forward',
                src_mac_address=mac,
                action='drop',
                comment=comment
            )
            # أيضاً إضافة لقائمة العناوين
            self.api.get_resource('/ip/firewall/address-list').add(
                list='blocked_devices',
                address=mac,
                comment=comment
            )
            logger.info(f"تم حظر الجهاز {mac}")
            return True
        except Exception as e:
            logger.error(f"خطأ في حظر الجهاز {mac}: {e}")
            return False

    async def unblock_device(self, mac: str) -> bool:
        self._ensure_connection()
        try:
            # حذف قاعدة الجدار الناري
            rules = self.api.get_resource('/ip/firewall/filter').get(
                **{'src-mac-address': mac}
            )
            for rule in rules:
                self.api.get_resource('/ip/firewall/filter').remove(id=rule['id'])

            # حذف من قائمة العناوين
            lists = self.api.get_resource('/ip/firewall/address-list').get(
                **{'address': mac}
            )
            for item in lists:
                self.api.get_resource('/ip/firewall/address-list').remove(id=item['id'])

            logger.info(f"تم إلغاء حظر الجهاز {mac}")
            return True
        except Exception as e:
            logger.error(f"خطأ في إلغاء حظر الجهاز {mac}: {e}")
            return False

    async def get_dhcp_leases_with_vendor(self) -> List[Dict]:
        leases = await self.get_dhcp_leases()
        # يمكن إضافة كشف البائع من MAC address
        for lease in leases:
            mac = lease.get('mac', '')
            if mac:
                oui = mac[:8].replace(':', '-')
                lease['vendor'] = _get_vendor_from_oui(oui)
            else:
                lease['vendor'] = 'غير معروف'
        return leases

    async def get_system_logs(self) -> List[Dict]:
        self._ensure_connection()
        try:
            logs = self.api.get_resource('/log').get()
            return [{
                'time': l.get('time', ''),
                'topics': l.get('topics', ''),
                'message': l.get('message', ''),
            } for l in logs[-100:]]  # آخر 100 سجل
        except Exception as e:
            logger.error(f"خطأ في جلب السجلات: {e}")
            return []

    async def get_routing_table(self) -> List[Dict]:
        self._ensure_connection()
        try:
            routes = self.api.get_resource('/ip/route').get()
            return [{
                'dst': r.get('dst-address', ''),
                'gateway': r.get('gateway', ''),
                'interface': r.get('pref-src', ''),
                'distance': r.get('distance', ''),
                'status': 'active' if r.get('disabled') != 'true' else 'disabled',
            } for r in routes]
        except Exception as e:
            logger.error(f"خطأ في جلب جدول التوجيه: {e}")
            return []

    async def ping(self, host: str, count: int = 4) -> Dict:
        self._ensure_connection()
        try:
            result = self.api.get_resource('/ping').call(
                {'address': host, 'count': str(count)}
            )
            if result:
                return {
                    'host': host,
                    'sent': count,
                    'received': len(result),
                    'avg_latency': sum(float(r.get('time', 0)) for r in result) / len(result) if result else 0,
                    'packet_loss': ((count - len(result)) / count) * 100,
                }
            return {'host': host, 'sent': count, 'received': 0, 'packet_loss': 100}
        except Exception as e:
            logger.error(f"خطأ في الـ ping: {e}")
            return {'host': host, 'error': str(e)}

    async def reboot(self) -> bool:
        self._ensure_connection()
        try:
            self.api.get_resource('/system').call('reboot')
            return True
        except Exception as e:
            logger.error(f"خطأ في إعادة التشغيل: {e}")
            return False

    async def get_cpu_load(self) -> float:
        self._ensure_connection()
        try:
            resource = self.api.get_resource('/system/resource').get()[0]
            return float(resource.get('cpu-load', 0))
        except:
            return -1

    async def get_memory_usage(self) -> Dict:
        self._ensure_connection()
        try:
            resource = self.api.get_resource('/system/resource').get()[0]
            total = int(resource.get('total-memory', 0))
            free = int(resource.get('free-memory', 0))
            used = total - free
            return {
                'total_mb': round(total / 1024 / 1024, 1),
                'used_mb': round(used / 1024 / 1024, 1),
                'free_mb': round(free / 1024 / 1024, 1),
                'usage_percent': round((used / total) * 100, 1) if total > 0 else 0,
            }
        except:
            return {}

    async def get_uptime(self) -> str:
        self._ensure_connection()
        try:
            resource = self.api.get_resource('/system/resource').get()[0]
            return resource.get('uptime', 'غير معروف')
        except:
            return 'غير متصل'

    async def add_dhcp_lease(self, mac: str, ip: str, hostname: str = "") -> bool:
        self._ensure_connection()
        try:
            params = {'mac-address': mac, 'address': ip}
            if hostname:
                params['host-name'] = hostname
            self.api.get_resource('/ip/dhcp-server/lease').add(**params)
            return True
        except Exception as e:
            logger.error(f"خطأ في إضافة DHCP lease: {e}")
            return False

    async def set_bandwidth_limit(self, ip: str, download: str, upload: str) -> bool:
        """تحديد سرعة الجهاز (download/upload بصيغة مثل 10M)"""
        self._ensure_connection()
        try:
            # إنشاء Simple Queue
            self.api.get_resource('/queue/simple').add(
                name=f"limit_{ip}",
                target=ip,
                max_limit=f"{upload}/{download}"
            )
            logger.info(f"تم تحديد سرعة {ip}: تحميل {download} / رفع {upload}")
            return True
        except Exception as e:
            logger.error(f"خطأ في تحديد السرعة: {e}")
            return False

    async def remove_bandwidth_limit(self, ip: str) -> bool:
        self._ensure_connection()
        try:
            queues = self.api.get_resource('/queue/simple').get(
                **{'target': ip}
            )
            for q in queues:
                self.api.get_resource('/queue/simple').remove(id=q['id'])
            logger.info(f"تم إزالة تحديد السرعة عن {ip}")
            return True
        except Exception as e:
            logger.error(f"خطأ في إزالة تحديد السرعة: {e}")
            return False


class OpenWrTRouter(RouterBase):
    """الاتصال براوتر OpenWrt عبر SSH"""

    def __init__(self):
        self.ssh_client = None
        self.connected = False

    async def connect(self) -> bool:
        try:
            import paramiko
            self.ssh_client = paramiko.SSHClient()
            self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            self.ssh_client.connect(
                config.OPENWRT_HOST,
                port=config.OPENWRT_PORT,
                username=config.OPENWRT_USER,
                password=config.OPENWRT_PASSWORD,
                timeout=10
            )
            self.connected = True
            logger.info("تم الاتصال براوتر OpenWrt بنجاح")
            return True
        except Exception as e:
            logger.error(f"فشل الاتصال بـ OpenWrt: {e}")
            self.connected = False
            return False

    async def disconnect(self):
        if self.ssh_client:
            self.ssh_client.close()
            self.connected = False

    def _run_command(self, cmd: str) -> str:
        if not self.connected:
            raise ConnectionError("غير متصل بالراوتر")
        stdin, stdout, stderr = self.ssh_client.exec_command(cmd, timeout=30)
        return stdout.read().decode('utf-8', errors='ignore')

    def _run_json_command(self, cmd: str) -> Any:
        import json
        output = self._run_command(cmd)
        try:
            return json.loads(output)
        except:
            return []

    async def get_dhcp_leases(self) -> List[Dict]:
        try:
            result = self._run_json_command("cat /tmp/dhcp.leases")
            leases = []
            for line in self._run_command("cat /tmp/dhcp.leases").strip().split('\n'):
                if line.strip():
                    parts = line.split()
                    if len(parts) >= 4:
                        leases.append({
                            'mac': parts[1].upper(),
                            'ip': parts[2],
                            'hostname': parts[3] if parts[3] != '*' else '',
                            'status': 'bound',
                            'server': 'dnsmasq',
                            'comment': '',
                        })
            return leases
        except Exception as e:
            logger.error(f"خطأ في جلب DHCP leases: {e}")
            return []

    async def get_arp_table(self) -> List[Dict]:
        try:
            output = self._run_command("cat /proc/net/arp")
            result = []
            for line in output.strip().split('\n')[1:]:
                parts = line.split()
                if len(parts) >= 6 and parts[3] != '00:00:00:00:00:00':
                    result.append({
                        'mac': parts[3].upper(),
                        'ip': parts[0],
                        'interface': parts[5],
                        'status': 'reachable' if parts[2] == '0x2' else 'unreachable',
                    })
            return result
        except Exception as e:
            logger.error(f"خطأ في جلب ARP table: {e}")
            return []

    async def get_interfaces(self) -> List[Dict]:
        try:
            output = self._run_command("ip -j addr show")
            interfaces = self._run_json_command("ip -j addr show 2>/dev/null || echo '[]'")
            result = []
            for i in interfaces:
                result.append({
                    'name': i.get('ifname', i.get('operstate', '')),
                    'type': i.get('link_type', ''),
                    'running': i.get('operstate') == 'UP',
                    'enabled': i.get('operstate') != 'DOWN',
                    'mac': i.get('address', ''),
                    'tx_bytes': 0,
                    'rx_bytes': 0,
                    'link_downs': 0,
                    'comment': '',
                })
            return result
        except Exception as e:
            logger.error(f"خطأ في جلب الواجهات: {e}")
            return []

    async def get_interface_traffic(self) -> List[Dict]:
        try:
            output = self._run_command("cat /proc/net/dev")
            result = []
            for line in output.strip().split('\n')[2:]:
                parts = line.split()
                if len(parts) >= 10:
                    name = parts[0].rstrip(':')
                    if name != 'lo':
                        result.append({
                            'name': name,
                            'rx_bytes': int(parts[1]),
                            'tx_bytes': int(parts[9]),
                            'rx_speed': 0,
                            'tx_speed': 0,
                            'type': 'eth' if 'eth' in name else 'wifi' if 'wlan' in name else 'other',
                        })
            return result
        except Exception as e:
            logger.error(f"خطأ في جلب بيانات المرور: {e}")
            return []

    async def get_system_info(self) -> Dict:
        try:
            hostname = self._run_command("hostname").strip()
            kernel = self._run_command("uname -r").strip()
            uptime = self._run_command("uptime").strip()
            meminfo = self._run_command("free -m").strip()
            lines = meminfo.split('\n')
            mem_parts = lines[1].split() if len(lines) > 1 else []
            
            return {
                'identity': hostname,
                'model': 'OpenWrt',
                'version': kernel,
                'uptime': uptime,
                'total_memory': int(mem_parts[1]) * 1024 if len(mem_parts) > 1 else 0,
                'free_memory': int(mem_parts[3]) * 1024 if len(mem_parts) > 3 else 0,
                'architecture': self._run_command("uname -m").strip(),
            }
        except Exception as e:
            logger.error(f"خطأ في جلب معلومات النظام: {e}")
            return {}

    async def get_firewall_rules(self) -> List[Dict]:
        try:
            rules = self._run_json_command("iptables -L -n -v --line-numbers 2>/dev/null || nft -j list ruleset 2>/dev/null || echo '[]'")
            # تحليل مبسط
            return [{'raw': str(r)} for r in (rules if isinstance(rules, list) else [])]
        except:
            return []

    async def block_device(self, mac: str, comment: str = "محظور بواسطة بوت حمد نت") -> bool:
        try:
            self._run_command(f"iptables -I FORWARD -m mac --mac-source {mac} -j DROP -m comment --comment '{comment}'")
            # حفظ القواعد
            self._run_command("/etc/init.d/firewall save 2>/dev/null || true")
            logger.info(f"تم حظر الجهاز {mac}")
            return True
        except Exception as e:
            logger.error(f"خطأ في حظر الجهاز {mac}: {e}")
            return False

    async def unblock_device(self, mac: str) -> bool:
        try:
            self._run_command(f"iptables -D FORWARD -m mac --mac-source {mac} -j DROP 2>/dev/null || true")
            self._run_command("/etc/init.d/firewall save 2>/dev/null || true")
            logger.info(f"تم إلغاء حظر الجهاز {mac}")
            return True
        except Exception as e:
            logger.error(f"خطأ في إلغاء حظر الجهاز {mac}: {e}")
            return False

    async def get_dhcp_leases_with_vendor(self) -> List[Dict]:
        leases = await self.get_dhcp_leases()
        for lease in leases:
            mac = lease.get('mac', '')
            if mac:
                oui = mac[:8].replace(':', '-')
                lease['vendor'] = _get_vendor_from_oui(oui)
            else:
                lease['vendor'] = 'غير معروف'
        return leases

    async def get_system_logs(self) -> List[Dict]:
        try:
            output = self._run_command("logread | tail -100")
            logs = []
            for line in output.strip().split('\n'):
                if line.strip():
                    parts = line.split(None, 5)
                    logs.append({
                        'time': ' '.join(parts[:3]) if len(parts) >= 3 else '',
                        'topics': parts[3] if len(parts) >= 4 else '',
                        'message': parts[5] if len(parts) >= 6 else line,
                    })
            return logs
        except:
            return []

    async def get_routing_table(self) -> List[Dict]:
        try:
            output = self._run_command("route -n")
            routes = []
            for line in output.strip().split('\n')[2:]:
                parts = line.split()
                if len(parts) >= 8:
                    routes.append({
                        'dst': parts[0],
                        'gateway': parts[1],
                        'interface': parts[7],
                        'status': 'active',
                    })
            return routes
        except:
            return []

    async def ping(self, host: str, count: int = 4) -> Dict:
        try:
            output = self._run_command(f"ping -c {count} -W 5 {host} 2>&1")
            lines = output.strip().split('\n')
            if 'packet loss' in lines[-2]:
                stats = lines[-2]
                import re
                loss_match = re.search(r'(\d+)% packet loss', stats)
                rtt_match = re.search(r'rtt min/avg/max/mdev = ([\d.]+)/([\d.]+)', output)
                loss = float(loss_match.group(1)) if loss_match else 100
                avg = float(rtt_match.group(2)) if rtt_match else 0
                return {
                    'host': host, 'sent': count,
                    'packet_loss': loss, 'avg_latency': avg,
                }
            return {'host': host, 'sent': count, 'received': 0, 'packet_loss': 100}
        except Exception as e:
            return {'host': host, 'error': str(e)}

    async def reboot(self) -> bool:
        try:
            self._run_command("reboot")
            return True
        except:
            return False

    async def get_cpu_load(self) -> float:
        try:
            output = self._run_command("cat /proc/loadavg")
            load = output.split()[1]
            return float(load) * 100
        except:
            return -1

    async def get_memory_usage(self) -> Dict:
        try:
            output = self._run_command("free -m")
            lines = output.strip().split('\n')
            parts = lines[1].split()
            total = float(parts[1])
            used = float(parts[2])
            free = float(parts[3])
            return {
                'total_mb': total,
                'used_mb': used,
                'free_mb': free,
                'usage_percent': round((used / total) * 100, 1) if total > 0 else 0,
            }
        except:
            return {}

    async def get_uptime(self) -> str:
        try:
            return self._run_command("uptime -p 2>/dev/null || uptime").strip()
        except:
            return 'غير متصل'

    async def add_dhcp_lease(self, mac: str, ip: str, hostname: str = "") -> bool:
        try:
            host_entry = f"host {hostname or mac.replace(':', '')} {{ hardware ethernet {mac}; fixed-address {ip}; }}"
            self._run_command(f"echo '{host_entry}' >> /etc/dnsmasq.conf")
            self._run_command("/etc/init.d/dnsmasq restart")
            return True
        except:
            return False

    async def set_bandwidth_limit(self, ip: str, download: str, upload: str) -> bool:
        try:
            # استخدام tc (traffic control)
            dl_rate = _bandwidth_to_bits(download)
            ul_rate = _bandwidth_to_bits(upload)
            self._run_command(f"tc qdisc add dev br-lan root handle 1: htb default 10")
            self._run_command(f"tc class add dev br-lan parent 1: classid 1:10 htb rate {dl_rate}bit")
            logger.info(f"تم تحديد سرعة {ip}")
            return True
        except:
            return False

    async def remove_bandwidth_limit(self, ip: str) -> bool:
        try:
            self._run_command("tc qdisc del dev br-lan root 2>/dev/null || true")
            return True
        except:
            return False


# === دوال مساعدة ===

# قاعدة بيانات OUI مبسطة
OUI_DATABASE = {
    'DC-A6-32': 'Apple',
    'AC-DE-48': 'Apple',
    '3C-22-FB': 'Apple',
    'A4-83-E7': 'Apple',
    '00-1A-2B': 'Apple',
    'F0-18-98': 'Apple',
    '78-CA-39': 'Samsung',
    'A0-CB-FD': 'Samsung',
    'B4-7B-44': 'Samsung',
    'D8-A2-5E': 'Samsung',
    '50-2E-5C': 'Samsung',
    'E8-50-8B': 'Samsung',
    'B8-27-EB': 'Raspberry Pi',
    'DC-A6-32': 'Raspberry Pi',
    'E4-5F-01': 'Raspberry Pi',
    '00-15-5D': 'Microsoft',
    '7C-ED-8D': 'Microsoft',
    '28-18-78': 'TP-Link',
    '60-32-B1': 'TP-Link',
    'F4-F2-6D': 'TP-Link',
    'EC-17-2F': 'TP-Link',
    'B0-4E-26': 'TP-Link',
    'A0-F3-C1': 'TP-Link',
    'C8-3A-35': 'TP-Link',
    'D4-6E-0E': 'Huawei',
    '48-5B-39': 'Huawei',
    '20-A6-CD': 'Huawei',
    '70-A8-D3': 'Huawei',
    'CC-96-A0': 'Huawei',
    'B0-5C-DA': 'Huawei',
    'FC-64-BA': 'Huawei',
    '6C-5B-3B': 'MikroTik',
    '4C-5E-0C': 'MikroTik',
    'D4-CA-6D': 'MikroTik',
    'E4-8D-8C': 'MikroTik',
    '00-0C-42': 'MikroTik',
    '00-26-93': 'Intel',
    'F8-0B-CB': 'Intel',
    '70-85-C2': 'Intel',
    '3C-97-0E': 'Intel',
    'B4-D5-BD': 'Intel',
    '00-1E-0B': 'Dell',
    'F8-BC-12': 'Dell',
    'B8-AC-6F': 'Dell',
    '00-14-22': 'Dell',
    '54-BF-64': 'Dell',
    '2C-F0-5D': 'Google',
    '3C-5A-37': 'Google',
    '54-60-09': 'Google',
    'A4-77-33': 'Google',
    'FA-8F-CA': 'Google',
    '94-B8-6B': 'Amazon',
    '40-B4-CD': 'Amazon',
    'F0-27-2D': 'Amazon',
    '7C-64-56': 'Amazon',
    'A0-02-DC': 'Amazon',
    'AC-63-BE': 'Xiaomi',
    '78-11-DC': 'Xiaomi',
    '9C-99-A0': 'Xiaomi',
    '0C-1D-AF': 'Xiaomi',
    '64-B4-73': 'Xiaomi',
    'D0-62-14': 'Cisco',
    '00-1B-54': 'Cisco',
    '5C-5A-C7': 'Cisco',
    'F8-66-F2': 'Cisco',
    '70-81-05': 'Cisco',
    'B0-9F-BA': 'Netgear',
    '60-38-E0': 'Netgear',
    '9C-3D-CF': 'Netgear',
    '00-26-F2': 'Netgear',
    'A0-21-B7': 'Netgear',
    'C0-3F-0E': 'Ubiquiti',
    'FC-EC-DA': 'Ubiquiti',
    '24-A4-3C': 'Ubiquiti',
    'F0-9F-C2': 'Ubiquiti',
    '80-2A-A8': 'Ubiquiti',
    '04-18-D6': 'Ubiquiti',
    '00-0C-29': 'VMware',
    '00-50-56': 'VMware',
    '00-05-69': 'VMware',
    'D8-C7-C8': 'OPPO',
    '5C-C5-D4': 'OPPO',
    '20-47-DA': 'OPPO',
    '14-A9-E3': 'OPPO',
    'E8-61-7E': 'OPPO',
    '94-87-4F': 'OPPO',
    '4C-11-BF': 'Honor',
    '28-CD-78': 'Honor',
    '50-1F-A5': 'Honor',
    'F0-D7-AA': 'Honor',
    '48-F1-7F': 'Honor',
    '1C-B0-94': 'OnePlus',
    '64-A2-F9': 'OnePlus',
    'A4-50-46': 'OnePlus',
    '34-2F-BE': 'OnePlus',
    '6C-D6-77': 'LG',
    'A8-16-B2': 'LG',
    'F0-6E-0B': 'LG',
    '00-1E-75': 'LG',
    'BC-0F-9A': 'LG',
    'A8-1B-5A': 'Sony',
    'B4-52-A7': 'Sony',
    '00-1B-24': 'Sony',
    '5C-96-56': 'Sony',
    'DC-2B-2A': 'Sony',
}


def _get_vendor_from_oui(oui: str) -> str:
    """معرفة الشركة المصنعة من OUI"""
    oui_upper = oui.upper()
    return OUI_DATABASE.get(oui_upper, 'غير معروف')


def _bandwidth_to_bits(bw_str: str) -> int:
    """تحويل سلسلة الباندويث إلى بت (مثل '10M' -> 10000000)"""
    bw_str = bw_str.strip().upper()
    if bw_str.endswith('G'):
        return int(float(bw_str[:-1]) * 1_000_000_000)
    elif bw_str.endswith('M'):
        return int(float(bw_str[:-1]) * 1_000_000)
    elif bw_str.endswith('K'):
        return int(float(bw_str[:-1]) * 1_000)
    return int(bw_str)


def create_router() -> RouterBase:
    """إنشاء كائن الراوتر المناسب حسب الإعدادات"""
    if config.ROUTER_TYPE.lower() == 'mikrotik':
        return MikroTikRouter()
    elif config.ROUTER_TYPE.lower() == 'openwrt':
        return OpenWrTRouter()
    else:
        raise ValueError(f"نوع الراوتر غير مدعوم: {config.ROUTER_TYPE}")
