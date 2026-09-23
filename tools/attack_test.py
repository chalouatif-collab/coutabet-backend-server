import requests
import time

# 🎯 ضع رابط السيرفر الخاص بك هنا (سواء المحلي أو على Render)
BASE_URL = "https://alpha-backend-server.onrender.com"
# BASE_URL = "https://alpha-backend-server.onrender.com"

print("🦅 بدء عملية اختبار الاختراق (Penetration Testing)...\n")

# ==========================================
# 🚨 الهجوم الأول: محاولة تغيير كلمة مرور المالك (IDOR)
# ==========================================
print("⚠️ جاري تنفيذ الهجوم الأول: محاولة تغيير كلمة مرور [fethi] من حساب عادي...")
# نصنع توكن وهمي أو نرسل الطلب بدون توكن أدمن
headers_fake = {"Authorization": "Bearer fake_user_token_123"}
payload_password = {
    "username": "fethi", # محاولة استهداف حساب المالك
    "new_password": "hacked_123"
}
try:
    res1 = requests.post(f"{BASE_URL}/api/user/change-password", json=payload_password, headers=headers_fake)
    if res1.status_code in [401, 403]:
        print(f"✅ [نجاح الحماية] السيرفر صد الهجوم ورفض الصلاحية! كود الرد: {res1.status_code}\n")
    else:
        print(f"❌ [فشل الحماية] السيرفر سمح بالعملية! كود الرد: {res1.status_code}\n")
except Exception as e:
    print(f"خطأ في الاتصال: {e}\n")

# ==========================================
# 🚨 الهجوم الثاني: محاولة الموافقة على سحب مالي (Broken Access Control)
# ==========================================
print("⚠️ جاري تنفيذ الهجوم الثاني: محاولة الموافقة على سحب مالي من خارج لوحة الإدارة...")
payload_approve = {
    "transaction_id": 9999,
    "decision": "approve",
    "admin_username": "hacker"
}
try:
    res2 = requests.post(f"{BASE_URL}/api/admin/handle-request", json=payload_approve) # بدون توكن
    if res2.status_code in [401, 403]:
        print(f"✅ [نجاح الحماية] السيرفر صد الهجوم ومنع معالجة الطلب! كود الرد: {res2.status_code}\n")
    else:
        print(f"❌ [فشل الحماية] السيرفر سمح بالعملية! كود الرد: {res2.status_code}\n")
except Exception as e:
    print(f"خطأ في الاتصال: {e}\n")

# ==========================================
# 🚨 الهجوم الثالث: إغراق السيرفر بطلبات الإيداع (DDoS / Spam)
# ==========================================
print("⚠️ جاري تنفيذ الهجوم الثالث: إرسال 5 طلبات إيداع متتالية سريعة جداً (Spam)...")
payload_deposit = {
    "player": "hacker_bot",
    "method": "RunPay",
    "amount": 100,
    "code": "123456"
}
success_blocks = 0
for i in range(1, 6):
    try:
        res3 = requests.post(f"{BASE_URL}/api/deposit", json=payload_deposit)
        print(f"الطلب رقم {i} -> كود الرد: {res3.status_code}")
        if res3.status_code == 429: # 429 تعني Too Many Requests
            success_blocks += 1
    except Exception as e:
        pass
    
if success_blocks > 0:
    print(f"✅ [نجاح الحماية] نظام (Rate Limiter) تدخل بنجاح وحظر الطلبات السريعة! (كود 429)\n")
else:
    print(f"❌ [فشل الحماية] السيرفر استقبل جميع الطلبات دون حظر!\n")

print("🛡️ انتهى فحص الأمان!")
