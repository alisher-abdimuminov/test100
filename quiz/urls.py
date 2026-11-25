from django.urls import path

from . import views

app_name = 'quiz'

urlpatterns = [
    path('', views.start, name='start'),
    path('test/', views.test, name='test'),
    path('test/answer/', views.save_answer, name='save_answer'),
    path('test/submit/', views.submit, name='submit'),
    path('result/', views.result, name='result'),
    path('restart/', views.restart, name='restart'),
]
