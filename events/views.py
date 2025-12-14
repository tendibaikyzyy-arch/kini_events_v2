from datetime import datetime

from django.utils import timezone
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponseForbidden
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError
from django.db.models import Avg

from .models import Event, Registration, Notification, Feedback


def home(request):
    return render(request, "events/home.html")


def register(request):
    if request.method == "POST":
        username = (request.POST.get("username") or "").strip()
        email = (request.POST.get("email") or "").strip()
        password = request.POST.get("password") or ""
        confirm = request.POST.get("confirm_password") or ""

        if not username or not email or not password:
            messages.error(request, "Все поля должны быть заполнены.")
            return render(request, "events/register.html")

        if password != confirm:
            messages.error(request, "Пароли не совпадают.")
            return render(request, "events/register.html")

        if User.objects.filter(username=username).exists():
            messages.error(request, "Пользователь с таким именем уже существует.")
            return render(request, "events/register.html")

        if User.objects.filter(email=email).exists():
            messages.error(request, "Эта почта уже используется.")
            return render(request, "events/register.html")

        user = User.objects.create_user(username=username, email=email, password=password)
        login(request, user)
        return redirect("dashboard")

    return render(request, "events/register.html")


def login_view(request):
    if request.method == "POST":
        username = (request.POST.get("username") or "").strip()
        password = request.POST.get("password") or ""
        user = authenticate(request, username=username, password=password)
        if user:
            login(request, user)
            return redirect("dashboard")
        messages.error(request, "Неверное имя пользователя или пароль.")
    return render(request, "events/login.html")


def logout_view(request):
    logout(request)
    return redirect("login")


def _event_dt(event: Event):
    t = event.time or datetime.min.time()
    return timezone.make_aware(
        datetime.combine(event.date, t),
        timezone.get_current_timezone()
    )


def _reminder_title_body(event: Event, now=None):
    now = now or timezone.localtime()
    dt = _event_dt(event)
    diff = dt - now

    when_str = f"{event.date} {event.time or ''}".strip()

    if diff.total_seconds() <= 0:
        return "Событие уже прошло", f"Мероприятие «{event.title}» ({when_str}) уже завершилось."

    total_minutes = int(diff.total_seconds() // 60)
    days = total_minutes // (60 * 24)
    hours = (total_minutes % (60 * 24)) // 60
    minutes = total_minutes % 60

    if days == 0 and hours == 0:
        return "Напоминание", f"У вас мероприятие «{event.title}» через {minutes} мин. ({when_str})."
    if days == 0:
        return "Напоминание", f"У вас мероприятие «{event.title}» через {hours} ч. {minutes} мин. ({when_str})."
    return "Напоминание", f"У вас мероприятие «{event.title}» через {days} дн. ({when_str})."


def generate_reminders_for_user(user):
    today = timezone.localdate()
    now = timezone.localtime()

    # ✅ только активные события (не отменённые)
    regs = (
        Registration.objects
        .select_related("event")
        .filter(user=user, event__is_cancelled=False)
    )

    created_texts = []

    for r in regs:
        e = r.event

        # ✅ не чаще 1 раза в день на регистрацию
        if r.last_reminded_on == today:
            continue

        event_dt = _event_dt(e)
        if event_dt <= now:
            continue

        title, body = _reminder_title_body(e, now=now)

        Notification.objects.create(user=user, title=title, body=body)

        r.last_reminded_on = today
        r.save(update_fields=["last_reminded_on"])

        created_texts.append(f"{title}: {body}")

    return created_texts


@login_required(login_url="/login/")
def dashboard(request):
    texts = generate_reminders_for_user(request.user)
    # максимум 2 тоста за вход
    for t in texts[:2]:
        messages.info(request, t)
    return render(request, "events/dashboard.html")


@login_required(login_url="/login/")
def events_json(request):
    now = timezone.localtime()

    # ✅ показываем только неотменённые
    events = Event.objects.filter(is_cancelled=False).order_by("date", "time")
    data = []

    for e in events:
        dt = _event_dt(e)
        is_past = dt <= now
        is_full = e.is_full()

        start = f"{e.date}T{(e.time or '00:00')}"
        data.append(
            {
                "id": e.id,
                "title": e.title,
                "start": start,
                "description": e.description,
                "place": e.place,
                "capacity": e.capacity,
                "taken": e.registered_count(),
                "is_past": is_past,
                "can_register": (not is_past) and (not is_full),
            }
        )

    return JsonResponse(data, safe=False)


@login_required(login_url="/login/")
def my_events_json(request):
    regs = (
        Registration.objects
        .select_related("event")
        .filter(user=request.user, event__is_cancelled=False)
        .order_by("created_at")
    )
    data = []
    for r in regs:
        e = r.event
        data.append(
            {
                "id": e.id,
                "title": e.title,
                "date": str(e.date),
                "time": str(e.time) if e.time else "",
                "place": e.place,
            }
        )
    return JsonResponse(data, safe=False)


@login_required(login_url="/login/")
def notifications_json(request):
    notes = Notification.objects.filter(user=request.user).order_by("-created_at")[:100]
    data = [
        {
            "id": n.id,
            "title": n.title,
            "body": n.body,
            "created": n.created_at.strftime("%Y-%m-%d %H:%M"),
            "is_read": n.is_read,
        }
        for n in notes
    ]

    Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
    return JsonResponse(data, safe=False)


@login_required(login_url="/login/")
def register_for_event(request, event_id):
    if request.method != "POST":
        return HttpResponseForbidden("Только POST")

    event = get_object_or_404(Event, id=event_id)

    # ✅ если отменено — нельзя
    if event.is_cancelled:
        messages.error(request, "Это мероприятие отменено. Записаться нельзя.")
        return redirect("dashboard")

    now = timezone.localtime()
    event_dt = _event_dt(event)

    # ✅ если прошло — нельзя
    if event_dt <= now:
        messages.error(request, "Ошибка: это мероприятие уже прошло. Записаться нельзя.")
        return redirect("dashboard")

    # ✅ если мест нет — нельзя
    if event.is_full():
        messages.error(request, "Свободных мест нет.")
        return redirect("dashboard")

    try:
        Registration.objects.create(user=request.user, event=event)
    except IntegrityError:
        messages.info(request, "Вы уже зарегистрированы на это мероприятие.")
        return redirect("dashboard")

    # ✅ по твоей логике: после записи создаём 1 уведомление (напоминание)
    title, body = _reminder_title_body(event, now=now)
    Notification.objects.create(user=request.user, title=title, body=body)

    # ✅ уведомление организатору о регистрации
    if event.created_by and event.created_by != request.user:
        Notification.objects.create(
            user=event.created_by,
            title="Новая регистрация",
            body=f"{request.user.username} записался на «{event.title}» ({event.date} {event.time or ''}).",
        )

    messages.success(request, "Вы записаны! Событие появится во вкладке “Мои события”.")
    return redirect("dashboard")


def leave_feedback(request, event_id):
    if not request.user.is_authenticated:
        return redirect("login")

    event = get_object_or_404(Event, id=event_id)

    if Feedback.objects.filter(event=event, user=request.user).exists():
        messages.info(request, "Вы уже оставили отзыв 👍")
        return redirect("dashboard")

    if request.method == "POST":
        rating = request.POST.get("rating")
        comment = request.POST.get("comment", "")

        if not rating:
            messages.error(request, "Поставьте оценку")
        else:
            Feedback.objects.create(
                event=event,
                user=request.user,
                rating=int(rating),
                comment=comment,
            )
            messages.success(request, "Спасибо за отзыв!")
            return redirect("dashboard")

    return render(request, "events/feedback_form.html", {"event": event})


@login_required(login_url="/login/")
def reports(request):
    if not request.user.is_staff:
        return HttpResponseForbidden("Только администраторы/организаторы могут смотреть отчёты.")

    events = Event.objects.all().order_by("date")
    rows = []
    for e in events:
        regs = Registration.objects.filter(event=e)
        total = regs.count()
        attended = regs.filter(attended=True).count()
        rate = round(attended / total * 100) if total > 0 else 0
        avg = Feedback.objects.filter(event=e).aggregate(avg=Avg("rating"))["avg"]
        rows.append(
            {
                "event": e,
                "total": total,
                "attended": attended,
                "rate": rate,
                "avg_rating": avg,
            }
        )
    return render(request, "events/reports.html", {"rows": rows})