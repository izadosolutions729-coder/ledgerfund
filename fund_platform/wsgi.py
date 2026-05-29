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

# Auto-migrate on Vercel startup to ensure tables exist
if os.environ.get('VERCEL'):
    from django.core.management import call_command
    try:
        print("Running auto-migrations on Vercel...")
        call_command('migrate', interactive=False)
    except Exception as e:
        print(f"Migration error: {e}")



