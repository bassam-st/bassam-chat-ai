#!/usr/bin/env python3
"""
تطبيق FastAPI سريع وحديث
نسخة حقيقية وجاهزة للتشغيل
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from datetime import datetime
from typing import List, Optional
import uvicorn

app = FastAPI(
    title="Bassam FastAPI",
    description="تطبيق FastAPI ذكي للمحادثة والبيانات",
    version="1.0.0"
)

# نماذج البيانات
class ChatRequest(BaseModel):
    message: str
    user_id: Optional[int] = 1

class ChatResponse(BaseModel):
    status: str
    response: str
    conversation_id: int
    timestamp: str

class User(BaseModel):
    id: int
    name: str
    role: str
    created_at: str

class SystemInfo(BaseModel):
    app_name: str
    version: str
    server_time: str
    total_requests: int

# بيانات التطبيق
conversations = []
request_count = 0

users_db = [
    User(id=1, name="باسَم الذكي", role="مساعد AI", created_at="2024-01-01"),
    User(id=2, name="مستخدم", role="مطور", created_at="2024-01-01")
]

@app.get("/")
async def root():
    """الصفحة الرئيسية"""
    global request_count
    request_count += 1
    
    return {
        "message": "مرحباً بك في Bassam FastAPI!",
        "endpoints": {
            "/docs": "التوثيق التفاعلي",
            "/api/chat": "المحادثة الذكية",
            "/api/users": "قائمة المستخدمين",
            "/api/info": "معلومات النظام"
        },
        "timestamp": datetime.now().isoformat()
    }

@app.post("/api/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    """نقطة نهاية المحادثة"""
    global request_count, conversations
    request_count += 1
    
    try:
        # محاكاة ذكاء اصطناعي بسيط
        user_message = request.message.lower()
        
        if any(word in user_message for word in ['مرحبا', 'اهلا', 'السلام']):
            ai_response = "مرحباً! أنا مساعد FastAPI الذكي. كيف يمكنني مساعدتك؟"
        elif any(word in user_message for word in ['برمجة', 'كود', 'تطوير']):
            ai_response = "رائع! البرمجة شغف رائع. أي لغة تفضل؟"
        elif any(word in user_message for word in ['شبكة', 'خادم', 'api']):
            ai_response = "FastAPI ممتاز لبناء APIs سريعة! هل تريد إنشاء نقطة نهاية جديدة؟"
        elif any(word in user_message for word in ['وقت', 'تاريخ', 'الآن']):
            ai_response = f"الوقت الحالي: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        else:
            ai_response = f"لقد قلت: '{request.message}'. هذا مثير للاهتمام!"
        
        # حفظ المحادثة
        conversation_entry = {
            "user_id": request.user_id,
            "user_message": request.message,
            "ai_response": ai_response,
            "timestamp": datetime.now().isoformat()
        }
        conversations.append(conversation_entry)
        
        return ChatResponse(
            status="success",
            response=ai_response,
            conversation_id=len(conversations),
            timestamp=conversation_entry["timestamp"]
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/users", response_model=List[User])
async def get_users():
    """جلب قائمة المستخدمين"""
    global request_count
    request_count += 1
    return users_db

@app.get("/api/conversations")
async def get_conversations(limit: int = 10):
    """جلب آخر المحادثات"""
    global request_count
    request_count += 1
    
    recent_conv = conversations[-limit:] if conversations else []
    return {
        "status": "success",
        "count": len(recent_conv),
        "conversations": recent_conv
    }

@app.get("/api/info", response_model=SystemInfo)
async def system_info():
    """معلومات النظام"""
    global request_count
    request_count += 1
    
    return SystemInfo(
        app_name="Bassam FastAPI",
        version="1.0.0",
        server_time=datetime.now().isoformat(),
        total_requests=request_count
    )

@app.get("/health")
async def health_check():
    """فحص صحة التطبيق"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "service": "bassam-fastapi"
    }

if __name__ == "__main__":
    print("🚀 بدء تشغيل FastAPI...")
    print("📚 التوثيق: http://localhost:8000/docs")
    print("🔧 الوضع: الإنتاج")
    
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=8000,
        log_level="info"
    )
