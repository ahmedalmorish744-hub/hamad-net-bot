"""
وحدة مراقبة الإنترنت - Internet Monitor Module
لكشف انقطاعات الإنترنت وتشخيص الأسباب
"""
import asyncio
import subprocess
import re
import logging
from typing import Dict, List, Optional
from datetime import datetime

import config
from utils.database import Database

logger = logging.getLogger(__name__)

# عناوين اختبار الاتصال
PING_TARGETS = {
    'google': '8.8.8.8',
    'cloudflare': '1.1.1.1',
    'gateway': config.NETWORK_GATEWAY,
}

# عناوين DNS للاختبار
DNS_TARGETS = {
    'google_dns': '8.8.8.8',
    'cloudflare_dns': '1.1.1.1',
}

# عناوين HTTP للاختبار
HTTP_TARGETS = [
    'https://www.google.com',
    'https://www.cloudflare.com',
    'https://www.youtube.com',
]


class InternetMonitor:
    """مراقبة اتصال الإنترنت وكشف الانقطاعات"""

    def __init__(self, db: Database, router=None):
        self.db = db
        self.router = router
        self.is_online = True
        self.current_outage_id: Optional[int] = None
        self.outage_start_time: Optional[datetime] = None
        self.consecutive_failures = 0
        self.last_check_time: Optional[datetime] = None
        self.last_latency: Dict[str, float] = {}
        self.previous_interface_stats: Dict[str, Dict] = {}

    async def check_internet(self) -> Dict:
        """فحص شامل لاتصال الإنترنت"""
        results = {
            'online': False,
            'latency': {},
            'dns_working': False,
            'http_working': False,
            'gateway_reachable': False,
            'wan_interface_up': False,
            'outage_detected': False,
            'outage_end': False,
            'diagnosis': '',
        }

        # 1. فحص Gateway
        gw_result = await self._ping(PING_TARGETS['gateway'])
        results['gateway_reachable'] = gw_result.get('success', False)
        results['latency']['gateway'] = gw_result.get('latency', -1)

        # 2. فحص الإنترنت (Ping)
        internet_reachable = False
        for name, target in PING_TARGETS.items():
            if name == 'gateway':
                continue
            result = await self._ping(target)
            results['latency'][name] = result.get('latency', -1)
            if result.get('success', False):
                internet_reachable = True

        results['online'] = internet_reachable

        # 3. فحص DNS
        dns_result = await self._check_dns()
        results['dns_working'] = dns_result

        # 4. فحص HTTP
        http_result = await self._check_http()
        results['http_working'] = http_result

        # 5. فحص واجهة WAN
        wan_result = await self._check_wan_interface()
        results['wan_interface_up'] = wan_result

        # 6. تشخيص الانقطاع
        if not internet_reachable:
            self.consecutive_failures += 1
            
            if self.consecutive_failures >= 3 and not self.current_outage_id:
                # بدء انقطاع جديد
                results['outage_detected'] = True
                self.outage_start_time = datetime.now()
                
                diagnosis = self._diagnose_outage(results)
                affected_area = self._determine_affected_area(results)
                
                self.current_outage_id = self.db.log_outage_start(
                    outage_type=diagnosis['type'],
                    affected_area=affected_area,
                )
                results['diagnosis'] = diagnosis['description']
                results['outage_type'] = diagnosis['type']

                # تسجيل تنبيه
                self.db.add_security_alert(
                    alert_type='internet_outage',
                    severity='critical',
                    description=f"انقطاع الإنترنت: {diagnosis['description']}",
                )
            elif self.current_outage_id:
                results['outage_detected'] = True
                results['diagnosis'] = 'الانقطاع مستمر'

        else:
            if self.consecutive_failures > 0:
                self.consecutive_failures = 0

            if self.current_outage_id:
                # انتهاء الانقطاع
                results['outage_end'] = True
                duration = (datetime.now() - self.outage_start_time).total_seconds()
                
                diagnosis = self._diagnose_outage(results)
                self.db.log_outage_end(
                    self.current_outage_id,
                    root_cause=diagnosis.get('type', 'unknown'),
                )
                
                results['outage_duration'] = duration
                results['diagnosis'] = f"تم استعادة الاتصال بعد {self._format_duration(duration)}"

                self.current_outage_id = None
                self.outage_start_time = None

        self.is_online = internet_reachable
        self.last_check_time = datetime.now()
        self.last_latency = results['latency']

        return results

    async def _ping(self, host: str, count: int = 3) -> Dict:
        """اختبار Ping"""
        try:
            result = subprocess.run(
                ['ping', '-c', str(count), '-W', '3', host],
                capture_output=True, text=True, timeout=15
            )

            if result.returncode == 0:
                # استخراج متوسط التأخير
                rtt_match = re.search(r'rtt min/avg/max/mdev = [\d.]+/([\d.]+)', result.stdout)
                latency = float(rtt_match.group(1)) if rtt_match else 0
                return {'success': True, 'latency': latency, 'host': host}
            else:
                return {'success': False, 'latency': -1, 'host': host}
        except Exception as e:
            return {'success': False, 'latency': -1, 'host': host, 'error': str(e)}

    async def _check_dns(self) -> bool:
        """فحص عمل DNS"""
        try:
            result = subprocess.run(
                ['nslookup', 'google.com', '8.8.8.8'],
                capture_output=True, text=True, timeout=10
            )
            return result.returncode == 0 and 'Address' in result.stdout
        except:
            return False

    async def _check_http(self) -> bool:
        """فحص عمل HTTP/HTTPS"""
        try:
            import urllib.request
            for url in HTTP_TARGETS[:1]:
                try:
                    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
                    urllib.request.urlopen(req, timeout=5)
                    return True
                except:
                    continue
            return False
        except:
            return False

    async def _check_wan_interface(self) -> bool:
        """فحص واجهة WAN"""
        if not self.router:
            return True  # لا يمكن الفحص بدون راوتر

        try:
            interfaces = await self.router.get_interfaces()
            for iface in interfaces:
                name = iface.get('name', '').lower()
                if name in ['wan', 'ether1', 'eth0', 'pppoe-out', 'lte']:
                    return iface.get('running', False) and iface.get('enabled', False)
            return True  # لم يتم التعرف على واجهة WAN
        except:
            return True

    def _diagnose_outage(self, results: Dict) -> Dict:
        """تشخيص سبب الانقطاع - مع وصف ثنائي اللغة"""
        gw_ok = results.get('gateway_reachable', False)
        dns_ok = results.get('dns_working', False)
        http_ok = results.get('http_working', False)
        wan_ok = results.get('wan_interface_up', True)

        if not gw_ok:
            return {
                'type': 'local_network',
                'description': 'انقطاع محلي: الراوتر/ال Gateway غير قابل للوصول - قد تكون مشكلة في الراوتر أو كابل الشبكة',
                'description_en': 'Local outage: Router/Gateway unreachable — possible router issue or network cable problem',
                'severity': 'critical',
            }
        elif not wan_ok:
            return {
                'type': 'wan_down',
                'description': 'واجهة WAN معطلة - انقطاع كابل الإنترنت أو مشكلة في مقدم الخدمة (ISP)',
                'description_en': 'WAN interface down — internet cable disconnected or ISP issue',
                'severity': 'critical',
            }
        elif not dns_ok and not http_ok:
            return {
                'type': 'internet_down',
                'description': 'لا يوجد اتصال إنترنت - مشكلة من مقدم الخدمة (ISP) أو Starlink',
                'description_en': 'No internet connection — ISP outage or Starlink disconnection',
                'severity': 'critical',
            }
        elif not dns_ok:
            return {
                'type': 'dns_issue',
                'description': 'مشكلة في DNS - الإنترنت يعمل لكن لا يمكن حل أسماء النطاقات',
                'description_en': 'DNS issue — internet works but domain names cannot be resolved',
                'severity': 'high',
            }
        elif not http_ok:
            return {
                'type': 'partial_outage',
                'description': 'اتصال جزئي - بعض الخدمات لا تعمل (قد يكون حجب أو مشكلة في بروكسي)',
                'description_en': 'Partial outage — some services unavailable (possible blocking or proxy issue)',
                'severity': 'medium',
            }
        elif results.get('latency', {}).get('google', -1) > 200:
            return {
                'type': 'high_latency',
                'description': 'اتصال بطيء جداً - تأخير مرتفع قد يكون بسبب ازدحام أو مشكلة في Starlink',
                'description_en': 'Very slow connection — high latency possibly due to congestion or Starlink issue',
                'severity': 'medium',
            }
        else:
            return {
                'type': 'unknown',
                'description': 'مشكلة غير محددة في الاتصال',
                'description_en': 'Unidentified connection issue',
                'severity': 'low',
            }

    def _determine_affected_area(self, results: Dict) -> str:
        """تحديد المنطقة المتأثرة - ثنائي اللغة"""
        if not results.get('gateway_reachable', False):
            return 'الشبكة المحلية بالكامل / Entire Local Network'
        elif not results.get('online', False):
            return 'جميع المستخدمين - لا إنترنت / All Users — No Internet'
        elif not results.get('dns_working', False):
            return 'جميع المستخدمين - DNS معطل / All Users — DNS Down'
        else:
            return 'بعض الخدمات / Some Services'

    async def get_bandwidth_stats(self) -> Dict:
        """جلب إحصائيات الباندويث"""
        stats = {
            'interfaces': [],
            'total_download': 0,
            'total_upload': 0,
            'top_users': [],
        }

        if not self.router:
            return stats

        try:
            interfaces = await self.router.get_interface_traffic()
            total_dl = 0
            total_ul = 0

            for iface in interfaces:
                rx = iface.get('rx_bytes', 0)
                tx = iface.get('tx_bytes', 0)
                
                # حساب السرعة من الفرق عن القياس السابق
                prev = self.previous_interface_stats.get(iface['name'], {})
                prev_rx = prev.get('rx_bytes', rx)
                prev_tx = prev.get('tx_bytes', tx)
                prev_time = prev.get('timestamp', datetime.now().isoformat())

                try:
                    time_diff = (datetime.now() - datetime.fromisoformat(prev_time)).total_seconds()
                except:
                    time_diff = config.BANDWIDTH_MONITOR_INTERVAL

                dl_speed = (rx - prev_rx) / time_diff if time_diff > 0 else 0
                ul_speed = (tx - prev_tx) / time_diff if time_diff > 0 else 0

                stats['interfaces'].append({
                    'name': iface['name'],
                    'type': iface.get('type', ''),
                    'download_bytes': rx,
                    'upload_bytes': tx,
                    'download_speed': dl_speed,
                    'upload_speed': ul_speed,
                    'download_speed_formatted': self._format_speed(dl_speed),
                    'upload_speed_formatted': self._format_speed(ul_speed),
                })

                total_dl += rx
                total_ul += tx

                # تحديث القياس السابق
                self.previous_interface_stats[iface['name']] = {
                    'rx_bytes': rx,
                    'tx_bytes': tx,
                    'timestamp': datetime.now().isoformat(),
                }

            stats['total_download'] = total_dl
            stats['total_upload'] = total_ul
            stats['total_download_formatted'] = self._format_bytes(total_dl)
            stats['total_upload_formatted'] = self._format_bytes(total_ul)

        except Exception as e:
            logger.error(f"خطأ في جلب إحصائيات الباندويث: {e}")

        # أكبر مستخدمي الباندويث
        try:
            stats['top_users'] = self.db.get_top_bandwidth_users(hours=24, limit=5)
        except:
            pass

        return stats

    async def check_starlink(self) -> Dict:
        """فحص حالة Starlink (إذا كان مفعلاً)"""
        if not config.STARLINK_ENABLED:
            return {'enabled': False}

        result = {
            'enabled': True,
            'dishy_reachable': False,
            'latency': -1,
            'uptime': 'unknown',
            'obstruction': 'unknown',
        }

        try:
            # فحص Dishy
            ping_result = await self._ping(config.STARLINK_IP)
            result['dishy_reachable'] = ping_result.get('success', False)
            result['latency'] = ping_result.get('latency', -1)

            # محاولة جلب بيانات من gRPC (إذا كان grpcurl متوفراً)
            try:
                grpc_result = subprocess.run(
                    ['grpcurl', '-plaintext', '-max-time', '5',
                     f'{config.STARLINK_IP}:9200',
                     'SpaceX.API.Device.Device/Handle'],
                    capture_output=True, text=True, timeout=10
                )
                if grpc_result.returncode == 0:
                    import json
                    data = json.loads(grpc_result.stdout)
                    dish_status = data.get('dishGetStatus', {})
                    result['uptime'] = dish_status.get('deviceState', {}).get('uptimeSeconds', 'unknown')
                    result['obstruction'] = dish_status.get('obstructionStats', {}).get(
                        'fractionObstructed', 'unknown'
                    )
                    result['pop_latency'] = dish_status.get('popPingLatencyMs', 'unknown')
            except:
                pass

        except Exception as e:
            logger.error(f"خطأ في فحص Starlink: {e}")

        return result

    async def trace_route(self, host: str = '8.8.8.8') -> List[Dict]:
        """تتبع مسار الاتصال"""
        hops = []
        try:
            result = subprocess.run(
                ['traceroute', '-n', '-m', '15', '-w', '2', host],
                capture_output=True, text=True, timeout=60
            )
            for line in result.stdout.strip().split('\n')[1:]:
                parts = line.split()
                if len(parts) >= 4:
                    hop_num = int(parts[0]) if parts[0].isdigit() else 0
                    ip = parts[1] if parts[1] != '*' else ''
                    latency = parts[2].replace('ms', '') if 'ms' in parts[2] else ''
                    hops.append({
                        'hop': hop_num,
                        'ip': ip,
                        'latency': latency,
                        'raw': line.strip(),
                    })
        except FileNotFoundError:
            # استخدم Windows tracert كبديل
            try:
                result = subprocess.run(
                    ['tracert', '-d', '-h', '15', '-w', '2000', host],
                    capture_output=True, text=True, timeout=120
                )
                for line in result.stdout.strip().split('\n')[4:]:
                    if '<1 ms' in line or 'ms' in line:
                        hops.append({'raw': line.strip()})
            except:
                pass
        except Exception as e:
            logger.error(f"خطأ في تتبع المسار: {e}")

        return hops

    async def get_dns_info(self) -> Dict:
        """معلومات DNS"""
        result = {'servers': [], 'test': {}}

        if self.router and hasattr(self.router, 'api'):
            try:
                dns = self.router.api.get_resource('/ip/dns').get()
                if dns:
                    result['servers'] = dns[0].get('servers', '').split(',')
                    result['allow_remote'] = dns[0].get('allow-remote-requests') == 'true'
                    result['cache_size'] = dns[0].get('cache-size', '0')
                    result['cache_used'] = dns[0].get('cache-used', '0')
            except:
                pass

        # اختبار DNS
        for name, server in DNS_TARGETS.items():
            try:
                proc = subprocess.run(
                    ['nslookup', 'google.com', server],
                    capture_output=True, text=True, timeout=5
                )
                result['test'][name] = proc.returncode == 0
            except:
                result['test'][name] = False

        return result

    @staticmethod
    def _format_speed(bytes_per_sec: float) -> str:
        """تنسيق السرعة"""
        if bytes_per_sec < 0:
            return '0 b/s'
        elif bytes_per_sec < 1024:
            return f'{bytes_per_sec:.0f} b/s'
        elif bytes_per_sec < 1024 * 1024:
            return f'{bytes_per_sec / 1024:.1f} KB/s'
        elif bytes_per_sec < 1024 * 1024 * 1024:
            return f'{bytes_per_sec / 1024 / 1024:.1f} MB/s'
        else:
            return f'{bytes_per_sec / 1024 / 1024 / 1024:.2f} GB/s'

    @staticmethod
    def _format_bytes(num_bytes: int) -> str:
        """تنسيق حجم البيانات"""
        if num_bytes < 1024:
            return f'{num_bytes} B'
        elif num_bytes < 1024 * 1024:
            return f'{num_bytes / 1024:.1f} KB'
        elif num_bytes < 1024 * 1024 * 1024:
            return f'{num_bytes / 1024 / 1024:.1f} MB'
        else:
            return f'{num_bytes / 1024 / 1024 / 1024:.2f} GB'

    @staticmethod
    def _format_duration(seconds: float) -> str:
        """تنسيق المدة"""
        if seconds < 60:
            return f'{int(seconds)} ثانية'
        elif seconds < 3600:
            return f'{int(seconds / 60)} دقيقة'
        elif seconds < 86400:
            hours = int(seconds / 3600)
            minutes = int((seconds % 3600) / 60)
            return f'{hours} ساعة و {minutes} دقيقة'
        else:
            days = int(seconds / 86400)
            hours = int((seconds % 86400) / 3600)
            return f'{days} يوم و {hours} ساعة'
