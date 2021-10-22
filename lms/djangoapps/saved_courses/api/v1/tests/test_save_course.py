"""
Tests for saved_courses API.
"""


import ddt
from django.urls import reverse
from unittest.mock import patch
from rest_framework.test import APITestCase
from opaque_keys.edx.keys import CourseKey

from organizations.tests.factories import OrganizationFactory
from openedx.core.djangoapps.catalog.tests.factories import OrganizationFactory as CatalogOrganizationFactory

from openedx.core.djangolib.testing.utils import skip_unless_lms
from common.djangoapps.third_party_auth.tests.testutil import ThirdPartyAuthTestMixin
from openedx.core.djangoapps.content.course_overviews.tests.factories import CourseOverviewFactory


@skip_unless_lms
@ddt.ddt
class SaveForLaterApiViewTest(ThirdPartyAuthTestMixin, APITestCase):
    """
    Save for later tests
    """

    def setUp(self):  # pylint: disable=arguments-differ
        """
        Test Setup
        """
        super().setUp()

        self.url = reverse('api:v1:save_course')
        self.email = 'test@edx.org'
        self.invalid_email = 'test@edx'
        self.course_id = 'course-v1:TestX+ProEnroll+P'
        self.course_key = CourseKey.from_string(self.course_id)
        CourseOverviewFactory.create(id=self.course_key)

    def test_send_course_using_email(self):
        """
        Test successfully email sent
        """
        with patch('lms.djangoapps.saved_courses.api.v1.views.get_course_organization') as mock_get_org:
            mock_get_org.return_value = {'logo': '/test-url'}
            request_payload = {'email': self.email, 'course_id': self.course_id, 'marketing_url': 'http://google.com'}
            response = self.client.post(self.url, data=request_payload)
            assert response.status_code == 200

    def test_invalid_email_address(self):
        """
        Test email validation
        """
        request_payload = {'email': self.invalid_email, 'course_id': self.course_id}
        response = self.client.post(self.url, data=request_payload)
        assert response.status_code == 400
