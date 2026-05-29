"""
WSGI config for fund_platform project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/wsgi/
"""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'fund_platform.settings')

application = get_wsgi_application()
app = application

# Auto-migrate only if running on Vercel with temporary SQLite
if os.environ.get('VERCEL') and not (os.environ.get('DATABASE_URL') or os.environ.get('POSTGRES_URL')):
    from django.core.management import call_command
    try:
        call_command('migrate', interactive=False)
    except Exception:
        pass


