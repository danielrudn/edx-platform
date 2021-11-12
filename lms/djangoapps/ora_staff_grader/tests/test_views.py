"""
Tests for ESG views
"""
import json

from uuid import uuid4
from django.http import QueryDict
from django.http.response import HttpResponse, HttpResponseForbidden
from django.urls import reverse
from opaque_keys.edx.keys import CourseKey
from rest_framework.test import APITestCase
from unittest.mock import patch

from common.djangoapps.student.tests.factories import StaffFactory
from openedx.core.djangoapps.content.course_overviews.tests.factories import CourseOverviewFactory
from xmodule.modulestore.tests.django_utils import TEST_DATA_SPLIT_MODULESTORE, SharedModuleStoreTestCase
from xmodule.modulestore.tests.factories import CourseFactory
from xmodule.modulestore.tests.factories import ItemFactory


class TestInitializeView(SharedModuleStoreTestCase, APITestCase):
    """
    Tests for the /initialize view, creating setup data for ESG
    """
    view_name = 'ora-staff-grader:initialize'
    api_url = reverse(view_name)

    MODULESTORE = TEST_DATA_SPLIT_MODULESTORE

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.course = CourseFactory.create()
        cls.course_key = cls.course.location.course_key

        cls.ora_block = ItemFactory.create(
            category='openassessment',
            parent_location=cls.course.location,
            display_name='test',
        )
        cls.ora_usage_key = str(cls.ora_block.location)

        cls.password = 'password'
        cls.staff = StaffFactory(course_key=cls.course_key, password=cls.password)

    def log_in(self):
        """ Log in as staff """
        self.client.login(username=self.staff.username, password=self.password)

    def test_missing_ora_location(self):
        """ Missing ora_location param should return 400 and error message """
        self.client.login(username=self.staff.username, password=self.password)
        response = self.client.get(self.api_url)

        assert response.status_code == 400
        assert response.content.decode() == "Query requires the following query params: ora_location"

    def test_bad_ora_location(self):
        """ Bad ORA location should return a 400 and error message """
        self.client.login(username=self.staff.username, password=self.password)
        response = self.client.get(self.api_url, {'ora_location': 'not_a_real_location'})

        assert response.status_code == 400
        assert response.content.decode() == "Invalid ora_location."

    @patch('lms.djangoapps.ora_staff_grader.views.InitializeView.get_rubric_config')
    @patch('lms.djangoapps.ora_staff_grader.views.InitializeView.get_submissions')
    @patch('lms.djangoapps.ora_staff_grader.views.get_course_overview_or_none')
    def test_init(self, mock_get_course_overview, mock_get_submissions, mock_get_rubric_config):
        """ A successful call should return course, ORA, submissions, and rubric data """
        mock_course_overview = CourseOverviewFactory.create()
        mock_get_course_overview.return_value = mock_course_overview

        mock_get_submissions.return_value = {
            "a": {
                "submissionUuid": "a",
                "username": "foo",
                "teamName": None,
                "dateSubmitted": "1969-07-16 13:32:00",
                "dateGraded": None,
                "gradedBy": None,
                "gradingStatus": "ungraded",
                "lockStatus": "unlocked",
                "score": {
                    "pointsEarned": 0,
                    "pointsPossible": 10
                }
            }
        }

        # Rubric data is passed through directly, so we can use a toy data payload
        mock_get_rubric_config.return_value = {"foo": "bar"}

        self.client.login(username=self.staff.username, password=self.password)
        response = self.client.get(self.api_url, {'ora_location': self.ora_usage_key})

        expected_keys = set(['courseMetadata', 'oraMetadata', 'submissions', 'rubricConfig'])
        assert response.status_code == 200
        assert response.data.keys() == expected_keys


class TestSubmissionLockView(APITestCase):
    """
    Tests for the /lock view, locking or unlocking a submission for grading
    """
    view_name = 'ora-staff-grader:lock'
    api_url = reverse(view_name)

    test_submission_uuid = str(uuid4())
    test_anon_user_id = 'anon-user-id'
    test_timestamp = '2020-08-29T02:14:00-04:00'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.course_key = CourseKey.from_string('course-v1:edX+ToyX+Toy_Course')
        cls.test_ora_location = 'block-v1:edX+ToyX+Toy_Course+type@openassessment+block@f00'
        cls.password = 'password'
        cls.staff = StaffFactory(course_key=cls.course_key, password=cls.password)

    def setUp(self):
        super().setUp()

        # Request to claim a lock must include ora_location, submissionID, and value=True
        self.test_claim_lock_params = {
            "ora_location": self.test_ora_location,
            "submissionId": self.test_submission_uuid,
            "value": True
        }

        # Request to claim a lock must include ora_location, submissionID, and value=False
        self.test_delete_lock_params = self.test_claim_lock_params.copy()
        self.test_delete_lock_params['value'] = False

        self.client.login(username=self.staff.username, password=self.password)

    def url_with_params(self, params):
        """ For DRF client.posts, you can't add query params easily. This helper adds it to the request URL """
        query_dictionary = QueryDict('', mutable=True)
        query_dictionary.update(params)

        return '{base_url}?{querystring}'.format(
            base_url=reverse(self.view_name),
            querystring=query_dictionary.urlencode()
        )

    def test_invalid_ora(self):
        """ An invalid ORA returns a 404 """
        self.test_claim_lock_params['ora_location'] = 'not_a_real_location'

        response = self.client.post(self.url_with_params(self.test_claim_lock_params))

        assert response.status_code == 400
        assert response.content.decode() == "Invalid ora_location."

    @patch('lms.djangoapps.ora_staff_grader.views.call_xblock_json_handler')
    def test_claim_lock(self, mock_xblock_handler):
        """ Passing value=True indicates to claim a submission lock. Success returns lock status 'in-progress'. """
        mock_return_data = {
            "submission_uuid": self.test_submission_uuid,
            "owner_id": self.test_anon_user_id,
            "created_at": self.test_timestamp,
            "lock_status": "in-progress"
        }
        mock_xblock_handler.return_value = HttpResponse(json.dumps(mock_return_data), content_type="application/json")

        response = self.client.post(self.url_with_params(self.test_claim_lock_params))

        expected_value = {"lockStatus": "in-progress"}
        assert response.status_code == 200
        assert json.loads(response.content) == expected_value

    @patch('lms.djangoapps.ora_staff_grader.views.call_xblock_json_handler')
    def test_claim_lock_contested(self, mock_xblock_handler):
        """ Attempting to claim a lock owned by another user returns a 403 - forbidden and passes error code. """
        mock_return_data = {
            "error": "ERR_LOCK_CONTESTED"
        }
        mock_xblock_handler.return_value = HttpResponseForbidden(json.dumps(mock_return_data), content_type="application/json")

        response = self.client.post(self.url_with_params(self.test_claim_lock_params))

        expected_value = mock_return_data
        assert response.status_code == 403
        assert json.loads(response.content) == expected_value

    @patch('lms.djangoapps.ora_staff_grader.views.call_xblock_json_handler')
    def test_delete_lock(self, mock_xblock_handler):
        """ Passing value=False indicates to delete a submission lock. Success returns lock status 'unlocked'. """
        mock_return_data = {
            "submission_uuid": "",
            "owner_id": "",
            "created_at": "",
            "lock_status": "unlocked"
        }
        mock_xblock_handler.return_value = HttpResponse(json.dumps(mock_return_data), content_type="application/json")

        response = self.client.post(self.url_with_params(self.test_delete_lock_params))

        expected_value = {"lockStatus": "unlocked"}
        assert response.status_code == 200
        assert json.loads(response.content) == expected_value

    @patch('lms.djangoapps.ora_staff_grader.views.call_xblock_json_handler')
    def test_delete_lock_contested(self, mock_xblock_handler):
        """ Attempting to delete a lock owned by another user returns a 403 - forbidden and passes error code. """
        mock_return_data = {
            "error": "ERR_LOCK_CONTESTED"
        }
        mock_xblock_handler.return_value = HttpResponseForbidden(json.dumps(mock_return_data), content_type="application/json")

        response = self.client.post(self.url_with_params(self.test_delete_lock_params))

        expected_value = mock_return_data
        assert response.status_code == 403
        assert json.loads(response.content) == expected_value
