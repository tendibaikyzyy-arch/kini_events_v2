from django.contrib import admin
from .models import Event, Registration, Notification, Feedback

def notify_event_participants(event: Event, title: str, body: str):
    user_ids = Registration.objects.filter(event=event).values_list("user_id", flat=True).distinct()
    notes = [Notification(user_id=uid, title=title, body=body) for uid in user_ids]
    if notes:
        Notification.objects.bulk_create(notes)

@admin.action(description="Отменить выбранные мероприятия")
def cancel_events(modeladmin, request, queryset):
    for e in queryset:
        if not e.is_cancelled:
            e.is_cancelled = True
            e.save(update_fields=["is_cancelled"])
            notify_event_participants(
                e,
                "Событие отменено",
                f"«{e.title}» отменено администратором."
            )

@admin.action(description="Снять отмену у выбранных мероприятий")
def uncancel_events(modeladmin, request, queryset):
    queryset.update(is_cancelled=False)

@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ('title', 'date', 'time', 'place', 'capacity', 'created_by', 'is_cancelled')
    list_filter = ('date', 'is_cancelled')
    search_fields = ('title', 'description', 'place')
    actions = [cancel_events, uncancel_events]

    def save_model(self, request, obj, form, change):
        old = None
        if change:
            old = Event.objects.get(pk=obj.pk)

        super().save_model(request, obj, form, change)

        # ✅ участникам: уведомление об обновлении (дата/время/место)
        if change and old:
            changed = []
            if old.date != obj.date: changed.append("дата")
            if old.time != obj.time: changed.append("время")
            if old.place != obj.place: changed.append("место")

            if changed:
                notify_event_participants(
                    obj,
                    "Событие обновлено",
                    f"«{obj.title}» обновлено ({', '.join(changed)}). Теперь: {obj.date} {obj.time or ''}, {obj.place or ''}".strip()
                )

@admin.register(Registration)
class RegistrationAdmin(admin.ModelAdmin):
    list_display = ('user', 'event', 'created_at', 'attended')
    list_filter = ('event', 'attended')
    search_fields = ('user__username', 'event__title')

    def save_model(self, request, obj, form, change):
        old_attended = None
        if change:
            old_attended = Registration.objects.get(pk=obj.pk).attended

        super().save_model(request, obj, form, change)

        # ✅ организатору: уведомление об обновлении посещаемости
        if change and old_attended != obj.attended:
            e = obj.event
            if e.created_by:
                Notification.objects.create(
                    user=e.created_by,
                    title="Посещаемость обновлена",
                    body=f"Посещаемость обновлена для «{e.title}»: {obj.user.username} attended = {obj.attended}"
                )

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
