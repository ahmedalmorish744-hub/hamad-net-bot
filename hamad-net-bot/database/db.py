"""
قاعدة البيانات - Database Layer
إدارة أجهزة الشبكة، السجلات، التنبيهات، والمحطات
"""
import aiosqlite
import json
import time
from datetime import datetime
from typing import Optional, List, Dict, Any


DB_SCHEMA = """
CREATE TABLE IF NOT EXISTS devices (
    mac TEXT PRIMARY KEY,
    ip TEXT,
    hostname TEXT,
    interface TEXT,
    vendor TEXT,
    first_seen REAL,
    last_seen REAL,
    is_online INTEGER DEFAULT 1,
    is_known INTEGER DEFAULT 0,
    is_blocked INTEGER DEFAULT 0,
    speed_limit TEXT DEFAULT '',
    notes TEXT DEFAULT '',
    group_name TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp REAL,
    alert_type TEXT,
    severity TEXT DEFAULT 'info',
    message TEXT,
    device_mac TEXT,
    is_read INTEGER DEFAULT 0,
    details TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS internet_status (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp REAL,
    is_up INTEGER,
    latency_ms REAL,
    wan_ip TEXT,
    reason TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS traffic_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp REAL,
    device_mac TEXT,
    download_bytes INTEGER DEFAULT 0,
    upload_bytes INTEGER DEFAULT 0,
    session_duration INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS intrusion_attempts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp REAL,
    source_ip TEXT,
    target_port INTEGER,
    protocol TEXT,
    attack_type TEXT,
    details TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS topology_changes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp REAL,
    change_type TEXT,
    device_mac TEXT,
    description TEXT,
    details TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS router_errors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp REAL,
    error_type TEXT,
    message TEXT,
    severity TEXT DEFAULT 'warning',
    resolved INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS blocked_attempts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp REAL,
    device_mac TEXT,
    device_ip TEXT,
    attempt_type TEXT,
    details TEXT DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_devices_online ON devices(is_online);
CREATE INDEX IF NOT EXISTS idx_alerts_type ON alerts(alert_type);
CREATE INDEX IF NOT EXISTS idx_alerts_timestamp ON alerts(timestamp);
CREATE INDEX IF NOT EXISTS idx_intrusion_timestamp ON intrusion_attempts(timestamp);
CREATE INDEX IF NOT EXISTS idx_internet_timestamp ON internet_status(timestamp);
"""


async def init_db(db_path: str):
    """تهيئة قاعدة البيانات وإنشاء الجداول"""
    async with aiosqlite.connect(db_path) as db:
        await db.executescript(DB_SCHEMA)
        await db.commit()


class Database:
    def __init__(self, db_path: str):
        self.db_path = db_path

    async def _get_conn(self):
        return await aiosqlite.connect(self.db_path)

    # ===== إدارة الأجهزة =====

    async def upsert_device(self, mac: str, ip: str, hostname: str = "",
                            interface: str = "", vendor: str = ""):
        """إضافة أو تحديث جهاز"""
        now = time.time()
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT INTO devices (mac, ip, hostname, interface, vendor, first_seen, last_seen, is_online)
                VALUES (?, ?, ?, ?, ?, ?, ?, 1)
                ON CONFLICT(mac) DO UPDATE SET
                    ip=excluded.ip,
                    hostname=COALESCE(NULLIF(excluded.hostname, ''), devices.hostname),
                    interface=COALESCE(NULLIF(excluded.interface, ''), devices.interface),
                    vendor=COALESCE(NULLIF(excluded.vendor, ''), devices.vendor),
                    last_seen=excluded.last_seen,
                    is_online=1
            """, (mac, ip, hostname, interface, vendor, now, now))
            await db.commit()

    async def set_device_offline(self, mac: str):
        """تحديد جهاز كغير متصل"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("UPDATE devices SET is_online=0 WHERE mac=?", (mac,))
            await db.commit()

    async def get_all_devices(self) -> List[Dict]:
        """جلب كل الأجهزة"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM devices ORDER BY is_online DESC, last_seen DESC") as cur:
                rows = await cur.fetchall()
                return [dict(r) for r in rows]

    async def get_online_devices(self) -> List[Dict]:
        """جلب الأجهزة المتصلة"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM devices WHERE is_online=1 ORDER BY last_seen DESC") as cur:
                rows = await cur.fetchall()
                return [dict(r) for r in rows]

    async def get_device_by_mac(self, mac: str) -> Optional[Dict]:
        """البحث عن جهاز بعنوان MAC"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM devices WHERE mac=?", (mac,)) as cur:
                row = await cur.fetchone()
                return dict(row) if row else None

    async def get_device_by_ip(self, ip: str) -> Optional[Dict]:
        """البحث عن جهاز بعنوان IP"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM devices WHERE ip=?", (ip,)) as cur:
                row = await cur.fetchone()
                return dict(row) if row else None

    async def block_device(self, mac: str) -> bool:
        """حظر جهاز"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("UPDATE devices SET is_blocked=1 WHERE mac=?", (mac,))
            await db.commit()
            return True

    async def unblock_device(self, mac: str) -> bool:
        """إلغاء حظر جهاز"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("UPDATE devices SET is_blocked=0 WHERE mac=?", (mac,))
            await db.commit()
            return True

    async def mark_device_known(self, mac: str, notes: str = ""):
        """وضع علامة على جهاز كمعروف"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("UPDATE devices SET is_known=1, notes=? WHERE mac=?", (notes, mac))
            await db.commit()

    async def set_speed_limit(self, mac: str, limit: str):
        """تحديد سرعة جهاز"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("UPDATE devices SET speed_limit=? WHERE mac=?", (limit, mac))
            await db.commit()

    async def get_unknown_devices(self) -> List[Dict]:
        """جلب الأجهزة غير المعروفة"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM devices WHERE is_known=0 AND is_online=1 ORDER BY last_seen DESC"
            ) as cur:
                rows = await cur.fetchall()
                return [dict(r) for r in rows]

    async def get_blocked_devices(self) -> List[Dict]:
        """جلب الأجهزة المحظورة"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM devices WHERE is_blocked=1") as cur:
                rows = await cur.fetchall()
                return [dict(r) for r in rows]

    # ===== التنبيهات =====

    async def add_alert(self, alert_type: str, message: str, severity: str = "info",
                        device_mac: str = "", details: str = ""):
        """إضافة تنبيه جديد"""
        now = time.time()
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT INTO alerts (timestamp, alert_type, severity, message, device_mac, details)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (now, alert_type, severity, message, device_mac, details))
            await db.commit()

    async def get_recent_alerts(self, limit: int = 20, unread_only: bool = False) -> List[Dict]:
        """جلب التنبيهات الأخيرة"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            query = "SELECT * FROM alerts"
            if unread_only:
                query += " WHERE is_read=0"
            query += " ORDER BY timestamp DESC LIMIT ?"
            async with db.execute(query, (limit,)) as cur:
                rows = await cur.fetchall()
                return [dict(r) for r in rows]

    async def mark_alerts_read(self):
        """تحديد كل التنبيهات كمقروءة"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("UPDATE alerts SET is_read=1 WHERE is_read=0")
            await db.commit()

    async def get_unread_alerts_count(self) -> int:
        """عدد التنبيهات غير المقروءة"""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT COUNT(*) FROM alerts WHERE is_read=0") as cur:
                row = await cur.fetchone()
                return row[0] if row else 0

    # ===== حالة الإنترنت =====

    async def log_internet_status(self, is_up: bool, latency: float = 0,
                                   wan_ip: str = "", reason: str = ""):
        """تسجيل حالة الإنترنت"""
        now = time.time()
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT INTO internet_status (timestamp, is_up, latency_ms, wan_ip, reason)
                VALUES (?, ?, ?, ?, ?)
            """, (now, 1 if is_up else 0, latency, wan_ip, reason))
            await db.commit()

    async def get_last_internet_status(self) -> Optional[Dict]:
        """آخر حالة إنترنت مسجلة"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM internet_status ORDER BY timestamp DESC LIMIT 1"
            ) as cur:
                row = await cur.fetchone()
                return dict(row) if row else None

    async def get_internet_outages(self, hours: int = 24) -> List[Dict]:
        """جلب انقطاعات الإنترنت في آخر N ساعة"""
        since = time.time() - (hours * 3600)
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM internet_status WHERE is_up=0 AND timestamp>? ORDER BY timestamp DESC",
                (since,)
            ) as cur:
                rows = await cur.fetchall()
                return [dict(r) for r in rows]

    # ===== محاولات الاختراق =====

    async def log_intrusion(self, source_ip: str, target_port: int,
                            protocol: str, attack_type: str, details: str = ""):
        """تسجيل محاولة اختراق"""
        now = time.time()
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT INTO intrusion_attempts (timestamp, source_ip, target_port, protocol, attack_type, details)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (now, source_ip, target_port, protocol, attack_type, details))
            await db.commit()

    async def get_recent_intrusions(self, limit: int = 20) -> List[Dict]:
        """جلب محاولات الاختراق الأخيرة"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM intrusion_attempts ORDER BY timestamp DESC LIMIT ?"
            ) as cur:
                rows = await cur.fetchall()
                return [dict(r) for r in rows]

    # ===== تغييرات الطوبولوجيا =====

    async def log_topology_change(self, change_type: str, device_mac: str,
                                   description: str, details: str = ""):
        """تسجيل تغيير في طوبولوجيا الشبكة"""
        now = time.time()
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT INTO topology_changes (timestamp, change_type, device_mac, description, details)
                VALUES (?, ?, ?, ?, ?)
            """, (now, change_type, device_mac, description, details))
            await db.commit()

    async def get_recent_topology_changes(self, limit: int = 20) -> List[Dict]:
        """جلب تغييرات الطوبولوجيا الأخيرة"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM topology_changes ORDER BY timestamp DESC LIMIT ?"
            ) as cur:
                rows = await cur.fetchall()
                return [dict(r) for r in rows]

    # ===== أخطاء الراوتر =====

    async def log_router_error(self, error_type: str, message: str,
                               severity: str = "warning"):
        """تسجيل خطأ في الراوتر"""
        now = time.time()
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT INTO router_errors (timestamp, error_type, message, severity)
                VALUES (?, ?, ?, ?)
            """, (now, error_type, message, severity))
            await db.commit()

    async def get_recent_errors(self, limit: int = 20, unresolved_only: bool = False) -> List[Dict]:
        """جلب الأخطاء الأخيرة"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            query = "SELECT * FROM router_errors"
            if unresolved_only:
                query += " WHERE resolved=0"
            query += " ORDER BY timestamp DESC LIMIT ?"
            async with db.execute(query, (limit,)) as cur:
                rows = await cur.fetchall()
                return [dict(r) for r in rows]

    async def resolve_error(self, error_id: int):
        """تحديد خطأ كمحلول"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("UPDATE router_errors SET resolved=1 WHERE id=?", (error_id,))
            await db.commit()

    async def resolve_all_errors(self):
        """تحديد كل الأخطاء كمحلولة"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("UPDATE router_errors SET resolved=1 WHERE resolved=0")
            await db.commit()

    # ===== إحصائيات =====

    async def get_network_stats(self) -> Dict[str, Any]:
        """إحصائيات الشبكة العامة"""
        async with aiosqlite.connect(self.db_path) as db:
            stats = {}
            async with db.execute("SELECT COUNT(*) FROM devices WHERE is_online=1") as cur:
                row = await cur.fetchone()
                stats["online_devices"] = row[0] if row else 0

            async with db.execute("SELECT COUNT(*) FROM devices WHERE is_online=0") as cur:
                row = await cur.fetchone()
                stats["offline_devices"] = row[0] if row else 0

            async with db.execute("SELECT COUNT(*) FROM devices WHERE is_known=0 AND is_online=1") as cur:
                row = await cur.fetchone()
                stats["unknown_devices"] = row[0] if row else 0

            async with db.execute("SELECT COUNT(*) FROM devices WHERE is_blocked=1") as cur:
                row = await cur.fetchone()
                stats["blocked_devices"] = row[0] if row else 0

            async with db.execute("SELECT COUNT(*) FROM alerts WHERE is_read=0") as cur:
                row = await cur.fetchone()
                stats["unread_alerts"] = row[0] if row else 0

            async with db.execute("SELECT COUNT(*) FROM intrusion_attempts WHERE timestamp>? ",
                                  (time.time() - 86400,)) as cur:
                row = await cur.fetchone()
                stats["intrusions_24h"] = row[0] if row else 0

            async with db.execute("SELECT COUNT(*) FROM router_errors WHERE resolved=0") as cur:
                row = await cur.fetchone()
                stats["unresolved_errors"] = row[0] if row else 0

            return stats
