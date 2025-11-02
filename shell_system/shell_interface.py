import os
import sys
import readline
from typing import List, Dict
from .command_executor import CommandExecutor
from .file_builder import FileBuilder

class SmartShell:
    def __init__(self, base_path: str = "."):
        self.base_path = base_path
        self.executor = CommandExecutor(base_path)
        self.builder = FileBuilder(base_path)
        self.history = []
        
        # أوامر مساعدة
        self.help_commands = {
            "create": "إنشاء ملف أو مجلد - الاستخدام: create <type> <name> [content]",
            "build": "بناء مشروع من قالب - الاستخدام: build <template>",
            "run": "تشغيل سكربت - الاستخدام: run <script_path>",
            "install": "تثبيت حزمة - الاستخدام: install <package>",
            "list": "عرض الملفات - الاستخدام: list [path]",
            "help": "عرض هذه المساعدة",
            "exit": "الخروج من Shell"
        }
    
    def start_shell(self):
        """بدء Shell التفاعلي"""
        print("🚀 Bassam AI Shell - الإصدار 1.0")
        print("أدخل 'help' لعرض الأوامر المتاحة")
        print("=" * 50)
        
        while True:
            try:
                command = input(f"\n🤖 {os.getcwd()} $ ").strip()
                
                if not command:
                    continue
                
                if command.lower() in ['exit', 'quit', 'خروج']:
                    print("👋 مع السلامة!")
                    break
                
                result = self.process_command(command)
                self.display_result(result)
                
            except KeyboardInterrupt:
                print("\n\n⏹️ تم إيقاف Shell")
                break
            except Exception as e:
                print(f"❌ خطأ غير متوقع: {e}")
    
    def process_command(self, command: str) -> Dict:
        """معالجة الأمر وإرجاع النتيجة"""
        self.history.append(command)
        parts = command.split()
        main_command = parts[0].lower()
        args = parts[1:]
        
        if main_command == "help":
            return self.show_help()
        elif main_command == "create":
            return self.handle_create(args)
        elif main_command == "build":
            return self.handle_build(args)
        elif main_command == "run":
            return self.executor.run_script(args[0] if args else "")
        elif main_command == "install":
            return self.executor.install_package(args[0] if args else "")
        elif main_command == "list":
            return self.executor.list_files(args[0] if args else ".")
        else:
            return self.executor.execute_command(main_command, args)
    
    def handle_create(self, args: List[str]) -> Dict:
        """معالجة أوامر الإنشاء"""
        if not args:
            return {"status": "error", "message": "الاستخدام: create <type> <name> [content]"}
        
        create_type = args[0].lower()
        
        if create_type == "file" and len(args) >= 2:
            filename = args[1]
            content = " ".join(args[2:]) if len(args) > 2 else ""
            return self.executor.create_file(filename, content)
        
        elif create_type == "dir" and len(args) >= 2:
            dirname = args[1]
            return self.executor.create_directory(dirname)
        
        elif create_type == "project" and len(args) >= 2:
            project_name = args[1]
            structure = {
                "directories": ["src", "tests", "docs", "data"],
                "files": [
                    {"name": "src/__init__.py", "content": ""},
                    {"name": "src/main.py", "content": "# المشروع الرئيسي\nprint('مرحباً!')\n"},
                    {"name": "README.md", "content": f"# {project_name}\n\nمشروع تم إنشاؤه تلقائياً."},
                    {"name": "requirements.txt", "content": "python>=3.8\n"}
                ]
            }
            return self.builder.create_project_structure(project_name, structure)
        
        else:
            return {"status": "error", "message": "نوع الإنشاء غير معروف"}
    
    def handle_build(self, args: List[str]) -> Dict:
        """معالجة أوامر البناء من القوالب"""
        if not args:
            return {"status": "error", "message": "الاستخدام: build <template> [params...]"}
        
        template_name = args[0].lower()
        
        if template_name == "flask":
            return self.builder.create_from_template("flask_app")
        elif template_name == "fastapi":
            return self.builder.create_from_template("fastapi_app")
        elif template_name == "requirements":
            return self.builder.create_from_template("requirements")
        elif template_name == "config":
            return self.builder.create_from_template("config")
        else:
            return {"status": "error", "message": f"القالب {template_name} غير معروف"}
    
    def show_help(self) -> Dict:
        """عرض المساعدة"""
        help_text = "📖 **الأوامر المتاحة:**\n\n"
        for cmd, desc in self.help_commands.items():
            help_text += f"• **{cmd}**: {desc}\n"
        
        help_text += "\n**أمثلة:**\n"
        help_text += "  create file main.py 'print(\\\"Hello\\\")'\n"
        help_text += "  create dir my_project\n"
        help_text += "  build flask\n"
        help_text += "  run script.py\n"
        help_text += "  install requests\n"
        
        return {"status": "success", "message": help_text}
    
    def display_result(self, result: Dict):
        """عرض نتيجة الأمر"""
        status = result.get("status", "unknown")
        message = result.get("message", "")
        
        if status == "success":
            print(f"✅ {message}")
            
            # عرض مخرجات إضافية إذا وجدت
            if "stdout" in result and result["stdout"]:
                print(f"📤 المخرجات:\n{result['stdout']}")
            
            if "filepath" in result:
                print(f"📄 المسار: {result['filepath']}")
                
        elif status == "error":
            print(f"❌ {message}")
            
            if "stderr" in result and result["stderr"]:
                print(f"📤 أخطاء:\n{result['stderr']}")
        else:
            print(f"🤔 نتيجة غير معروفة: {result}")
