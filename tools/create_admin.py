import json
from passlib.context import CryptContext

# إعداد التشفير تماماً كما في ملفك الرئيسي
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
hashed_password = pwd_context.hash("123456")

# بيانات حساب المدير
admin_user = {
    "username": "admin",
    "password": hashed_password,
    "role": "super_admin",
    "balance": 10000.0,
    "is_blocked": 0,
    "created_by": "System"
}

# حفظ الحساب في ملف قاعدة البيانات
with open("tickets_database.json", "w", encoding="utf-8") as f:
    json.dump([admin_user], f, indent=4)

print("تم إنشاء حساب المدير بنجاح! اسم المستخدم: admin | كلمة المرور: 123456")