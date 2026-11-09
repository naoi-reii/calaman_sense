from django.urls import path
from django.contrib.auth import views as auth_views
from django.views.generic import TemplateView
from . import views

urlpatterns = [
    path('login/', views.AccountLoginView.as_view(), name='login'),
    path('forgot-password/', TemplateView.as_view(template_name='forgot_password.html'), name='forgot_password'),
    path('register/', views.register_view, name='register'),
    path('logout/', views.DeviceLogoutView.as_view(), name='logout'),
    path('', views.home, name='home'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('upload/', views.upload_view, name='upload'),
    path('reports/', views.reports_view, name='reports'),
    path('reports/upload/<str:token>/', views.upload_results_view, name='upload_results'),
    path('reports/compare/', views.compare_scans, name='compare_scans'),
    path('reports/overview/', views.reports_overview, name='reports_overview'),
    path('reports/<int:id>/', views.report_detail_view, name='report_detail'),
    path('training/', views.training_view, name='training'),
    path('knowledge/', views.knowledge_hub, name='knowledge_hub'),
    path('settings/', views.settings_view, name='settings'),
    path('settings/appearance/', views.settings_appearance, name='settings_appearance'),
    path('settings/<slug:page>/', views.settings_guide, name='settings_guide'),
    path('profile/', views.profile_view, name='profile'),
    path('sw.js', views.service_worker, name='service_worker'),
    path('manifest.json', views.manifest_view, name='manifest_view'),
]

