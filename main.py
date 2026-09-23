import traceback
from fastapi.responses import JSONResponse

@app.get("/setup-first-owner")
def setup_first_owner():
    try:
        # اختبار جلب البيانات من Firebase
        db_data = load_db()
        owner_username = "fethi"
        owner_password = "Coutabet2026!"
        
        # التحقق مما إذا كان الحساب موجوداً بالفعل
        for u in db_data:
            if str(u.get("username", "")).strip().lower() == owner_username.lower():
                return {"status": "success", "message": "حساب المالك موجود بالفعل!"}
        
        # تحديد ID جديد
        new_id = max([int(u.get("id", 0)) for u in db_data]) + 1 if db_data else 1
        
        # إنشاء الحساب الجديد
        new_owner = {
            "id": new_id,
            "username": owner_username,
            "password": hash_password(owner_password),
            "role": "owner",
            "balance": 1000000.0,
            "rtp": 50,
            "is_blocked": 0,
            "created_by": "system",
            "last_spin_date": "",
            "daily_deposits": 0.0,
            "two_factor_secret": "",
            "phone": "00000000"
        }
        
        db_data.append(new_owner)
        save_db(db_data)
        
        return {"status": "success", "message": f"تم إنشاء حساب المالك '{owner_username}' بنجاح!"}
    
    except Exception as e:
        # طباعة الخطأ كاملاً على الشاشة لنعرف السبب الحقيقي
        error_details = traceback.format_exc()
        print(error_details)
        return JSONResponse(
            status_code=500,
            content={
                "error": str(e),
                "details": "تأكد من أن ملف firebase-key.json مرفوع على السيرفر أو أن إعدادات قاعدة البيانات صحيحة."
            }
        )
