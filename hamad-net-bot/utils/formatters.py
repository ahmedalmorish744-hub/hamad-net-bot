"""
مُنسق الرسائل - Message Formatters
تنسيق الرسائل المرسلة عبر البوت
"""
import time
from datetime import datetime
from typing import Dict, List, Optional


def format_timestamp(ts: float) -> str:
    """تنسيق الطابع الزمني"""
    if not ts:
        return "غير متوفر"
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")


def format_uptime(uptime_str: str) -> str:
    """تنسيق وقت التشغيل"""
    if not uptime_str:
        return "غير متوفر"
    # RouterOS format: "15d7h32m15s"
    parts = []
    if "d" in uptime_str:
        parts.append(uptime_str.split("d")[0] + " يوم")
        uptime_str = uptime_str.split("d")[1]
    if "h" in uptime_str:
        parts.append(uptime_str.split("h")[0] + " ساعة")
        uptime_str = uptime_str.split("h")[1]
    if "m" in uptime_str:
        parts.append(uptime_str.split("m")[0] + " دقيقة")
        uptime_str = uptime_str.split("m")[1]
    if "s" in uptime_str:
        parts.append(uptime_str.split("s")[0] + " ثانية")
    return " ".join(parts) if parts else uptime_str


def format_bytes(bytes_val: int) -> str:
    """تنسيق حجم البيانات"""
    if bytes_val < 1024:
        return f"{bytes_val} B"
    elif bytes_val < 1024 * 1024:
        return f"{bytes_val / 1024:.1f} KB"
    elif bytes_val < 1024 * 1024 * 1024:
        return f"{bytes_val / (1024 * 1024):.1f} MB"
    else:
        return f"{bytes_val / (1024 * 1024 * 1024):.2f} GB"


def format_speed(kbps: int) -> str:
    """تنسيق السرعة"""
    if kbps < 1000:
        return f"{kbps} Kbps"
    else:
        return f"{kbps / 1000:.1f} Mbps"


def format_network_status(stats: Dict, router_stats, internet: Dict) -> str:
    """تنسيق حالة الشبكة العامة"""
    online = stats.get("online_devices", 0)
    offline = stats.get("offline_devices", 0)
    unknown = stats.get("unknown_devices", 0)
    blocked = stats.get("blocked_devices", 0)
    unread = stats.get("unread_alerts", 0)
    intrusions = stats.get("intrusions_24h", 0)
    errors = stats.get("unresolved_errors", 0)

    # حالة الإنترنت
    inet_emoji = "🟢" if internet.get("is_up") else "🔴"
    inet_status = "متصل" if internet.get("is_up") else "منقطع"
    latency = internet.get("latency", 0)

    # صحة الراوتر
    cpu = router_stats.cpu_load if router_stats else 0
    mem = router_stats.memory_usage if router_stats else 0
    cpu_emoji = "🟢" if cpu < 60 else ("🟡" if cpu < 85 else "🔴")
    mem_emoji = "🟢" if mem < 60 else ("🟡" if mem < 85 else "🔴")

    msg = f"""📡 <b>شبكة حمد نت - حالة الشبكة</b>

🌐 <b>الإنترنت:</b> {inet_emoji} {inet_status}
📡 <b>زمن الاستجابة:</b> {latency:.1f} ms
🌍 <b>IP العام:</b> {internet.get('wan_ip', 'غير متوفر')}

📱 <b>الأجهزة:</b>
  🟢 متصل: {online}
  🔴 منفصل: {offline}
  ❓ غير معروف: {unknown}
  🚫 محظور: {blocked}

🖥️ <b>الراوتر:</b>
  {cpu_emoji} المعالج: {cpu}%
  {mem_emoji} الذاكرة: {mem}%
  ⏰ وقت التشغيل: {format_uptime(router_stats.uptime) if router_stats else 'غير متوفر'}
  🔧 الموديل: {router_stats.model if router_stats else 'غير متوفر'}

🔔 <b>التنبيهات:</b> {unread} غير مقروء
🚨 <b>اختراقات (24س):</b> {intrusions}
⚠️ <b>أخطاء:</b> {errors}
"""
    return msg


def format_device_list(devices: List[Dict], title: str = "قائمة الأجهزة") -> str:
    """تنسيق قائمة الأجهزة"""
    if not devices:
        return f"📋 <b>{title}</b>\n\nلا توجد أجهزة."

    msg = f"📋 <b>{title}</b>\n\n"
    for i, d in enumerate(devices[:20], 1):  # حد أقصى 20 جهاز
        status = "🟢" if d.get("is_online") else "🔴"
        blocked = " 🚫" if d.get("is_blocked") else ""
        known = "" if d.get("is_known") else " ❓"
        hostname = d.get("hostname") or "غير معروف"
        ip = d.get("ip", "")
        mac = d.get("mac", "")
        interface = d.get("interface", "")
        limit = f" ⚡{d['speed_limit']}" if d.get("speed_limit") else ""

        msg += (f"{i}. {status} <b>{hostname}</b>{blocked}{known}\n"
                f"   🌐 {ip} | 🔗 {mac}\n"
                f"   📡 {interface}{limit}\n")

    if len(devices) > 20:
        msg += f"\n... و {len(devices) - 20} جهاز آخر"

    return msg


def format_device_detail(device: Dict) -> str:
    """تنسيق تفاصيل جهاز"""
    status = "🟢 متصل" if device.get("is_online") else "🔴 غير متصل"
    blocked = "🚫 محظور" if device.get("is_blocked") else "✅ غير محظور"
    known = "✅ معروف" if device.get("is_known") else "❓ غير معروف"

    msg = f"""📱 <b>تفاصيل الجهاز</b>

📌 <b>الاسم:</b> {device.get('hostname') or 'غير معروف'}
🌐 <b>IP:</b> {device.get('ip', 'غير متوفر')}
🔗 <b>MAC:</b> {device.get('mac', 'غير متوفر')}
📡 <b>الواجهة:</b> {device.get('interface', 'غير محدد')}
🏭 <b>الشركة:</b> {device.get('vendor', 'غير معروفة')}
📊 <b>الحالة:</b> {status}
🔒 <b>الحظر:</b> {blocked}
🏷️ <b>التصنيف:</b> {known}
⚡ <b>تحديد السرعة:</b> {device.get('speed_limit') or 'بدون تحديد'}
📝 <b>ملاحظات:</b> {device.get('notes') or 'لا يوجد'}
🕐 <b>أول ظهور:</b> {format_timestamp(device.get('first_seen', 0))}
🕐 <b>آخر ظهور:</b> {format_timestamp(device.get('last_seen', 0))}
"""
    return msg


def format_alert(alert: Dict) -> str:
    """تنسيق تنبيه"""
    severity_emoji = {
        "info": "ℹ️",
        "warning": "⚠️",
        "critical": "🚨",
        "error": "❌"
    }
    emoji = severity_emoji.get(alert.get("severity", "info"), "ℹ️")
    ts = format_timestamp(alert.get("timestamp", 0))

    return f"{emoji} <b>[{alert.get('alert_type', '')}]</b>\n📅 {ts}\n{alert.get('message', '')}"


def format_internet_status(status: Dict) -> str:
    """تنسيق حالة الإنترنت"""
    is_up = status.get("is_up", False)
    emoji = "🟢" if is_up else "🔴"
    status_text = "متصل ✅" if is_up else "منقطع ❌"

    msg = f"""🌐 <b>حالة الإنترنت - شبكة حمد نت</b>

{emoji} <b>الحالة:</b> {status_text}
📡 <b>زمن الاستجابة:</b> {status.get('latency', 0):.1f} ms
🌍 <b>IP العام:</b> {status.get('wan_ip', 'غير متوفر')}
📋 <b>السبب (إذا منقطع):</b> {status.get('reason', '-')}
"""
    return msg


def format_router_stats(stats) -> str:
    """تنسيق إحصائيات الراوتر"""
    if not stats:
        return "🖥️ <b>الراوتر</b>\n\nغير متوفر"

    cpu_emoji = "🟢" if stats.cpu_load < 60 else ("🟡" if stats.cpu_load < 85 else "🔴")
    mem_emoji = "🟢" if stats.memory_usage < 60 else ("🟡" if stats.memory_usage < 85 else "🔴")
    temp_emoji = "🟢" if stats.temperature < 60 else ("🟡" if stats.temperature < 75 else "🔴")

    msg = f"""🖥️ <b>إحصائيات الراوتر - شبكة حمد نت</b>

🔧 <b>الموديل:</b> {stats.model}
📦 <b>النسخة:</b> {stats.firmware_version}
⏰ <b>وقت التشغيل:</b> {format_uptime(stats.uptime)}

{cpu_emoji} <b>المعالج:</b> {stats.cpu_load}%
{mem_emoji} <b>الذاكرة:</b> {stats.memory_usage}% (حر: {stats.memory_free})
{temp_emoji} <b>الحرارة:</b> {stats.temperature}°C
⚡ <b>الجهد:</b> {stats.voltage}V
🌍 <b>IP العام:</b> {stats.wan_ip}
"""
    return msg


def format_intrusion(intrusion: Dict) -> str:
    """تنسيق محاولة اختراق"""
    return (f"🚨 <b>{intrusion.get('attack_type', 'محاولة')}</b>\n"
            f"⏰ {intrusion.get('time', '')}\n"
            f"🌐 المصدر: {intrusion.get('source_ip', 'غير معروف')}\n"
            f"🔌 المنفذ: {intrusion.get('target_port', '-')}\n"
            f"📡 البروتوكول: {intrusion.get('protocol', '-')}\n"
            f"📋 {intrusion.get('message', '')}")


def format_topology_change(change: Dict) -> str:
    """تنسيق تغيير طوبولوجيا"""
    return (f"🔄 <b>تغيير في الشبكة</b>\n"
            f"⏰ {format_timestamp(change.get('timestamp', 0))}\n"
            f"📋 {change.get('description', '')}\n"
            f"🔗 MAC: {change.get('device_mac', '')}")


def format_error(error: Dict) -> str:
    """تنسيق خطأ"""
    severity_emoji = {"warning": "⚠️", "error": "❌", "critical": "🚨"}
    emoji = severity_emoji.get(error.get("severity", "warning"), "⚠️")
    resolved = "✅" if error.get("resolved") else "❌"

    return (f"{emoji} <b>{error.get('error_type', 'خطأ')}</b> {resolved}\n"
            f"⏰ {format_timestamp(error.get('timestamp', 0))}\n"
            f"📋 {error.get('message', '')}")


def format_ping_result(result: Dict) -> str:
    """تنسيق نتيجة Ping"""
    if "error" in result:
        return f"❌ <b>Ping فشل</b>\n🌐 {result.get('host', '')}\n📋 {result['error']}"

    loss = result.get("packet_loss", 100)
    emoji = "🟢" if loss == 0 else ("🟡" if loss < 50 else "🔴")

    return (f"{emoji} <b>Ping {result.get('host', '')}</b>\n"
            f"📦 مرسل: {result.get('sent', 0)} | مستلم: {result.get('received', 0)}\n"
            f"📉 فقدان: {loss}%\n"
            f"📡 متوسط: {result.get('avg_latency', 0):.1f} ms")
