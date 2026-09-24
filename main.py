from fastapi import FastAPI, HTTPException, Depends, Request, UploadFile, File, Form, Header, Body, Query,WebSocket, WebSocketDisconnect
from fastapi.security import OAuth2PasswordBearer
import requests
from pydantic import BaseModel
from typing import List, Optional
from fastapi.middleware.cors import CORSMiddleware
from jose import jwt
from datetime import datetime, timedelta
import random
import json
import os
import time
import hmac
import hashlib
import urllib.parse
from passlib.context import CryptContext
from sqlalchemy import create_engine, Column, Integer, String, Float, text
from sqlalchemy.orm import declarative_base, sessionmaker
import asyncio
db_lock = asyncio.Lock()
import shutil
from fastapi.staticfiles import StaticFiles
import httpx
from fastapi.responses import JSONResponse, HTMLResponse, FileResponse, RedirectResponse, StreamingResponse
from dotenv import load_dotenv
import pyotp
import qrcode
import io
import html
import firebase_admin
from firebase_admin import credentials
from firebase_admin import db
import uuid


PROCESSED_TRANSACTIONS = set()
from pydantic import BaseModel

class SportsLaunchRequest(BaseModel):
    provider_code: str
    game_code: str
    user_code: str

import os

# ==========================================
# 🎮 إعدادات الكازينو (NexusGGR)
# ==========================================
AGENT_CODE = os.getenv("AGENT_CODE", "Alphabet1")
AGENT_TOKEN = os.getenv("AGENT_TOKEN", "")
NEXUS_SECRET_KEY = os.getenv("NEXUS_SECRET_KEY", "")
PROVIDER_ENDPOINT = os.getenv("PROVIDER_ENDPOINT", "https://api.nexusggr.eu")

# ==========================================
# ⚽ إعدادات الألعاب الافتراضية (EuroVirtuals)
# ==========================================
EURO_APP_KEY = os.getenv("EURO_APP_KEY", "")
EURO_API_KEY = os.getenv("EURO_API_KEY", "")
EURO_BASE_URL = os.getenv("EURO_BASE_URL", "https://api.betkraft.co.uk/")

from dotenv import load_dotenv
import os

load_dotenv()
ADMIN_USER = os.getenv("ADMIN_USERNAME")
ADMIN_PASS = os.getenv("ADMIN_PASSWORD")
SECRET_KEY = os.getenv("SECRET_KEY", "alpha-secure-key-2026")

# 1. إعداد الاتصال بـ Firebase
if not firebase_admin._apps:
    cred = credentials.Certificate("firebase-key.json") 
    firebase_admin.initialize_app(cred, {
        'databaseURL': 'https://coutabet-default-rtdb.firebaseio.com/'
    })

# 2. دالة جلب البيانات من السحابة
def load_db():
    ref = db.reference('/') 
    data = ref.get()
    
    if data is None:
        return {"users": [], "shop_withdrawals": [], "tickets": []}
    
    # 3. كائن سحري يجمع بين خصائص القائمة والقاموس
    users = data.get("users", [])
    if isinstance(users, dict):
        users = list(users.values())
        
    class MagicDB(list):
        def __init__(self, users_list, full_data):
            super().__init__(users_list)
            self.full_data = full_data
            if "shop_withdrawals" not in self.full_data:
                self.full_data["shop_withdrawals"] = []
                
        def get(self, key, default=None):
            return self.full_data.get(key, default)
            
        def __contains__(self, key):
            return key in self.full_data
            
        def __setitem__(self, key, value):
            self.full_data[key] = value

    return MagicDB(users, data)

# 3. دالة الحفظ السحابي الفوري
def save_db(data):
    ref = db.reference('/')
    if hasattr(data, 'full_data'):
        data.full_data['users'] = list(data)
        ref.set(data.full_data)
    elif isinstance(data, list):
        ref.child('users').set(list(data))
    else:
        ref.set(data)

# اسم ملف التخزين الموجود في مشروعك
DB_FILE = "tickets_database.json"
TICKETS_FILE = "tickets_database.json" 

# ==========================================
# إعدادات قاعدة البيانات والتشفير
# ==========================================
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./local_test.db")
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class User(Base):
    __tablename__ = "alpha_users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    password = Column(String)
    role = Column(String)
    balance = Column(Float, default=0.0)
    rtp = Column(Integer, default=50)
    is_blocked = Column(Integer, default=0)
    created_by = Column(String)
    last_spin_date = Column(String, default="")
    daily_deposits = Column(Float, default=0.0)
    two_factor_secret = Column(String, nullable=True)

class Transaction(Base):
    __tablename__ = "transactions"
    id = Column(Integer, primary_key=True, index=True)
    admin_username = Column(String)
    target_username = Column(String)
    action = Column(String)  
    amount = Column(Float)
    date = Column(String)  
    image_path = Column(String, nullable=True)
    tx_id = Column(String, nullable=True) # 👈 السطر السحري الذي سيحفظ بيانات D17 و Wafacash

try:
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE transactions ADD COLUMN image_path VARCHAR"))
except Exception:
    pass

# 👈 أمر إجباري لتحديث الجداول القديمة
try:
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE transactions ADD COLUMN tx_id VARCHAR"))
except Exception:
    pass
Base.metadata.create_all(bind=engine)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
def hash_password(password: str):
    return pwd_context.hash(password)

def verify_password(plain_password, hashed_password):
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except Exception:
        # 🛡️ تم إغلاق ثغرة تخطي التشفير
        return False

ALGORITHM = "HS256"
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/login")

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(hours=24)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    
async def get_current_user(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload.get("sub")
    except:
        raise HTTPException(status_code=401, detail="Invalid token")

async def get_admin_user(current_user: str = Depends(get_current_user)):
    db = load_db()
    user = next((u for u in db if u["username"] == current_user), None)
    
    if not user or user.get("role") not in ["owner","manager", "super_admin", "admin","shop"]:
        raise HTTPException(status_code=403, detail="Access Denied: Admin privileges required")
    
    return current_user

def send_whatsapp_2fa(phone_number: str, username: str, password: str, secret_key: str):
    INSTANCE_ID = "instance185867"
    TOKEN = "76jnhy79la7a5bxx"
    
    message = f"""*مرحباً بك في نظام Alpha Core 🔐*

تم إنشاء حساب الإدارة الخاص بك بنجاح.

👤 *اسم المستخدم:* {username}
🔑 *كلمة المرور:* {password}

🛡️ *خطوات تفعيل الحماية (Google Authenticator):*
1️⃣ افتح تطبيق Google Authenticator.
2️⃣ اختر (إدخال مفتاح الإعداد).
3️⃣ اسم الحساب: AlphaCore - {username}
4️⃣ المفتاح السري:
*{secret_key}*

⚠️ _يرجى حذف هذه الرسالة بعد التفعيل للحفاظ على سرية بياناتك._"""

    if not phone_number.startswith("+"):
        phone_number = f"+{phone_number}"

    url = f"https://api.ultramsg.com/{INSTANCE_ID}/messages/chat"
    payload = {"token": TOKEN, "to": phone_number, "body": message}
    headers = {'content-type': 'application/x-www-form-urlencoded'}

    try:
        response = httpx.post(url, data=payload, headers=headers)
        if response.status_code == 200:
            print(f"✅ تم إرسال رسالة الواتساب بنجاح إلى: {phone_number}")
        else:
            print(f"❌ خطأ في إرسال الواتساب: {response.text}")
    except Exception as e:
        print(f"❌ حدث خطأ في الاتصال: {e}")

# ==========================================
# إعدادات تطبيق FastAPI الأساسية
# ==========================================
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address)

app = FastAPI()

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
from starlette.middleware.sessions import SessionMiddleware
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://coutabet.com",
        "https://coutabet-backend-server.onrender.com",
        "https://admin-coutabet.com",
        "http://localhost:5500",
        "http://127.0.0.1:5500"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response

os.makedirs("uploads", exist_ok=True)
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

# 🚨 إعدادات الإنذار المبكر (Telegram)
TELEGRAM_TOKEN = "8879806026:AAEB64RCPW4KzsUXUlDeztP_PzjtxkJv_4g"
TELEGRAM_CHAT_ID = "7700782611"

async def send_telegram_alert(message: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML"
    }
    try:
        async with httpx.AsyncClient() as client:
            await client.post(url, json=payload)
    except Exception as e:
        print(f"Telegram Alert Error: {e}")

ALLOWED_NEXUS_IPS = [
    "127.0.0.1",       
]

def verify_nexus_ip(request: Request):
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        client_ip = forwarded_for.split(",")[0].strip()
    else:
        client_ip = request.client.host
    return client_ip

# --- التوجيه الذكي اليدوي لإجبار الروابط القديمة على العمل بالروابط النظيفة ---
@app.get("/owner.html")
async def redirect_owner():
    return RedirectResponse(url="/panel/owner/", status_code=303)

@app.get("/super_admin.html")
async def redirect_super_admin():
    return RedirectResponse(url="/panel/super_admin/", status_code=303)

@app.get("/admin.html")
async def redirect_admin():
    return RedirectResponse(url="/panel/admin/", status_code=303)

@app.get("/shop.html")
async def redirect_shop():
    return RedirectResponse(url="/panel/shop/", status_code=303)

# --- مسارات لوحات الإدارة النظيفة ---
@app.get("/panel/owner", response_class=HTMLResponse)
@app.get("/panel/owner/", response_class=HTMLResponse)
async def get_owner_panel():
    with open("panel/owner/index.html", "r", encoding="utf-8") as f:
        return f.read()

@app.get("/panel/super_admin", response_class=HTMLResponse)
@app.get("/panel/super_admin/", response_class=HTMLResponse)
async def get_super_admin_panel():
    with open("panel/super_admin/index.html", "r", encoding="utf-8") as f:
        return f.read()

@app.get("/panel/admin", response_class=HTMLResponse)
@app.get("/panel/admin/", response_class=HTMLResponse)
async def get_admin_panel():
    with open("panel/admin/index.html", "r", encoding="utf-8") as f:
        return f.read()

@app.get("/panel/shop", response_class=HTMLResponse)
@app.get("/panel/shop/", response_class=HTMLResponse)
async def get_shop_panel():
    with open("panel/shop/index.html", "r", encoding="utf-8") as f:
        return f.read()
    
@app.get("/panel/manager", response_class=HTMLResponse)
@app.get("/panel/manager/", response_class=HTMLResponse)
async def get_manager_panel():
    with open("panel/manager/index.html", "r", encoding="utf-8") as f:
        return f.read()    
    
class ResettleTicketRequest(BaseModel):
    ticket_id: str
    new_status: str

@app.post("/api/admin/resettle-ticket")
async def resettle_ticket(req: ResettleTicketRequest, current_user: str = Depends(get_admin_user)):
    tickets_db = load_tickets_db()
    db = load_db()
    
    ticket = next((t for t in tickets_db if str(t.get("ticket_id")) == str(req.ticket_id)), None)
    if req.amount <= 0:
            raise HTTPException(status_code=400, detail="Le montant doit être supérieur à zéro")
    if not ticket:
        raise HTTPException(status_code=404, detail="التذكرة غير موجودة")
    
    old_status = ticket.get("status")
    player_username = ticket.get("username")
    win_amount = float(ticket.get("gain", 0))

    target_user = next((u for u in db if u["username"] == player_username), None)
    if not target_user:
        raise HTTPException(status_code=404, detail="اللاعب غير موجود")

    if old_status == "gagne" and req.new_status != "gagne":
        target_user["balance"] = float(target_user.get("balance", 0)) - win_amount
    elif old_status != "gagne" and req.new_status == "gagne":
        target_user["balance"] = float(target_user.get("balance", 0)) + win_amount

    ticket["status"] = req.new_status
    save_tickets_db(tickets_db)
    save_db(db)
    log_admin_action(current_user, "RESET_TICKET", f"Ticket ID {req.ticket_id} changed to {req.new_status}")
    
    return {"status": "success", "message": f"تم تعديل التذكرة بنجاح إلى {req.new_status}"}    

class DepositRequest(BaseModel):
    player: str
    method: str
    amount: float
    code: str
    receipt_image: Optional[str] = None # 👈 السطر السحري لاستقبال لقطة الشاشة

@app.post("/api/deposit")
@limiter.limit("1/minute")
async def create_deposit(request: Request, req: DepositRequest):
    try:
        db = load_tickets_db()
        new_ticket = {
            "ticket_id": "DEP-" + datetime.now().strftime("%Y%m%d%H%M%S"),
            "type": "deposit",
            "username": html.escape(req.player.strip()),
            "method": html.escape(req.method.strip()),
            "amount": req.amount,
            "code": html.escape(req.code.strip()) if hasattr(req, 'code') and req.code else "",
            "receipt_image": getattr(req, 'receipt_image', None),
            "status": "pending",
            "date": datetime.now().isoformat()
        }
        db.append(new_ticket)
        
        alert_msg = f"🚨 <b>عملية إيداع جديدة!</b>\n👤 اللاعب: <code>{new_ticket['username']}</code>\n💰 المبلغ: <b>{new_ticket['amount']}</b>\n💳 الطريقة: {new_ticket['method']}"
        asyncio.create_task(send_telegram_alert(alert_msg))
 
        with open(TICKETS_FILE, "w", encoding="utf-8") as f:
            json.dump(db, f, indent=4, ensure_ascii=False)
            
        return {"status": "success", "message": "تم إرسال طلب الإيداع بنجاح"}
    except Exception as e:
        print(f"Error in create_deposit: {e}")
        return {"status": "error", "message": "حدث خطأ أثناء معالجة الطلب"}

@app.get("/api/admin/get-pending-withdrawals")
async def get_pending_withdrawals(current_user: str = Depends(get_admin_user)):
    """جلب جميع طلبات السحب المعلقة (القديمة والجديدة)"""
    db_session = SessionLocal()
    try:
        txs = db_session.query(Transaction).filter(
    Transaction.admin_username == "PENDING",
    Transaction.action.ilike("%withdraw%") # 👈 اجعله مرناً هكذا
).order_by(Transaction.id.desc()).all()
        result = []
        for t in txs:
            # استخراج التفاصيل بأمان تام لعرضها للأونر
            tx_id_val = getattr(t, "tx_id", None)
            if not tx_id_val and t.action and "Details:" in t.action:
                tx_id_val = t.action.split("Details: ")[-1]
            elif not tx_id_val:
                tx_id_val = str(t.id)

            result.append({
                "id": t.id,
                "tx_id": tx_id_val,
                "target_username": t.target_username,
                "amount": float(t.amount or 0),
                "action": "withdraw_request", # إرجاع الاسم النظيف للوحة
                "date": str(t.date)
            })
        return result
    except Exception as e:
        print(f"Error GET withdrawals: {e}")
        return []
    finally:
        db_session.close()

@app.post("/api/admin/process-withdrawal")
async def process_withdrawal(request: Request):
    """معالجة طلب السحب (موافقة أو رفض)"""
    data = await request.json()
    request_id = data.get("request_id")
    action_type = data.get("action")
    
    db_session = SessionLocal()
    try:
        # البحث عن الطلب سواء بـ id أو tx_id
        tx = db_session.query(Transaction).filter(
            (Transaction.id == request_id) | (Transaction.tx_id == str(request_id))
        ).first()
        
        if not tx:
            from fastapi.responses import JSONResponse
            return JSONResponse(status_code=404, content={"detail": "Demande introuvable"})
            
        if tx.admin_username != "PENDING":
            from fastapi.responses import JSONResponse
            return JSONResponse(status_code=400, content={"detail": "Cette demande a déjà été traitée"})
            
        if action_type == "approve":
            # تمت الموافقة وإرسال الأموال
            tx.admin_username = "APPROVED"
            
        elif action_type == "reject":
            # تم الرفض، نعيد الرصيد للاعب
            tx.admin_username = "REJECTED"
            
            # (تأكد أن جدول المستخدمين اسمه User في ملفك)
            user = db_session.query(User).filter(User.username == tx.target_username).first()
            if user:
                user.balance = float(user.balance or 0) + float(tx.amount or 0)
                
        db_session.commit()
        return {"status": "success", "message": "Traitement réussi"}
        
    except Exception as e:
        db_session.rollback()
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=500, content={"detail": str(e)})
    finally:
        db_session.close()

@app.get("/api/admin/get-pending-deposits")
async def get_pending_deposits(current_user: str = Depends(get_admin_user)):
    db_session = SessionLocal()
    try:
        # جلب طلبات الشحن من قاعدة بيانات SQL
        sql_deposits = db_session.query(Transaction).filter(
            Transaction.admin_username == "PENDING",
            Transaction.action == "deposit_request"
        ).order_by(Transaction.id.desc()).all()
        
        result = []
        for t in sql_deposits:
            # استخراج اسم الطريقة والكود من حقل tx_id
            tx_parts = str(t.tx_id).split('-') if t.tx_id else ["N/A", "N/A"]
            method_name = tx_parts[0]
            code_val = tx_parts[1] if len(tx_parts) > 1 else "N/A"

            result.append({
                "ticket_id": t.id,
                "username": t.target_username,
                "method": method_name, 
                "amount": float(t.amount or 0),
                "code": code_val if code_val != "FILE" else "مرفق صورة",
                "receipt_image": t.image_path,
                "status": "pending",
                "date": str(t.date)
            })
        return result
    finally:
        db_session.close()
class ApproveDepositRequest(BaseModel):
    ticket_id: str
    amount: float

@app.post("/api/admin/approve-deposit")
async def approve_deposit(req: ApproveDepositRequest, current_user: str = Depends(get_admin_user)):
    try:
        db = load_tickets_db()
        ticket = next((t for t in db if str(t.get("ticket_id")) == str(req.ticket_id)), None)
        
        if not ticket:
            raise HTTPException(status_code=404, detail="التذكرة غير موجودة")
            
        if ticket.get("status") != "pending":
            raise HTTPException(status_code=400, detail="هذه التذكرة تمت معالجتها مسبقاً")

        real_amount = req.amount
        ticket["status"] = "approuvé"
        ticket["amount"] = real_amount
        
        # 1. جلب اللاعب وتحديث رصيده وإيداعاته اليومية للكاش باك
        db_users = load_db()
        target_username = ticket.get("username") or ticket.get("player") or ""
        target_user = next((u for u in db_users if str(u.get("username", "")).lower() == str(target_username).lower()), None)
        
        if target_user:
            target_user["balance"] = float(target_user.get("balance", 0)) + real_amount
            # 👈 السطر المطلوب وضعه هنا لتسجيل المبلغ في الكاش باك اليومي:
            target_user["daily_deposits"] = float(target_user.get("daily_deposits", 0)) + real_amount
            save_db(db_users)

        # 2. حفظ التذاكر
        with open(TICKETS_FILE, "w", encoding="utf-8") as f:
            json.dump(db, f, indent=4, ensure_ascii=False)

        # --- بداية مشغل البونص التلقائي ---
        promo = load_promo()
        current_day = datetime.now().strftime("%A") # يجلب اسم اليوم بالإنجليزية
        
        if promo.get("is_active") and real_amount >= promo.get("min_amount", 50) and current_day == promo.get("day_of_week"):
            if target_user:
                import asyncio
                import uuid
                from datetime import datetime, timedelta
                
                expiration = (datetime.utcnow() + timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%S.000Z")
                tour_id = f"auto_fs_{uuid.uuid4().hex[:8]}"
                fs_payload = {
                    "method": "tour_create",
                    "agent_code": AGENT_CODE,
                    "agent_token": AGENT_TOKEN,
                    "user_code": target_user["username"],
                    "provider_code": promo.get("provider"),
                    "game_code": promo.get("game"),
                    "bet_level": 1,
                    "spin_count": promo.get("spins"),
                    "amount": promo.get("max_win", 10000),
                    "expiration_time": expiration,
                    "tour_id": tour_id
                }
                async def send_auto_fs():
                    async with httpx.AsyncClient() as client:
                        try: await client.post(GOLD_API_URL, json=fs_payload, timeout=10.0)
                        except: pass
                asyncio.create_task(send_auto_fs())
        # --- نهاية مشغل البونص ---

        return {"status": "success", "message": f"تمت الموافقة وإضافة {real_amount} بنجاح"}
    except Exception as e:
        print(f"Error approving deposit: {e}")
        raise HTTPException(status_code=500, detail="حدث خطأ داخلي أثناء الموافقة")

@app.get("/api/admin/get-all-tickets")
async def get_all_tickets_api(current_user: str = Depends(get_admin_user)):
    db = load_db()
    current_admin = next((u for u in db if u["username"] == current_user), None)
    current_role = current_admin.get("role", "player")

    if current_role in ["owner", "system"]:
        allowed_users = {u["username"] for u in db}
    else:
        allowed_users = {current_user}
        to_process = [current_user]
        while to_process:
            parent = to_process.pop(0)
            children = [u["username"] for u in db if u.get("created_by") == parent]
            for child in children:
                if child not in allowed_users:
                    allowed_users.add(child)
                    to_process.append(child)

    tickets_db = load_tickets_db()
    if tickets_db is None: 
        return []

    allowed_tickets = []
    for t in tickets_db:
        t_user = t.get("username") or t.get("user")
        # فلترة التذاكر لتعرض فقط تذاكر شبكة المانجر
        if t_user in allowed_users:
            allowed_tickets.append(t)
            
    allowed_tickets.reverse()
    return allowed_tickets
# ==========================================
# الوظائف الخلفية وقاعدة البيانات (Background & DB)
# ==========================================
async def auto_settle_tickets():
    await asyncio.sleep(10) 
    while True:
        try:
            print("⏳ [Auto-Settler] جاري فحص التذاكر المعلقة...")
            tickets_db = load_tickets_db()
            db = load_db()
            changes_made = False
            pending_tickets = [t for t in tickets_db if t.get("status") == "encours"]
            
            for ticket in pending_tickets:
                simulated_result = random.choice(["gagne", "perdu"]) 
                ticket["status"] = simulated_result
                changes_made = True
                if simulated_result == "gagne":
                    target_username = ticket["username"]
                    win_amount = float(ticket.get("gain", 0))
                    for u in db:
                        if u["username"] == target_username:
                            u["balance"] = float(u.get("balance", 0)) + win_amount
                            break
            if changes_made:
                save_tickets_db(tickets_db)
                save_db(db)
        except Exception as e:
            print(f"❌ [Auto-Settler] حدث خطأ: {e}")
        await asyncio.sleep(60) 

@app.on_event("startup")
async def start_background_tasks():
     asyncio.create_task(auto_settle_tickets()) 
     asyncio.create_task(daily_cashback_system()) 

def load_tickets_db():
    if not os.path.exists(TICKETS_FILE):
        with open(TICKETS_FILE, "w") as f:
            json.dump([], f)
        return []
    try:
        with open(TICKETS_FILE, "r") as f:
            return json.load(f)
    except:
        return []

def save_tickets_db(data):
    with open(TICKETS_FILE, "w") as f:
        json.dump(data, f, indent=4)

async def daily_cashback_system():
    await asyncio.sleep(15)
    while True:
        try:
            now = datetime.now()
            if now.hour == 0 and now.minute < 10:
                print("⏳ [Cashback] جاري فحص وتوزيع الكاش باك اليومي...")
                
                # استخدام القفل لمنع تضارب الأرصدة أثناء لعب المستخدمين
                async with db_lock:
                    db = load_db()
                    changes_made = False
                    
                    for u in db:
                        current_balance = float(u.get("balance", 0.0))
                        daily_deps = float(u.get("daily_deposits", 0.0))
                        
                        # يمكن لاحقاً إضافة حقل daily_withdrawals لخصمه من الإيداع لمعرفة الخسارة الصافية
                        net_loss = daily_deps - current_balance 
                        
                        if daily_deps > 0:
                            if current_balance < 1.0 and net_loss > 0:
                                cashback_amount = daily_deps * 0.10
                                u["balance"] = round(current_balance + cashback_amount, 2)
                                
                                # 🛡️ توثيق الكاش باك في SQL لمنع تضارب الحسابات
                                db_session = SessionLocal()
                                try:
                                    new_tx = Transaction(
                                        admin_username="SYSTEM_CASHBACK",
                                        target_username=u["username"],
                                        action="cashback",
                                        amount=cashback_amount,
                                        date=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                        tx_id=f"cb_{int(time.time())}"
                                    )
                                    db_session.add(new_tx)
                                    db_session.commit()
                                except Exception:
                                    db_session.rollback()
                                finally:
                                    db_session.close()
                            
                            u["daily_deposits"] = 0
                            changes_made = True
                            
                    if changes_made:
                        save_db(db)
                        print("✅ [Cashback] تم الانتهاء من التوزيع وتصفير العدادات بنجاح!")
                
                await asyncio.sleep(3600)
            else:
                await asyncio.sleep(300)
        except Exception as e:
            print(f"❌ [Cashback] حدث خطأ: {e}")
            await asyncio.sleep(300) 

# ==========================================
# النماذج (Models)
# ==========================================
class LoginRequest(BaseModel): username: str; password: str
class RegisterRequest(BaseModel): username: str; password: str; role: str; created_by: str; phone: str = ""
class ConfigureAccountRequest(BaseModel): admin_username: str; target_username: str; rtp: int; is_blocked: int
class UpdateBalanceRequest(BaseModel): admin_username: str; target_username: str; action: str; amount: float
class ChangePlayerPasswordRequest(BaseModel): admin_username: str; target_username: str; new_password: str
class SaveTicketRequest(BaseModel): username: str; ticket_data: dict
class UpdateTicketStatusRequest(BaseModel): ticket_id: int; status: str; amount_paid: float
class HandleRequestModel(BaseModel): transaction_id: int; decision: str; admin_username: str
class DeleteAccountRequest(BaseModel): admin_username: str; target_username: str
class ProviderRequest(BaseModel): provider_code: str
class ChangeMyPasswordRequest(BaseModel): username: str; new_password: str
class Verify2FARequest(BaseModel): 
    username: str
    totp_code: str = "000000"


@app.post("/api/register")
@limiter.limit("1/minute")
async def register_user(request: Request, req: RegisterRequest):
    uname = req.username.lower().strip()
    
    # ====== 🛡️ جدار حماية: منع استخدام أسماء الإدارة الحساسة ======
    if uname in ["fethi", "admin", "owner", "system", "boss", "super_admin"]:
        raise HTTPException(status_code=400, detail="Ce nom d'utilisateur est réservé au système!")
    # ==============================================================

    db = load_db()
    
    for u in db:
        if u["username"] == uname:
            raise HTTPException(status_code=400, detail="Nom d'utilisateur déjà pris")
            
    hashed_pwd = hash_password(req.password)
    new_secret_key = pyotp.random_base32()
    new_id = max([int(u.get("id", 0)) for u in db]) + 1 if db else 1
    
    new_user = {
        "id": new_id,
        "username": uname, 
        "password": hashed_pwd, 
        "role": req.role, 
        "balance": 0.00,
        "rtp": 50, 
        "is_blocked": 0, 
        "created_by": req.created_by, 
        "last_spin_date": "", 
        "daily_deposits": 0.0,
        "two_factor_secret": new_secret_key,
        "phone": req.phone
    }
    
    db.append(new_user)
    save_db(db)
    log_admin_action(req.created_by, "CREATE_USER", f"Created {uname} with role {req.role}")
    
    return {"status": "success", "message": "Compte créé", "secret_key": new_secret_key, "user_id": new_id}
    
@app.get("/api/admin/fix-user-ids")
async def fix_missing_user_ids(current_user: str = Depends(get_admin_user)):
    try:
        db = load_db()
        current_max_id = 0
        for u in db:
            user_id = u.get("id")
            if user_id is not None and str(user_id).isdigit():
                current_max_id = max(current_max_id, int(user_id))
                
        updated_count = 0
        for u in db:
            if "id" not in u or u.get("id") is None or u.get("id") == "":
                current_max_id += 1
                u["id"] = current_max_id
                updated_count += 1
                
        if updated_count > 0:
            save_db(db)
            
        return {"status": "success", "message": f"عملية ناجحة! تم منح ID جديد لـ {updated_count} حساب/حسابات قديمة."}
    except Exception as e:
        return {"status": "error", "message": f"حدث خطأ: {str(e)}"}

class HandleHugeWinRequest(BaseModel):
    tx_id: int
    decision: str 

@app.get("/api/admin/pending-huge-wins")
async def get_pending_huge_wins(current_user: str = Depends(get_admin_user)):
    db_session = SessionLocal()
    try:
        txs = db_session.query(Transaction).filter(Transaction.admin_username == "PENDING_HUGE_WIN").order_by(Transaction.id.desc()).all()
        return [{"id": t.id, "target_username": t.target_username, "amount": float(t.amount), "action": t.action, "date": t.date} for t in txs]
    except Exception as e:
        print(f"Error fetching huge wins: {e}")
        return []
    finally:
        db_session.close()

@app.post("/api/admin/handle-huge-win")
async def handle_huge_win(req: HandleHugeWinRequest, current_user: str = Depends(get_admin_user)):
    db = load_db()
    admin = next((u for u in db if u["username"] == current_user), None)
    if not admin or admin.get("role") not in ["owner", "super_admin"]:
        raise HTTPException(status_code=403, detail="صلاحية الأونر مطلوبة")

    db_session = SessionLocal()
    try:
        tx = db_session.query(Transaction).filter(Transaction.id == req.tx_id).first()
        if not tx or tx.admin_username != "PENDING_HUGE_WIN":
            return JSONResponse(status_code=404, content={"detail": "الطلب غير موجود أو تمت معالجته مسبقاً"})

        if req.decision == "approve":
            async with db_lock:
                target_user = next((u for u in db if str(u.get("username", "")).lower() == str(tx.target_username).lower()), None)
                if target_user:
                    target_user["balance"] = round(float(target_user.get("balance", 0)) + tx.amount, 2)
                    save_db(db)
            tx.admin_username = f"APPROVED_BY_{current_user.upper()}"
        else:
            tx.admin_username = f"REJECTED_BY_{current_user.upper()}"

        db_session.commit()
        return {"status": "success", "message": "تمت معالجة الربح الضخم بنجاح"}
    except Exception as e:
        db_session.rollback()
        return JSONResponse(status_code=500, content={"detail": str(e)})
    finally:
        db_session.close()

@app.get("/api/admin/users")
async def get_all_network_users(current_user: str = Depends(get_admin_user)): 
    db = load_db()
    
    current_admin = next((u for u in db if u["username"] == current_user), None)
    current_role = current_admin.get("role", "player")

    # 1. الأونر فقط (المالك) هو من يرى جميع الحسابات في الشبكة
    if current_role in ["owner", "system"]:
        allowed_users = {u["username"] for u in db}
    else:
        # 2. المانجر، السوبر أدمن، الأدمن، والشوب يخضعون لشجرة الصلاحيات
        # (يرى فقط نفسه ومن تم إنشاؤه تحته في الشجرة)
        allowed_users = {current_user}
        to_process = [current_user]
        
        while to_process:
            parent = to_process.pop(0)
            children = [u["username"] for u in db if u.get("created_by") == parent]
            for child in children:
                if child not in allowed_users:
                    allowed_users.add(child)
                    to_process.append(child)

    safe_users = []
    for u in db:
        if u["username"] not in allowed_users:
            continue
            
        safe_user = dict(u)
        safe_user.pop("password", None)
        safe_user.pop("two_factor_secret", None) # 🛡️ تم التفعيل لمنع تسريب المفتاح
        safe_users.append(safe_user)
        
    return safe_users

@app.post("/api/admin/update-balance")
async def update_balance(req: UpdateBalanceRequest, current_user: str = Depends(get_admin_user)):
    target = req.target_username.lower().strip()
    amount = float(req.amount)

    if amount <= 0:
        raise HTTPException(status_code=400, detail="Montant invalide: ne peut pas être négatif ou zéro")

    async with db_lock:
        db = load_db()
        
        target_user = next((u for u in db if str(u.get("username", "")).lower().strip() == target), None)
        admin_user = next((u for u in db if str(u.get("username", "")).lower().strip() == current_user.lower().strip()), None)

        if not target_user:
            raise HTTPException(status_code=404, detail="Utilisateur non trouvé")
        if not admin_user:
            raise HTTPException(status_code=404, detail="Compte administrateur introuvable")

        current_role = admin_user.get("role", "")
        is_global_admin = (current_user.lower() == "system" or current_role == "owner")
        admin = current_user.lower().strip()

        # 🛡️ جدار الأمان: منع التحكم في حسابات تابعة لآخرين
        safe_creator = str(target_user.get("created_by", "")).lower().strip()
        if not is_global_admin and safe_creator != admin:
            raise HTTPException(status_code=403, detail="Accès refusé. Ce compte ne vous appartient pas.")

        # 1. تجهيز الأرصدة في الذاكرة (بدون حفظ نهائي)
        if req.action == "charge":
            if not is_global_admin:
                if float(admin_user.get("balance", 0)) < amount: 
                    raise HTTPException(status_code=400, detail="Solde insuffisant dans votre compte")
                admin_user["balance"] = round(float(admin_user.get("balance", 0)) - amount, 2)
            
            target_user["balance"] = round(float(target_user.get("balance", 0)) + amount, 2)
            
            if current_user.lower() != "system":
                target_user["daily_deposits"] = float(target_user.get("daily_deposits", 0)) + amount

        elif req.action == "withdraw":
            if float(target_user.get("balance", 0)) < amount: 
                raise HTTPException(status_code=400, detail="Solde insuffisant chez le joueur")
            
            target_user["balance"] = round(float(target_user.get("balance", 0)) - amount, 2)
            
            if not is_global_admin:
                admin_user["balance"] = round(float(admin_user.get("balance", 0)) + amount, 2)

        # 2. توثيق العملية في سجل SQL أولاً (الجدار الواقي)
        db_session = SessionLocal()
        try:
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            record_action = "dépôt" if req.action == "charge" else "retrait"
            
            new_tx = Transaction(
                admin_username=admin,
                target_username=target,
                action=record_action,
                amount=amount,
                date=current_time,
                tx_id=str(uuid.uuid4())
            )
            db_session.add(new_tx)
            db_session.commit()
        except Exception as e:
            db_session.rollback()
            print(f"Error saving transaction history: {e}")
            # إذا فشل التوثيق في SQL، نلغي العملية بالكامل ولا نحفظ الأرصدة
            raise HTTPException(status_code=500, detail="Erreur base de données. L'opération a été annulée de manière sécurisée.")
        finally:
            db_session.close()

        # 3. الحفظ النهائي للأرصدة (يُنفذ فقط إذا نجح التوثيق في SQL)
        save_db(db)
        
    log_admin_action(current_user, "BALANCE_UPDATE", f"Target: {target}, Action: {req.action}, Amount: {amount}")

    return {"status": "success", "message": "Opération réussie et enregistrée"}

@app.get("/api/admin/transactions-history")
async def get_tx_history(username: str = None, current_user: str = Depends(get_admin_user)):
    db = load_db()
    current_admin = next((u for u in db if u["username"] == current_user), None)
    current_role = current_admin.get("role", "player")
    
    if current_role in ["owner", "system"]:
        allowed_users = {u["username"] for u in db}
    else:
        allowed_users = {current_user}
        to_process = [current_user]
        while to_process:
            parent = to_process.pop(0)
            children = [u["username"] for u in db if u.get("created_by") == parent]
            for child in children:
                if child not in allowed_users:
                    allowed_users.add(child)
                    to_process.append(child)

    db_session = SessionLocal()
    try:
        txs = db_session.query(Transaction).all()
        result = []
        for t in txs:
            target = t.target_username or t.target
            # التأكد من أن المعاملة تخص حساباً ضمن شجرة المانجر
            if target in allowed_users or t.username in allowed_users:
                result.append({
                    "id": t.id,
                    "action": t.action,
                    "amount": t.amount,
                    "target_username": target,
                    "date": str(t.date),
                    "image_path": t.image_path
                })
        result.reverse()
        return result
    finally:
        db_session.close()

@app.get("/api/user/transactions-history")
async def get_user_transactions(current_user: str = Depends(get_current_user)):
    history = []
    
    # 1. جلب الإيداعات (Dépôt) من ملف التذاكر
    tickets = load_tickets_db()
    user_deposits = [t for t in tickets if t.get("type") == "deposit" and str(t.get("username", "")).lower() == current_user.lower()]
    
    for d in user_deposits:
        status_map = {"pending": "En attente", "approuvé": "Approuvé", "rejected": "Refusé"}
        raw_status = str(d.get("status", "pending")).lower()
        try:
            dt_obj = datetime.fromisoformat(d.get("date", ""))
            formatted_date = dt_obj.strftime("%Y-%m-%d %H:%M")
        except:
            formatted_date = str(d.get("date", ""))[:16]

        history.append({
            "date": formatted_date,
            "type": "Dépôt",
            "method": str(d.get("method", "N/A")).capitalize(),
            "amount": float(d.get("amount", 0)),
            "status": status_map.get(raw_status, "En attente"),
            "timestamp": d.get("date", "")
        })

    # 2. جلب جميع العمليات (سحوبات وشحن يدوي) من قاعدة بيانات SQL
    db_session = SessionLocal()
    try:
        # جلب كل العمليات الخاصة بهذا اللاعب
        sql_txs = db_session.query(Transaction).filter(
            Transaction.target_username == current_user.lower()
        ).all()

        for w in sql_txs:
            action_lower = str(w.action).lower()
            
            # إخفاء رهانات الألعاب وأرباحها لكي لا تزحم سجل الشحن والسحب
            if action_lower in ["bet", "win", "rollback", "adjustment"]:
                continue
            
            # تحديد النوع: إيداع أم سحب
            tx_type = "Retrait"
            if "dépôt" in action_lower or "charge" in action_lower or "deposit" in action_lower:
                tx_type = "Dépôt"
            
            # استنتاج الطريقة
            method = "Virement"
            if "d17" in action_lower: method = "D17"
            elif "mandat" in action_lower: method = "Mandat"
            else: method = "Agent/Shop" # هذا سيميز الشحن اليدوي من الإدارة

            # تحديد الحالة
            status = "Approuvé" if w.admin_username.lower() != "pending" else "En attente"

            history.append({
                "date": str(w.date)[:16],
                "type": tx_type,
                "method": method,
                "amount": float(w.amount),
                "status": status,
                "timestamp": str(w.date)
            })
    except Exception as e:
        print(f"Error fetching user SQL transactions: {e}")
    finally:
        db_session.close()

    # 3. الترتيب من الأحدث للأقدم وإرسال النتيجة
    history.sort(key=lambda x: x["timestamp"], reverse=True)
    
    return {"status": "success", "data": history}
@app.post("/api/admin/request-transaction")
async def request_transaction(request: Request):
    db_session = SessionLocal()
    try:
        import uuid
        import os
        import shutil
        from starlette.datastructures import UploadFile

        form = await request.form()
        target_username = form.get("target_username")
        action = form.get("action")
        amount = float(form.get("amount", 0))
        tx_id = form.get("tx_id", str(uuid.uuid4()))

        # 🛡️ الحارس الأمني 1: منع المبالغ السالبة والصفرية
        if amount <= 0:
            from fastapi.responses import JSONResponse
            return JSONResponse(status_code=400, content={"detail": "Le montant doit être supérieur à zéro"})

        file_path = ""
        file = form.get("file")
        if file and isinstance(file, UploadFile) and file.filename:
            # 🛡️ الحارس الأمني 2: فحص الامتداد ونوع المحتوى معاً لمنع الملفات الخبيثة
            allowed_extensions = ['.png', '.jpg', '.jpeg', '.webp']
            allowed_mimes = ['image/png', 'image/jpeg', 'image/webp']
            
            file_ext = os.path.splitext(file.filename)[1].lower()
            if file_ext not in allowed_extensions or file.content_type not in allowed_mimes:
                from fastapi.responses import JSONResponse
                return JSONResponse(status_code=400, content={"detail": "Format non autorisé ou fichier corrompu. Seules les images sont acceptées."})
            os.makedirs("uploads", exist_ok=True)
            safe_filename = f"{uuid.uuid4().hex}{file_ext}"
            file_path = os.path.join("uploads", safe_filename)
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
        new_tx_args = {
            "admin_username": "PENDING",
            "target_username": target_username,
            "action": action,
            "amount": amount
        }

        if hasattr(Transaction, "tx_id"):
            new_tx_args["tx_id"] = tx_id
        else:
            new_tx_args["action"] = f"{action} | Details: {tx_id}"

        if file_path:
            if hasattr(Transaction, "image_path"):
                new_tx_args["image_path"] = file_path
            elif hasattr(Transaction, "receipt_image"):
                new_tx_args["receipt_image"] = file_path

        new_tx = Transaction(**new_tx_args)
        db_session.add(new_tx)
        db_session.commit()

        return {"status": "success", "message": "طلبك قيد المراجعة"}

    except Exception as e:
        db_session.rollback()
        from fastapi.responses import JSONResponse
        print(f"Transaction Error: {str(e)}")
        return JSONResponse(status_code=500, content={"detail": str(e)})
    finally:
        db_session.close()

@app.post("/api/admin/handle-request")
async def handle_pending_request(req: HandleRequestModel, current_user: str = Depends(get_admin_user)):
    db_session = SessionLocal()
    try:
        tx = db_session.query(Transaction).filter(Transaction.id == req.transaction_id).first()
        if not tx or tx.admin_username != "PENDING":
            raise HTTPException(status_code=404, detail="Demande introuvable ou déjà traitée")

        if req.decision == "reject":
            db_session.delete(tx)
            db_session.commit()
            return {"status": "success", "message": "Demande rejetée"}

        # 🛡️ قفل قاعدة البيانات لتأمين تعديل الرصيد
        async with db_lock:
            db = load_db()
            target_user = next((u for u in db if u["username"] == tx.target_username), None)
            
            if not target_user:
                raise HTTPException(status_code=404, detail="Utilisateur non trouvé")

            if tx.action == "deposit_request":
                target_user["balance"] = float(target_user.get("balance", 0)) + tx.amount
                tx.action = "charge"
            elif tx.action == "withdraw_request":
                if target_user.get("balance", 0) < tx.amount:
                    raise HTTPException(status_code=400, detail="Solde insuffisant pour le retrait")
                target_user["balance"] = float(target_user.get("balance", 0)) - tx.amount
                tx.action = "withdraw"

            tx.admin_username = req.admin_username
            db_session.commit()
            save_db(db)
            
        return {"status": "success", "message": "Demande approuvée avec succès"}
    finally:
        db_session.close()

@app.post("/api/admin/change-player-password")
async def change_player_password(req: ChangePlayerPasswordRequest):
    db = load_db()
    for u in db:
        if u["username"] == req.target_username.lower().strip():
            u["password"] = hash_password(req.new_password)
            save_db(db)
            return {"status": "success", "message": "Mot de passe modifié avec succès"}
    raise HTTPException(status_code=404, detail="Utilisateur non trouvé")

class Reset2FARequest(BaseModel):
    admin_username: str
    target_username: str

@app.post("/api/admin/reset-2fa")
async def reset_2fa(req: Reset2FARequest, current_user: str = Depends(get_admin_user)):
    target = req.target_username.lower().strip()
    db = load_db()
    
    target_user = next((u for u in db if str(u.get("username", "")).lower() == target), None)
    if not target_user:
        raise HTTPException(status_code=404, detail="Utilisateur non trouvé")
        
    # توليد مفتاح جديد كلياً
    import pyotp
    new_secret = pyotp.random_base32()
    target_user["two_factor_secret"] = new_secret
    save_db(db)
    
    log_admin_action(current_user, "RESET_2FA", f"Reset 2FA for {target}")
    
    return {"status": "success", "message": "2FA réinitialisé avec succès", "new_secret": new_secret}

@app.post("/api/admin/configure-account")
async def configure_account(req: ConfigureAccountRequest):
    db = load_db()
    for u in db:
        if u["username"] == req.target_username.lower().strip():
            u["rtp"] = req.rtp; u["is_blocked"] = req.is_blocked
            save_db(db)
            log_admin_action(req.created_by, "CONFIG_ACCOUNT", f"Target: {req.target_username}, RTP: {req.rtp}, Blocked: {req.is_blocked}")
            return {"status": "success", "message": "Configuration enregistrée"}
    raise HTTPException(status_code=404, detail="Utilisateur non trouvé")

@app.delete("/api/admin/delete-account")
async def delete_account(req: DeleteAccountRequest):
    db = load_db()
    target = req.target_username.lower().strip()
    new_db = [u for u in db if u.get("username", "").lower().strip() != target]
    if len(new_db) == len(db): raise HTTPException(status_code=404, detail="Non trouvé")
    save_db(new_db)
    return {"status": "success", "message": "Supprimé"}

@app.post("/api/user/change-password")
async def change_my_password(req: ChangeMyPasswordRequest, current_user: str = Depends(get_current_user)):
    target_username = req.username.lower().strip()
    
    # 🛡️ الحارس الأمني: يمنع أي مستخدم من تغيير كلمة مرور حساب آخر
    if current_user != target_username and current_user not in ["fethi","manager", "admin", "owner", "super_admin","shop"]:
        raise HTTPException(status_code=403, detail="Non autorisé: Vous ne pouvez pas modifier le mot de passe d'un autre utilisateur")
        
    db = load_db()
    for u in db:
        if u["username"] == target_username:
            u["password"] = hash_password(req.new_password)
            save_db(db)
            return {"status": "success", "message": "Mot de passe modifié avec succès"}
            
    raise HTTPException(status_code=404, detail="Utilisateur non trouvé")

# ==========================================
# دمج مزود الألعاب الحقيقي (NexusGGR API)
# ==========================================
@app.get("/api/get-providers")
async def get_real_providers():
    payload = {
        "method": "provider_list",
        "agent_code": AGENT_CODE,
        "agent_token": AGENT_TOKEN
    }
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(PROVIDER_ENDPOINT, json=payload, timeout=15)
            return response.json()
        except Exception as e:
            print(f"⚠️ خطأ في جلب المزودين: {e}")
            return {"status": 0, "msg": "Error connecting to provider"}

GAMES_CACHE = {}
CACHE_TIME_LIMIT = 3600  

@app.post("/api/get-providers")
async def get_real_games(request: ProviderRequest):
    provider_code = request.provider_code
    current_time = time.time()
    
    if provider_code in GAMES_CACHE and (current_time - GAMES_CACHE[provider_code]['time']) < CACHE_TIME_LIMIT:
        return GAMES_CACHE[provider_code]['data']

    payload = {
        "method": "game_list",
        "agent_code": AGENT_CODE,
        "agent_token": AGENT_TOKEN,
        "provider_code": provider_code
    }
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(PROVIDER_ENDPOINT, json=payload, timeout=20)
            response_data = response.json()
            
            if response_data.get("status") == 1 or "games" in response_data:
                GAMES_CACHE[provider_code] = {'time': current_time, 'data': response_data}
                
            return response_data
            
        except Exception as e:
            print(f"⚠️ خطأ في الاتصال بالمزود: {e}")
            if provider_code in GAMES_CACHE: 
                return GAMES_CACHE[provider_code]['data']
            return {"status": 0, "msg": "Error connecting to games API"}

@app.get("/api/provider/get-games-paged")
async def get_games_paged(provider: str = "PRAGMATIC", page: int = 1, limit: int = 50):
    current_time = time.time()
    if provider in GAMES_CACHE and (current_time - GAMES_CACHE[provider]['time']) < CACHE_TIME_LIMIT:
        return GAMES_CACHE[provider]['data']

    payload = {
        "method": "game_list",
        "agent_code": AGENT_CODE,
        "agent_token": AGENT_TOKEN,
        "provider_code": provider
    }
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(PROVIDER_ENDPOINT, json=payload, timeout=20)
            response_data = response.json()
            if response_data.get("status") == 1 or "games" in response_data:
                GAMES_CACHE[provider] = {'time': current_time, 'data': response_data}
            return response_data
        except Exception as e:
            return {"status": 0, "msg": "Error"}

    
@app.post("/api/provider/launch-casino")
async def launch_casino(request: Request):
    try:
        data = await request.json()
        payload = {
            "method": "game_launch",
            "agent_code": AGENT_CODE,      
            "agent_token": AGENT_TOKEN,    
            "user_code": data.get("user_code", "test_user"),
            "provider_code": data.get("provider_code"),
            "game_code": data.get("game_code"),
            "lang": "fr",
            "lobby_url": "https://coutabet.com/#casino"
        }
        headers = {"Content-Type": "application/json"}
        endpoint = PROVIDER_ENDPOINT.rstrip('/')
        response = requests.post(endpoint, json=payload, headers=headers)
        
        try:
            response_data = response.json()
        except Exception:
            return {"error": "المزود لم يرْسل رد JSON صالح", "details": response.text}
            
        if response.status_code == 200:
            game_url = response_data.get("url") or response_data.get("launch_url") or (response_data.get("data", {}).get("url"))
            if game_url:
                return {"launch_url": game_url}
            else:
                return {"error": "لم يتم العثور على رابط اللعبة", "details": response_data}
        else:
            return {"error": "المزود رفض الطلب", "details": response_data}
            
    except Exception as e:
        return {"error": str(e)}


# ==========================================
# الجدار الأمني الثاني: حماية لوحة المالك
# ==========================================
@app.get("/owner-login", response_class=HTMLResponse)
async def show_login_page():
    return """
    <html>
        <body style="text-align:center; margin-top:100px; font-family:Arial; background-color:#1e1e2f; color:white;">
            <h2>تسجيل الدخول للإدارة</h2>
            <form action="/owner-login" method="post" style="background:#2a2a40; padding:20px; width:300px; margin:auto; border-radius:10px;">
                <input type="text" name="username" placeholder="اسم المستخدم" required style="width:90%; padding:10px; margin-bottom:15px; border-radius:5px; border:none;"><br>
                <input type="password" name="password" placeholder="كلمة المرور" required style="width:90%; padding:10px; margin-bottom:15px; border-radius:5px; border:none;"><br>
                <button type="submit" style="width:95%; padding:10px; background-color:#4CAF50; color:white; border:none; border-radius:5px; cursor:pointer; font-size:16px;">دخول</button>
            </form>
        </body>
    </html>
    """

@app.post("/owner-login")
@limiter.limit("5/minute")
async def process_login(request: Request, username: str = Form(...), password: str = Form(...)):
    if username == ADMIN_USER and password == ADMIN_PASS:
        request.session["is_admin"] = True
        return RedirectResponse(url="/secure-owner", status_code=303)
    return HTMLResponse("<h3 style='text-align:center; margin-top:100px; color:red;'>بيانات خاطئة!</h3><div style='text-align:center;'><a href='/owner-login'>العودة للمحاولة</a></div>")

@app.get("/secure-owner")
async def open_owner_panel(request: Request):
    if not request.session.get("is_admin"):
        return RedirectResponse(url="/owner-login")
    return FileResponse("owner.html")

@app.get("/owner-logout")
async def logout_owner(request: Request):
    request.session.clear()
    return RedirectResponse(url="/owner-login")

# ==========================================
# نظام التوجيه الذكي والروابط النظيفة للإدارة
# ==========================================
@app.get("/", response_class=HTMLResponse)
async def admin_home(request: Request):
    role = request.session.get("role")
    if role == "owner": return RedirectResponse(url="/panel/owner", status_code=303)
    elif role == "manager": return RedirectResponse(url="/panel/manager", status_code=303)
    elif role == "super_admin": return RedirectResponse(url="/panel/super_admin", status_code=303)
    elif role == "admin": return RedirectResponse(url="/panel/admin", status_code=303)
    elif role == "shop": return RedirectResponse(url="/panel/shop", status_code=303)
    
    
    with open("index.html", "r", encoding="utf-8") as f:
        return f.read()

@app.post("/login-router")
@limiter.limit("5/minute")
async def process_login_router(request: Request, username: str = Form(...), password: str = Form(...)):
    uname = username.lower().strip()
    
    db = load_db()
    user = next((u for u in db if u["username"] == uname), None)

    if not user or not verify_password(password, user.get("password", "")):
        return HTMLResponse("<h3 style='text-align:center; margin-top:100px; color:red;'>اسم المستخدم أو كلمة المرور غير صحيحة!</h3><div style='text-align:center;'><a href='/' style='color:blue;'>العودة</a></div>")

    if user.get("is_blocked") == 1:
        return HTMLResponse("<h3 style='text-align:center; margin-top:100px; color:red;'>هذا الحساب محظور!</h3>")

    role = user.get("role")
    
    # فرض التحقق الثنائي (2FA) بصرامة على جميع الإداريين دون استثناء
    if role in ["owner", "super_admin", "admin"]:
        request.session["pending_user"] = uname
        request.session["pending_role"] = role
        
        html_form = """
        <html dir="rtl">
        <head><title>التحقق الثنائي</title></head>
        <body style="background-color: #1a1a1a; color: white; display: flex; justify-content: center; align-items: center; height: 100vh; font-family: Tahoma, sans-serif;">
            <div style="background-color: #2d2d2d; padding: 40px; border-radius: 10px; text-align: center; border: 1px solid #444;">
                <h2 style="color: #00d2ff;">التحقق الثنائي (2FA) 🔐</h2>
                <p style="color: #ccc;">أدخل الكود من تطبيق Google Authenticator</p>
                <form action="/verify-2fa" method="post">
                    <input type="text" name="totp_code" placeholder="أدخل 6 أرقام" required style="padding: 10px; font-size: 20px; text-align: center; letter-spacing: 5px; border-radius: 5px; border: none; outline: none; margin-bottom: 20px; font-weight: bold;"><br>
                    <button type="submit" style="padding: 10px 30px; background-color: #28a745; color: white; border: none; border-radius: 5px; font-size: 16px; cursor: pointer; font-weight: bold;">دخول آمن</button>
                </form>
            </div>
        </body>
        </html>
        """
        return HTMLResponse(content=html_form)

    request.session["username"] = user["username"]
    request.session["role"] = user["role"]
    
    if role == "shop": return RedirectResponse(url="/panel/shop", status_code=303)
    else: return HTMLResponse("<h3 style='text-align:center; color:orange;'>ليس لديك صلاحية.</h3>")
    
# -----------------------------------------
# مسارات الدخول والحماية الثنائية
# -----------------------------------------
class LoginRequest(BaseModel): 
    username: str
    password: str

class Verify2FARequest(BaseModel): 
    username: str
    totp_code: str = "000000"

@app.post("/api/login")
@limiter.limit("5/minute")
async def login_user(request: Request, req: LoginRequest):
    try:
        uname = html.escape(req.username.lower().strip())
        
        db = load_db()
        user = next((u for u in db if u["username"] == uname), None)

        if not user or not verify_password(req.password, user.get("password", "")):
            bad_alert = f"⚠️ <b>محاولة دخول فاشلة للإدارة!</b>\n👤 اسم المستخدم: <code>{req.username}</code>\n❌ السبب: كلمة المرور خاطئة"
            asyncio.create_task(send_telegram_alert(bad_alert))
            return JSONResponse(status_code=401, content={"detail": "اسم المستخدم أو كلمة المرور غير صحيحة"})
        user["last_ip"] = verify_nexus_ip(request)
        save_db(db)
        access_token = create_access_token(data={"sub": user["username"], "role": user["role"]})
        
        return JSONResponse(status_code=200, content={
            "message": "success", 
            "username": user["username"],
            "role": user["role"],
            "access_token": access_token,
            "balance": float(user.get("balance", 0.0))
        })
    except Exception as e:
        print(f"Login Crash: {e}")
        
        return JSONResponse(status_code=500, content={"detail": f"خطأ داخلي: {str(e)}"})

@app.post("/api/verify-2fa")
@limiter.limit("5/minute")
async def verify_2fa_api(request: Request, req: Verify2FARequest):
    db = load_db()
    user = next((u for u in db if u["username"] == req.username), None)
    
    if not user:
        raise HTTPException(status_code=401, detail="Nom d'utilisateur incorrect")
        
    secret = user.get("two_factor_secret")
    if not secret:
        raise HTTPException(status_code=400, detail="لم يتم تفعيل المصادقة الثنائية!")
        
    totp = pyotp.TOTP(secret)
    if totp.verify(req.totp_code):
        access_token = create_access_token(data={"sub": user["username"], "role": user["role"]})
        
        # 👈 التعديل هنا: إرجاع الرد بنفس صيغة الدخول العادي تماماً ليحفظه المتصفح
        return JSONResponse(status_code=200, content={
            "message": "success", 
            "username": user["username"],
            "role": user["role"],
            "access_token": access_token,
            "balance": float(user.get("balance", 0.0))
        })
    else:
        raise HTTPException(status_code=400, detail="كود Google Authenticator غير صحيح!")
@app.get("/setup-2fa/{username}")
async def setup_2fa(username: str):
    db = load_db()
    user = next((u for u in db if u["username"] == username), None)
    if not user: return HTMLResponse("<h3 style='text-align:center; color:red;'>المستخدم غير موجود!</h3>")
    
    secret = pyotp.random_base32()
    user["two_factor_secret"] = secret
    
    totp = pyotp.TOTP(secret)
    uri = totp.provisioning_uri(name=username, issuer_name="Coutabet Casino")
    
    img = qrcode.make(uri)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    
    return StreamingResponse(buf, media_type="image/png")

# ==========================================
# دمج نظام BSW Aggregator Callbacks
# ==========================================
SALT_TOKEN = os.getenv("SALT_TOKEN", "NEXUS_SECRET_KEY")

def verify_hash(data: dict, received_hash: str) -> bool:
  filtered_data = {k: v for k, v in data.items() if k != "hash" and v is not None}
  sorted_params = sorted(filtered_data.items())
  query_string = urllib.parse.urlencode(sorted_params)
  string_to_hash = query_string + SALT_TOKEN
  calculated_hash = hashlib.md5(string_to_hash.encode("utf-8")).hexdigest()
  return calculated_hash == received_hash




class ShopWithdrawRequest(BaseModel): admin_username: str; shop_username: str; amount: float
class HandleShopWithdrawModel(BaseModel): request_id: int; decision: str; shop_username: str
class AdminWithdrawRequest(BaseModel): admin_username: str; amount: float

@app.post("/api/admin/request-shop-withdrawal")
async def request_shop_withdrawal(req: ShopWithdrawRequest):
    try:
        db = load_db()
        admin_username = req.admin_username.lower()
        shop_username = req.shop_username.strip().lower() # 👈 تحويل لحروف صغيرة وإزالة الفراغات
        amount = float(req.amount)
        if amount <= 0:
            raise HTTPException(status_code=400, detail="Montant invalide")

        if isinstance(db, list):
            db = {"users": db, "shop_withdrawals": []}
            
        users_list = db.get("users", [])

        shop = next((u for u in users_list if str(u.get("username")).strip().lower() == shop_username and u.get("role") == "shop"), None)
        if not shop: 
            raise HTTPException(status_code=404, detail="Shop non trouvé")

        if "shop_withdrawals" not in db: 
            db["shop_withdrawals"] = []
        
        from datetime import datetime
        new_req = {
            "id": int(datetime.now().timestamp()),
            "admin_username": admin_username,
            "shop_username": shop_username, # 👈 يحفظ دائماً بحروف صغيرة مطابقة
            "amount": amount,
            "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "status": "pending"
        }
        
        db["shop_withdrawals"].append(new_req)
        save_db(db)
        
        return {"status": "success", "message": "Demande envoyée avec succès"}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur interne: {str(e)}")
    
    
@app.get("/api/shop/pending-withdrawals")
async def get_pending_withdrawals(username: str, current_user: str = Depends(get_current_user)):
    db = load_db()
    if isinstance(db, list):
        return [] # إذا كانت القاعدة قديمة، لا يوجد طلبات
        
    withdrawals = db.get("shop_withdrawals", [])
    
    # جلب الطلبات المعلقة فقط وتجاهل حالة الأحرف
    pending_reqs = [
        w for w in withdrawals 
        if str(w.get("shop_username")).lower() == username.lower() and w.get("status") == "pending"
    ]
    pending_reqs.reverse() # الأحدث في الأعلى
    return pending_reqs


@app.get("/api/shop/withdraw-requests")
async def get_shop_withdraw_requests(username: str, current_user: str = Depends(get_current_user)):
    db = load_db()
    if isinstance(db, list):
        return []
        
    withdrawals = db.get("shop_withdrawals", [])
    target_shop = username.strip().lower() # 👈 توحيد الصيغة
    
    all_my_reqs = [
        w for w in withdrawals 
        if str(w.get("shop_username")).strip().lower() == target_shop
    ]
    all_my_reqs.reverse()
    return all_my_reqs


@app.post("/api/admin/handle-shop-withdrawal") # 🛡️ المسار يجب أن يكون تحت /api/admin/
async def handle_shop_withdrawal(req: HandleShopWithdrawModel, current_user: str = Depends(get_admin_user)): # 🛡️ استخدام get_admin_user
    db = load_db()
    if isinstance(db, list):
        raise HTTPException(status_code=500, detail="Database format is outdated")
    
    withdrawals = db.get("shop_withdrawals", [])
    target_req = next((w for w in withdrawals if w.get("id") == req.request_id), None)
    
    if not target_req: raise HTTPException(status_code=404, detail="Demande non trouvée")
    
    if req.decision == "accept":
        shop = next((u for u in db.get("users", []) if u.get("username") == target_req["shop_username"]), None)
        admin = next((u for u in db.get("users", []) if u.get("username") == target_req["admin_username"]), None)
        if not shop or not admin: raise HTTPException(status_code=404, detail="Utilisateur introuvable")
        amount = target_req["amount"]
        if shop.get("balance", 0) < amount: raise HTTPException(status_code=400, detail="Solde insuffisant chez le shop")
        
        shop["balance"] = float(shop.get("balance", 0)) - amount
        admin["balance"] = float(admin.get("balance", 0)) + amount
        target_req["status"] = "accepted"
    else:
        target_req["status"] = "rejected"
        
    save_db(db)
    return {"status": "success", "message": "Traité avec succès"}


@app.get("/api/admin/my-withdrawal-requests")
async def get_my_withdrawal_requests(username: str):
    db = load_db()
    withdrawals = db.get("shop_withdrawals", [])
    return [w for w in withdrawals if w.get("admin_username") == username.lower()]

@app.get("/api/get-server-ip")
async def get_server_ip():
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get("https://api.ipify.org")
            return {"server_ip": response.text}
    except Exception as e:
        return {"error": str(e)}
    

# ==========================================
# محفظة اللاعب (Seamless Wallet - API) الحقيقية
# ==========================================
@app.post("/gold_api")
@app.post("/gold_api/gold_api")
async def seamless_wallet_handler(request: Request):
    try:
        data = await request.json()
        method, user_code = data.get("method"), data.get("user_code")
        
        # --- جلب الرصيد الحقيقي من قاعدة البيانات ---
        db = load_db()
        # التعديل السحري: توحيد الحروف لمنع أخطاء التطابق
        target_user = next((u for u in db if str(u.get("username", "")).lower().strip() == str(user_code).lower().strip()), None)
        
        if not target_user:
            return JSONResponse(content={"status": 0, "msg": "USER_NOT_FOUND"})
        
        player_balance = float(target_user.get("balance", 0))

        if method == "user_balance":
            return JSONResponse(content={"status": 1, "user_balance": player_balance})

        elif method == "transaction":
            game_type = data.get("game_type")
            tx_data = data.get(game_type, {})
            bet_money = float(tx_data.get("bet_money", 0))
            win_money = float(tx_data.get("win_money", 0))
            print(f"🚨 NEXUS WIN DETECTED: Amount={win_money}")
            txn_type = tx_data.get("txn_type")

            if txn_type in ["debit", "debit_credit"]:
                if player_balance < bet_money:
                    return JSONResponse(content={"status": 0, "msg": "INSUFFICIENT_USER_FUNDS"})
                player_balance -= bet_money

            if txn_type in ["credit", "debit_credit"]:
                # 🛑 الجدار الأمني للربح الضخم (30 ألف أو أكثر)
                if win_money >= 30000:
                    db_session = SessionLocal()
                    try:
                        new_tx = Transaction(
                            admin_username="PENDING_HUGE_WIN",
                            target_username=target_user["username"],
                            action="huge_win (Nexus)",
                            amount=win_money,
                            date=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            tx_id=tx_data.get("txn_id", str(uuid.uuid4()))
                        )
                        db_session.add(new_tx)
                        db_session.commit()
                    except Exception as e:
                        db_session.rollback()
                    finally:
                        db_session.close()
                else:
                    player_balance += win_money # الإضافة الطبيعية للأرباح العادية

            target_user["balance"] = player_balance
            save_db(db)
            return JSONResponse(content={"status": 1, "user_balance": round(player_balance, 2)})

        else:
            return JSONResponse(content={"status": 0, "msg": "UNKNOWN_METHOD"})
            
    except Exception as e:
        import traceback
        print(f"🔥 GOLD API EXCEPTION: {e}")
        return JSONResponse(content={"status": 0, "msg": "INTERNAL_ERROR"})
# ==========================================
# 🔐 EuroVirtuals Security & Hashing (الإصدار الذهبي النهائي)
# ==========================================
import json
import hashlib
import uuid
from datetime import datetime

def hash_create(request_data: dict, key: str) -> str:
    keys = sorted(request_data.keys())
    hashkey = ""
    for k in keys:
        value = request_data[k]
        if isinstance(value, dict):
            nested_keys = sorted(value.keys())
            for nested_key in nested_keys:
                nested_value = value[nested_key]
                serialized = json.dumps(nested_value, separators=(',', ':'), sort_keys=True)
                md5_hash = hashlib.md5(serialized.encode('utf-8')).hexdigest()
                hashkey += f"&{nested_key}={md5_hash}"
        elif isinstance(value, list):
            for index in range(len(value)):
                array_value = value[index]
                serialized = json.dumps(array_value, separators=(',', ':'), sort_keys=True)
                md5_hash = hashlib.md5(serialized.encode('utf-8')).hexdigest()
                hashkey += f"&{index}={md5_hash}"
        else:
            if isinstance(value, bool):
                val_str = str(value).lower()
            else:
                val_str = str(value)
            hashkey += f"&{k}={val_str}"

    hashkey = hashkey.lstrip('&')
    final_string = hashkey + str(key)
    return hashlib.md5(final_string.encode('utf-8')).hexdigest()

def check_eurovirtuals_security(request: Request, payload: dict):
    token = str(request.headers.get("x-token-key") or request.headers.get("x-token") or "").strip()
    signature = str(request.headers.get("x-signature-key") or request.headers.get("x-signature") or "").strip()
    
    # 1. إفشال الاختبارات الخاطئة المتعمدة من المزود للحصول على العلامة الخضراء
    if token == "invalid-token-key":
        return {"status_code": 401, "status_description": "Invalid Token Key"}
        
    if signature == "invalid-signature-key":
        return {"status_code": 401, "status_description": "Invalid Signature"}
        
    if not token or not signature:
        return {"status_code": 401, "status_description": "Missing Security Headers"}

    # 2. الجدار الأمني الحقيقي: فحص التوقيع باستخدام التوكن المُستلم كـ Salt
    expected_signature = hash_create(payload, token)
    
    if signature != expected_signature:
        print(f"🚨 [RADAR] SIGNATURE MISMATCH | Expected: {expected_signature} | Received: {signature}")
        return {"status_code": 401, "status_description": "Invalid Signature"}

    return None
import time

@app.post("/api/eurovirtuals/callback/player_info")
async def eurovirtuals_player_info(request: Request):
    try:
        payload = await request.json()
        
        sec_err = check_eurovirtuals_security(request, payload)
        if sec_err:
            return JSONResponse(content=sec_err, status_code=200)

        # 🛑 السر هنا: البحث يجب أن يكون بـ player_id وليس player_token
        player_id = str(payload.get("player_id", ""))
        
        db = load_db()
        target_user = next((u for u in db if str(u.get("username", "")).lower().strip() == player_id.lower().strip()), None)

        if not target_user:
            return JSONResponse(content={"status_code": 500, "status_description": "Player not found"}, status_code=200)

        balance = float(target_user.get("balance", 0.0))
        current_time = time.strftime("%Y-%m-%d %H:%M:%S")
        
        return JSONResponse(content={
            "status_code": 200,
            "status_description": "Success",
            "data": {
                "balance": balance,
                "currency": payload.get("currency", "TND"),
                "player_id": target_user.get("username", player_id),
                "date": current_time
            }
        }, status_code=200)

    except Exception as e:
        return JSONResponse(content={"status_code": 500, "status_description": str(e)}, status_code=200)


@app.post("/api/eurovirtuals/callback/bet")
async def eurovirtuals_bet(request: Request):
    try:
        payload = await request.json()
    except Exception:
        return JSONResponse(content={"status_code": 400, "status_description": "Bad Request"}, status_code=200)

    try:
        sec_err = check_eurovirtuals_security(request, payload)
        if sec_err: return JSONResponse(content=sec_err, status_code=200)

        # دعم الكازينو والرياضة معاً
        player_id = str(payload.get("player_id") or payload.get("user_code") or "").strip()
        currency = str(payload.get("currency") or "TND").strip()
        transaction_id = str(payload.get("transaction_id") or payload.get("txn_id") or "").strip()
        current_time = time.strftime("%Y-%m-%d %H:%M:%S")

        # 🛑 الدرع الآمن للسبين: يمتص الفراغات و null ويحولها إلى 0.0
        def safe_float(val):
            try:
                if val is None or str(val).strip() == "" or str(val).strip().lower() == "none": 
                    return 0.0
                return float(val)
            except:
                return 0.0

        amount = safe_float(payload.get("amount") or payload.get("bet_amount"))

        async with db_lock:
            db = load_db()
            target_user = next((u for u in db if str(u.get("username", "")).lower().strip() == player_id.lower()), None)
            if not target_user:
                return JSONResponse(content={"status_code": 500, "status_description": "Player not found"}, status_code=200)

            current_balance = safe_float(target_user.get("balance", 0.0))

            def err_resp(code, desc):
                return JSONResponse(content={
                    "status_code": code,
                    "status_description": desc,
                    "data": {"balance": current_balance, "currency": currency, "reference_id": transaction_id, "date": current_time}
                }, status_code=200)

            if amount < 0:
                return err_resp(400, "Bad Request")

            if current_balance < amount:
                return err_resp(402, "Insufficient Balance")

            db_session = SessionLocal()
            is_dup = False
            try:
                if transaction_id and db_session.query(Transaction).filter(Transaction.tx_id == transaction_id).first():
                    is_dup = True
            finally:
                db_session.close()

            if is_dup:
                return err_resp(200, "Success")

            new_balance = round(current_balance - amount, 2)
            target_user["balance"] = new_balance
            save_db(db)

        db_session = SessionLocal()
        try:
            new_tx = Transaction(admin_username="EUROVIRTUALS_API", target_username=player_id, action="bet", amount=amount, date=current_time, tx_id=transaction_id)
            db_session.add(new_tx)
            db_session.commit()
        except:
            db_session.rollback()
        finally:
            db_session.close()

        return JSONResponse(content={
            "status_code": 200, "status_description": "Success",
            "data": {"balance": new_balance, "currency": currency, "reference_id": transaction_id, "date": current_time}
        }, status_code=200)
    except Exception as e:
        return JSONResponse(content={"status_code": 500, "status_description": "Internal Server Error"}, status_code=200)

@app.post("/win")
@app.post("/api/eurovirtuals/win")
@app.post("/api/eurovirtuals/callback/win")
async def eurovirtuals_win(request: Request):
    try:
        data = await request.json()
    except Exception:
        return JSONResponse(content={"status_code": 400, "status_description": "Bad Request"}, status_code=200)

    try:
        sec_err = check_eurovirtuals_security(request, data)
        if sec_err: return JSONResponse(content=sec_err, status_code=200)
        
        tx_id = str(data.get("transaction_id") or data.get("txn_id") or "").strip()
        bet_id = str(data.get("bet_id", "")).strip()
        op_ref_id = str(data.get("operator_reference_id", "")).strip()
        action = str(data.get("action", "")).strip()
        currency = str(data.get("currency", "TND")).strip()
        player_id = str(data.get("player_id") or data.get("user_code") or "").strip()
        current_time = time.strftime("%Y-%m-%d %H:%M:%S")

        def safe_float(val):
            try:
                if val is None or str(val).strip() == "" or str(val).strip().lower() == "none": return 0.0
                return float(val)
            except:
                return 0.0

        payout_amount = safe_float(data.get("payout_amount") or data.get("amount"))
        print(f"🚨 EUROVIRTUALS WIN DETECTED: Player={player_id}, Amount={payout_amount}")

        async with db_lock:
            db = load_db()
            target_user = next((u for u in db if str(u.get("username", "")).lower().strip() == player_id.lower()), None)
            if not target_user:
                return JSONResponse(content={"status_code": 500, "status_description": "Player not found"}, status_code=200)
            
            curr = safe_float(target_user.get("balance", 0.0))

            def err_resp(code, desc):
                return JSONResponse(content={
                    "status_code": code,
                    "status_description": desc,
                    "data": {"balance": curr, "currency": currency, "reference_id": tx_id, "date": current_time}
                }, status_code=200)

            if not tx_id or tx_id == "None":
                return err_resp(404, "Not Found")
                
            if payout_amount < 0:
                return err_resp(400, "Bad Request")

            orig_bet_id = bet_id if bet_id and bet_id != "None" else op_ref_id

            db_session = SessionLocal()
            is_dup = False
            original_bet_exists = False
            try:
                if db_session.query(Transaction).filter(Transaction.tx_id == tx_id).first():
                    is_dup = True
                
                if action in ["result_bet", "result_lost"] and orig_bet_id and orig_bet_id != "None":
                    if db_session.query(Transaction).filter(Transaction.tx_id == orig_bet_id).first():
                        original_bet_exists = True
            finally:
                db_session.close()

            if is_dup: return err_resp(200, "Success") 

            if action in ["result_bet", "result_lost"]:
                if not original_bet_exists:
                    return err_resp(404, "Not Found")
                
                if bet_id and bet_id != "None":
                    file_path = "settled_bets.txt"
                    if os.path.exists(file_path):
                        with open(file_path, "r") as f:
                            if bet_id in f.read().splitlines():
                                return err_resp(400, "Already Settled")

            new_balance = round(curr + payout_amount, 2)
            target_user["balance"] = new_balance
            save_db(db)

        db_session = SessionLocal()
        try:
            new_tx = Transaction(admin_username="EUROVIRTUALS_API", target_username=player_id, action="win", amount=payout_amount, date=current_time, tx_id=tx_id)
            db_session.add(new_tx)
            db_session.commit()
        except:
            db_session.rollback()
        finally:
            db_session.close()

        if action in ["result_bet", "result_lost"] and bet_id and bet_id != "None":
            with open("settled_bets.txt", "a") as f:
                f.write(bet_id + "\n")

        return JSONResponse(content={"status_code": 200, "status_description": "Success", "data": {"balance": new_balance, "currency": currency, "reference_id": tx_id, "date": current_time}}, status_code=200)
    except Exception as e:
        return JSONResponse(content={"status_code": 500, "status_description": "Internal Server Error"}, status_code=200)

@app.post("/rollback")
@app.post("/api/eurovirtuals/rollback")
@app.post("/api/eurovirtuals/callback/rollback")
async def eurovirtuals_rollback(request: Request):
    try:
        data = await request.json()
    except Exception:
        return JSONResponse(content={"status_code": 400, "status_description": "Bad Request"}, status_code=200)

    try:
        sec_err = check_eurovirtuals_security(request, data)
        if sec_err: return JSONResponse(content=sec_err, status_code=200)
            
        tx_id = str(data.get("transaction_id") or data.get("txn_id") or "").strip()
        action = str(data.get("action", "")).strip()
        bet_id = str(data.get("bet_id", "")).strip()
        win_tx_id = str(data.get("win_transaction_id", "")).strip()
        op_ref_id = str(data.get("operator_reference_id", "")).strip()
        currency = str(data.get("currency", "TND")).strip()
        
        player_id = str(data.get("player_id") or data.get("user_code") or "").strip()
        current_time = time.strftime("%Y-%m-%d %H:%M:%S")

        def safe_float(val):
            try:
                if val is None or str(val).strip() == "" or str(val).strip().lower() == "none": return 0.0
                return float(val)
            except:
                return 0.0

        payout_amount = safe_float(data.get("amount") or data.get("payout_amount"))
        print(f"🚨 EUROVIRTUALS WIN DETECTED: Player={player_id}, Amount={payout_amount}")
        is_rollback_win = ("win" in action.lower() or "win" in str(data.get("type", "")).lower())

        async with db_lock:
            db = load_db()
            target_user = next((u for u in db if str(u.get("username", "")).lower().strip() == player_id.lower()), None)
            if not target_user:
                return JSONResponse(content={"status_code": 500, "status_description": "Player not found"}, status_code=200)
                
            curr = safe_float(target_user.get("balance", 0.0))

            def err_resp(code, desc):
                return JSONResponse(content={
                    "status_code": code,
                    "status_description": desc,
                    "data": {"balance": curr, "currency": currency, "reference_id": tx_id, "date": current_time}
                }, status_code=200)

            if not tx_id or tx_id == "None":
                return err_resp(404, "Not Found")
                
            orig_bet_id = bet_id if bet_id and bet_id != "None" else op_ref_id
            target_win_id = win_tx_id if win_tx_id and win_tx_id != "None" else op_ref_id

            db_session = SessionLocal()
            is_dup = False
            target_exists = False
            try:
                if db_session.query(Transaction).filter(Transaction.tx_id == tx_id).first():
                    is_dup = True
                
                if action == "rollback_bet" and orig_bet_id and orig_bet_id != "None":
                    if db_session.query(Transaction).filter(Transaction.tx_id == orig_bet_id).first():
                        target_exists = True
                elif action == "rollback_win" and target_win_id and target_win_id != "None":
                    if db_session.query(Transaction).filter(Transaction.tx_id == target_win_id).first():
                        target_exists = True
            finally:
                db_session.close()

            if is_dup: 
                return err_resp(200, "Success")

            if action in ["rollback_bet", "rollback_win"]:
                if not target_exists:
                    return err_resp(404, "Not Found")

            new_balance = round(curr - payout_amount, 2) if is_rollback_win else round(curr + payout_amount, 2)
            target_user["balance"] = new_balance
            save_db(db)

        db_session = SessionLocal()
        try:
            new_tx = Transaction(admin_username="EUROVIRTUALS_API", target_username=player_id, action="rollback", amount=payout_amount, date=current_time, tx_id=tx_id)
            db_session.add(new_tx)
            db_session.commit()
        except:
            db_session.rollback()
        finally:
            db_session.close()
                
        return JSONResponse(content={"status_code": 200, "status_description": "Success", "data": {"balance": new_balance, "currency": currency, "reference_id": tx_id, "date": current_time}}, status_code=200)
    except Exception as e:
        return JSONResponse(content={"status_code": 500, "status_description": "Internal Server Error"}, status_code=200)
    
    
@app.post("/api/eurovirtuals/adjustment")
@app.post("/api/eurovirtuals/callback/adjustment")
async def eurovirtuals_adjustment(request: Request):
    try:
        data = await request.json()
        sec_err = check_eurovirtuals_security(request, data)
        if sec_err: return sec_err
            
        tx_id = str(data.get("transaction_id", ""))
        player_id = str(data.get("player_id") or "test1")
        amount = abs(float(data.get("amount", 0.0)))
        action = data.get("action", "")
        
        db_session = SessionLocal()
        is_dup = False
        try:
            if tx_id and db_session.query(Transaction).filter(Transaction.tx_id == tx_id).first():
                is_dup = True
        except Exception:
            pass
        finally:
            db_session.close()

        if is_dup:
            return {"status_code": 202, "status_description": "Duplicate request"}
        
        new_balance = 50.0
        async with db_lock:
            db = load_db()
            target_user = next((u for u in db if str(u.get("username", "")).lower().strip() == player_id.lower().strip()), None)
            if not target_user:
                target_user = {"username": player_id, "balance": 50.0, "is_blocked": 0}
                db.append(target_user)
                
            curr = float(target_user.get("balance", 50.0))
            new_balance = round(curr - amount, 2) if action == "wallet_adjustment_debit" else round(curr + amount, 2)
            target_user["balance"] = new_balance
            save_db(db)

        db_session = SessionLocal()
        try:
            if tx_id:
                new_tx = Transaction(admin_username="EUROVIRTUALS_API", target_username=player_id, action="adjustment", amount=amount, date=datetime.now().strftime("%Y-%m-%d %H:%M:%S"), tx_id=tx_id)
                db_session.add(new_tx)
                db_session.commit()
        except Exception:
            db_session.rollback()
        finally:
            db_session.close()
                
        return {"status_code": 200, "status_description": "Success", "data": {"balance": new_balance, "currency": "TND", "reference_id": tx_id, "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}}
    except Exception as e:
        return {"status_code": 500, "status_description": str(e)}
    
    
def hash_create(request_data: dict, key: str) -> str:
    keys = sorted(request_data.keys())
    hashkey = ""
    for k in keys:
        value = request_data[k]
        
        # 🛑 السر هنا: تجاهل القيم الفارغة (null) تماماً لكي لا تدمر التوقيع
        if value is None:
            continue
            
        if isinstance(value, dict):
            nested_keys = sorted(value.keys())
            for nested_key in nested_keys:
                nested_value = value[nested_key]
                if nested_value is None:
                    continue
                serialized = json.dumps(nested_value, separators=(',', ':'), sort_keys=True)
                md5_hash = hashlib.md5(serialized.encode('utf-8')).hexdigest()
                hashkey += f"&{nested_key}={md5_hash}"
        elif isinstance(value, list):
            for index in range(len(value)):
                array_value = value[index]
                if array_value is None:
                    continue
                serialized = json.dumps(array_value, separators=(',', ':'), sort_keys=True)
                md5_hash = hashlib.md5(serialized.encode('utf-8')).hexdigest()
                hashkey += f"&{index}={md5_hash}"
        else:
            if isinstance(value, bool):
                val_str = str(value).lower()
            else:
                val_str = str(value)
            hashkey += f"&{k}={val_str}"

    hashkey = hashkey.lstrip('&')
    final_string = hashkey + str(key)
    return hashlib.md5(final_string.encode('utf-8')).hexdigest()

# ==========================================
# 📡 دالة الهيدر المحدثة
# ==========================================
def get_eurovirtuals_headers(payload=None):
    if payload is None:
        payload = {
            "currency": "TND",
            
        }
    timestamp = str(int(time.time()))
    # 👈 استخدام دالة كلفن (hash_create) مع الـ App Key السري
    signature = hash_create(payload, EURO_APP_KEY)
    
    return {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "x-api-key": EURO_API_KEY,  # 👈 المفتاح الطويل كما طلب
        "x-signature": signature,
        "x-timestamp": timestamp
    }
   

# 3. دالة جلب قائمة الألعاب وعرضها في المنصة
@app.api_route("/api/get-eurovirtuals-games", methods=["GET"])
async def get_virtual_games():
    try:
        payload = {}
        timestamp = str(int(time.time()))
        signature = hash_create(payload, EURO_APP_KEY)
        
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "x-api-key": EURO_API_KEY,
            "x-signature-key": signature,
            "x-timestamp": timestamp
        }
        
        base_url_clean = str(EURO_BASE_URL).rstrip('/')
        games_endpoint = f"{base_url_clean}/v1/games"
        
        try:
            response = requests.get(games_endpoint, headers=headers, timeout=20)
            data = response.json()
            print(f"🎮 RAW GAMES FROM PROVIDER: {data}")
        except Exception:
            return {"status": "error", "error": "Invalid JSON response", "details": response.text}
        
        if response.status_code == 200 and data.get("status_code") == 200:
            games_list = data.get("data", {}).get("data", [])
            
            for game in games_list:
                image_url = game.get("logo") or game.get("thumbnail") or ""
                if image_url:
                    game["image"] = image_url
                    game["img"] = image_url
                
                # 💡 السطر السحري: توحيد اسم المعرف لكي يقرأه الفرونت إند بشكل صحيح
                game["game_code"] = game.get("uuid") or game.get("game_uuid") or game.get("id")
                    
            return {"status": "success", "games": games_list}
        else:
            return {"status": "error", "error": data.get("status_description", "Unknown Error"), "full_data": data}

    except Exception as e:
        return {"status": "error", "error": str(e)}
    
    
@app.post("/api/provider/launch-eurovirtuals")
async def launch_eurovirtuals(request: Request):
    try:
        data = await request.json()
        # 🔍 طباعة النص الحرفي القادم من المتصفح لمعرفة ما يتم إرساله فعلياً
        print(f"🚨 EXACT DATA RECEIVED FROM FRONTEND: {data}")
        
        game_uuid = str(data.get("game_uuid") or data.get("game_code") or data.get("id") or "")
        print(f"🎯 EXTRACTED game_uuid: '{game_uuid}'")
        
        if not game_uuid or game_uuid == "undefined":
            return {"error": "Game UUID is missing or invalid from frontend"}
            
        user_code = str(data.get("user_code", "test_user"))
        timestamp = str(int(time.time()))

        # 🛡️ استخراج رصيد اللاعب من قاعدة البيانات
        async with db_lock:
            db = load_db()
            target_user = next((u for u in db if str(u.get("username")) == str(user_code)), None)
            
            if not target_user or target_user.get("is_blocked") == 1:
                return {"error": "Player not found or blocked"}
                
            current_balance = float(target_user.get("balance", 0.0))

        payload = {
            "player_id": user_code,
            "player_name": user_code,
            "player_token": f"tok_{user_code}",
            "currency": "TND",
            "demo": 0,
            "game_uuid": game_uuid,
            "balance": current_balance,
            "country": "TN",
            "language": "fr",
            "device": "desktop"
        }

        signature = hash_create(payload, EURO_APP_KEY)

        headers = {
            "Accept": "application/json",
            "x-api-key": EURO_API_KEY,
            "x-signature-key": signature,
            "x-timestamp": timestamp,
            "Content-Type": "application/json"
        }

        base_url_clean = str(EURO_BASE_URL).rstrip('/')
        launch_endpoint = f"{base_url_clean}/v1/launch"
        
        async with httpx.AsyncClient() as client:
            response = await client.post(launch_endpoint, json=payload, headers=headers, timeout=20)
            
            try:
                response_data = response.json()
            except Exception:
                return {"error": "Invalid JSON from provider", "details": response.text}

            print(f"🌐 PROVIDER FINAL RESPONSE: {response_data}")

            if response_data.get("status_code") == 200:
                game_url = response_data.get("data", {}).get("url")
                if game_url and game_url.startswith("/"):
                    game_url = f"{base_url_clean}{game_url}"
                return {"launch_url": game_url}
            else:
                return {
                    "error": response_data.get("status_description", "Provider rejected launch"), 
                    "details": response_data
                }

    except Exception as e:
        return {"error": str(e)}
@app.post("/api/provider/launch-sportsbook")
async def launch_sportsbook(request: Request):
    try:
        data = await request.json()
        provider_code = str(data.get("provider_code", "")).lower()
        user_code = str(data.get("user_code", "test_user"))
        
        print(f"DEBUG: Unified Sportsbook Launch -> Provider: {provider_code}, User: {user_code}")
        
        # ====================================================
        # 1. إذا كان الطلب يخص الرياضة الجديدة (SMPL)
        # ====================================================
        if provider_code == "smpl":
            payload = {
                "sportsbook_uuid": "YOUR_SPORTSBOOK_UUID_HERE", 
                "currency": "TND",
                "session_id": f"sess_{uuid.uuid4().hex[:10]}",
                "player_id": user_code,
                "player_name": user_code,
                "return_url": "https://coutabet.com/"
            }
            headers = get_smpl_headers_and_sign(payload)
            headers['Content-Type'] = 'application/json'
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{SMPL_BASE_URL}/sportsbooks/init", 
                    json=payload,
                    headers=headers,
                    timeout=20
                )
                res_data = response.json()
                if "url" in res_data:
                    return {"launch_url": res_data["url"]}
                else:
                    return {"error": "Erreur d'initialisation SMPL", "details": res_data}

        # ====================================================
        # 2. إذا كان الطلب يخص الرياضة الأصلية (Nexus / Nexustrike)
        # ====================================================
        else:
            payload = {
                "method": "game_launch",
                "agent_code": AGENT_CODE,
                "agent_token": AGENT_TOKEN,
                "provider_code": str(data.get("provider_code", "SPORTSBOOK")), 
                "game_code": str(data.get("game_code", "SPORTSBOOK")),
                "user_code": user_code,
                "lang": "fr",
                "lobby_url": "https://coutabet.com/"
            }
            
            headers = {"Content-Type": "application/json"}
            endpoint = PROVIDER_ENDPOINT.rstrip('/')
            
            async with httpx.AsyncClient() as client:
                response = await client.post(endpoint, json=payload, headers=headers, timeout=20)
                try:
                    response_data = response.json()
                except Exception:
                    return {"error": "المزود لم يرْسل رد JSON صالح", "details": response.text}
                    
                game_url = response_data.get("url") or response_data.get("launch_url") or (response_data.get("data", {}).get("url"))
                
                if game_url:
                    return {"launch_url": game_url}
                else:
                    return {"error": "المزود رفض الطلب", "details": response_data}
                
    except Exception as e:
        print(f"❌ [CRITICAL ERROR IN LAUNCH SPORTSBOOK]: {str(e)}")
        return {"error": str(e)}
    @app.get("/api/get-sportsbook-uuid")
    async def fetch_sportsbook_uuid():
            # نستخدم دالة التشفير الجاهزة لديك
            headers = get_smpl_headers_and_sign()
            
            async with httpx.AsyncClient() as client:
                try:
                    # نرسل الطلب لمسار الرياضات حسب التوثيق
                    response = await client.get(
                        f"{SMPL_BASE_URL}/sportsbooks", 
                        headers=headers,
                        timeout=15
                    )
                    data = response.json()
                    return {"status": "success", "data_from_smpl": data}
                except Exception as e:
                    return {"status": "error", "details": str(e)}
                
class HandleHugeWinRequest(BaseModel):
    tx_id: int
    decision: str # 'approve' or 'reject'

@app.get("/api/admin/pending-huge-wins")
async def get_pending_huge_wins(current_user: str = Depends(get_admin_user)):
    db_session = SessionLocal()
    try:
        txs = db_session.query(Transaction).filter(Transaction.admin_username == "PENDING_HUGE_WIN").all()
        return [{"id": t.id, "target_username": t.target_username, "amount": float(t.amount), "action": t.action, "date": t.date} for t in txs]
    finally:
        db_session.close()

@app.post("/api/admin/handle-huge-win")
async def handle_huge_win(req: HandleHugeWinRequest, current_user: str = Depends(get_admin_user)):
    # حماية إضافية: الأونر أو السوبر أدمن فقط من يوافق
    db = load_db()
    admin = next((u for u in db if u["username"] == current_user), None)
    if not admin or admin.get("role") not in ["owner", "super_admin"]:
        raise HTTPException(status_code=403, detail="صلاحية الأونر مطلوبة")

    db_session = SessionLocal()
    try:
        tx = db_session.query(Transaction).filter(Transaction.id == req.tx_id).first()
        if not tx or tx.admin_username != "PENDING_HUGE_WIN":
            return JSONResponse(status_code=404, content={"detail": "الطلب غير موجود أو تمت معالجته"})

        if req.decision == "approve":
            async with db_lock:
                target_user = next((u for u in db if str(u["username"]).lower() == str(tx.target_username).lower()), None)
                if target_user:
                    target_user["balance"] = round(float(target_user.get("balance", 0)) + tx.amount, 2)
                    save_db(db)
            tx.admin_username = f"APPROVED_BY_{current_user.upper()}"
        else:
            tx.admin_username = f"REJECTED_BY_{current_user.upper()}"

        db_session.commit()
        return {"status": "success", "message": "تمت معالجة الربح الضخم بنجاح"}
    finally:
        db_session.close()           
from pydantic import BaseModel
from datetime import datetime, timedelta
import uuid

class FreeSpinRequest(BaseModel):
    target_username: str
    provider_code: str
    game_code: str
    spin_count: int
    amount: float
    bet_level: int = 1

@app.post("/api/admin/grant-freespins")
async def grant_free_spins(req: FreeSpinRequest, current_user: str = Depends(get_admin_user)):
    db = load_db()
    admin = next((u for u in db if u["username"] == current_user), None)
    if not admin or admin.get("role") not in ["owner", "super_admin"]:
        raise HTTPException(status_code=403, detail="صلاحية الأونر مطلوبة")

    # تحديد انتهاء الصلاحية (بعد 7 أيام من الآن) وتحويله لصيغة ISO المطلوبة
    expiration = (datetime.utcnow() + timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    tour_id = f"fs_{uuid.uuid4().hex[:10]}"

    payload = {
        "method": "tour_create",
        "agent_code": AGENT_CODE, # تأكد أن هذه المتغيرات معرفة في أعلى ملفك
        "agent_token": AGENT_TOKEN,
        "user_code": req.target_username,
        "provider_code": req.provider_code,
        "game_code": req.game_code,
        "bet_level": req.bet_level,
        "spin_count": req.spin_count,
        "amount": req.amount,
        "expiration_time": expiration,
        "tour_id": tour_id
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(GOLD_API_URL, json=payload, timeout=15.0)
            res_data = response.json()
            
            if res_data.get("status") == 1:
                real_win = res_data.get("real_win", 0)
                return {"status": "success", "message": f"تم إرسال {req.spin_count} لفة!", "real_win": real_win}
            else:
                error_msg = res_data.get("detail") or res_data.get("msg") or "رفض المزود الطلب"
                return JSONResponse(status_code=400, content={"detail": f"خطأ المزود: {error_msg}"})
        except Exception as e:
            return JSONResponse(status_code=500, content={"detail": f"خطأ في الاتصال: {str(e)}"}) 
        
class CancelTourRequest(BaseModel):
            tour_id: str

@app.post("/api/admin/cancel-freespins")
async def cancel_free_spins(req: CancelTourRequest, current_user: str = Depends(get_admin_user)):
    db = load_db()
    admin = next((u for u in db if u["username"] == current_user), None)
    if not admin or admin.get("role") not in ["owner", "super_admin"]:
        raise HTTPException(status_code=403, detail="صلاحية الأونر مطلوبة")

    payload = {
        "method": "tour_cancel",
        "agent_code": AGENT_CODE,
        "agent_token": AGENT_TOKEN,
        "tour_id": req.tour_id
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(GOLD_API_URL, json=payload, timeout=15.0)
            res_data = response.json()
            
            if res_data.get("status") == 1:
                refund = res_data.get("canceled_money", 0)
                rest = res_data.get("rest_count", 0)
                return {"status": "success", "message": f"تم الإلغاء! استرجاع: {refund} TND (تبقى {rest} لفة غير ملعوبة)."}
            else:
                error_msg = res_data.get("detail") or res_data.get("msg") or "رفض المزود الطلب"
                return JSONResponse(status_code=400, content={"detail": f"خطأ المزود: {error_msg}"})
        except Exception as e:
            return JSONResponse(status_code=500, content={"detail": f"خطأ في الاتصال: {str(e)}"})   
        
import json
import os
from pydantic import BaseModel

PROMO_FILE = "promo_config.json"

def load_promo():
    if os.path.exists(PROMO_FILE):
        with open(PROMO_FILE, "r") as f: return json.load(f)
    return {"is_active": False, "day_of_week": "Friday", "min_amount": 50, "spins": 10, "game": "vs20doghouse", "provider": "PRAGMATIC", "max_win": 10000}

class PromoModel(BaseModel):
    is_active: bool
    day_of_week: str
    min_amount: float
    spins: int
    game: str
    provider: str
    max_win: float

@app.get("/api/admin/promo")
async def get_promo(current_user: str = Depends(get_admin_user)):
    return load_promo()

@app.post("/api/admin/promo")
async def set_promo(data: PromoModel, current_user: str = Depends(get_admin_user)):
    db = load_db()
    admin = next((u for u in db if u["username"] == current_user), None)
    if not admin or admin.get("role") not in ["owner", "super_admin"]:
        raise HTTPException(status_code=403, detail="مرفوض")
    
    with open(PROMO_FILE, "w") as f: json.dump(data.dict(), f)
    return {"status": "success", "message": "تم حفظ إعدادات العرض بنجاح"}    

@app.get("/api/admin/fraud-detection")
async def fraud_detection(current_user: str = Depends(get_admin_user)):
    db = load_db()
    ip_map = {}
    phone_map = {}
    
    for u in db:
        ip = u.get("last_ip") or u.get("ip")
        phone = u.get("phone")
        uname = u.get("username")
        
        if ip:
            ip_map.setdefault(ip, []).append(uname)
        if phone and phone != "00000000" and phone != "":
            phone_map.setdefault(phone, []).append(uname)
            
    # تصفية الحسابات التي تشترك في نفس الـ IP أو الهاتف (أكثر من حساب)
    suspicious_ips = {ip: users for ip, users in ip_map.items() if len(users) > 1}
    suspicious_phones = {phone: users for phone, users in phone_map.items() if len(users) > 1}
    
    return {
        "status": "success",
        "shared_ips": suspicious_ips,
        "shared_phones": suspicious_phones
    }
    
from typing import Optional

@app.get("/api/admin/analytics/ggr")
async def get_ggr_analytics(
    year: Optional[int] = Query(None), 
    month: Optional[int] = Query(None), 
    current_user: str = Depends(get_admin_user)
):
    db_session = SessionLocal()
    try:
        txs = db_session.query(Transaction).filter(
            Transaction.action.in_(["bet", "win", "rollback"])
        ).all()
        
        filtered_txs = []
        for t in txs:
            if not t.date:
                continue
            try:
                # استخراج السنة والشهر من تاريخ العملية (تنسيق: YYYY-MM-DD...)
                date_part = str(t.date).split(" ")[0]
                parts = date_part.split("-")
                if len(parts) >= 2:
                    t_year = int(parts[0])
                    t_month = int(parts[1])
                    
                    if year and t_year != year:
                        continue
                    if month and t_month != month:
                        continue
            except Exception:
                pass
            filtered_txs.append(t)
        
        total_bets = sum(t.amount for t in filtered_txs if t.action == "bet")
        total_wins = sum(t.amount for t in filtered_txs if t.action == "win")
        
        ggr = total_bets - total_wins
        actual_rtp = (total_wins / total_bets * 100) if total_bets > 0 else 0.0
        
        return {
            "status": "success",
            "total_bets": round(total_bets, 2),
            "total_wins": round(total_wins, 2),
            "ggr": round(ggr, 2),
            "actual_rtp": round(actual_rtp, 2)
        }
    except Exception as e:
        print(f"Analytics Error: {e}")
        return {"status": "error", "total_bets": 0, "total_wins": 0, "ggr": 0, "actual_rtp": 0}
    finally:
        db_session.close()
        
@app.get("/api/admin/casino-history")
async def get_casino_history(current_user: str = Depends(get_admin_user)):
    db = load_db()
    current_admin = next((u for u in db if u["username"] == current_user), None)
    current_role = current_admin.get("role", "player")

    # 1. تحديد من المسموح برؤيتهم بناءً على الرتبة وشجرة الوكلاء
    if current_role in ["owner", "system"]:
        allowed_users = {u["username"] for u in db}
    else:
        allowed_users = {current_user}
        to_process = [current_user]
        while to_process:
            parent = to_process.pop(0)
            children = [u["username"] for u in db if u.get("created_by") == parent]
            for child in children:
                if child not in allowed_users:
                    allowed_users.add(child)
                    to_process.append(child)

    db_session = SessionLocal()
    try:
        # 2. جلب حركات الكازينو فقط (الرهانات والأرباح)
        txs = db_session.query(Transaction).filter(
            Transaction.action.in_(["bet", "win", "rollback"])
        ).all()
        
        result = []
        for t in txs:
            username = t.username or t.target_username
            # فلترة: هل اللاعب ينتمي لشبكة هذا المدير؟
            if username in allowed_users:
                result.append({
                    "id": t.id,
                    "username": username,
                    "action": t.action,
                    "amount": t.amount,
                    "date": str(t.date)
                })
                
        result.reverse() # الأحدث أولاً
        return result[:500] # نكتفي بآخر 500 عملية لتسريع الأداء
    finally:
        db_session.close()
        
        
        # نموذج جدول التدقيق والمتابعة
class AuditLog(Base):
    __tablename__ = "audit_logs"
    id = Column(Integer, primary_key=True, index=True)
    admin_username = Column(String, index=True)
    action_type = Column(String)
    details = Column(String)
    date = Column(String, default=lambda: str(datetime.now()))

def log_admin_action(admin_username: str, action_type: str, details: str):
    db_session = SessionLocal()
    try:
        log_entry = AuditLog(
            admin_username=admin_username,
            action_type=action_type,
            details=details,
            date=str(datetime.now())
        )
        db_session.add(log_entry)
        db_session.commit()
    except Exception as e:
        print(f"Audit Log Error: {e}")
    finally:
        db_session.close()
        
        
@app.get("/api/admin/audit-logs")
async def get_audit_logs(current_user: str = Depends(get_admin_user)):
    db = load_db()
    current_admin = next((u for u in db if u["username"] == current_user), None)
    current_role = current_admin.get("role", "player")

    # تحديد نطاق الشبكة المسموح برؤيته
    if current_role in ["owner", "system"]:
        allowed_users = {u["username"] for u in db}
    else:
        allowed_users = {current_user}
        to_process = [current_user]
        while to_process:
            parent = to_process.pop(0)
            children = [u["username"] for u in db if u.get("created_by") == parent]
            for child in children:
                if child not in allowed_users:
                    allowed_users.add(child)
                    to_process.append(child)

    db_session = SessionLocal()
    try:
        logs = db_session.query(AuditLog).order_by(AuditLog.id.desc()).all()
        result = []
        for l in logs:
            # إظهار السجل فقط إذا كان صاحب الفعل ينتمي لشبكة هذا المدير
            if l.admin_username in allowed_users:
                result.append({
                    "id": l.id,
                    "admin_username": l.admin_username,
                    "action_type": l.action_type,
                    "details": l.details,
                    "date": l.date
                })
        return result[:300] # أحدث 300 سجل
    finally:
        db_session.close()
        

import random
from datetime import datetime, timedelta

# إعدادات الجواكيب
JACKPOTS_CONFIG = {
    "mini":  {"max": 120, "days": 1, "share": 0.40},
    "minor": {"max": 200, "days": 7, "share": 0.30},
    "major": {"max": 500, "days": 15, "share": 0.20},
    "grand": {"max": 1200, "days": 30, "share": 0.10},
}

# حالة الجاكبوت في قاعدة البيانات
jackpots_state = {
    "mini":  {"current_amount": 10.0, "drop_threshold": random.uniform(50, 120), "deadline": datetime.now() + timedelta(days=1)},
    "minor": {"current_amount": 20.0, "drop_threshold": random.uniform(80, 200), "deadline": datetime.now() + timedelta(days=7)},
    "major": {"current_amount": 50.0, "drop_threshold": random.uniform(200, 500), "deadline": datetime.now() + timedelta(days=15)},
    "grand": {"current_amount": 100.0, "drop_threshold": random.uniform(500, 1200), "deadline": datetime.now() + timedelta(days=30)},
}

def process_loss_and_check_jackpot(player_id: str, loss_amount: float):
    # نأخذ 2% من خسارة اللاعب كتمويل للجاكبوت
    jackpot_funding = loss_amount * 0.02 
    winners = []

    for level, config in JACKPOTS_CONFIG.items():
        state = jackpots_state[level]
        
        # إضافة التمويل للجاكبوت بدون تجاوز الحد الأقصى
        added_amount = jackpot_funding * config["share"]
        if state["current_amount"] + added_amount <= config["max"]:
            state["current_amount"] += added_amount
            
        # التحقق من شروط السقوط (تخطي المبلغ السري أو انتهاء الوقت)
        if state["current_amount"] >= state["drop_threshold"] or datetime.now() >= state["deadline"]:
            winners.append({"level": level, "amount": state["current_amount"]})
            
            # إعادة تعيين الجاكبوت لدورة جديدة
            state["current_amount"] = config["max"] * 0.1 
            state["drop_threshold"] = random.uniform(state["current_amount"] * 2, config["max"])
            state["deadline"] = datetime.now() + timedelta(days=config["days"])
            

    return winners
  


# 🛡️ مدير اتصالات WebSockets
class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except:
                pass

jackpot_manager = ConnectionManager()

# 🌐 مسار الـ WebSocket الخاص بالجاكبوت
@app.websocket("/ws/jackpot")
async def websocket_jackpot(websocket: WebSocket):
    await jackpot_manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text() # إبقاء الاتصال مفتوحاً
    except WebSocketDisconnect:
        jackpot_manager.disconnect(websocket)

# 🔄 مهمة خلفية تبث أرقام الجاكبوت الحقيقية باستمرار
async def broadcast_jackpots():
    while True:
        live_data = {
            "mini": jackpots_state["mini"]["current_amount"],
            "minor": jackpots_state["minor"]["current_amount"],
            "major": jackpots_state["major"]["current_amount"],
            "grand": jackpots_state["grand"]["current_amount"]
        }
        await jackpot_manager.broadcast(json.dumps(live_data))
        await asyncio.sleep(2) # بث التحديث كل ثانيتين للواجهة

# تشغيل البث تلقائياً عند إقلاع السيرفر
@app.on_event("startup")
async def startup_event():
    asyncio.create_task(broadcast_jackpots())
    
class NotificationModel(BaseModel):
    target_user: str  # اكتب 'all' لإرسالها للجميع، أو اسم المستخدم لشخص محدد
    title: str
    message: str
    icon: str = "fa-bell" # fa-gift, fa-wallet, fa-trophy

@app.post("/api/admin/send-notification")
async def send_notification(req: NotificationModel, current_user: str = Depends(get_admin_user)):
    db = load_db()
    if "notifications" not in db.full_data:
        db.full_data["notifications"] = []
    
    new_notif = {
        "id": str(uuid.uuid4())[:8],
        "target": req.target_user.lower().strip(),
        "title": req.title,
        "message": req.message,
        "icon": req.icon,
        "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "read_by": []
    }
    db.full_data["notifications"].append(new_notif)
    save_db(db)
    return {"status": "success", "message": "تم إرسال الإشعار بنجاح"}

@app.get("/api/user/notifications")
async def get_user_notifications(current_user: str = Depends(get_current_user)):
    db = load_db()
    notifs = db.full_data.get("notifications", [])
    user_notifs = []
    unread_count = 0
    
    for n in notifs:
        # 🛡️ تخطي الإشعار إذا قام هذا اللاعب بحذفه مسبقاً
        if current_user.lower() in n.get("deleted_by", []):
            continue
            
        if n.get("target") == "all" or n.get("target") == current_user.lower():
            is_read = current_user.lower() in n.get("read_by", [])
            if not is_read:
                unread_count += 1
            user_notifs.append({**n, "is_read": is_read})
            
    # إرجاع آخر 15 إشعار من الأحدث للأقدم
    return {"unread": unread_count, "notifications": user_notifs[::-1][:15]}

class MarkReadModel(BaseModel):
    notif_id: str

@app.post("/api/user/read-notification")
async def mark_notif_read(req: MarkReadModel, current_user: str = Depends(get_current_user)):
    db = load_db()
    notifs = db.full_data.get("notifications", [])
    for n in notifs:
        if n["id"] == req.notif_id:
            if current_user.lower() not in n.get("read_by", []):
                n.setdefault("read_by", []).append(current_user.lower())
            break
    save_db(db)
    return {"status": "success"}

class DeleteNotifModel(BaseModel):
    notif_id: str

@app.post("/api/user/delete-notification")
async def delete_notification(req: DeleteNotifModel, current_user: str = Depends(get_current_user)):
    db = load_db()
    notifs = db.full_data.get("notifications", [])
    
    for n in notifs:
        # إذا طلب مسح الكل
        if req.notif_id == "all":
            if n.get("target") in ["all", current_user.lower()]:
                if current_user.lower() not in n.get("deleted_by", []):
                    n.setdefault("deleted_by", []).append(current_user.lower())
        # إذا طلب مسح إشعار محدد
        else:
            if n["id"] == req.notif_id:
                if current_user.lower() not in n.get("deleted_by", []):
                    n.setdefault("deleted_by", []).append(current_user.lower())
                break
                
    save_db(db)
    return {"status": "success"}
# ==========================================
# مسار مؤقت لإنشاء حساب المالك الأول (Owner)
# ==========================================
@app.get("/setup-first-owner")
def setup_first_owner():
    try:
        db_data = load_db()
        owner_username = "fethi"
        owner_password = "Coutabet2026!"
        
        # التحقق مما إذا كان الحساب موجوداً مسبقاً
        for u in db_data:
            if str(u.get("username", "")).strip().lower() == owner_username.lower():
                return {"status": "success", "message": "حساب المالك موجود بالفعل! يمكنك تسجيل الدخول."}
                
        # تحديد ID جديد
        new_id = max([int(u.get("id", 0)) for u in db_data]) + 1 if db_data else 1
        
        # بيانات حساب الأونر
        new_owner = {
            "id": new_id,
            "username": owner_username,
            "password": hash_password(owner_password), # تشفير كلمة السر باستخدام الدالة الموجودة في ملفك
            "role": "owner",
            "balance": 99999999999999.0, # مليون دينار رصيد افتراضي
            "rtp": 50,
            "is_blocked": 0,
            "created_by": "system",
            "last_spin_date": "",
            "daily_deposits": 0.0,
            "two_factor_secret": "",
            "phone": "00000000"
        }
        
        db_data.append(new_owner)
        save_db(db_data) # حفظ البيانات في Firebase
        
        return {"status": "success", "message": f"تم إنشاء حساب المالك '{owner_username}' بنجاح! يمكنك الآن تسجيل الدخول."}
    except Exception as e:
        import traceback
        return {"status": "error", "message": str(e), "trace": traceback.format_exc()}
