from django.urls import path
from . import views
from .views import apply_partner, approve_partner   # ← Add this
from .views import partner_status

urlpatterns = [
    path('register/', views.register_user, name='register'),
    path('login/', views.login_user, name='login'),
    path('logout/', views.logout_user, name='logout'),
    path('current-user/', views.get_current_user, name='get_current_user'),
    path('update-profile/', views.update_profile, name='update_profile'),
    path('profile/', views.get_profile, name='get_profile'),
    path("points/", views.get_kudi_points, name="get_kudi_points"),
    path("apply-partner/", apply_partner, name="apply-partner"),
    path("partner-application/<int:application_id>/review/",
         approve_partner,
         name="approve-partner"),  # ✅ NEW
    path("partner-status/", partner_status),     
]
