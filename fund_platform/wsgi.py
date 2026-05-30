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

# Auto-migrate and Seed on Vercel startup
if os.environ.get('VERCEL'):
    from django.core.management import call_command
    try:
        print("Running auto-migrations and seeding on Vercel...")
        call_command('migrate', interactive=False)
        
        # Seed demo user
        from core.models import User, Organization
        if not User.objects.filter(username='treasurer_bob').exists():
            org, _ = Organization.objects.get_or_create(organization_name="Enterprise Community Fund")
            User.objects.create_superuser(
                username='treasurer_bob',
                password='bobpassword123',
                email='izadosolution729@gmail.com', # Use your company gmail for testing
                organization=org,
                role='treasurer',
                first_name='Bob',
                last_name='Treasurer'
            )
            print("Demo user 'treasurer_bob' created with company gmail.")

    except Exception as e:
        print(f"Startup error: {e}")




