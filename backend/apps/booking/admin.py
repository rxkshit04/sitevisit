from django.contrib import admin

from .models import Booking, Slot

admin.site.register(Slot)
admin.site.register(Booking)