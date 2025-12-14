from datetime import datetime
from django.utils import timezone

from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponseForbidden
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db import IntegrityError
from django.db.models import Avg

from .models import Event, Registration, Notification, Feedback


def home(request):
    return render(request, 'events/home.html')


def register(request):
    if request.method == 'POST':
        username = (request.POST.get('username') or '').strip()
        email    = (request.POST.get('email') or '').strip()
        password = request.POST.get('password') or ''
        confirm  = request.POST.get('confirm_password') or ''

        if not username or not email or not password:
            messages.error(request, 'Все поля должны быть заполнены.')
            return render(request, 'events/register.html')

        if password != confirm:
            messages.error(request, 'Пароли не совпадают.')
            return render(request, 'events/register.html')

        if User.objects.filter(username=username).exists():
            messages.error(request, 'Пользователь с таким именем уже существует.')
            return render(request, 'events/register.html')

        if User.objects.filter(email=email).exists():
            messages.error(request, 'Эта почта уже используется.')
            return render(request, 'events/register.html')

        user = User.objects.create_user(username=username, email=email, password=password)
        login(request, user)
        return redirect('dashboard')

    return render(request, 'events/register.html')


def login_view(request):
    if request.method == 'POST':
        username = (request.POST.get('username') or '').strip()
        password = request.POST.get('password') or ''
        user = authenticate(request, username=username, password=password)
        if user:
            login(request, user)
            return redirect('dashboard')
        messages.error(request, 'Неверное имя пользователя или пароль.')
    return render(request, 'events/login.html')


def logout_view(request):
    logout(request)
    return redirect('login')


def create_login_reminders(user):
    """
    ✅ Требование: напоминания участникам.
    Мы делаем их при входе, но НЕ через messages (тост),
    а создаём Notification, чтобы не было 2 сообщений снизу.
    """
    today = timezone.localdate()
    now = timezone.localtime()

    regs = (Registration.objects
            .select_related("event")
            .filter(user=user, event__is_cancelled=False))

    for r in regs:
        e = r.event

        # уже напоминали сегодня
        if r.last_reminded_on == today:
            continue

        event_time = e.time or datetime.min.time()
        event_dt = timezone.make_aware(datetime.combine(e.date, event_time), timezone.get_current_timezone())

        # прошедшие не напоминаем
        if event_dt <= now:
            continue

        days_left = (event_dt.date() - today).days

        # условие: осталось <= 5 дней
        if 0 <= days_left <= 5:
            Notification.objects.create(
                user=user,
                title="Напоминание о мероприятии",
                body=f"«{e.title}» через {days_left} дн. ({e.date} {e.time or ''})"
            )
            r.last_reminded_on = today
            r.save(update_fields=["last_reminded_on"])


@login_required(login_url='/login/')
def dashboard(request):
    create_login_reminders(request.user)
    return render(request, 'events/dashboard.html')


@login_required(login_url='/login/')
def events_json(request):
    now = timezone.localtime()
    events = Event.objects.all().order_by('date', 'time')

    data = []
    for e in events:
        event_time = e.time or datetime.min.time()
        event_dt = timezone.make_aware(datetime.combine(e.date, event_time), timezone.get_current_timezone())

        is_past = event_dt <= now
        is_full = e.is_full()
        is_cancelled = getattr(e, "is_cancelled", False)

        start = f"{e.date}T{(e.time or '00:00')}"
        data.append({
            'id': e.id,
            'title': e.title,
            'start': start,
            'description': e.description,
            'place': e.place,
            'capacity': e.capacity,
            'taken': e.registered_count(),
            'is_past': is_past,
            'is_cancelled': is_cancelled,
            'can_register': (not is_past) and (not is_full) and (not is_cancelled),
        })

    return JsonResponse(data, safe=False)


@login_required(login_url='/login/')
def my_events_json(request):
    now = timezone.localtime()
    regs = (
        Registration.objects
        .select_related('event')
        .filter(user=request.user, event__is_cancelled=False)
        .order_by('event__date', 'event__time')
    )

    data = []
    for r in regs:
        e = r.event
        event_time = e.time or datetime.min.time()
        event_dt = timezone.make_aware(datetime.combine(e.date, event_time), timezone.get_current_timezone())

        # не показываем прошедшие
        if event_dt <= now:
            continue

        data.append({
            'id': e.id,
            'title': e.title,
            'date': str(e.date),
            'time': str(e.time) if e.time else '',
            'place': e.place,
        })
    return JsonResponse(data, safe=False)


@login_required(login_url='/login/')
def notifications_json(request):
    notes = Notification.objects.filter(user=request.user).order_by('-created_at')[:100]
    data = [{
        'id': n.id,
        'title': n.title,
        'body': n.body,
        'created': n.created_at.strftime('%Y-%m-%d %H:%M'),
        'is_read': n.is_read,
    } for n in notes]

    Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
    return JsonResponse(data, safe=False)


@login_required(login_url='/login/')
def register_for_event(request, event_id):
    if request.method != 'POST':
        return HttpResponseForbidden('Только POST')

    event = get_object_or_404(Event, id=event_id)

    # ❌ отменено — нельзя
    if getattr(event, "is_cancelled", False):
        messages.error(request, "Ошибка: мероприятие отменено администратором.")
        return redirect("dashboard")

    now = timezone.localtime()
    event_time = event.time or datetime.min.time()
    event_dt = timezone.make_aware(datetime.combine(event.date, event_time), timezone.get_current_timezone())

    # ❌ прошло — нельзя
    if event_dt <= now:
        messages.error(request, "Ошибка: это мероприятие уже прошло. Записаться нельзя.")
        return redirect("dashboard")

    if event.is_full():
        messages.error(request, 'Свободных мест нет.')
        return redirect('dashboard')

    try:
        Registration.objects.create(user=request.user, event=event)
    except IntegrityError:
        messages.info(request, 'Вы уже зарегистрированы на это мероприятие.')
        return redirect('dashboard')

    # ✅ участнику: уведомление "Вы записались"
    Notification.objects.create(
        user=request.user,
        title="Вы записались",
        body=f"Вы записались на «{event.title}» ({event.date} {event.time or ''})."
    )

    # ✅ организатору: "Новая регистрация"
    if event.created_by and event.created_by != request.user:
        Notification.objects.create(
            user=event.created_by,
            title='Новая регистрация',
            body=f'{request.user.username} записался на «{event.title}» ({event.date} {event.time or ""}).'
        )

    # ✅ один тост (не два)
    days_left = (event.date - timezone.localdate()).days
    if days_left < 0:
        days_left = 0
    messages.success(request, f'Вы успешно зарегистрировались! Мероприятие через {days_left} дн. Оно появится в “Мои события”.')

    return redirect('dashboard')


def leave_feedback(request, event_id):
    if not request.user.is_authenticated:
        return redirect('login')

    event = get_object_or_404(Event, id=event_id)

    if Feedback.objects.filter(event=event, user=request.user).exists():
        messages.info(request, 'Вы уже оставили отзыв 👍')
        return redirect('dashboard')

    if request.method == 'POST':
        rating = request.POST.get('rating')
        comment = request.POST.get('comment', '')

        if not rating:
            messages.error(request, 'Поставьте оценку')
        else:
            Feedback.objects.create(
                event=event,
                user=request.user,
                rating=int(rating),
                comment=comment
            )
            messages.success(request, 'Спасибо за отзыв!')
            return redirect('dashboard')

    return render(request, 'events/feedback_form.html', {'event': event})


@login_required(login_url='/login/')
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
        rows.append({"event": e, "total": total, "attended": attended, "rate": rate, "avg_rating": avg})
    return render(request, "events/reports.html", {"rows": rows})
