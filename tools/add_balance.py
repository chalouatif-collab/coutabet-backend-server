import sqlite3

# إعدادات الشحن
db_path = 'local_test.db'  # اسم قاعدة البيانات
username = 'baya'          # اسم المستخدم
new_balance = 500001        # الرصيد الجديد

try:
    # الاتصال بقاعدة البيانات
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # تنفيذ أمر التحديث
    cursor.execute("UPDATE alpha_users SET balance = ? WHERE username = ?", (new_balance, username))
    
    # حفظ التغييرات
    conn.commit()
    print(f"✅ تم تحديث رصيد اللاعب '{username}' بنجاح إلى: {new_balance}")
    
except Exception as e:
    print(f"❌ حدث خطأ: {e}")
finally:
    # إغلاق الاتصال
    conn.close()