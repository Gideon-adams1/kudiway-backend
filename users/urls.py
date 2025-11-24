from django.urls import path
from . import views

urlpatterns = [
    path("register/", views.register_user, name="register"),
    path("login/", views.login_user, name="login"),
    path("logout/", views.logout_user, name="logout"),
    path("current-user/", views.get_current_user, name="get_current_user"),
    path("update-profile/", views.update_profile, name="update_profile"),
    path("profile/", views.get_profile, name="get_profile"),
    path("points/", views.get_kudi_points, name="get_kudi_points"),
    path("partner-status/", views.partner_status, name="partner-status"),
    path("partner-apply/", views.apply_partner, name="partner-apply"),
    path(
        "admin/partners/pending/",
        views.pending_partners,
        name="admin-partners-pending",
    ),
    path(
        "partner-approve/<int:user_id>/",
        views.approve_partner,
        name="partner-approve",
    ),
    path(
        "partner-reject/<int:user_id>/",
        views.reject_partner,
        name="partner-reject",
    ),

    # ✅ new
    path("admin-status/", views.admin_status, name="admin-status"),
]
