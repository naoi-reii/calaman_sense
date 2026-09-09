from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    path('login/', auth_views.LoginView.as_view(template_name='login.html'), name='login'),
    path('register/', views.register_view, name='register'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('', views.dashboard, name='dashboard'),
    path('upload/', views.upload_view, name='upload'),
    path('reports/', views.reports_view, name='reports'),
    path('reports/overview/', views.reports_overview, name='reports_overview'),
    path('reports/<int:id>/', views.report_detail_view, name='report_detail'),
    path('training/', views.training_view, name='training'),
    path('knowledge/', views.knowledge_hub, name='knowledge_hub'),
    path('settings/', views.settings_view, name='settings'),
    path('profile/', views.profile_view, name='profile'),
]
