import firebase_admin
from firebase_admin import credentials, db
import bcrypt

# 1. الاتصال بقاعدة بيانات فايربيس الحية
cred = credentials.Certificate("firebase-key.json")
firebase_admin.initialize_app(cred, {
    'databaseURL': 'https://alphabet-7d14c-default-rtdb.firebaseio.com/'
})

# 2. تشفير كلمة السر الجديدة
new_password = "123456"
hashed = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

print("جاري الاتصال بالسحابة (Firebase)...")
ref = db.reference('/')
data = ref.get()

if data is not None:
    users = data.get("users", [])
    # فايربيس قد يحفظ القوائم كـ dictionary، نعالج ذلك:
    is_dict = isinstance(users, dict)
    users_list = list(users.values()) if is_dict else users
    
    found = False
    for u in users_list:
        if u and u.get("username") == "fethi":
            u["password"] = hashed
            u["two_factor_secret"] = "" # إيقاف التوثيق الثنائي من السحابة
            found = True
            break
            
    if found:
        # إعادة حفظ البيانات بصيغتها الأصلية
        if is_dict:
            data["users"] = {str(i): u for i, u in enumerate(users_list)}
        else:
            data["users"] = users_list
            
        ref.set(data)
        print("✅ تم تفجير المشكلة! كلمة سر fethi الآن هي 123456")
        print("🚀 اذهب وسجل دخولك الآن فوراً (لا حاجة لعمل git push)")
    else:
        print("❌ لم نعثر على حساب fethi في السحابة.")
else:
    print("❌ قاعدة البيانات في فايربيس فارغة.")