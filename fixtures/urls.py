from django.urls import path
from . import views

urlpatterns = [
    path('', views.fixture_list, name='fixture_list'),
    path('tv/', views.tv_display_view, name='tv_display'),
    path('fixture/<int:fixture_id>/scorers/', views.update_scorers, name='update_scorers'),
    path('fixture/<int:fixture_id>/goal/save/', views.add_or_update_goal, name='add_or_update_goal'),
    path('add_player/', views.add_player, name='add_player'),
]