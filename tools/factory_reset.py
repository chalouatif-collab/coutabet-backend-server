import firebase_admin
from firebase_admin import credentials, db
from passlib.context import CryptContext
import pyotp

print("⏳ جاري تحضير عملية المسح الشامل...")

# 1. إعداد التشفير والـ 2FA
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
temp_password = "AlphaOwner2026!" # كلمة سر مؤقتة قوية
hashed_password = pwd_context.hash(temp_password)
new_secret = pyotp.random_base32()

# 2. الاتصال بقاعدة البيانات السحابية
if not firebase_admin._apps:
    cred = credentials.Certificate("firebase-key.json")
    firebase_admin.initialize_app(cred, {'databaseURL': 'https://alphabet-7d14c-default-rtdb.firebaseio.com/'})

# 3. تجهيز حساب المالك الوحيد (fethi)
owner_account = {
    "id": 1,
    "username": "fethi",
    "password": hashed_password,
    "role": "owner",
    "balance": 0.0,
    "rtp": 50,
    "is_blocked": 0,
    "created_by": "system",
    "last_spin_date": "",
    "daily_deposits": 0.0,
    "two_factor_secret": new_secret,
    "phone": ""
}

# 4. مسح الكل وزراعة المالك فقط
try:
    # نقوم بتحديث عقدة المستخدمين فقط للحفاظ على سجلات التذاكر إن وجدت
    db.reference('/users').set([owner_account])
    
    print("\n✅ تم مسح جميع الحسابات الوهمية والقديمة بنجاح!")
    print("👑 تم تأسيس حساب المالك الجديد والوحيد في النظام:")
    print("--------------------------------------------------")
    print("👤 اسم المستخدم: fethi")
    print(f"🔑 كلمة المرور المؤقتة: {temp_password}")
    print(f"🔐 كود 2FA السري: {new_secret}")
    print("--------------------------------------------------")
    print("⚠️ هام جداً: قم بإضافة كود الـ 2FA في تطبيق Google Authenticator الآن!")
except Exception as e:
    print(f"❌ حدث خطأ أثناء الاتصال بقاعدة البيانات: {e}")