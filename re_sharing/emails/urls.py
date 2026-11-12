from django.urls import path

from . import views

app_name = "emails"
urlpatterns = [
    path("", views.list_emails_view, name="list-emails"),
    path("resend/", views.resend_selected_emails_view, name="resend-selected-emails"),
    path("<int:pk>/", views.show_email_view, name="show-email"),
    path("<int:pk>/resend/", views.resend_email_view, name="resend-email"),
]
