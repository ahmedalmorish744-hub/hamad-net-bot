"""
بوت حمد نت - النقطة الرئيسية
Hamad Net Bot - Main Entry Point
"""
import asyncio
import logging
import os
import sys

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from config import config
from database.db import init_db, Database
from router.mikrotik import MikroTikRouter
from monitoring.network_monitor import NetworkMonitor
from handlers.bot_handlers import HamadNetBot

# إعداد التسجيل
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('hamad_net.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)


async def main():
    """الوظيفة الرئيسية"""

    # التحقق من الإعدادات
    if not config.BOT_TOKEN:
        logger.error("BOT_TOKEN غير محدد! ضعه في ملف .env")
        return

    if not config.ADMIN_CHAT_ID:
        logger.error("ADMIN_CHAT_ID غير محدد! ضعه في ملف .env")
        return

    logger.info("=" * 60)
    logger.info("  بوت حمد نت - Hamad Net Bot")
    logger.info("  المراقبة والإدارة الشاملة للشبكة")
    logger.info("=" * 60)

    # إنشاء قاعدة البيانات
    await init_db(config.DB_PATH)
    db = Database(config.DB_PATH)
    logger.info("تم تهيئة قاعدة البيانات")

    # إنشاء البوت
    bot = Bot(token=config.BOT_TOKEN)
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)

    # إنشاء معالج البوت
    hamad_bot = HamadNetBot(bot)
    await hamad_bot.initialize()
    dp.include_router(hamad_bot.get_router())

    # إعداد المراقبة الدورية
    scheduler = AsyncIOScheduler()

    async def periodic_scan():
        """فحص دوري للأجهزة"""
        try:
            logger.info("فحص دوري: جاري مسح الأجهزة...")
            await hamad_bot.monitor.scan_devices()
        except Exception as e:
            logger.error(f"خطأ في الفحص الدوري: {e}")

    async def periodic_internet_check():
        """فحص دوري للإنترنت"""
        try:
            await hamad_bot.monitor.check_internet()
        except Exception as e:
            logger.error(f"خطأ في فحص الإنترنت: {e}")

    async def periodic_intrusion_check():
        """فحص دوري لمحاولات الاختراق"""
        try:
            await hamad_bot.monitor.check_intrusions()
        except Exception as e:
            logger.error(f"خطأ في فحص الاختراقات: {e}")

    async def periodic_health_check():
        """فحص دوري لصحة الراوتر"""
        try:
            await hamad_bot.monitor.check_router_health()
        except Exception as e:
            logger.error(f"خطأ في فحص صحة الراوتر: {e}")

    async def periodic_topology_check():
        """فحص دوري لتغييرات الطوبولوجيا"""
        try:
            await hamad_bot.monitor.detect_topology_changes()
        except Exception as e:
            logger.error(f"خطأ في فحص الطوبولوجيا: {e}")

    # جدولة المهام الدورية
    scheduler.add_job(periodic_scan, 'interval',
                      seconds=config.SCAN_INTERVAL, id='scan')
    scheduler.add_job(periodic_internet_check, 'interval',
                      seconds=config.INTERNET_CHECK_INTERVAL, id='internet')
    scheduler.add_job(periodic_intrusion_check, 'interval',
                      seconds=config.SCAN_INTERVAL * 2, id='intrusions')
    scheduler.add_job(periodic_health_check, 'interval',
                      seconds=config.SCAN_INTERVAL * 3, id='health')
    scheduler.add_job(periodic_topology_check, 'interval',
                      seconds=config.TRAFFIC_UPDATE_INTERVAL, id='topology')

    scheduler.start()
    logger.info("تم بدء المراقبة الدورية")

    # إرسال رسالة بدء التشغيل للمدير
    try:
        await bot.send_message(
            config.ADMIN_CHAT_ID,
            "📡 <b>بوت حمد نت يعمل!</b>\n\n"
            "✅ تم الاتصال بالراوتر\n"
            "✅ تم بدء المراقبة الدورية\n"
            "✅ نظام التنبيهات نشط\n\n"
            "📱 استخدم /menu للقائمة الرئيسية",
            parse_mode="HTML"
        )
    except Exception as e:
        logger.warning(f"لم يتم إرسال رسالة البدء: {e}")

    # بدء البوت
    logger.info("بدء تشغيل البوت...")
    try:
        await dp.start_polling(bot)
    except KeyboardInterrupt:
        logger.info("تم إيقاف البوت")
    finally:
        scheduler.shutdown()
        await hamad_bot.router_api.disconnect()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
