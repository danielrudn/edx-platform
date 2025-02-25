"""
Test app view logic
"""
# pylint: disable=test-inherits-tests
import itertools
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

import ddt
from django.core.exceptions import ValidationError
from django.urls import reverse
from lti_consumer.models import CourseAllowPIISharingInLTIFlag
from rest_framework import status
from rest_framework.test import APITestCase
from xmodule.modulestore import ModuleStoreEnum
from xmodule.modulestore.tests.django_utils import CourseUserType, ModuleStoreTestCase
from xmodule.modulestore.tests.factories import CourseFactory

from common.djangoapps.student.tests.factories import UserFactory
from lms.djangoapps.discussion.django_comment_client.tests.factories import RoleFactory

from ..models import AVAILABLE_PROVIDER_MAP, DEFAULT_CONFIG_ENABLED, DEFAULT_PROVIDER_TYPE

DATA_LEGACY_COHORTS = {
    'divided_inline_discussions': [],
    'divided_course_wide_discussions': [],
    'always_divide_inline_discussions': True,
    'division_scheme': 'none',
}
DATA_LEGACY_CONFIGURATION = {
    'allow_anonymous': True,
    'allow_anonymous_to_peers': True,
    'discussion_blackouts': [],
    'discussion_topics': {
        'General': {
            'id': 'course',
        },
    },
}
DATA_LTI_CONFIGURATION = {
    'lti_1p1_client_key': 'KEY',
    'lti_1p1_client_secret': 'SECRET',
    'lti_1p1_launch_url': 'https://localhost',
    'version': 'lti_1p1'
}


class ApiTest(ModuleStoreTestCase, APITestCase):
    """
    Test basic API operations
    """
    CREATE_USER = True
    USER_TYPE = None

    def setUp(self):
        super().setUp()
        store = ModuleStoreEnum.Type.split
        self.course = CourseFactory.create(default_store=store)
        if self.USER_TYPE:
            self.user = self.create_user_for_course(self.course, user_type=self.USER_TYPE)

    @property
    def url(self):
        """Returns the discussion API url. """
        return reverse(
            'discussions',
            kwargs={
                'course_key_string': str(self.course.id),
            }
        )

    def _get(self):
        return self.client.get(self.url)

    def _post(self, data):
        return self.client.post(self.url, data, format='json')


class UnauthorizedApiTest(ApiTest):
    """
    Logged-out users should _not_ have any access
    """

    expected_response_code = status.HTTP_401_UNAUTHORIZED

    def test_access_get(self):
        response = self._get()
        assert response.status_code == self.expected_response_code

    def test_access_patch(self):
        response = self.client.patch(self.url)
        assert response.status_code == self.expected_response_code

    def test_access_post(self):
        response = self._post({})
        assert response.status_code == self.expected_response_code

    def test_access_put(self):
        response = self.client.put(self.url)
        assert response.status_code == self.expected_response_code


class AuthenticatedApiTest(UnauthorizedApiTest):
    """
    Logged-in users should _not_ have any access
    """

    expected_response_code = status.HTTP_403_FORBIDDEN
    USER_TYPE = CourseUserType.ENROLLED


class AuthorizedApiTest(AuthenticatedApiTest):
    """
    Global Staff should have access to all supported methods
    """

    expected_response_code = status.HTTP_200_OK
    USER_TYPE = CourseUserType.GLOBAL_STAFF

    def test_access_patch(self):
        response = self.client.patch(self.url)
        assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

    def test_access_put(self):
        response = self.client.put(self.url)
        assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED


class CourseStaffAuthorizedTest(AuthorizedApiTest):
    """
    Course Staff should have the same access as Global Staff
    """

    USER_TYPE = CourseUserType.UNENROLLED_STAFF


class CourseInstructorAuthorizedTest(AuthorizedApiTest):
    """
    Course instructor should have the same access as Global Staff.
    """

    USER_TYPE = CourseUserType.COURSE_INSTRUCTOR


class CourseDiscussionRoleAuthorizedTests(ApiTest):
    """Test cases for discussion api for users with discussion privileges."""

    def setUp(self):
        super().setUp()

        self.course = CourseFactory.create(default_store=ModuleStoreEnum.Type.split)
        self.student_role = RoleFactory(name='Student', course_id=self.course.id)
        self.moderator_role = RoleFactory(name='Moderator', course_id=self.course.id)
        self.community_ta_role = RoleFactory(name='Community TA', course_id=self.course.id)
        self.student_user = UserFactory(password=self.TEST_PASSWORD)
        self.moderator_user = UserFactory(password=self.TEST_PASSWORD)
        self.community_ta_user = UserFactory(password=self.TEST_PASSWORD)
        self.student_role.users.add(self.student_user)
        self.moderator_role.users.add(self.moderator_user)
        self.community_ta_role.users.add(self.community_ta_user)

    def login(self, user):
        """Login the given user."""
        self.client.login(username=user.username, password=self.TEST_PASSWORD)

    def test_student_role_access_get(self):
        """Tests that student role does not have access to the API"""
        self.login(self.student_user)
        response = self._get()
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_student_role_access_post(self):
        """Tests that student role does not have access to the API"""
        self.login(self.student_user)
        response = self._post({})
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_moderator_role_access_get(self):
        """Tests that discussion moderator role have access to the API"""
        self.login(self.moderator_user)
        response = self._get()
        assert response.status_code == status.HTTP_200_OK

    def test_moderator_role_access_post(self):
        """Tests that discussion moderator role have access to the API"""
        self.login(self.moderator_user)
        response = self._post({})
        assert response.status_code == status.HTTP_200_OK

    def test_community_ta_role_access_get(self):
        """Tests that discussion community TA role have access to the API"""
        self.login(self.community_ta_user)
        response = self._get()
        assert response.status_code == status.HTTP_200_OK

    def test_community_ta_role_access_post(self):
        """Tests that discussion community TA role have access to the API"""
        self.login(self.community_ta_user)
        response = self._post({})
        assert response.status_code == status.HTTP_200_OK


@ddt.ddt
class DataTest(AuthorizedApiTest):
    """
    Check API-data correctness
    """

    def _assert_defaults(self, response):
        """
        Check for default values
        """
        data = response.json()
        assert response.status_code == self.expected_response_code
        assert data['enabled'] == DEFAULT_CONFIG_ENABLED
        assert data['provider_type'] == DEFAULT_PROVIDER_TYPE
        assert data['providers']['available']['legacy'] == AVAILABLE_PROVIDER_MAP['legacy']
        assert not [
            name for name, spec in data['providers']['available'].items()
            if "messages" not in spec
        ], "Found available providers without messages field"
        assert data['lti_configuration'] == {}
        assert data['plugin_configuration'] == {
            'allow_anonymous': True,
            'allow_anonymous_to_peers': False,
            'always_divide_inline_discussions': False,
            'available_division_schemes': [],
            'discussion_blackouts': [],
            'discussion_topics': {'General': {'id': 'course'}},
            'divided_course_wide_discussions': [],
            'divided_inline_discussions': [],
            'division_scheme': 'none',
        }
        assert len(data['plugin_configuration']) > 0

    def _setup_lti(self):
        """
        Configure an LTI-based provider
        """
        payload = {
            'enabled': True,
            'provider_type': 'piazza',
            'lti_configuration': DATA_LTI_CONFIGURATION,
            'plugin_configuration': {
            }
        }
        response = self._post(payload)
        data = response.json()
        assert response.status_code == self.expected_response_code
        return data

    def test_get_nonexistent_with_defaults(self):
        """
        If no record exists, defaults should be returned.
        """
        response = self._get()
        self._assert_defaults(response)

    @contextmanager
    def _pii_sharing_for_course(self, enabled):
        instance = CourseAllowPIISharingInLTIFlag.objects.create(course_id=self.course.id, enabled=enabled)
        yield
        instance.delete()

    @ddt.data(
        {"pii_share_username": True},
        {"pii_share_email": True},
        {"pii_share_email": True, "pii_share_username": True},
    )
    def test_post_pii_fields_fail(self, pii_fields):
        """
        If no record exists, defaults should be returned.
        """
        data = self._setup_lti()
        data['lti_configuration'].update(pii_fields)
        response = self._post(data)
        assert response.status_code == 400

    @ddt.data(
        {"pii_share_username": True},
        {"pii_share_email": True},
        {"pii_share_email": True, "pii_share_username": True},
    )
    def test_post_pii_fields(self, pii_fields):
        """
        Only if PII sharing is enabled should a user be able to set pii fields.
        """
        data = self._setup_lti()
        data['lti_configuration'].update(pii_fields)
        with self._pii_sharing_for_course(enabled=False):
            response = self._post(data)
            assert response.status_code == 400
        with self._pii_sharing_for_course(enabled=True):
            response = self._post(data)
            assert response.status_code == 200

    @ddt.data(
        True, False
    )
    def test_get_pii_fields(self, pii_sharing):
        """
        Only if PII is enabled should pii fields be returned.
        """
        self._setup_lti()
        with self._pii_sharing_for_course(enabled=pii_sharing):
            response = self._get()
            data = response.json()
            # If pii_sharing is true, then the fields should be present, and absent otherwise
            assert ("pii_share_email" in data["lti_configuration"]) == pii_sharing
            assert ("pii_share_username" in data["lti_configuration"]) == pii_sharing

    def test_post_everything(self):
        """
        API should accept requests to update _all_ fields at once
        """
        data = self._setup_lti()
        assert data['enabled']
        assert data['provider_type'] == 'piazza'
        assert data['providers']['available']['piazza'] == AVAILABLE_PROVIDER_MAP['piazza']
        assert data['lti_configuration'] == DATA_LTI_CONFIGURATION
        assert len(data['plugin_configuration']) == 0
        assert len(data['lti_configuration']) > 0
        response = self._get()
        # the GET should pull back the same data as the POST
        response_data = response.json()
        assert response_data == data

    def test_post_invalid_key(self):
        """
        Unsupported keys should be gracefully ignored
        """
        payload = {
            'non-existent-key': 'value',
        }
        response = self._post(payload)
        assert response.status_code == self.expected_response_code

    def test_configuration_valid(self):
        """
        Check we can set basic configuration
        """
        provider_type = 'piazza'
        payload = {
            'enabled': True,
            'provider_type': provider_type,
            'plugin_configuration': {
                'key': 'value',
            },
        }
        self._post(payload)
        response = self._get()
        data = response.json()
        assert data['enabled']
        assert data['provider_type'] == provider_type
        assert data['plugin_configuration'] == payload['plugin_configuration']

    @ddt.data(
        {
            'enabled': 3,
        },
    )
    def test_configuration_invalid(self, payload):
        """
        Check validation of basic configuration
        """
        response = self._post(payload)
        assert status.is_client_error(response.status_code)
        assert 'enabled' in response.json()
        response = self._get()
        self._assert_defaults(response)

    @ddt.data(
        *DATA_LTI_CONFIGURATION.items()
    )
    @ddt.unpack
    def test_post_lti_valid(self, key, value):
        """
        Check we can set LTI configuration
        """
        provider_type = 'piazza'
        payload = {
            'enabled': True,
            'provider_type': provider_type,
            'lti_configuration': {
                key: value,
            }
        }
        self._post(payload)
        response = self._get()
        data = response.json()
        assert data['enabled']
        assert data['provider_type'] == provider_type
        assert data['lti_configuration'][key] == value

    def test_post_lti_invalid(self):
        """
        Check validation of LTI configuration ignores unsupported values

        The fields are all open-ended strings and will accept any values.
        """
        provider_type = 'piazza'
        for key, value in DATA_LTI_CONFIGURATION.items():
            payload = {
                'enabled': True,
                'provider_type': provider_type,
                'lti_configuration': {
                    key: value,
                    'ignored-key': 'ignored value',
                }
            }
            response = self._post(payload)
            assert response
            response = self._get()
            data = response.json()
            assert data['enabled']
            assert data['provider_type'] == provider_type
            assert data['lti_configuration'][key] == value
            assert 'ignored-key' not in data['lti_configuration']

    def test_post_legacy_valid(self):
        """
        Check we can set legacy settings configuration
        """
        provider_type = 'legacy'
        for key, value in DATA_LEGACY_CONFIGURATION.items():
            payload = {
                'enabled': True,
                'provider_type': provider_type,
                'plugin_configuration': {
                    key: value,
                }
            }
            response = self._post(payload)
            assert response
            response = self._get()
            data = response.json()
            assert data['enabled']
            assert data['provider_type'] == provider_type
            assert data['plugin_configuration'][key] == value

    @ddt.data(
        {
            'allow_anonymous': 3,
        },
        {
            'allow_anonymous_to_peers': 3,
        },
        {
            'discussion_blackouts': 3,
        },
        {
            'discussion_topics': 3,
        },
    )
    def test_post_legacy_invalid(self, plugin_configuration):
        """
        Check validation of legacy settings configuration
        """
        provider_type = 'legacy'
        payload = {
            'enabled': True,
            'provider_type': provider_type,
            'plugin_configuration': plugin_configuration,
        }
        with self.assertRaises(ValidationError):
            response = self._post(payload)
            if status.is_client_error(response.status_code):
                raise ValidationError(str(response.status_code))
        response = self._get()
        self._assert_defaults(response)

    @ddt.data(*DATA_LEGACY_COHORTS.items())
    def test_post_cohorts_valid(self, kvp):
        """
        Check we can set legacy cohorts configuration
        """
        key, value = kvp
        provider_type = 'legacy'
        payload = {
            'enabled': True,
            'provider_type': provider_type,
            'plugin_configuration': {
                key: value,
            }
        }
        response = self._post(payload)
        response = self._get()
        data = response.json()
        assert data['enabled']
        assert data['provider_type'] == provider_type
        assert data['plugin_configuration'][key] == value

    @ddt.data(*DATA_LEGACY_COHORTS.items())
    def test_post_cohorts_invalid(self, kvp):
        """
        Check validation of legacy cohorts configuration
        """
        key, value = kvp
        if isinstance(value, str):
            # For the string value, we can only fail here if it's blank
            value = ''
        else:
            # Otherwise, submit a string when non-string is required
            value = str(value)
        provider_type = 'legacy'
        payload = {
            'enabled': True,
            'provider_type': provider_type,
            'plugin_configuration': {
                key: value,
            }
        }
        with self.assertRaises(ValidationError):
            response = self._post(payload)
            if status.is_client_error(response.status_code):
                raise ValidationError(str(response.status_code))
        response = self._get()
        self._assert_defaults(response)

    def test_change_to_lti(self):
        """
        Ensure we can switch to an LTI-backed provider (from a non-LTI one)
        """
        payload = {
            'enabled': True,
            'provider_type': 'legacy',
            'plugin_configuration': {
                'allow_anonymous': False,
            },
        }
        response = self._post(payload)
        data = response.json()
        data = self._setup_lti()
        assert data['enabled']
        assert data['provider_type'] == 'piazza'
        assert not data['plugin_configuration']
        assert data['lti_configuration']

    def test_change_from_lti(self):
        """
        Ensure we can switch away from an LTI-backed provider (to a non-LTI one)
        """
        data = self._setup_lti()
        payload = {
            'enabled': True,
            'provider_type': 'legacy',
            'plugin_configuration': {
                'allow_anonymous': False,
            },
        }
        response = self._post(payload)
        data = response.json()
        assert data['enabled']
        assert data['provider_type'] == 'legacy'
        assert not data['plugin_configuration']['allow_anonymous']

    @ddt.data(
        *itertools.product(
            ["enable_in_context", "enable_graded_units", "unit_level_visibility"],
            [True, False],
        ),
        ("provider_type", "piazza"),
    )
    @ddt.unpack
    def test_change_course_fields(self, field, value):
        """
        Test changing fields that are saved to the course
        """
        payload = {
            field: value
        }
        response = self._post(payload)
        data = response.json()
        assert data[field] == value
        course = self.store.get_course(self.course.id)
        assert course.discussions_settings[field] == value

    def test_change_plugin_configuration(self):
        """
        Test changing plugin config that is saved to the course
        """
        payload = {
            "provider_type": "piazza",
            "plugin_configuration": {
                "allow_anonymous": False,
                "custom_field": "custom_value",
            },
        }
        response = self._post(payload)
        data = response.json()
        assert data["plugin_configuration"] == payload["plugin_configuration"]
        course = self.store.get_course(self.course.id)
        # Only configuration fields not stored in the course, or
        # directly in the model should be stored here.
        assert course.discussions_settings["piazza"] == {
            "custom_field": "custom_value",
        }

    @ddt.data(*[
        user_type.name for user_type in CourseUserType
        if user_type not in {  # pylint: disable=undefined-variable
            CourseUserType.ANONYMOUS,
            CourseUserType.GLOBAL_STAFF
        }
    ])
    def test_unable_to_change_provider_for_running_course(self, user_type):
        """
        Ensure that certain users cannot change provider for a running course.
        """
        self.course.start = datetime.now(timezone.utc) - timedelta(days=5)
        self.course = self.update_course(self.course, self.user.id)

        # use the global staff user to do the initial config
        # so we're sure to not get permissions errors
        response = self._post({
            'enabled': True,
            'provider_type': 'legacy',
        })
        assert response.status_code == status.HTTP_200_OK

        self.create_user_for_course(self.course, CourseUserType[user_type])

        response = self._post({
            'enabled': True,
            'provider_type': 'piazza',
        })
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_global_staff_can_change_provider_for_running_course(self):
        """
        Ensure that global staff can change provider for a running course.
        """
        self.course.start = datetime.now(timezone.utc) - timedelta(days=5)
        self.course = self.update_course(self.course, self.user.id)

        # use the global staff user to do the initial config
        # so we're sure to not get permissions errors
        response = self._post({
            'enabled': True,
            'provider_type': 'legacy',
        })
        assert response.status_code == status.HTTP_200_OK

        response = self._post({
            'enabled': True,
            'provider_type': 'piazza',
        })
        assert response.status_code == status.HTTP_200_OK
