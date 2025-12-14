from django.contrib import admin
from django.utils import timezone

from .models import Event, Registration, Notification, Feedback


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ("title", "date", "time", "place", "capacity", "created_by", "is_cancelled")
    list_filter = ("date",)
    search_fields = ("title", "description", "place")
    actions = ("cancel_events",)

    def is_cancelled(self, obj):
        return bool(getattr(obj, "event_cancelled_at", None))
    is_cancelled.boolean = True
    is_cancelled.short_description = "Отменено"

    def _notify_registered(self, event, title, body):
        regs = Registration.objects.select_related("user").filter(event=event)
        notes = []
        for r in regs:
            notes.append(Notification(user=r.user, title=title, body=body))
        if notes:
            Notification.objects.bulk_create(notes)

    @admin.action(description="Отменить выбранные события (и уведомить участников)")
    def cancel_events(self, request, queryset):
        now = timezone.now()
        for event in queryset:
            if getattr(event, "event_cancelled_at", None):
                continue
            event.event_cancelled_at = now
            event.save(update_fields=["event_cancelled_at"])

            self._notify_registered(
                event,
                "Мероприятие отменено",
                f"Мероприятие «{event.title}» ({event.date} {event.time or ''}) отменено."
            )

    def save_model(self, request, obj, form, change):
        old = None
        if change and obj.pk:
            old = Event.objects.filter(pk=obj.pk).first()

        super().save_model(request, obj, form, change)

        if not old:
            return

        # 1) если событие стало отменённым через редактирование
        if hasattr(obj, "event_cancelled_at"):
            was_cancelled = bool(getattr(old, "event_cancelled_at", None))
            is_cancelled = bool(getattr(obj, "event_cancelled_at", None))
            if (not was_cancelled) and is_cancelled:
                self._notify_registered(
                    obj,
                    "Мероприятие отменено",
                    f"Мероприятие «{obj.title}» ({obj.date} {obj.time or ''}) отменено."
                )
                return

        # 2) если изменили важные поля (дата/время/место/название)
        changed = []
        if old.title != obj.title:
            changed.append(("Название", old.title, obj.title))
        if old.date != obj.date:
            changed.append(("Дата", str(old.date), str(obj.date)))
        if old.time != obj.time:
            changed.append(("Время", str(old.time or ""), str(obj.time or "")))
        if old.place != obj.place:
            changed.append(("Место", old.place or "-", obj.place or "-"))

        if changed:
            lines = ["Организатор изменил данные мероприятия:"]
            for name, before, after in changed:
                lines.append(f"{name}: {before} → {after}")

            self._notify_registered(
                obj,
                "Изменение мероприятия",
                "\n".join(lines)
            )


@admin.register(Registration)
class RegistrationAdmin(admin.ModelAdmin):
    list_display = ("user", "event", "created_at", "attended")
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