import os
import subprocess
import sys

class SmartShell:
    def __init__(self, base_path: str = "."):
        self.base_path = base_path
        self.history = []
    
    def start_shell(self):
        print("🚀 Bassam AI Shell - الإصدار 1.0")
        print("أدخل 'help' لعرض الأوامر المتاحة")
        print("=" * 50)
        
        while True:
            try:
                command = input(f"🤖 {os.getcwd()} $ ").strip()
                
                if command.lower() in ['exit', 'quit', 'خروج']:
                    print("👋 مع السلامة!")
                    break
                elif command == 'help':
                    self.show_help()
                elif command.startswith('create file'):
                    self.create_file(command)
                elif command.startswith('create dir'):
                    self.create_dir(command)
                elif command == 'list':
                    self.list_files()
                elif command.startswith('build'):
                    self.build_project(command)
                else:
                    self.run_system_command(command)
                    
            except KeyboardInterrupt:
                print("\n⏹️ تم إيقاف Shell")
                break
            except Exception as e:
                print(f"❌ خطأ: {e}")
    
    def show_help(self):
        print("""
📖 **الأوامر المتاحة:**

• create file <اسم الملف> [المحتوى] - إنشاء ملف
• create dir <اسم المجلد> - إنشاء مجلد  
• build flask - بناء تطبيق Flask
• build fastapi - بناء تطبيق FastAPI
• list - عرض الملفات
• run <سكربت> - تشغيل سكربت
• install <حزمة> - تثبيت حزمة
• help - عرض هذه المساعدة
• exit - الخروج
        """)
    
    def create_file(self, command):
        parts = command.split()
        if len(parts) >= 3:
            filename = parts[2]
            content = " ".join(parts[3:]) if len(parts) > 3 else ""
            
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"✅ تم إنشاء الملف: {filename}")
        else:
            print("❌ الاستخدام: create file <اسم الملف> [المحتوى]")
    
    def create_dir(self, command):
        parts = command.split()
        if len(parts) >= 3:
            dirname = parts[2]
            os.makedirs(dirname, exist_ok=True)
            print(f"✅ تم إنشاء المجلد: {dirname}")
        else:
            print("❌ الاستخدام: create dir <اسم المجلد>")
    
    def list_files(self):
        items = os.listdir('.')
        for item in items:
            if os.path.isdir(item):
                print(f"📁 {item}/")
            else:
                print(f"📄 {item}")
    
    def build_project(self, command):
        if 'flask' in command:
            with open('app.py', 'w', encoding='utf-8') as f:
                f.write("""
from flask import Flask
app = Flask(__name__)

@app.route('/')
def home():
    return 'مرحباً من Flask!'

if __name__ == '__main__':
    app.run(debug=True)
""")
            print("✅ تم بناء تطبيق Flask في app.py")
        
        elif 'fastapi' in command:
            with open('main.py', 'w', encoding='utf-8') as f:
                f.write("""
from fastapi import FastAPI
app = FastAPI()

@app.get("/")
def home():
    return {"message": "مرحباً من FastAPI!"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
""")
            print("✅ تم بناء تطبيق FastAPI في main.py")
    
    def run_system_command(self, command):
        try:
            result = subprocess.run(command, shell=True, capture_output=True, text=True)
            if result.stdout:
                print(result.stdout)
            if result.stderr:
                print(f"⚠️ {result.stderr}")
        except Exception as e:
            print(f"❌ فشل تنفيذ الأمر: {e}")

if __name__ == "__main__":
    shell = SmartShell()
    shell.start_shell()
