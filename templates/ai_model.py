#!/usr/bin/env python3
"""
نموذج الذكاء الاصطناعي البسيط
نسخة حقيقية - لا تتطلب مكتبات خارجية
"""

import json
import re
from datetime import datetime

class SimpleAIModel:
    def __init__(self):
        self.knowledge_base = self.load_knowledge()
        self.conversation_context = []
        
    def load_knowledge(self):
        """تحميل قاعدة المعرفة"""
        return {
            "البرمجة": {
                "python": "لغة Python ممتازة للذكاء الاصطناعي وتحليل البيانات",
                "javascript": "JavaScript أساسية لتطوير الويب والتطبيقات التفاعلية",
                "html_css": "HTML و CSS لبناء واجهات الويب الجذابة"
            },
            "الشبكات": {
                "tcp_ip": "بروتوكول TCP/IP هو أساس الاتصالات عبر الإنترنت",
                "http": "HTTP بروتوكول لنقل بيانات الويب",
                "dns": "DNS يحول أسماء النطاقات إلى عناوين IP"
            },
            "الذكاء الاصطناعي": {
                "ml": "التعلم الآلي يتعلم من البيانات دون برمجة صريحة",
                "dl": "التعلم العميق يستخدم الشبكات العصبية المتعددة الطبقات",
                "nlp": "معالجة اللغة الطبيعية تفهم وتولد النص البشري"
            }
        }
    
    def preprocess_text(self, text):
        """معالجة النص المدخل"""
        # إزالة علامات الترقيم وتحويل للحروف الصغيرة
        text = re.sub(r'[^\w\s]', '', text.lower())
        return text
    
    def find_best_match(self, processed_text):
        """إيجاد أفضل تطابق في قاعدة المعرفة"""
        best_category = None
        best_topic = None
        max_matches = 0
        
        for category, topics in self.knowledge_base.items():
            for topic, content in topics.items():
                # البحث عن كلمات مفتاحية
                matches = sum(1 for word in processed_text.split() 
                            if word in content.lower() or word in topic.lower())
                
                if matches > max_matches:
                    max_matches = matches
                    best_category = category
                    best_topic = topic
        
        return best_category, best_topic
    
    def generate_response(self, user_input):
        """توليد رد ذكي"""
        processed_input = self.preprocess_text(user_input)
        
        # البحث في قاعدة المعرفة
        category, topic = self.find_best_match(processed_input)
        
        if category and topic:
            response = self.knowledge_base[category][topic]
        else:
            # رد افتراضي مع تحليل بسيط
            words = processed_input.split()
            if any(word in words for word in ['كود', 'برمجة', 'سكريبت']):
                response = "يمكنني مساعدتك في البرمجة! ما نوع الكود الذي تريده؟"
            elif any(word in words for word in ['شبكة', 'خادم', 'اتصال']):
                response = "أفهم أنك مهتم بالشبكات. أي بروتوكول تريد التعلم عنه؟"
            elif any(word in words for word in ['ذكاء', 'تعلم', 'نموذج']):
                response = "الذكاء الاصطناعي مجال رائع! أي تقنية تريد معرفة المزيد عنها؟"
            else:
                response = "أفهم أنك تقول: " + user_input + ". يمكنني مساعدتك في البرمجة والشبكات والذكاء الاصطناعي."
        
        # حفظ السياق
        self.conversation_context.append({
            'user': user_input,
            'ai': response,
            'time': datetime.now().isoformat()
        })
        
        # الحفاظ على حجم معقول للسياق
        if len(self.conversation_context) > 10:
            self.conversation_context.pop(0)
        
        return response
    
    def get_conversation_summary(self):
        """الحصول على ملخص المحادثة"""
        if not self.conversation_context:
            return "لا توجد محادثات سابقة"
        
        topics = []
        for conv in self.conversation_context[-5:]:  # آخر 5 محادثات
            if 'برمجة' in conv['user']:
                topics.append('البرمجة')
            elif 'شبكة' in conv['user']:
                topics.append('الشبكات')
            elif 'ذكاء' in conv['user']:
                topics.append('الذكاء الاصطناعي')
        
        unique_topics = list(set(topics))
        summary = f"ناقشنا: {', '.join(unique_topics) if unique_topics else 'مواضيع عامة'}"
        
        return summary

# نموذج استخدام مباشر
if __name__ == "__main__":
    ai = SimpleAIModel()
    
    print("🧠 نموذج الذكاء الاصطناعي البسيط")
    print("=" * 40)
    
    while True:
        user_input = input("\n👤 أنت: ")
        
        if user_input.lower() in ['exit', 'quit', 'خروج']:
            print("ملخص المحادثة:", ai.get_conversation_summary())
            break
            
        response = ai.generate_response(user_input)
        print(f"🤖 النموذج: {response}")
