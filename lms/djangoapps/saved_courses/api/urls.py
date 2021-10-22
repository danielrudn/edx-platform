"""
URL definitions for the saved_courses API.
"""


from django.conf.urls import include, url

app_name = 'lms.djangoapps.saved_courses'

urlpatterns = [
    url(r'^v1/', include(('lms.djangoapps.saved_courses.api.v1.urls', 'v1'), namespace='v1')),
]
