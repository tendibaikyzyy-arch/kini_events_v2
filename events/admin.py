# events/admin.py
from django.contrib import admin
from django.utils import timezone

from .models import Event, Registration, Notification, Feedback


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ("title", "date", "time", "place", "capacity", "created_by", "is_cancelled")
    list_filter = ("date", "is_cancelled")
    search_fields = ("title", "description", "place")
    actions = ["cancel_events"]

    def save_model(self, request, obj, form, change):
        if change:
            old = Event.objects.get(pk=obj.pk)

            date_changed = old.date != obj.date
            time_changed = old.time != obj.time
            place_changed = old.place != obj.place

            if date_changed or time_changed or place_changed:
                regs = Registration.objects.filter(event=obj).select_related("user")
                when_old = f"{old.date} {old.time or ''}".strip()
                when_new = f"{obj.date} {obj.time or ''}".strip()

                for r in regs:
                    Notification.objects.create(
                        user=r.user,
                        title="Изменение мероприятия",
                        body=(
                            f"Событие «{obj.title}» изменено.\n"
                            f"Было: {when_old}\n"
                            f"Стало: {when_new}\n"
                            f"Место: {obj.place or '-'}"
                        )
                    )

        super().save_model(request, obj, form, change)

    def cancel_events(self, request, queryset):
        for event in queryset:
            if event.is_cancelled:
                continue

            event.is_cancelled = True
            event.save(update_fields=["is_cancelled"])

            regs = Registration.objects.filter(event=event).select_related("user")
            when_str = f"{event.date} {event.time or ''}".strip()

            for r in regs:
                Notification.objects.create(
                    user=r.user,
                    title="Мероприятие отменено",
                    body=f"Событие «{event.title}» ({when_str}) было отменено."
                )

    cancel_events.short_description = "Отменить выбранные мероприятия"


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
