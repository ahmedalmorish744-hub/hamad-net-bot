"""
قاعدة بيانات بوت حمد نت - Database Manager
"""
import sqlite3
import os
import json
from datetime import datetime
from typing import List, Dict, Optional, Any


class Database:
    """إدارة قاعدة بيانات SQLite للبوت"""

    def __init__(self, db_path: str = "data/hamad_net.db"):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.conn = None
        self._connect()
        self._create_tables()

    def _connect(self):
        """إنشاء اتصال بقاعدة البيانات"""
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA foreign_keys=ON")

    def _create_tables(self):
        """إنشاء جداول قاعدة البيانات"""
        cursor = self.conn.cursor()

        # جدول الأجهزة المعروفة
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS known_devices (
                mac_address TEXT PRIMARY KEY,
                ip_address TEXT,
                hostname TEXT,
                device_type TEXT DEFAULT 'unknown',
                vendor TEXT DEFAULT 'unknown',
                first_seen TEXT NOT NULL,
                last_seen TEXT NOT NULL,
                is_authorized INTEGER DEFAULT 1,
                is_online INTEGER DEFAULT 0,
                nickname TEXT,
                notes TEXT,
                blocked INTEGER DEFAULT 0
            )
        """)

        # جدول سجل الدخول والخروج
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS connection_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                mac_address TEXT NOT NULL,
                ip_address TEXT,
                event_type TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                details TEXT,
                FOREIGN KEY (mac_address) REFERENCES known_devices(mac_address)
            )
        """)

        # جدول تنبيهات الأمن
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS security_alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                alert_type TEXT NOT NULL,
                severity TEXT NOT NULL,
                source_ip TEXT,
                source_mac TEXT,
                description TEXT,
                timestamp TEXT NOT NULL,
                resolved INTEGER DEFAULT 0,
                resolved_by TEXT,
                resolved_at TEXT
            )
        """)

        # جدول سجل الانقطاعات
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS outage_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                outage_type TEXT NOT NULL,
                start_time TEXT NOT NULL,
                end_time TEXT,
                duration_seconds INTEGER,
                affected_area TEXT,
                root_cause TEXT,
                resolved INTEGER DEFAULT 0
            )
        """)

        # جدول تغييرات التهيئة
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS config_changes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                change_type TEXT NOT NULL,
                description TEXT,
                old_value TEXT,
                new_value TEXT,
                timestamp TEXT NOT NULL,
                detected_by TEXT DEFAULT 'bot'
            )
        """)

        # جدول استخدام الباندويث
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS bandwidth_usage (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                mac_address TEXT,
                ip_address TEXT,
                download_bytes INTEGER DEFAULT 0,
                upload_bytes INTEGER DEFAULT 0,
                download_speed REAL DEFAULT 0,
                upload_speed REAL DEFAULT 0,
                timestamp TEXT NOT NULL,
                FOREIGN KEY (mac_address) REFERENCES known_devices(mac_address)
            )
        """)

        # جدول أوامر البوت
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS bot_commands_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER,
                user_id INTEGER,
                username TEXT,
                command TEXT,
                arguments TEXT,
                timestamp TEXT NOT NULL,
                result TEXT
            )
        """)

        # جدول حالة الشبكة
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS network_status (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                status_type TEXT NOT NULL,
                value TEXT,
                timestamp TEXT NOT NULL
            )
        """)

        self.conn.commit()

    # === عمليات الأجهزة ===

    def add_or_update_device(self, mac: str, ip: str, hostname: str = "",
                              device_type: str = "unknown", vendor: str = "unknown") -> bool:
        """إضافة أو تحديث جهاز في قاعدة البيانات"""
        now = datetime.now().isoformat()
        cursor = self.conn.cursor()

        existing = cursor.execute(
            "SELECT mac_address FROM known_devices WHERE mac_address = ?", (mac,)
        ).fetchone()

        if existing:
            cursor.execute("""
                UPDATE known_devices 
                SET ip_address = ?, hostname = ?, last_seen = ?, is_online = 1,
                    device_type = COALESCE(?, device_type), vendor = COALESCE(?, vendor)
                WHERE mac_address = ?
            """, (ip, hostname, now, device_type, vendor, mac))
        else:
            cursor.execute("""
                INSERT INTO known_devices 
                (mac_address, ip_address, hostname, device_type, vendor, first_seen, last_seen, is_online, is_authorized)
                VALUES (?, ?, ?, ?, ?, ?, ?, 1, 0)
            """, (mac, ip, hostname, device_type, vendor, now, now))

        self.conn.commit()
        return not bool(existing)  # True إذا كان جهاز جديد

    def set_device_offline(self, mac: str):
        """تحديث حالة الجهاز إلى غير متصل"""
        now = datetime.now().isoformat()
        self.conn.execute(
            "UPDATE known_devices SET is_online = 0, last_seen = ? WHERE mac_address = ?",
            (now, mac)
        )
        self.conn.commit()

    def get_all_devices(self, online_only: bool = False) -> List[Dict]:
        """جلب جميع الأجهزة"""
        cursor = self.conn.cursor()
        if online_only:
            rows = cursor.execute(
                "SELECT * FROM known_devices WHERE is_online = 1 ORDER BY ip_address"
            ).fetchall()
        else:
            rows = cursor.execute(
                "SELECT * FROM known_devices ORDER BY is_online DESC, ip_address"
            ).fetchall()
        return [dict(row) for row in rows]

    def get_device_by_mac(self, mac: str) -> Optional[Dict]:
        """جلب جهاز بعنوان MAC"""
        row = self.conn.execute(
            "SELECT * FROM known_devices WHERE mac_address = ?", (mac,)
        ).fetchone()
        return dict(row) if row else None

    def authorize_device(self, mac: str, authorized: bool = True):
        """ترخيص أو إلغاء ترخيص جهاز"""
        self.conn.execute(
            "UPDATE known_devices SET is_authorized = ? WHERE mac_address = ?",
            (1 if authorized else 0, mac)
        )
        self.conn.commit()

    def block_device(self, mac: str, blocked: bool = True):
        """حظر أو إلغاء حظر جهاز"""
        self.conn.execute(
            "UPDATE known_devices SET blocked = ? WHERE mac_address = ?",
            (1 if blocked else 0, mac)
        )
        self.conn.commit()

    def set_device_nickname(self, mac: str, nickname: str):
        """تعيين اسم مستعار لجهاز"""
        self.conn.execute(
            "UPDATE known_devices SET nickname = ? WHERE mac_address = ?",
            (nickname, mac)
        )
        self.conn.commit()

    def get_online_count(self) -> int:
        """عدد الأجهزة المتصلة"""
        row = self.conn.execute(
            "SELECT COUNT(*) as count FROM known_devices WHERE is_online = 1"
        ).fetchone()
        return row["count"]

    def get_authorized_count(self) -> int:
        """عدد الأجهزة المرخصة"""
        row = self.conn.execute(
            "SELECT COUNT(*) as count FROM known_devices WHERE is_authorized = 1"
        ).fetchone()
        return row["count"]

    # === عمليات سجل الاتصال ===

    def log_connection_event(self, mac: str, ip: str, event_type: str, details: str = ""):
        """تسجيل حدث دخول أو خروج"""
        now = datetime.now().isoformat()
        self.conn.execute("""
            INSERT INTO connection_log (mac_address, ip_address, event_type, timestamp, details)
            VALUES (?, ?, ?, ?, ?)
        """, (mac, ip, event_type, now, details))
        self.conn.commit()

    def get_recent_connections(self, limit: int = 20) -> List[Dict]:
        """جلب آخر أحداث الاتصال"""
        rows = self.conn.execute("""
            SELECT cl.*, kd.nickname, kd.hostname 
            FROM connection_log cl
            LEFT JOIN known_devices kd ON cl.mac_address = kd.mac_address
            ORDER BY cl.timestamp DESC LIMIT ?
        """, (limit,)).fetchall()
        return [dict(row) for row in rows]

    # === عمليات التنبيهات الأمنية ===

    def add_security_alert(self, alert_type: str, severity: str,
                            source_ip: str = "", source_mac: str = "",
                            description: str = ""):
        """إضافة تنبيه أمني"""
        now = datetime.now().isoformat()
        self.conn.execute("""
            INSERT INTO security_alerts 
            (alert_type, severity, source_ip, source_mac, description, timestamp)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (alert_type, severity, source_ip, source_mac, description, now))
        self.conn.commit()

    def get_unresolved_alerts(self) -> List[Dict]:
        """جلب التنبيهات غير المعالجة"""
        rows = self.conn.execute("""
            SELECT * FROM security_alerts 
            WHERE resolved = 0 
            ORDER BY timestamp DESC
        """).fetchall()
        return [dict(row) for row in rows]

    def resolve_alert(self, alert_id: int, resolved_by: str = "admin"):
        """معالجة تنبيه"""
        now = datetime.now().isoformat()
        self.conn.execute("""
            UPDATE security_alerts 
            SET resolved = 1, resolved_by = ?, resolved_at = ?
            WHERE id = ?
        """, (resolved_by, now, alert_id))
        self.conn.commit()

    # === عمليات سجل الانقطاعات ===

    def log_outage_start(self, outage_type: str, affected_area: str = "") -> int:
        """تسجيل بداية انقطاع"""
        now = datetime.now().isoformat()
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO outage_log (outage_type, start_time, affected_area)
            VALUES (?, ?, ?)
        """, (outage_type, now, affected_area))
        self.conn.commit()
        return cursor.lastrowid

    def log_outage_end(self, outage_id: int, root_cause: str = ""):
        """تسجيل نهاية انقطاع"""
        now = datetime.now().isoformat()
        row = self.conn.execute(
            "SELECT start_time FROM outage_log WHERE id = ?", (outage_id,)
        ).fetchone()
        if row:
            start = datetime.fromisoformat(row["start_time"])
            end = datetime.fromisoformat(now)
            duration = int((end - start).total_seconds())
            self.conn.execute("""
                UPDATE outage_log 
                SET end_time = ?, duration_seconds = ?, root_cause = ?, resolved = 1
                WHERE id = ?
            """, (now, duration, root_cause, outage_id))
            self.conn.commit()

    def get_recent_outages(self, limit: int = 20) -> List[Dict]:
        """جلب آخر الانقطاعات"""
        rows = self.conn.execute("""
            SELECT * FROM outage_log ORDER BY start_time DESC LIMIT ?
        """, (limit,)).fetchall()
        return [dict(row) for row in rows]

    # === عمليات تغييرات التهيئة ===

    def log_config_change(self, change_type: str, description: str,
                           old_value: str = "", new_value: str = ""):
        """تسجيل تغيير في التهيئة"""
        now = datetime.now().isoformat()
        self.conn.execute("""
            INSERT INTO config_changes (change_type, description, old_value, new_value, timestamp)
            VALUES (?, ?, ?, ?, ?)
        """, (change_type, description, old_value, new_value, now))
        self.conn.commit()

    def get_recent_config_changes(self, limit: int = 20) -> List[Dict]:
        """جلب آخر التغييرات"""
        rows = self.conn.execute("""
            SELECT * FROM config_changes ORDER BY timestamp DESC LIMIT ?
        """, (limit,)).fetchall()
        return [dict(row) for row in rows]

    # === عمليات الباندويث ===

    def log_bandwidth(self, mac: str, ip: str, dl_bytes: int, ul_bytes: int,
                       dl_speed: float, ul_speed: float):
        """تسجيل استخدام الباندويث"""
        now = datetime.now().isoformat()
        self.conn.execute("""
            INSERT INTO bandwidth_usage 
            (mac_address, ip_address, download_bytes, upload_bytes, download_speed, upload_speed, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (mac, ip, dl_bytes, ul_bytes, dl_speed, ul_speed, now))
        self.conn.commit()

    def get_top_bandwidth_users(self, hours: int = 24, limit: int = 10) -> List[Dict]:
        """جلب أكبر مستخدمي الباندويث"""
        since = datetime.now().timestamp() * 1000 - (hours * 3600 * 1000)
        rows = self.conn.execute("""
            SELECT mac_address, ip_address,
                   SUM(download_bytes) as total_download,
                   SUM(upload_bytes) as total_upload,
                   AVG(download_speed) as avg_dl_speed,
                   AVG(upload_speed) as avg_ul_speed
            FROM bandwidth_usage
            WHERE timestamp >= datetime(?, 'unixepoch')
            GROUP BY mac_address
            ORDER BY total_download DESC
            LIMIT ?
        """, (since / 1000, limit)).fetchall()
        return [dict(row) for row in rows]

    # === عمليات حالة الشبكة ===

    def update_network_status(self, status_type: str, value: str):
        """تحديث حالة الشبكة"""
        now = datetime.now().isoformat()
        self.conn.execute("""
            INSERT INTO network_status (status_type, value, timestamp)
            VALUES (?, ?, ?)
        """, (status_type, value, now))
        self.conn.commit()

    def get_latest_status(self, status_type: str) -> Optional[Dict]:
        """جلب آخر حالة"""
        row = self.conn.execute("""
            SELECT * FROM network_status 
            WHERE status_type = ? 
            ORDER BY timestamp DESC LIMIT 1
        """, (status_type,)).fetchone()
        return dict(row) if row else None

    # === عمليات سجل الأوامر ===

    def log_command(self, chat_id: int, user_id: int, username: str,
                     command: str, arguments: str = "", result: str = ""):
        """تسجيل أمر البوت"""
        now = datetime.now().isoformat()
        self.conn.execute("""
            INSERT INTO bot_commands_log 
            (chat_id, user_id, username, command, arguments, timestamp, result)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (chat_id, user_id, username, command, arguments, now, result))
        self.conn.commit()

    # === عمليات الصيانة ===

    def cleanup_old_records(self, max_entries: int = 1000):
        """تنظيف السجلات القديمة"""
        for table in ['bandwidth_usage', 'connection_log', 'network_status', 'bot_commands_log']:
            self.conn.execute(f"""
                DELETE FROM {table} WHERE id NOT IN (
                    SELECT id FROM {table} ORDER BY id DESC LIMIT {max_entries}
                )
            """)
        self.conn.commit()

    def get_network_summary(self) -> Dict[str, Any]:
        """جلب ملخص الشبكة"""
        online = self.get_online_count()
        total = self.conn.execute("SELECT COUNT(*) as c FROM known_devices").fetchone()["c"]
        authorized = self.get_authorized_count()
        alerts = len(self.get_unresolved_alerts())
        recent_outages = len(self.get_recent_outages(5))

        return {
            "total_devices": total,
            "online_devices": online,
            "offline_devices": total - online,
            "authorized_devices": authorized,
            "unauthorized_devices": total - authorized,
            "unresolved_alerts": alerts,
            "recent_outages": recent_outages,
        }

    def close(self):
        """إغلاق الاتصال"""
        if self.conn:
            self.conn.close()
