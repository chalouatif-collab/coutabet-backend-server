import firebase_admin
from firebase_admin import credentials, db
import pyotp

# إنشاء مفتاح سري جديد
new_secret = pyotp.random_base32()

# الاتصال بقاعدة البيانات
if not firebase_admin._apps:
    cred = credentials.Certificate("firebase-key.json")
    firebase_admin.initialize_app(cred, {'databaseURL': 'https://alphabet-7d14c-default-rtdb.firebaseio.com/'})

print("⏳ جاري تحديث كود الحماية الثنائية لحساب fethi...")
ref = db.reference('/users')
users_data = ref.get()

found = False
if isinstance(users_data, list):
    for i, user in enumerate(users_data):
        if user and user.get("username") == "fethi":
            db.reference(f'/users/{i}').update({"two_factor_secret": new_secret})
            found = True
            break
elif isinstance(users_data, dict):
    for key, user in users_data.items():
        if user and user.get("username") == "fethi":
            db.reference(f'/users/{key}').update({"two_factor_secret": new_secret})
            found = True
            break

if found:
    print("✅ تم بنجاح! السيرفر الآن جاهز.")
    print("==================================================")
    print("📱 افتح تطبيق Google Authenticator في هاتفك وافعل الآتي:")
    print("1. امسح أي حساب قديم باسم موقعك (لكي لا تختلط عليك الأرقام).")
    print("2. اضغط على علامة (+) في التطبيق واختر 'إدخال مفتاح الإعداد' (Enter a setup key).")
    print("3. اسم الحساب: Alpha Owner")
    print(f"4. المفتاح (Key): {new_secret}")
    print("==================================================")
else:
    print("❌ لم أتمكن من العثور على حساب fethi!")