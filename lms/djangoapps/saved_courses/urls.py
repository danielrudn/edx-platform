""" URLs for Saved Courses """

from django.conf.urls import include, url

urlpatterns = [
    url(r'^api/', include(('lms.djangoapps.saved_courses.api.urls', 'api'), namespace='api')),
]
