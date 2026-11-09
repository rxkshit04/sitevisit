from django.contrib import admin

from .models import OutboxMessage

admin.site.register(OutboxMessage)