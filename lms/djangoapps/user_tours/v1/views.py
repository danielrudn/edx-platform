""" API for User Tours. """
from edx_rest_framework_extensions.auth.jwt.authentication import JwtAuthentication
from rest_framework.generics import RetrieveUpdateAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from lms.djangoapps.user_tours.models import UserTour
from lms.djangoapps.user_tours.toggles import USER_TOURS_ENABLED
from lms.djangoapps.user_tours.v1.serializers import UserTourSerializer


class UserTourView(RetrieveUpdateAPIView):
    """
    Supports retrieving and patching the UserTour model

    **Example Requests**

        GET /api/user_tours/v1/{username}
        PATCH /api/user_tours/v1/{username}
    """
    authentication_classes = (JwtAuthentication,)
    permission_classes = (IsAuthenticated,)
    serializer_class = UserTourSerializer

    def get(self, request, username):
        """
        Retrieve the User Tour for the given username.

        Allows staff users to retrieve any user's User Tour.

        Returns
            403 if waffle flag is not enabled
            400 if there is a not allowed request (requesting a user you don't have access to)
            404 if the UserTour does not exist (shouldn't happen, but safety first)
            200 with the following fields:
                course_home_tour_status (str): one of UserTour.CourseHomeTourStatusChoices
                show_courseware_tour (bool): indicates if courseware tour should be shown.
        """
        if not USER_TOURS_ENABLED.is_enabled():
            return Response(status=status.HTTP_403_FORBIDDEN)

        if self.request.user.username != username and not self.request.user.is_staff:
            return Response(status=status.HTTP_400_BAD_REQUEST)

        try:
            user_tour = UserTour.objects.get(user__username=username)
        except UserTour.DoesNotExist as e:
            return Response(status=status.HTTP_404_NOT_FOUND)

        return Response(self.get_serializer_class()(user_tour).data, status=status.HTTP_200_OK)

    def patch(self, request, username):
        """
        Patch the User Tour for the request.user.

        Supports updating the `course_home_tour_status` and `show_courseware_tour` fields.

        Returns:
            403 if waffle flag is not enabled
            200 response if update was successful, else 400.
        """
        if not USER_TOURS_ENABLED.is_enabled():
            return Response(status=status.HTTP_403_FORBIDDEN)

        if self.request.user.username != username:
            return Response(status=status.HTTP_400_BAD_REQUEST)

        serializer = self.get_serializer_class()(data=request.data)
        serializer.is_valid(raise_exception=True)
        updated = UserTour.objects.filter(user__username=username).update(**serializer.validated_data)
        if updated:
            return Response(status=status.HTTP_200_OK)
        else:
            return Response(status=status.HTTP_400_BAD_REQUEST)

    def put(self, _request, _username):
        """ Unsupported method. """
        return Response(status=status.HTTP_405_METHOD_NOT_ALLOWED)
