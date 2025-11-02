#!/usr/bin/env python3
"""
هيكل مشروع Django كامل
نسخة حقيقية - يمكن استخدامه لإنشاء مشروع حقيقي
"""

import os
import subprocess
import sys

class DjangoProjectCreator:
    def __init__(self, project_name: str):
        self.project_name = project_name
        self.apps = ['chat', 'users', 'api']
        
    def create_project_structure(self):
        """إنشاء هيكل مشروع Django"""
        structure = {
            'directories': [
                self.project_name,
                f"{self.project_name}/static",
                f"{self.project_name}/static/css",
                f"{self.project_name}/static/js",
                f"{self.project_name}/static/images",
                f"{self.project_name}/templates",
                f"{self.project_name}/templates/{self.project_name}",
                f"{self.project_name}/media",
                'requirements',
                'docs'
            ],
            'files': {
                'manage.py': self.manage_py_content(),
                f'{self.project_name}/__init__.py': '',
                f'{self.project_name}/settings.py': self.settings_content(),
                f'{self.project_name}/urls.py': self.urls_content(),
                f'{self.project_name}/wsgi.py': self.wsgi_content(),
                'requirements/base.txt': self.requirements_content(),
                '.env.example': self.env_example_content(),
                'README.md': self.readme_content()
            }
        }
        
        return structure
    
    def manage_py_content(self):
        """محتويات manage.py"""
        return f"""#!/usr/bin/env python3
import os
import sys

if __name__ == "__main__":
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "{self.project_name}.settings")
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable?"
        ) from exc
    execute_from_command_line(sys.argv)
"""
    
    def settings_content(self):
        """إعدادات Django"""
        return f"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = 'bassam-django-secret-key-2024-{self.project_name}'

DEBUG = True

ALLOWED_HOSTS = ['localhost', '127.0.0.1', '0.0.0.0']

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = '{self.project_name}.urls'

TEMPLATES = [
    {{
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {{
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        }},
    }},
]

DATABASES = {{
    'default': {{
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }}
}}

LANGUAGE_CODE = 'ar-sa'
TIME_ZONE = 'Asia/Riyadh'
USE_I18N = True
USE_L10N = True
USE_TZ = True

STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# إعدادات REST Framework
REST_FRAMEWORK = {{
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.AllowAny',
    ],
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
    ],
}}
"""
    
    def urls_content(self):
        """روابط المشروع"""
        return f"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
"""
    
    def wsgi_content(self):
        """WSGI configuration"""
        return f"""
import os
from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', '{self.project_name}.settings')

application = get_wsgi_application()
"""
    
    def requirements_content(self):
        """متطلبات المشروع"""
        return """Django==4.2.7
djangorestframework==3.14.0
python-dotenv==1.0.0
"""
    
    def env_example_content(self):
        """نموذج ملف البيئة"""
        return """DEBUG=True
SECRET_KEY=your-secret-key-here
DATABASE_URL=sqlite:///db.sqlite3
ALLOWED_HOSTS=localhost,127.0.0.1
"""
    
    def readme_content(self):
        """ملف README"""
        return f"""# {self.project_name}

مشروع Django تم إنشاؤه تلقائياً بواسطة Bassam AI.

## المميزات

- ✅ Django 4.2
- ✅ REST API
- ✅ إعدادات عربية
- ✅ هيكل منظم

## التنصيب

```bash
pip install -r requirements/base.txt
python manage.py migrate
python manage.py runserver
