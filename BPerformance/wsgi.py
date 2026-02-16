"""
WSGI config for BPerformance project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.0/howto/deployment/wsgi/
"""

import os

from django.core.wsgi import get_wsgi_application

# We updated this to point to BPerformance instead of config
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'BPerformance.settings')

application = get_wsgi_application()