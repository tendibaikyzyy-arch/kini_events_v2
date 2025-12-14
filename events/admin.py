from django.contrib import admin
from django.utils import timezone

from .models import Event, Registration, Notification, Feedback


def _notify_participants(event: Event, title: str, body: str):
    regs = event.registrations.select_related("user").all()
    for r in regs:
        Notification.objects.create(user=r.user, title=title, body=body)


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ("title", "date", "time", "place", "capacity", "created_by", "is_cancelled", "cancelled_at")
    list_filter = ("date", "is_cancelled")
    search_fields = ("title", "description", "place")
    actions = ["cancel_selected_events"]

    def cancel_selected_events(self, request, queryset):
        now = timezone.localtime()
        count = 0

        for event in queryset:
            if event.is_cancelled:
                continue

            event.is_cancelled = True
            event.cancelled_at = now
            event.save(update_fields=["is_cancelled", "cancelled_at"])

            when_str = f"{event.date} {event.time or ''}".strip()
            _notify_participants(
                event,
                "Мероприятие отменено",
                f"Мероприятие «{event.title}» ({when_str}) отменено."
            )
            count += 1

        self.message_user(request, f"Отменено мероприятий: {count}")

    cancel_selected_events.short_description = "Отменить выбранные мероприятия (и уведомить участников)"

    def save_model(self, request, obj, form, change):
        # до сохранения — берём старую версию, чтобы понять что изменилось
        old = None
        if change and obj.pk:
            old = Event.objects.get(pk=obj.pk)

        # если админ поставил is_cancelled=True вручную — проставим cancelled_at
        if obj.is_cancelled and not obj.cancelled_at:
            obj.cancelled_at = timezone.localtime()

        super().save_model(request, obj, form, change)

        # после сохранения — рассылаем уведомления
        if old:
            # 1) отмена через чекбокс
            if (not old.is_cancelled) and obj.is_cancelled:
                when_str = f"{obj.date} {obj.time or ''}".strip()
                _notify_participants(
                    obj,
                    "Мероприятие отменено",
                    f"Мероприятие «{obj.title}» ({when_str}) отменено."
                )
                return

            # 2) изменение даты/времени/места/названия
            changed = []
            if old.date != obj.date or old.time != obj.time:
                changed.append("дата/время")
            if old.place != obj.place:
                changed.append("место")
            if old.title != obj.title:
                changed.append("название")

            if changed and (not obj.is_cancelled):
                old_when = f"{old.date} {old.time or ''}".strip()
                new_when = f"{obj.date} {obj.time or ''}".strip()
                _notify_participants(
                    obj,
                    "Изменение мероприятия",
                    f"Мероприятие было обновлено ({', '.join(changed)}): "
                    f"«{old.title}» ({old_when}) → «{obj.title}» ({new_when})."
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