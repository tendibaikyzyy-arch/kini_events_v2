from django.contrib import admin
from .models import Event, Registration, Notification, Feedback

@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ('title', 'date', 'time', 'place', 'capacity', 'created_by')
    list_filter = ('date',)
    search_fields = ('title', 'description', 'place')

@admin.register(Registration)
class RegistrationAdmin(admin.ModelAdmin):
    list_display = ('user', 'event', 'created_at', 'attended')
    list_filter = ('event', 'attended')
    search_fields = ('user__username', 'event__title')

@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('user', 'title', 'is_read', 'created_at')
    list_filter = ('is_read',)
    search_fields = ('user__username', 'title', 'body')

@admin.register(Feedback)
class FeedbackAdmin(admin.ModelAdmin):
    list_display = ('event', 'user', 'rating', 'created_at', 'has_reply')
    list_filter = ('event', 'rating')
    search_fields = ('user__username', 'comment', 'reply')

    def has_reply(self, obj):
        return bool(obj.reply)
    has_reply.boolean = True
    has_reply.short_description = 'Ответ'
