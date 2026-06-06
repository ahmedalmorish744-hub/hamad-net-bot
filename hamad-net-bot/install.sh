#!/bin/bash
# سكربت تثبيت بوت حمد نت
# Installation Script for Hamad Net Bot

echo "🏠 تثبيت بوت حمد نت - Hamad Net Bot"
echo "====================================="

# التحقد من Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 غير مثبت. يرجى تثبيته أولاً."
    exit 1
fi

echo "✅ Python 3 متوفر"

# إنشاء بيئة افتراضية
if [ ! -d "venv" ]; then
    echo "📦 إنشاء بيئة افتراضية..."
    python3 -m venv venv
fi

# تفعيل البيئة الافتراضية
source venv/bin/activate

# تثبيت المتطلبات
echo "📥 تثبيت المتطلبات..."
pip install -r requirements.txt

# إنشاء مجلد البيانات
mkdir -p data

# التحقق من ملف .env
if [ ! -f ".env" ]; then
    echo "⚙️ إنشاء ملف الإعدادات..."
    cp .env.example .env
    echo ""
    echo "⚠️  مهم: يجب تعديل ملف .env وإضافة:"
    echo "   1. TELEGRAM_BOT_TOKEN - توكن البوت من @BotFather"
    echo "   2. AUTHORIZED_CHAT_IDS - معرف المحادثة المصرح لها"
    echo "   3. إعدادات الراوتر (نوع، عنوان، كلمة مرور)"
    echo ""
fi

# التحقق من nmap
if ! command -v nmap &> /dev/null; then
    echo "⚠️  nmap غير مثبت - يُنصح بتثبيته لفحص أفضل:"
    echo "   Ubuntu/Debian: sudo apt install nmap"
    echo "   CentOS/RHEL: sudo yum install nmap"
fi

# التحقد من traceroute
if ! command -v traceroute &> /dev/null; then
    echo "⚠️  traceroute غير مثبت - يُنصح بتثبيته:"
    echo "   Ubuntu/Debian: sudo apt install traceroute"
fi

echo ""
echo "✅ التثبيت مكتمل!"
echo ""
echo "لتشغيل البوت:"
echo "  source venv/bin/activate"
echo "  python bot.py"
echo ""
echo "أو استخدام systemd:"
echo "  sudo cp scripts/hamad-net-bot.service /etc/systemd/system/"
echo "  sudo systemctl enable hamad-net-bot"
echo "  sudo systemctl start hamad-net-bot"
