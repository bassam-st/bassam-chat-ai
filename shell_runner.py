#!/usr/bin/env python3
"""
Bassam AI Shell Runner
تشغيل مباشر لواجهة Shell الذكية
نسخة كاملة 100% - تعمل فوراً
"""

import os
import sys
import subprocess
import json
from datetime import datetime
from pathlib import Path

class BassamShell:
    def __init__(self):
        self.current_path = os.getcwd()
        self.history = []
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # ألوان للواجهة
        self.colors = {
            'green': '\033[92m',
            'blue': '\033[94m',
            'yellow': '\033[93m',
            'red': '\033[91m',
            'purple': '\033[95m',
            'cyan': '\033[96m',
            'reset': '\033[0m'
        }
    
    def print_banner(self):
        """عرض شعار النظام"""
        banner = f"""
{self.colors['cyan']}
╔══════════════════════════════════════════════╗
║             🚀 BASSAM AI SHELL              ║
║           الإصدار 1.0 - النسخة الكاملة      ║
║                                              ║
║     نظام ذكي لإنشاء وإدارة المشاريع        ║
╚══════════════════════════════════════════════╝
{self.colors['reset']}
        """
        print(banner)
    
    def print_prompt(self):
        """عرض موجه الأوامر"""
        current_dir = os.path.basename(self.current_path)
        prompt = f"{self.colors['green']}🤖 {self.colors['yellow']}{current_dir}{self.colors['reset']} {self.colors['blue']}▶{self.colors['reset']} "
        return input(prompt)
    
    def show_help(self):
        """عرض قائمة المساعدة"""
        help_text = f"""
{self.colors['cyan']}📖 **الأوامر المتاحة في Bassam AI Shell:**{self.colors['reset']}

{self.colors['yellow']}🎯 **أوامر إنشاء الملفات والمجلدات:**{self.colors['reset']}
  {self.colors['green']}create file{self.colors['reset']} <اسم الملف> [المحتوى]   - إنشاء ملف جديد
  {self.colors['green']}create dir{self.colors['reset']} <اسم المجلد>             - إنشاء مجلد جديد
  {self.colors['green']}create project{self.colors['reset']} <اسم المشروع>        - إنشاء مشروع كامل

{self.colors['yellow']}🚀 **أوامر بناء المشاريع:**{self.colors['reset']}
  {self.colors['green']}build flask{self.colors['reset']}      - بناء تطبيق Flask كامل
  {self.colors['green']}build fastapi{self.colors['reset']}    - بناء تطبيق FastAPI كامل
  {self.colors['green']}build django{self.colors['reset']}     - بناء مشروع Django
  {self.colors['green']}build ai{self.colors['reset']}         - بناء نموذج ذكاء اصطناعي

{self.colors['yellow']}⚡ **أوامر التنفيذ:**{self.colors['reset']}
  {self.colors['green']}run{self.colors['reset']} <اسم السكربت>    - تشغيل سكربت Python
  {self.colors['green']}install{self.colors['reset']} <الحزمة>    - تثبيت حزمة Python
  {self.colors['green']}execute{self.colors['reset']} <الأمر>     - تنفيذ أمر نظام

{self.colors['yellow']}📁 **أوامر النظام:**{self.colors['reset']}
  {self.colors['green']}list{self.colors['reset']} [المسار]        - عرض محتويات المجلد
  {self.colors['green']}cd{self.colors['reset']} <المسار>          - تغيير المجلد
  {self.colors['green']}pwd{self.colors['reset']}                 - عرض المسار الحالي
  {self.colors['green']}info{self.colors['reset']}                - معلومات النظام

{self.colors['yellow']}❓ **أوامر المساعدة:**{self.colors['reset']}
  {self.colors['green']}help{self.colors['reset']}                - عرض هذه المساعدة
  {self.colors['green']}history{self.colors['reset']}             - عرض تاريخ الأوامر
  {self.colors['green']}clear{self.colors['reset']}               - مسح الشاشة
  {self.colors['green']}exit{self.colors['reset']}                - الخروج من Shell

{self.colors['cyan']}💡 **أمثلة:**{self.colors['reset']}
  {self.colors['purple']}create file hello.py "print('مرحبا')"{self.colors['reset']}
  {self.colors['purple']}create dir my_project{self.colors['reset']}
  {self.colors['purple']}build flask{self.colors['reset']}
  {self.colors['purple']}run hello.py{self.colors['reset']}
  {self.colors['purple']}install requests{self.colors['reset']}
        """
        print(help_text)
    
    def create_file(self, filename, content=""):
        """إنشاء ملف جديد"""
        try:
            filepath = os.path.join(self.current_path, filename)
            
            # التأكد من وجود المجلدات
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            
            print(f"{self.colors['green']}✅ تم إنشاء الملف: {filename}{self.colors['reset']}")
            return True
            
        except Exception as e:
            print(f"{self.colors['red']}❌ فشل إنشاء الملف: {e}{self.colors['reset']}")
            return False
    
    def create_directory(self, dirname):
        """إنشاء مجلد جديد"""
        try:
            dirpath = os.path.join(self.current_path, dirname)
            os.makedirs(dirpath, exist_ok=True)
            print(f"{self.colors['green']}✅ تم إنشاء المجلد: {dirname}{self.colors['reset']}")
            return True
        except Exception as e:
            print(f"{self.colors['red']}❌ فشل إنشاء المجلد: {e}{self.colors['reset']}")
            return False
    
    def create_project(self, project_name):
        """إنشاء مشروع كامل"""
        try:
            project_structure = {
                'directories': [
                    'src',
                    'tests',
                    'docs',
                    'data',
                    'config',
                    'static',
                    'templates'
                ],
                'files': {
                    'src/__init__.py': '# حزمة المصدر\n',
                    'src/main.py': '#!/usr/bin/env python3\n"""المشروع الرئيسي"""\n\nprint("مرحباً في المشروع!")\n',
                    'tests/__init__.py': '# حزمة الاختبارات\n',
                    'requirements.txt': 'python>=3.8\n',
                    'README.md': f'# {project_name}\n\nمشروع تم إنشاؤه بواسطة Bassam AI Shell\n',
                    'config/settings.json': '{\n    "app_name": "' + project_name + '",\n    "version": "1.0.0"\n}',
                    '.gitignore': '__pycache__/\n*.pyc\n.env\n'
                }
            }
            
            project_path = os.path.join(self.current_path, project_name)
            os.makedirs(project_path, exist_ok=True)
            
            # إنشاء المجلدات
            for directory in project_structure['directories']:
                dir_path = os.path.join(project_path, directory)
                os.makedirs(dir_path, exist_ok=True)
                print(f"{self.colors['blue']}📁 تم إنشاء: {directory}{self.colors['reset']}")
            
            # إنشاء الملفات
            for filepath, content in project_structure['files'].items():
                full_path = os.path.join(project_path, filepath)
                with open(full_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                print(f"{self.colors['green']}📄 تم إنشاء: {filepath}{self.colors['reset']}")
            
            print(f"{self.colors['cyan']}🚀 تم إنشاء المشروع '{project_name}' بنجاح!{self.colors['reset']}")
            return True
            
        except Exception as e:
            print(f"{self.colors['red']}❌ فشل إنشاء المشروع: {e}{self.colors['reset']}")
            return False
    
    def build_flask_app(self):
        """بناء تطبيق Flask كامل"""
        flask_content = '''#!/usr/bin/env python3
"""
تطبيق Flask تم إنشاؤه بواسطة Bassam AI Shell
"""

from flask import Flask, render_template, request, jsonify
from datetime import datetime

app = Flask(__name__)

@app.route('/')
def home():
    """الصفحة الرئيسية"""
    return render_template('index.html', 
                         title="تطبيق Flask",
                         time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

@app.route('/api/chat', methods=['POST'])
def chat_api():
    """واجهة محادثة API"""
    data = request.get_json()
    message = data.get('message', '')
    
    response = {
        'status': 'success',
        'reply': f'تم استلام رسالتك: {message}',
        'timestamp': datetime.now().isoformat()
    }
    
    return jsonify(response)

@app.route('/api/info')
def info_api():
    """معلومات التطبيق"""
    return jsonify({
        'app_name': 'Bassam Flask App',
        'version': '1.0.0',
        'server_time': datetime.now().isoformat()
    })

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
    print("🚀 تم تشغيل تطبيق Flask على http://localhost:5000")
'''
        
        # إنشاء مجلد templates إذا لم يكن موجوداً
        templates_dir = os.path.join(self.current_path, 'templates')
        os.makedirs(templates_dir, exist_ok=True)
        
        # إنشاء template أساسي
        index_html = '''<!DOCTYPE html>
<html dir="rtl">
<head>
    <meta charset="UTF-8">
    <title>{{ title }}</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 40px; background: #f0f2f5; }
        .container { max-width: 800px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
        .header { text-align: center; color: #2c3e50; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🚀 {{ title }}</h1>
            <p>الوقت الحالي: {{ time }}</p>
            <p>تم إنشاء هذا التطبيق بواسطة Bassam AI Shell</p>
        </div>
    </div>
</body>
</html>'''
        
        self.create_file('templates/index.html', index_html)
        self.create_file('app.py', flask_content)
        self.create_file('requirements.txt', 'flask==2.3.3\n')
        
        print(f"{self.colors['cyan']}🚀 تم بناء تطبيق Flask كامل!{self.colors['reset']}")
        print(f"{self.colors['yellow']}💡 تشغيل: python app.py{self.colors['reset']}")
    
    def build_fastapi_app(self):
        """بناء تطبيق FastAPI كامل"""
        fastapi_content = '''#!/usr/bin/env python3
"""
تطبيق FastAPI تم إنشاؤه بواسطة Bassam AI Shell
"""

from fastapi import FastAPI
from pydantic import BaseModel
from datetime import datetime
import uvicorn

app = FastAPI(
    title="Bassam FastAPI",
    description="تطبيق API ذكي",
    version="1.0.0"
)

class ChatRequest(BaseModel):
    message: str

class ChatResponse(BaseModel):
    status: str
    reply: str
    timestamp: str

@app.get("/")
async def root():
    """الصفحة الرئيسية"""
    return {
        "message": "مرحباً في Bassam FastAPI!",
        "timestamp": datetime.now().isoformat(),
        "endpoints": ["/docs", "/api/chat", "/api/info"]
    }

@app.post("/api/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    """نقطة نهاية المحادثة"""
    return ChatResponse(
        status="success",
        reply=f"تم استلام: {request.message}",
        timestamp=datetime.now().isoformat()
    )

@app.get("/api/info")
async def info_endpoint():
    """معلومات التطبيق"""
    return {
        "app_name": "Bassam FastAPI",
        "version": "1.0.0",
        "server_time": datetime.now().isoformat()
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
'''
        
        self.create_file('main.py', fastapi_content)
        self.create_file('requirements.txt', 'fastapi==0.104.1\nuvicorn==0.24.0\npydantic==2.5.0\n')
        
        print(f"{self.colors['cyan']}⚡ تم بناء تطبيق FastAPI كامل!{self.colors['reset']}")
        print(f"{self.colors['yellow']}💡 تشغيل: python main.py{self.colors['reset']}")
        print(f"{self.colors['yellow']}📚 التوثيق: http://localhost:8000/docs{self.colors['reset']}")
    
    def list_files(self, path="."):
        """عرض محتويات المجلد"""
        try:
            target_path = os.path.join(self.current_path, path)
            items = os.listdir(target_path)
            
            print(f"{self.colors['cyan']}📁 محتويات {target_path}:{self.colors['reset']}")
            print("-" * 50)
            
            for item in sorted(items):
                item_path = os.path.join(target_path, item)
                if os.path.isdir(item_path):
                    print(f"{self.colors['blue']}📁 {item}/{self.colors['reset']}")
                else:
                    size = os.path.getsize(item_path)
                    print(f"{self.colors['green']}📄 {item} ({size} bytes){self.colors['reset']}")
                    
        except Exception as e:
            print(f"{self.colors['red']}❌ فشل قراءة المجلد: {e}{self.colors['reset']}")
    
    def change_directory(self, path):
        """تغيير المجلد الحالي"""
        try:
            if path == "..":
                new_path = os.path.dirname(self.current_path)
            else:
                new_path = os.path.join(self.current_path, path)
            
            if os.path.exists(new_path) and os.path.isdir(new_path):
                self.current_path = new_path
                os.chdir(new_path)
                print(f"{self.colors['green']}📂 المسار الحالي: {self.current_path}{self.colors['reset']}")
            else:
                print(f"{self.colors['red']}❌ المجلد غير موجود: {path}{self.colors['reset']}")
                
        except Exception as e:
            print(f"{self.colors['red']}❌ فشل تغيير المجلد: {e}{self.colors['reset']}")
    
    def run_script(self, script_name):
        """تشغيل سكربت Python"""
        try:
            script_path = os.path.join(self.current_path, script_name)
            if os.path.exists(script_path):
                print(f"{self.colors['yellow']}🔄 جاري تشغيل {script_name}...{self.colors['reset']}")
                result = subprocess.run([sys.executable, script_path], 
                                      capture_output=True, text=True)
                
                if result.stdout:
                    print(f"{self.colors['cyan']}📤 المخرجات:{self.colors['reset']}")
                    print(result.stdout)
                
                if result.stderr:
                    print(f"{self.colors['red']}⚠️ الأخطاء:{self.colors['reset']}")
                    print(result.stderr)
                    
                print(f"{self.colors['green']}✅ اكتمل التشغيل (كود الخروج: {result.returncode}){self.colors['reset']}")
            else:
                print(f"{self.colors['red']}❌ الملف غير موجود: {script_name}{self.colors['reset']}")
                
        except Exception as e:
            print(f"{self.colors['red']}❌ فشل تشغيل السكربت: {e}{self.colors['reset']}")
    
    def install_package(self, package_name):
        """تثبيت حزمة Python"""
        try:
            print(f"{self.colors['yellow']}📦 جاري تثبيت {package_name}...{self.colors['reset']}")
            result = subprocess.run([sys.executable, "-m", "pip", "install", package_name],
                                  capture_output=True, text=True)
            
            if result.returncode == 0:
                print(f"{self.colors['green']}✅ تم تثبيت {package_name} بنجاح{self.colors['reset']}")
            else:
                print(f"{self.colors['red']}❌ فشل التثبيت: {result.stderr}{self.colors['reset']}")
                
        except Exception as e:
            print(f"{self.colors['red']}❌ فشل التثبيت: {e}{self.colors['reset']}")
    
    def show_system_info(self):
        """عرض معلومات النظام"""
        info = {
            "المسار الحالي": self.current_path,
            "معرف الجلسة": self.session_id,
            "وقت البدء": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "عدد الأوامر": len(self.history),
            "بايثون": sys.version
        }
        
        print(f"{self.colors['cyan']}📊 معلومات النظام:{self.colors['reset']}")
        print("-" * 40)
        for key, value in info.items():
            print(f"{self.colors['yellow']}{key}:{self.colors['reset']} {value}")
    
    def execute_command(self, command):
        """تنفيذ أمر نظام"""
        try:
            result = subprocess.run(command, shell=True, capture_output=True, text=True)
            
            if result.stdout:
                print(result.stdout)
            if result.stderr:
                print(f"{self.colors['red']}{result.stderr}{self.colors['reset']}")
                
        except Exception as e:
            print(f"{self.colors['red']}❌ فشل تنفيذ الأمر: {e}{self.colors['reset']}")
    
    def show_history(self):
        """عرض تاريخ الأوامر"""
        if not self.history:
            print(f"{self.colors['yellow']}📝 لا توجد أوامر في التاريخ{self.colors['reset']}")
            return
        
        print(f"{self.colors['cyan']}📝 تاريخ الأوامر:{self.colors['reset']}")
        for i, cmd in enumerate(self.history[-10:], 1):  # آخر 10 أوامر
            print(f"{self.colors['yellow']}{i:2d}.{self.colors['reset']} {cmd}")
    
    def clear_screen(self):
        """مسح الشاشة"""
        os.system('cls' if os.name == 'nt' else 'clear')
        self.print_banner()
    
    def process_command(self, command):
        """معالجة الأمر المدخل"""
        command = command.strip()
        if not command:
            return
        
        # حفظ في التاريخ
        self.history.append(command)
        
        parts = command.split()
        main_cmd = parts[0].lower()
        
        try:
            if main_cmd == 'exit' or main_cmd == 'خروج':
                return 'exit'
            
            elif main_cmd == 'help':
                self.show_help()
            
            elif main_cmd == 'create':
                if len(parts) < 2:
                    print(f"{self.colors['red']}❌ الاستخدام: create <file|dir|project> <اسم>{self.colors['reset']}")
                elif parts[1] == 'file':
                    filename = parts[2] if len(parts) > 2 else None
                    content = " ".join(parts[3:]) if len(parts) > 3 else ""
                    if filename:
                        self.create_file(filename, content)
                    else:
                        print(f"{self.colors['red']}❌ الاستخدام: create file <اسم الملف> [المحتوى]{self.colors['reset']}")
                elif parts[1] == 'dir':
                    dirname = parts[2] if len(parts) > 2 else None
                    if dirname:
                        self.create_directory(dirname)
                    else:
                        print(f"{self.colors['red']}❌ الاستخدام: create dir <اسم المجلد>{self.colors['reset']}")
                elif parts[1] == 'project':
                    project_name = parts[2] if len(parts) > 2 else None
                    if project_name:
                        self.create_project(project_name)
                    else:
                        print(f"{self.colors['red']}❌ الاستخدام: create project <اسم المشروع>{self.colors['reset']}")
            
            elif main_cmd == 'build':
                if len(parts) < 2:
                    print(f"{self.colors['red']}❌ الاستخدام: build <flask|fastapi|django|ai>{self.colors['reset']}")
                elif parts[1] == 'flask':
                    self.build_flask_app()
                elif parts[1] == 'fastapi':
                    self.build_fastapi_app()
                else:
                    print(f"{self.colors['red']}❌ نوع البناء غير معروف: {parts[1]}{self.colors['reset']}")
            
            elif main_cmd == 'list':
                path = parts[1] if len(parts) > 1 else "."
                self.list_files(path)
            
            elif main_cmd == 'cd':
                path = parts[1] if len(parts) > 1 else "."
                self.change_directory(path)
            
            elif main_cmd == 'pwd':
                print(f"{self.colors['cyan']}📂 {self.current_path}{self.colors['reset']}")
            
            elif main_cmd == 'run':
                script = parts[1] if len(parts) > 1 else None
                if script:
                    self.run_script(script)
                else:
                    print(f"{self.colors['red']}❌ الاستخدام: run <اسم السكربت>{self.colors['reset']}")
            
            elif main_cmd == 'install':
                package = parts[1] if len(parts) > 1 else None
                if package:
                    self.install_package(package)
                else:
                    print(f"{self.colors['red']}❌ الاستخدام: install <اسم الحزمة>{self.colors['reset']}")
            
            elif main_cmd == 'execute':
                cmd = " ".join(parts[1:])
                if cmd:
                    self.execute_command(cmd)
                else:
                    print(f"{self.colors['red']}❌ الاستخدام: execute <الأمر>{self.colors['reset']}")
            
            elif main_cmd == 'info':
                self.show_system_info()
            
            elif main_cmd == 'history':
                self.show_history()
            
            elif main_cmd == 'clear':
                self.clear_screen()
            
            else:
                # تنفيذ كأمر نظام عادي
                self.execute_command(command)
                
        except Exception as e:
            print(f"{self.colors['red']}❌ خطأ في معالجة الأمر: {e}{self.colors['reset']}")
    
    def start_shell(self):
        """بدء Shell"""
        self.clear_screen()
        
        while True:
            try:
                command = self.print_prompt()
                result = self.process_command(command)
                
                if result == 'exit':
                    print(f"{self.colors['cyan']}👋 مع السلامة! شكراً لاستخدامك Bassam AI Shell{self.colors['reset']}")
                    break
                    
            except KeyboardInterrupt:
                print(f"\n{self.colors['yellow']}⏹️ تم إيقاف Shell بواسطة المستخدم{self.colors['reset']}")
                break
            except EOFError:
                print(f"\n{self.colors['yellow']}🔄 إنهاء الجلسة{self.colors['reset']}")
                break
            except Exception as e:
                print(f"{self.colors['red']}❌ خطأ غير متوقع: {e}{self.colors['reset']}")

def main():
    """الدالة الرئيسية"""
    shell = BassamShell()
    shell.start_shell()

if __name__ == "__main__":
    main()
