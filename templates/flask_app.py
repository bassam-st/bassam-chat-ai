#!/usr/bin/env python3
"""
تطبيق Flask كامل وجاهز للتشغيل
نسخة حقيقية 100%
"""

from flask import Flask, render_template, request, jsonify, session
from datetime import datetime
import json
import os

app = Flask(__name__)
app.secret_key = 'bassam-ai-secret-key-2024'

# بيانات نموذجية
users_data = [
    {"id": 1, "name": "باسَم", "role": "مساعد ذكي"},
    {"id": 2, "name": "مستخدم", "role": "مطور"}
]

class ChatManager:
    def __init__(self):
        self.conversations = []
    
    def add_message(self, user_message, ai_response):
        """إضافة رسالة للمحادثة"""
        message = {
            'user': user_message,
            'ai': ai_response,
            'timestamp': datetime.now().isoformat()
        }
        self.conversations.append(message)
        return message

chat_manager = ChatManager()

@app.route('/')
def home():
    """الصفحة الرئيسية"""
    return render_template('index.html', 
                         title="باسَم Flask App",
                         users=users_data,
                         current_time=datetime.now().strftime('%Y-%m-%d %H:%M:%S'))

@app.route('/api/chat', methods=['POST'])
def chat_api():
    """واجهة محادثة API"""
    try:
        data = request.get_json()
        user_message = data.get('message', '')
        
        # رد ذكي بسيط
        if 'مرحبا' in user_message:
            ai_response = "مرحباً بك! كيف يمكنني مساعدتك اليوم؟"
        elif 'برمجة' in user_message:
            ai_response = "يمكنني مساعدتك في مواضيع البرمجة والتطوير!"
        elif 'شبكة' in user_message:
            ai_response = "أفهم أنك مهتم بالشبكات والخوادم."
        else:
            ai_response = f"لقد قلت: {user_message}. هذا مثير للاهتمام!"
        
        # حفظ المحادثة
        message = chat_manager.add_message(user_message, ai_response)
        
        return jsonify({
            'status': 'success',
            'response': ai_response,
            'conversation_id': len(chat_manager.conversations),
            'timestamp': message['timestamp']
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/api/users')
def get_users():
    """جلب بيانات المستخدمين"""
    return jsonify({
        'status': 'success',
        'count': len(users_data),
        'users': users_data
    })

@app.route('/api/conversations')
def get_conversations():
    """جلب سجل المحادثات"""
    return jsonify({
        'status': 'success',
        'count': len(chat_manager.conversations),
        'conversations': chat_manager.conversations[-10:]  # آخر 10 محادثات
    })

@app.route('/api/system-info')
def system_info():
    """معلومات النظام"""
    return jsonify({
        'status': 'success',
        'app_name': 'Bassam Flask App',
        'version': '1.0.0',
        'server_time': datetime.now().isoformat(),
        'total_conversations': len(chat_manager.conversations)
    })

@app.route('/health')
def health_check():
    """فحص صحة التطبيق"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat()
    })

if __name__ == '__main__':
    # إنشاء مجلد القوالب إذا لم يكن موجوداً
    templates_dir = 'templates'
    if not os.path.exists(templates_dir):
        os.makedirs(templates_dir)
        
        # إنشاء template أساسي
        with open(os.path.join(templates_dir, 'index.html'), 'w', encoding='utf-8') as f:
            f.write("""
<!DOCTYPE html>
<html dir="rtl">
<head>
    <meta charset="UTF-8">
    <title>{{ title }}</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 40px; background: #f5f5f5; }
        .container { max-width: 800px; margin: 0 auto; background: white; padding: 20px; border-radius: 10px; }
        .header { text-align: center; color: #333; }
        .users { margin: 20px 0; }
        .user-card { background: #e3f2fd; padding: 10px; margin: 10px 0; border-radius: 5px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🚀 {{ title }}</h1>
            <p>الوقت الحالي: {{ current_time }}</p>
        </div>
        
        <div class="users">
            <h2>المستخدمون</h2>
            {% for user in users %}
            <div class="user-card">
                <strong>{{ user.name }}</strong> - {{ user.role }}
            </div>
            {% endfor %}
        </div>
        
        <div>
            <h2>واجهات API المتاحة:</h2>
            <ul>
                <li><code>/api/chat</code> - المحادثة</li>
                <li><code>/api/users</code> - المستخدمون</li>
                <li><code>/api/conversations</code> - المحادثات</li>
                <li><code>/api/system-info</code> - معلومات النظام</li>
                <li><code>/health</code> - فحص الصحة</li>
            </ul>
        </div>
    </div>
</body>
</html>
            """)
    
    print("🚀 بدء تشغيل تطبيق Flask...")
    print("📧 العنوان: http://localhost:5000")
    print("🔧 الوضع: التطوير")
    
    app.run(debug=True, host='0.0.0.0', port=5000)
