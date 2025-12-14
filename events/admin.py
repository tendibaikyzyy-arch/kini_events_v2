from django.contrib import admin
from .models import Event, Registration, Notification, Feedback


@admin.action(description="Отменить событие и уведомить участников")
def cancel_events(modeladmin, request, queryset):
    qs = queryset.filter(is_cancelled=False)
    for event in qs:
        regs = Registration.objects.select_related("user").filter(event=event)
        when_str = f"{event.date} {event.time or ''}".strip()

        for r in regs:
            Notification.objects.create(
                user=r.user,
                title="Событие отменено",
                body=f"Мероприятие «{event.title}» ({when_str}) было отменено."
            )

        event.is_cancelled = True
        event.save(update_fields=["is_cancelled"])


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ("title", "date", "time", "place", "capacity", "created_by", "is_cancelled")
    list_filter = ("date", "is_cancelled")
    search_fields = ("title", "description", "place")
    actions = [cancel_events]


@admin.register(Registration)
class RegistrationAdmin(admin.ModelAdmin):
    list_display = ("user", "event", "created_at", "attended", "last_reminded_on")
    list_filter = ("event", "attended")
    search_fields = ("user__username", "event__title")


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("user", "title", "is_read", "created_at")
    list_filter = ("is_read",)
    search_fields = ("user__username", "title", "body")


@admin.register(Feedback)
class FeedbackAdmin(admin.ModelAdmin):
    list_display = ("event", "user", "rating", "created_at", "has_reply")
    list_filter = ("event", "rating")
    search_fields = ("user__username", "comment", "reply")

    def has_reply(self, obj):
        return bool(obj.reply)

    has_reply.boolean = True
    has_reply.short_description = "Ответ"
