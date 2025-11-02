import subprocess
import os
import sys
import shutil
from typing import Dict, List, Tuple

class CommandExecutor:
    def __init__(self, base_path: str = "."):
        self.base_path = base_path
        self.command_history = []
        
    def execute_command(self, command: str, args: List[str] = None) -> Dict:
        """تنفيذ أمر shell مع معالجة الأخطاء"""
        try:
            if command == "create_file":
                return self.create_file(args[0], args[1] if len(args) > 1 else "")
            elif command == "create_directory":
                return self.create_directory(args[0])
            elif command == "run_script":
                return self.run_script(args[0])
            elif command == "install_package":
                return self.install_package(args[0])
            elif command == "list_files":
                return self.list_files(args[0] if args else ".")
            else:
                return self.run_system_command([command] + args)
                
        except Exception as e:
            return {"status": "error", "message": f"خطأ في التنفيذ: {str(e)}"}
    
    def create_file(self, filename: str, content: str = "") -> Dict:
        """إنشاء ملف جديد"""
        try:
            filepath = os.path.join(self.base_path, filename)
            
            # التأكد من وجود المجلد
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            
            self.command_history.append(f"create_file: {filename}")
            return {
                "status": "success", 
                "message": f"تم إنشاء الملف: {filename}",
                "filepath": filepath
            }
        except Exception as e:
            return {"status": "error", "message": f"فشل إنشاء الملف: {str(e)}"}
    
    def create_directory(self, dirname: str) -> Dict:
        """إنشاء مجلد جديد"""
        try:
            dirpath = os.path.join(self.base_path, dirname)
            os.makedirs(dirpath, exist_ok=True)
            
            self.command_history.append(f"create_directory: {dirname}")
            return {
                "status": "success", 
                "message": f"تم إنشاء المجلد: {dirname}",
                "dirpath": dirpath
            }
        except Exception as e:
            return {"status": "error", "message": f"فشل إنشاء المجلد: {str(e)}"}
    
    def run_script(self, script_path: str) -> Dict:
        """تشغيل سكربت Python"""
        try:
            result = subprocess.run(
                [sys.executable, script_path],
                capture_output=True,
                text=True,
                cwd=self.base_path
            )
            
            return {
                "status": "success",
                "returncode": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr
            }
        except Exception as e:
            return {"status": "error", "message": f"فشل تشغيل السكربت: {str(e)}"}
    
    def install_package(self, package: str) -> Dict:
        """تثبيت حزمة Python"""
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", package],
                capture_output=True,
                text=True
            )
            
            return {
                "status": "success" if result.returncode == 0 else "error",
                "message": f"تم تثبيت {package}" if result.returncode == 0 else f"فشل تثبيت {package}",
                "stdout": result.stdout,
                "stderr": result.stderr
            }
        except Exception as e:
            return {"status": "error", "message": f"فشل التثبيت: {str(e)}"}
    
    def list_files(self, path: str = ".") -> Dict:
        """عرض محتويات المجلد"""
        try:
            full_path = os.path.join(self.base_path, path)
            items = os.listdir(full_path)
            
            files = []
            directories = []
            
            for item in items:
                item_path = os.path.join(full_path, item)
                if os.path.isfile(item_path):
                    files.append(item)
                else:
                    directories.append(item)
            
            return {
                "status": "success",
                "path": full_path,
                "files": files,
                "directories": directories
            }
        except Exception as e:
            return {"status": "error", "message": f"فشل قراءة المجلد: {str(e)}"}
    
    def run_system_command(self, command_list: List[str]) -> Dict:
        """تنفيذ أمر نظام عام"""
        try:
            result = subprocess.run(
                command_list,
                capture_output=True,
                text=True,
                cwd=self.base_path
            )
            
            return {
                "status": "success" if result.returncode == 0 else "error",
                "returncode": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "command": " ".join(command_list)
            }
        except Exception as e:
            return {"status": "error", "message": f"فشل تنفيذ الأمر: {str(e)}"}
