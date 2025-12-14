from django.contrib import admin, messages
from django.utils import timezone

from .models import Event, Registration, Notification, Feedback


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ("title", "date", "time", "place", "capacity", "created_by", "is_cancelled")
    list_filter = ("date", "is_cancelled")
    search_fields = ("title", "description", "place")
    actions = ("cancel_events",)

    def get_queryset(self, request):
        # ✅ чтобы "исчезало" из списка мероприятий в админке
        qs = super().get_queryset(request)
        return qs.filter(is_cancelled=False)

    @admin.action(description="Отменить выбранные мероприятия (и уведомить участников)")
    def cancel_events(self, request, queryset):
        now = timezone.localtime()
        cancelled_count = 0

        for event in queryset:
            if event.is_cancelled:
                continue

            event.is_cancelled = True
            event.cancelled_at = now
            event.save(update_fields=["is_cancelled", "cancelled_at"])
            cancelled_count += 1

            # ✅ уведомляем всех зарегистрированных
            regs = Registration.objects.select_related("user").filter(event=event)
            when_str = f"{event.date} {event.time or ''}".strip()

            for r in regs:
                Notification.objects.create(
                    user=r.user,
                    title="Мероприятие отменено",
                    body=f"Мероприятие «{event.title}» ({when_str}) было отменено организатором."
                )

        self.message_user(request, f"Отменено мероприятий: {cancelled_count}", level=messages.SUCCESS)

    def save_model(self, request, obj, form, change):
        """
        ✅ если админ меняет дату/время/место — уведомить всех зарегистрированных
        """
        old = None
        if change and obj.pk:
            try:
                old = Event.objects.get(pk=obj.pk)
            except Event.DoesNotExist:
                old = None

        super().save_model(request, obj, form, change)

        # если отменено — не шлём "изменения"
        if obj.is_cancelled:
            return

        if old is not None:
            changed_fields = []
            if old.date != obj.date:
                changed_fields.append("дата")
            if old.time != obj.time:
                changed_fields.append("время")
            if old.place != obj.place:
                changed_fields.append("место")

            if changed_fields:
                regs = Registration.objects.select_related("user").filter(event=obj)
                before = f"{old.date} {old.time or ''}".strip()
                after = f"{obj.date} {obj.time or ''}".strip()

                for r in regs:
                    Notification.objects.create(
                        user=r.user,
                        title="Изменение мероприятия",
                        body=(
                            f"Изменилось мероприятие «{obj.title}»: "
                            f"{', '.join(changed_fields)}. Было: ({before}), стало: ({after})."
                        )
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