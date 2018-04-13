from django.urls import path

from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('complete/', views.complete, name='complete'),
    path('moves_complete/', views.moves_complete, name='moves_complete'),
]
