from django.contrib import admin
from django.urls import include, path

admin.site.site_header = 'Test tizimi boshqaruvi'
admin.site.site_title = 'Test tizimi'
admin.site.index_title = 'Boshqaruv paneli'

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('quiz.urls')),
]
