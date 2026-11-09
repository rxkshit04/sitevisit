from django.contrib import admin

from .models import ChatMessage, Conversation, FactEntry, Handoff

admin.site.register(FactEntry)
admin.site.register(Conversation)
admin.site.register(ChatMessage)
admin.site.register(Handoff)