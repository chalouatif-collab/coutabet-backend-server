import sqlite3

# الاتصال بقاعدة البيانات
conn = sqlite3.connect("local_test.db")
cursor = conn.cursor()

# 1. إضافة العمود الجديد (سيتجاهل الأمر إذا كان العمود موجوداً)
try:
    cursor.execute("ALTER TABLE alpha_users ADD COLUMN two_factor_secret TEXT")
    print("✅ تم إنشاء عمود two_factor_secret بنجاح!")
except sqlite3.OperationalError:
    print("⚠️ العمود موجود مسبقاً.")

# 2. إضافة المفتاح السري لحساب Fethi
cursor.execute("UPDATE alpha_users SET two_factor_secret = 'JBSWY3DPEHPK3PXP' WHERE username = 'fethi'")
conn.commit()
conn.close()

print("✅ تم تحديث حساب fethi بالمفتاح السري بنجاح!")