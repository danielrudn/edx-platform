"""
URLs for saved_courses v1
"""


from django.conf.urls import url

from lms.djangoapps.saved_courses.api.v1.views import SaveForLaterApiView

urlpatterns = [
    url(r'^save/course/', SaveForLaterApiView.as_view(), name='save_course'),
]
