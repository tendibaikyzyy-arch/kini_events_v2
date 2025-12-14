from django.urls import path
from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("register/", views.register, name="register"),
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("dashboard/", views.dashboard, name="dashboard"),

    path("events-json/", views.events_json, name="events_json"),
    path("my-events-json/", views.my_events_json, name="my_events_json"),
    path("notifications-json/", views.notifications_json, name="notifications_json"),
   # path("reminders-json/", views.reminders_json, name="reminders_json"),

    path("events/<int:event_id>/book/", views.register_for_event, name="register_for_event"),
    path("events/<int:event_id>/feedback/", views.leave_feedback, name="leave_feedback"),
    path("reports/", views.reports, name="reports"),
]