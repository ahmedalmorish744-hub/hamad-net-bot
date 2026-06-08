"""
وحدة المراقبة الأمنية - Security Monitor Module
لكشف محاولات الاختراق والتهديدات
"""
import asyncio
import re
import logging
from typing import List, Dict, Optional
from datetime import datetime, timedelta

import config
from utils.database import Database

logger = logging.getLogger(__name__)


class SecurityMonitor:
    """مراقبة أمنية للشبكة"""

    def __init__(self, db: Database, router=None):
        self.db = db
        self.router = router
        self.known_failed_attempts: Dict[str, int] = {}
        self.port_scan_tracker: Dict[str, List[int]] = {}
        self.last_check_results: Dict = {}

    async def full_security_check(self) -> Dict:
        """فحص أمني شامل"""
        results = {
            'intrusion_attempts': [],
            'unauthorized_devices': [],
            'suspicious_activity': [],
            'firewall_issues': [],
            'vulnerabilities': [],
            'overall_status': 'secure',
        }

        # 1. كشف الأجهزة غير المرخصة
        unauthorized = await self._check_unauthorized_devices()
        results['unauthorized_devices'] = unauthorized

        # 2. كشف محاولات الاختراق
        intrusions = await self._check_intrusion_attempts()
        results['intrusion_attempts'] = intrusions

        # 3. كشف النشاط المشبوه
        suspicious = await self._check_suspicious_activity()
        results['suspicious_activity'] = suspicious

        # 4. فحص الجدار الناري
        firewall = await self._check_firewall()
        results['firewall_issues'] = firewall

        # 5. فحص الثغرات
        vulns = await self._check_vulnerabilities()
        results['vulnerabilities'] = vulns

        # تحديد الحالة العامة
        if intrusions or unauthorized:
            results['overall_status'] = 'danger'
        elif suspicious or firewall:
            results['overall_status'] = 'warning'
        elif vulns:
            results['overall_status'] = 'caution'

        self.last_check_results = results
        return results

    async def _check_unauthorized_devices(self) -> List[Dict]:
        """كشف الأجهزة غير المرخصة المتصلة"""
        unauthorized = []
        devices = self.db.get_all_devices(online_only=True)
        
        for device in devices:
            if not device.get('is_authorized', False) and not device.get('blocked', False):
                unauthorized.append({
                    'mac': device['mac_address'],
                    'ip': device['ip_address'],
                    'hostname': device.get('hostname', ''),
                    'nickname': device.get('nickname', ''),
                    'vendor': device.get('vendor', ''),
                    'device_type': device.get('device_type', ''),
                    'first_seen': device.get('first_seen', ''),
                    'severity': 'high',
                    'description': f"جهاز غير مرخص متصل: {device.get('nickname') or device.get('hostname') or device['mac_address']}",
                })

                # تسجيل تنبيه
                self.db.add_security_alert(
                    alert_type='unauthorized_device',
                    severity='high',
                    source_ip=device['ip_address'],
                    source_mac=device['mac_address'],
                    description=f"جهاز غير مرخص: {device.get('hostname', device['mac_address'])} ({device['ip_address']})",
                )

        return unauthorized

    async def _check_intrusion_attempts(self) -> List[Dict]:
        """كشف محاولات الاختراق من سجلات الراوتر"""
        attempts = []

        if not self.router:
            return attempts

        try:
            logs = await self.router.get_system_logs()
            
            # أنماط محاولات الاختراق - مع وصف ثنائي اللغة
            intrusion_patterns = [
                (r'login failure', 'brute_force', 'محاولة تسجيل دخول فاشلة', 'Failed login attempt'),
                (r'invalid password', 'brute_force', 'كلمة مرور خاطئة', 'Invalid password'),
                (r'authentication failure', 'brute_force', 'فشل المصادقة', 'Authentication failure'),
                (r'login attempt', 'brute_force', 'محاولة تسجيل دخول', 'Login attempt'),
                (r'port scan', 'port_scan', 'فحص منافذ', 'Port scan detected'),
                (r'denied', 'access_denied', 'وصول مرفوض', 'Access denied'),
                (r'firewall.*drop', 'firewall_drop', 'حظر جدار ناري', 'Firewall drop'),
                (r'connection.*refused', 'connection_refused', 'اتصال مرفوض', 'Connection refused'),
                (r'suspicious', 'suspicious', 'نشاط مشبوه', 'Suspicious activity'),
                (r'intrusion', 'intrusion', 'محاولة اختراق', 'Intrusion attempt'),
                (r'attack', 'attack', 'هجوم', 'Network attack'),
                (r'ddos', 'ddos', 'هجوم DDoS', 'DDoS attack'),
                (r'flood', 'flood', 'هجوم فيضاني', 'Flood attack'),
            ]

            for log in logs:
                message = log.get('message', '').lower()
                topics = log.get('topics', '').lower()
                
                for pattern, attack_type, desc_ar, desc_en in intrusion_patterns:
                    if re.search(pattern, message) or re.search(pattern, topics):
                        # استخراج IP المصدر
                        ip_match = re.search(r'(\d+\.\d+\.\d+\.\d+)', message)
                        source_ip = ip_match.group(1) if ip_match else ''
                        
                        mac_match = re.search(r'([0-9A-Fa-f]{2}:[0-9A-Fa-f]{2}:[0-9A-Fa-f]{2}:[0-9A-Fa-f]{2}:[0-9A-Fa-f]{2}:[0-9A-Fa-f]{2})', log.get('message', ''))
                        source_mac = mac_match.group(1).upper() if mac_match else ''

                        attempts.append({
                            'type': attack_type,
                            'source_ip': source_ip,
                            'source_mac': source_mac,
                            'description': desc_ar,
                            'description_en': desc_en,
                            'log_message': log.get('message', ''),
                            'timestamp': log.get('time', ''),
                            'severity': 'critical' if attack_type in ['intrusion', 'attack', 'ddos'] else 'high',
                        })

                        # تسجيل تنبيه
                        self.db.add_security_alert(
                            alert_type=attack_type,
                            severity='critical' if attack_type in ['intrusion', 'attack', 'ddos'] else 'high',
                            source_ip=source_ip,
                            source_mac=source_mac,
                            description=f"{desc_ar}: {log.get('message', '')[:200]}",
                        )

                        # حظر تلقائي إذا كان مفعلاً
                        if config.AUTO_BLOCK_INTRUSION and source_ip:
                            await self._auto_block(source_ip, source_mac, attack_type)

        except Exception as e:
            logger.error(f"خطأ في فحص محاولات الاختراق: {e}")

        return attempts

    async def _check_suspicious_activity(self) -> List[Dict]:
        """كشف النشاط المشبوه"""
        suspicious = []
        
        # 1. كشف استخدام باندويث غير عادي
        try:
            if self.router:
                traffic = await self.router.get_interface_traffic()
                for iface in traffic:
                    speed = iface.get('tx_speed', 0) + iface.get('rx_speed', 0)
                    if speed > config.HIGH_BANDWIDTH_THRESHOLD * 1_000_000:
                        suspicious.append({
                            'type': 'high_bandwidth',
                            'description': f"استخدام باندويث مرتفع على {iface['name']}: {speed / 1_000_000:.1f} Mbps",
                            'severity': 'medium',
                            'interface': iface['name'],
                        })
        except:
            pass

        # 2. كشف أجهزة تتصل في أوقات غير عادية
        recent = self.db.get_recent_connections(50)
        for conn in recent:
            if conn.get('event_type') == 'connect':
                try:
                    ts = datetime.fromisoformat(conn['timestamp'])
                    # إذا كان اتصال بين 2-5 صباحاً قد يكون مشبوهاً
                    if 2 <= ts.hour <= 5:
                        device = self.db.get_device_by_mac(conn['mac_address'])
                        if device and not device.get('is_authorized', False):
                            suspicious.append({
                                'type': 'unusual_time',
                                'description': f"اتصال في وقت غير عادي: {device.get('nickname') or conn['mac_address']} في {ts.strftime('%H:%M')}",
                                'severity': 'low',
                                'mac': conn['mac_address'],
                            })
                except:
                    pass

        # 3. كشف تغييرات MAC (MAC Spoofing)
        devices = self.db.get_all_devices(online_only=True)
        ip_to_mac = {}
        for d in devices:
            ip = d['ip_address']
            if ip in ip_to_mac and ip_to_mac[ip] != d['mac_address']:
                suspicious.append({
                    'type': 'mac_spoofing',
                    'description': f"تغيير MAC لنفس IP {ip}: {ip_to_mac[ip]} → {d['mac_address']}",
                    'severity': 'critical',
                    'ip': ip,
                })
                self.db.add_security_alert(
                    alert_type='mac_spoofing',
                    severity='critical',
                    source_ip=ip,
                    description=f"MAC Spoofing محتمل: {ip_to_mac[ip]} → {d['mac_address']}",
                )
            ip_to_mac[ip] = d['mac_address']

        return suspicious

    async def _check_firewall(self) -> List[Dict]:
        """فحص حالة الجدار الناري"""
        issues = []

        if not self.router:
            return issues

        try:
            rules = await self.router.get_firewall_rules()
            
            # فحص وجود قواعد حماية أساسية
            has_drop_rule = False
            has_input_filter = False

            for rule in rules:
                if rule.get('action') == 'drop' and rule.get('chain') == 'forward':
                    has_drop_rule = True
                if rule.get('chain') == 'input' and rule.get('action') in ['drop', 'reject']:
                    has_input_filter = True

            if not has_drop_rule:
                issues.append({
                    'type': 'no_drop_rule',
                    'description': 'لا توجد قاعدة حظر في Forward Chain - الشبكة معرضة للوصول غير المصرح',
                    'severity': 'high',
                })

            if not has_input_filter:
                issues.append({
                    'type': 'no_input_filter',
                    'description': 'لا يوجد تصفية على Input Chain - الراوتر معرض للوصول المباشر',
                    'severity': 'medium',
                })

        except Exception as e:
            logger.error(f"خطأ في فحص الجدار الناري: {e}")

        return issues

    async def _check_vulnerabilities(self) -> List[Dict]:
        """فحص الثغرات الأمنية"""
        vulns = []

        if not self.router:
            return vulns

        try:
            # 1. فحص منافذ الراوتر المفتوحة
            info = await self.router.get_system_info()
            
            # فحص إذا كان Winbox مفتوحاً للعالم
            if self.router and hasattr(self.router, 'api'):
                try:
                    ip_services = self.router.api.get_resource('/ip/service').get()
                    for svc in ip_services:
                        if svc.get('name') in ['winbox', 'api', 'telnet', 'ftp']:
                            address = svc.get('address', '0.0.0.0/0')
                            if address == '0.0.0.0/0':
                                vulns.append({
                                    'type': 'open_service',
                                    'description': f"خدمة {svc['name']} مفتوحة للعالم الخارجي! يُنصح بتقييد الوصول",
                                    'severity': 'high',
                                    'service': svc['name'],
                                    'port': svc.get('port', ''),
                                })
                                self.db.add_security_alert(
                                    alert_type='open_service',
                                    severity='high',
                                    description=f"خدمة {svc['name']} مفتوحة بدون تقييد (المنفذ {svc.get('port', '')})",
                                )
                        if svc.get('name') == 'www' and svc.get('disabled') != 'true':
                            address = svc.get('address', '0.0.0.0/0')
                            if address == '0.0.0.0/0':
                                vulns.append({
                                    'type': 'open_web',
                                    'description': "واجهة الويب مفتوحة للعالم الخارجي",
                                    'severity': 'medium',
                                })
                except:
                    pass

            # 2. فحص DNS
            try:
                dns = self.router.api.get_resource('/ip/dns').get()
                if dns and dns[0].get('allow-remote-requests') == 'true':
                    vulns.append({
                        'type': 'dns_open',
                        'description': "DNS يسمح بالطلبات البعيدة - يمكن استغلاله في هجمات DNS Amplification",
                        'severity': 'critical',
                    })
                    self.db.add_security_alert(
                        alert_type='dns_open',
                        severity='critical',
                        description="DNS مفتوح للطلبات البعيدة - خطر هجوم DNS Amplification",
                    )
            except:
                pass

        except Exception as e:
            logger.error(f"خطأ في فحص الثغرات: {e}")

        return vulns

    async def _auto_block(self, ip: str, mac: str, attack_type: str):
        """حظر تلقائي للتهديدات"""
        if not self.router:
            return

        try:
            comment = f"حظر تلقائي - {attack_type} - بوت حمد نت"
            
            # حظر في الجدار الناري
            if mac:
                await self.router.block_device(mac, comment)
            elif ip:
                # حظر IP
                if hasattr(self.router, 'api'):
                    self.router.api.get_resource('/ip/firewall/filter').add(
                        chain='input',
                        src_address=ip,
                        action='drop',
                        comment=comment
                    )

            # تسجيل الحظر
            self.db.add_security_alert(
                alert_type='auto_block',
                severity='info',
                source_ip=ip,
                source_mac=mac,
                description=f"تم الحظر التلقائي: {mac or ip} بسبب {attack_type}",
            )
            logger.info(f"تم الحظر التلقائي: {mac or ip}")

        except Exception as e:
            logger.error(f"خطأ في الحظر التلقائي: {e}")

    async def get_security_summary(self) -> Dict:
        """ملخص الحالة الأمنية"""
        unresolved = self.db.get_unresolved_alerts()
        
        by_severity = {'critical': 0, 'high': 0, 'medium': 0, 'low': 0, 'info': 0}
        by_type = {}
        
        for alert in unresolved:
            sev = alert.get('severity', 'info')
            by_severity[sev] = by_severity.get(sev, 0) + 1
            atype = alert.get('alert_type', 'unknown')
            by_type[atype] = by_type.get(atype, 0) + 1

        return {
            'total_alerts': len(unresolved),
            'by_severity': by_severity,
            'by_type': by_type,
            'status': self._calculate_security_status(by_severity),
            'last_check': datetime.now().isoformat(),
        }

    def _calculate_security_status(self, by_severity: Dict) -> str:
        """حساب حالة الأمان"""
        if by_severity.get('critical', 0) > 0:
            return '🔴 حرج'
        elif by_severity.get('high', 0) > 0:
            return '🟠 خطر'
        elif by_severity.get('medium', 0) > 0:
            return '🟡 تحذير'
        elif by_severity.get('low', 0) > 0:
            return '🔵 انتباه'
        else:
            return '🟢 آمن'

    async def block_device(self, mac: str) -> bool:
        """حظر جهاز"""
        if self.router:
            success = await self.router.block_device(mac)
            if success:
                self.db.block_device(mac, True)
            return success
        return False

    async def unblock_device(self, mac: str) -> bool:
        """إلغاء حظر جهاز"""
        if self.router:
            success = await self.router.unblock_device(mac)
            if success:
                self.db.block_device(mac, False)
            return success
        return False
