#!/usr/bin/env python3
"""
Bassam Chat AI - النظام الرئيسي
نسخة حقيقية وقابلة للتشغيل فوراً
"""

import os
import sys
import json
from datetime import datetime
from shell_system.shell_interface import SmartShell

class BassamChatAI:
    def __init__(self):
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.history = []
        
    def start_chat_mode(self):
        """بدء وضع المحادثة"""
        print("\n💬 **وضع المحادثة النشط**")
        print("=" * 40)
        
        while True:
            user_input = input("\n👤 أنت: ").strip()
            
            if user_input.lower() in ['exit', 'خروج', 'quit']:
                print("👋 العودة للقائمة الرئيسية...")
                break
                
            if not user_input:
                continue
                
            # معالجة المدخلات
            response = self.process_chat_input(user_input)
            print(f"🤖 باسَم: {response}")
            
            # حفظ التاريخ
            self.history.append({
                'user': user_input,
                'ai': response,
                'timestamp': datetime.now().isoformat()
            })
    
    def process_chat_input(self, user_input):
        """معالجة مدخلات المحادثة"""
        input_lower = user_input.lower()
        
        # ردود ذكية بناء على المحتوى
        if any(word in input_lower for word in ['مرحبا', 'اهلا', 'السلام']):
            return "مرحباً بك! أنا باسَم المساعد الذكي. كيف يمكنني مساعدتك اليوم؟"
        
        elif any(word in input_lower for word in ['برمجة', 'كود', 'سكريبت']):
            return "يمكنني مساعدتك في البرمجة! جرب وضع Shell لإنشاء الأكواد تلقائياً."
        
        elif any(word in input_lower for word in ['شبكة', 'خادم', 'سيرفر']):
            return "لإنشاء خوادم وشبكات، استخدم وضع Shell واختر القوالب الجاهزة."
        
        elif any(word in input_lower for word in ['شكرا', 'ممتاز', 'رائع']):
            return "شكراً لك! 😊 أنا هنا دائماً لمساعدتك."
        
        elif 'اسمك' in input_lower:
            return "أنا باسَم - مساعدك الذكي في البرمجة والتطوير!"
        
        else:
            return "أفهم أنك تريد: " + user_input + "\nيمكنني مساعدتك بشكل أفضل في وضع Shell لإنشاء الأكواد والمشاريع!"

def main():
    """الدالة الرئيسية للتشغيل"""
    print("""
    🧠 **Bassam Chat AI - الإصدار 1.0**
    ===================================
    """)
    
    # إنشاء النظام الرئيسي
    ai_system = BassamChatAI()
    
    while True:
        print("\n" + "="*50)
        print("**القائمة الرئيسية**")
        print("1. 💬 وضع المحادثة")
        print("2. 🛠️  وضع Shell الذكي")
        print("3. 📊 معلومات النظام")
        print("4. 🚪 خروج")
        print("="*50)
        
        choice = input("\n🎯 اختر الوضع: ").strip()
        
        if choice == "1":
            ai_system.start_chat_mode()
            
        elif choice == "2":
            print("\n🚀 **بدء Shell الذكي...**")
            shell = SmartShell()
            shell.start_shell()
            
        elif choice == "3":
            print(f"""
📊 **معلومات النظام:**
- المعرف: {ai_system.session_id}
- المحادثات: {len(ai_system.history)}
- الوقت: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
- المسار: {os.getcwd()}
            """)
            
        elif choice == "4":
            print("\n👋 **شكراً لاستخدامك Bassam Chat AI!**")
            break
            
        else:
            print("❌ **خيار غير صحيح، الرجاء المحاولة مرة أخرى**")

if __name__ == "__main__":
    main()
