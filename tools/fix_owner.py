import sqlite3
import bcrypt

# سنستخدم كلمة سر بسيطة وموحدة للتجربة لضمان عدم وجود أخطاء في الكتابة
password = "123456"
hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

print("جاري الاتصال بقاعدة البيانات لتنفيذ الحل الجذري...")
try:
    conn = sqlite3.connect('local_test.db')
    cursor = conn.cursor()

    # 1. صيانة حساب fethi (تحديث كلمة السر وإلغاء التوثيق الثنائي بقوة)
    cursor.execute("""
        UPDATE alpha_users 
        SET password = ?, 2fa_enabled = 0, 2fa_secret = '' 
        WHERE username = 'fethi'
    """, (hashed,))

    # 2. إنشاء حساب طوارئ جديد بصلاحيات Owner (للضمان)
    try:
        cursor.execute("""
            INSERT INTO alpha_users (username, password, role, balance, 2fa_enabled, 2fa_secret)
            VALUES ('boss', ?, 'owner', 999999, 0, '')
        """, (hashed,))
    except sqlite3.IntegrityError:
        # إذا كان حساب boss موجوداً، نقوم بتحديثه فقط
        cursor.execute("""
            UPDATE alpha_users 
            SET password = ?, 2fa_enabled = 0, 2fa_secret = '' 
            WHERE username = 'boss'
        """, (hashed,))

    conn.commit()
    print("✅ تم بنجاح! لديك الآن حسابان جاهزان للدخول:")
    print("👤 الحساب الأول -> الاسم: fethi | كلمة المرور: 123456")
    print("👤 حساب الطوارئ -> الاسم: boss | كلمة المرور: 123456")

except Exception as e:
    print(f"❌ حدث خطأ: {e}")
finally:
    conn.close()