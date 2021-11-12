"""
Tests for ESG Serializers
"""
from django.test import TestCase
from unittest.mock import Mock

from lms.djangoapps.ora_staff_grader.serializers import (
    CourseMetadataSerializer,
    InitializeSerializer,
    LockStatusSerializer,
    OpenResponseMetadataSerializer,
    SubmissionMetadataSerializer,
)
from openedx.core.djangoapps.content.course_overviews.tests.factories import CourseOverviewFactory
from xmodule.modulestore.tests.django_utils import SharedModuleStoreTestCase


class TestCourseMetadataSerializer(SharedModuleStoreTestCase):
    """
    Tests for CourseMetadataSerializer
    """
    course_data = {
        "org": "Oxford",
        "display_name": "Introduction to Time Travel",
        "display_number_with_default": "TT101",
        "run": "2054",
    }

    course_id = "course-v1:Oxford+TT101+2054"

    def setUp(self):
        super().setUp()

        self.course_overview = CourseOverviewFactory.create(**self.course_data)

    def test_course_serialize(self):
        data = CourseMetadataSerializer(self.course_overview).data

        assert data == {
            "title": self.course_data["display_name"],
            "org": self.course_data["org"],
            "number": self.course_data["display_number_with_default"],
            "courseId": self.course_id,
        }


class TestOpenResponseMetadataSerializer(TestCase):
    """
    Tests for OpenResponseMetadataSerializer
    """
    ora_data = {
        "display_name": "Week 1: Time Travel Paradoxes",
        "prompts": ["<p>In your own words, explain a famous time travel paradox</p>"],
        "teams_enabled": False
    }

    def setUp(self):
        super().setUp()

        self.mock_ora_instance = Mock(name='openassessment-block', **self.ora_data)

    def test_individual_ora(self):
        # An ORA with teams disabled should have type "individual"
        data = OpenResponseMetadataSerializer(self.mock_ora_instance).data

        assert data == {
            "name": self.ora_data['display_name'],
            "prompts": self.ora_data['prompts'],
            "type": "individual",
        }

    def test_team_ora(self):
        # An ORA with teams enabled should have type "team"
        self.mock_ora_instance.teams_enabled = True
        data = OpenResponseMetadataSerializer(self.mock_ora_instance).data

        assert data == {
            "name": self.ora_data['display_name'],
            "prompts": self.ora_data['prompts'],
            "type": "team",
        }


class TestSubmissionMetadataSerializer(TestCase):
    """
    Tests for SubmissionMetadataSerializer. Implicitly, this also exercises ScoreSerializer.
    SubmissionMetadata comes from the ORA list_staff_workflows XBlock.json_handler and has the shape:
    "<submission_uuid>": {
        "submissionUuid": "<submission_uuid>",
        "username": "<username/empty>",
        "teamName": "<team_name/empty>",
        "dateSubmitted": "<yyyy-mm-dd HH:MM:SS>",
        "dateGraded": "<yyyy-mm-dd HH:MM:SS/None>",
        "gradedBy": "<username/empty>",
        "gradingStatus": "<ungraded/graded>",
        "lockStatus": "<locked/unlocked/in-progress",
        "score": {
            "pointsEarned": <num>,
            "pointsPossible": <num>
        }
    }
    Right now, this is just passed through without any transforms.
    """
    submission_data = {
        "a": {
            "submissionUuid": "a",
            "username": "foo",
            "teamName": "",
            "dateSubmitted": "1969-07-16 13:32:00",
            "dateGraded": "None",
            "gradedBy": "",
            "gradingStatus": "ungraded",
            "lockStatus": "unlocked",
            "score": {
                "pointsEarned": 0,
                "pointsPossible": 10
            }
        },
        "b": {
            "submissionUuid": "b",
            "username": "",
            "teamName": "bar",
            "dateSubmitted": "1969-07-20 20:17:40",
            "dateGraded": "None",
            "gradedBy": "",
            "gradingStatus": "ungraded",
            "lockStatus": "in-progress",
            "score": {
                "pointsEarned": 0,
                "pointsPossible": 10
            }
        },
        "c": {
            "submissionUuid": "c",
            "username": "baz",
            "teamName": "",
            "dateSubmitted": "1969-07-21 21:35:00",
            "dateGraded": "1969-07-24 16:44:00",
            "gradedBy": "buz",
            "gradingStatus": "graded",
            "lockStatus": "unlocked",
            "score": {
                "pointsEarned": 9,
                "pointsPossible": 10
            }
        }
    }

    def test_submission_serialize(self):
        for submission_id, submission_data in self.submission_data.items():
            data = SubmissionMetadataSerializer(submission_data).data

            # For each submission, data is just passed through
            assert self.submission_data[submission_id] == data

    def test_empty_score(self):
        """
        An empty score dict should be serialized as None
        """
        submission = {
            "submissionUuid": "empty-score",
            "username": "WOPR",
            "dateSubmitted": "1983-06-03 00:00:00",
            "dateGraded": None,
            "gradedBy": None,
            "gradingStatus": "ungraded",
            "lockStatus": "unlocked",
            "score": {}
        }

        expected_output = {
            "submissionUuid": "empty-score",
            "username": "WOPR",
            "teamName": None,
            "dateSubmitted": "1983-06-03 00:00:00",
            "dateGraded": None,
            "gradedBy": None,
            "gradingStatus": "ungraded",
            "lockStatus": "unlocked",
            "score": None
        }

        data = SubmissionMetadataSerializer(submission).data

        assert data == expected_output


class TestInitializeSerializer(TestCase):
    """
    Tests for InitializeSerializer
    """
    def set_up_ora(self):
        """ Create a mock Open Repsponse Assessment for serialization """
        ora_data = {
            "display_name": "Week 1: Time Travel Paradoxes",
            "prompts": ["<p>In your own words, explain a famous time travel paradox</p>"],
            "teams_enabled": False
        }

        return Mock(name='openassessment-block', **ora_data)

    def set_up_course_metadata(self):
        """ Create mock course metadata for serialization """
        course_org = "Oxford"
        course_name = "Introduction to Time Travel"
        course_number = "TT101"
        course_run = "2054"

        return CourseOverviewFactory.create(
            org=course_org,
            display_name=course_name,
            display_number_with_default=course_number,
            run=course_run,
        )

    def setUp(self):
        super().setUp()

        self.mock_ora_instance = self.set_up_ora()
        self.mock_course_metadata = self.set_up_course_metadata()

        # Submissions data gets some minor transforms
        # This test data does not undergo any transforms so we can do easier comparison tests
        self.mock_submissions_data = {
            "space-oddity": {
                "submissionUuid": "space-oddity",
                "username": "Major Tom",
                "teamName": None,
                "dateSubmitted": "1969-06-20 00:00:00",
                "dateGraded": "1969-07-11 00:00:00",
                "gradedBy": "Ground Control",
                "gradingStatus": "graded",
                "lockStatus": "unlocked",
                "score": {
                    "pointsEarned": 10,
                    "pointsPossible": 10,
                }
            }
        }

        # Rubric data is passed through without transforms, we can create a toy response
        self.mock_rubric_data = {"foo": "bar"}

    def test_serializer_output(self):
        input_data = {
            "courseMetadata": self.mock_course_metadata,
            "oraMetadata": self.mock_ora_instance,
            "submissions": self.mock_submissions_data,
            "rubricConfig": self.mock_rubric_data,
        }

        output_data = InitializeSerializer(input_data).data

        # Check that each of the sub-serializers assembles data correctly
        assert output_data['courseMetadata'] == CourseMetadataSerializer(self.mock_course_metadata).data
        assert output_data['oraMetadata'] == OpenResponseMetadataSerializer(self.mock_ora_instance).data
        assert output_data['submissions'] == self.mock_submissions_data
        assert output_data['rubricConfig'] == self.mock_rubric_data


class TestLockStatusSerializer(SharedModuleStoreTestCase):
    """
    Tests for LockStatusSerializer
    """
    lock_in_progress = {
        "submission_uuid": "e34ef789-a4b1-48cf-b1bc-b3edacfd4eb2",
        "owner_id": "10ab03f1b75b4f9d9ab13a1fd1dccca1",
        "created_at": "2021-09-21T21:54:09.901221Z",
        "lock_status": "in-progress",
    }

    lock_in_progress_expected = {
        "lockStatus": "in-progress"
    }

    lock_owned_by_other_user = {
        "submission_uuid": "e34ef789-a4b1-48cf-b1bc-b3edacfd4eb2",
        "owner_id": "10ab03f1b75b4f9d9ab13a1fd1dccca1",
        "created_at": "2021-09-21T21:54:09.901221Z",
        "lock_status": "locked",
    }

    lock_owned_by_other_user_expected = {
        "lockStatus": "locked"
    }

    course_id = "course-v1:Oxford+TT101+2054"

    def setUp(self):
        super().setUp()

    def test_happy_path(self):
        """ For simple cases, lock status is passed through directly """
        data = LockStatusSerializer(self.lock_in_progress).data
        assert data == self.lock_in_progress_expected

        data = LockStatusSerializer(self.lock_owned_by_other_user).data
        assert data == self.lock_owned_by_other_user_expected
