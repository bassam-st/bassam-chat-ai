import os
import json
from typing import Dict, List

class FileBuilder:
    def __init__(self, base_path: str = "."):
        self.base_path = base_path
        self.templates = self.load_templates()
    
    def load_templates(self) -> Dict:
        """تحميل قوالب الملفات الجاهزة"""
        return {
            "flask_app": {
                "filename": "app.py",
                "content": """
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)

@app.route('/')
def home():
    return '<h1>مرحباً في تطبيق Flask!</h1>'

@app.route('/api/chat', methods=['POST'])
def chat_api():
    data = request.get_json()
    message = data.get('message', '')
    
    response = {
        'status': 'success',
        'reply': f'تم استلام رسالتك: {message}',
        'timestamp': '2024-01-01 12:00:00'
    }
    
    return jsonify(response)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
"""
            },
            "fastapi_app": {
                "filename": "main.py",
                "content": """
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="Bassam Chat API")

class ChatRequest(BaseModel):
    message: str

class ChatResponse(BaseModel):
    status: str
    reply: str
    timestamp: str

@app.get("/")
async def home():
    return {"message": "مرحباً في FastAPI!"}

@app.post("/api/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    return ChatResponse(
        status="success",
        reply=f"تم استلام: {request.message}",
        timestamp="2024-01-01 12:00:00"
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
"""
            },
            "requirements": {
                "filename": "requirements.txt",
                "content": """flask==2.3.3
fastapi==0.104.1
uvicorn==0.24.0
pydantic==2.5.0
transformers==4.35.0
torch==2.1.0
numpy==1.24.3
scikit-learn==1.3.0
"""
            },
            "config": {
                "filename": "config.json",
                "content": """{
    "api": {
        "host": "0.0.0.0",
        "port": 5000,
        "debug": true
    },
    "model": {
        "name": "bassam-chat-ai",
        "version": "1.0.0"
    },
    "security": {
        "secret_key": "your-secret-key-here"
    }
}
"""
            }
        }
    
    def create_project_structure(self, project_name: str, structure: Dict) -> Dict:
        """إنشاء هيكل مشروع كامل"""
        try:
            project_path = os.path.join(self.base_path, project_name)
            os.makedirs(project_path, exist_ok=True)
            
            results = []
            
            for item_type, items in structure.items():
                if item_type == "directories":
                    for directory in items:
                        dir_path = os.path.join(project_path, directory)
                        os.makedirs(dir_path, exist_ok=True)
                        results.append(f"📁 تم إنشاء: {directory}")
                
                elif item_type == "files":
                    for file_info in items:
                        filename = file_info["name"]
                        content = file_info.get("content", "")
                        file_path = os.path.join(project_path, filename)
                        
                        os.makedirs(os.path.dirname(file_path), exist_ok=True)
                        
                        with open(file_path, 'w', encoding='utf-8') as f:
                            f.write(content)
                        
                        results.append(f"📄 تم إنشاء: {filename}")
            
            return {
                "status": "success",
                "project_path": project_path,
                "created_items": results
            }
            
        except Exception as e:
            return {"status": "error", "message": f"فشل إنشاء المشروع: {str(e)}"}
    
    def create_from_template(self, template_name: str, **kwargs) -> Dict:
        """إنشاء ملف من قالب معين"""
        try:
            if template_name not in self.templates:
                return {"status": "error", "message": f"القالب {template_name} غير موجود"}
            
            template = self.templates[template_name]
            filename = template["filename"]
            content = template["content"]
            
            # تطبيق المتغيرات على المحتوى
            for key, value in kwargs.items():
                content = content.replace(f"{{{key}}}", str(value))
            
            filepath = os.path.join(self.base_path, filename)
            
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            
            return {
                "status": "success",
                "message": f"تم إنشاء {filename} من القالب {template_name}",
                "filepath": filepath
            }
            
        except Exception as e:
            return {"status": "error", "message": f"فشل إنشاء الملف: {str(e)}"}
