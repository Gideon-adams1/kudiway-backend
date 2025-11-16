# dashboard/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path("overview/", views.admin_overview, name="admin-dashboard-overview"),
    path(
        "partner-performance/",
        views.partner_performance,
        name="admin-dashboard-partner-performance",
    ),
]
