from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Notification
from .serializers import NotificationSerializer


class NotificationPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


class NotificationListView(generics.ListAPIView):
    serializer_class = NotificationSerializer
    permission_classes = (IsAuthenticated,)
    pagination_class = NotificationPagination

    def get_queryset(self):
        return Notification.objects.filter(recipient=self.request.user).select_related(
            "related_item", "related_claim"
        )


class UnreadNotificationCountView(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request):
        unread_count = Notification.objects.filter(
            recipient=request.user,
            is_read=False,
        ).count()
        return Response({"unread_count": unread_count})


class MarkNotificationReadView(APIView):
    permission_classes = (IsAuthenticated,)

    def patch(self, request, notification_id):
        notification = get_object_or_404(
            Notification.objects.filter(recipient=request.user),
            pk=notification_id,
        )
        if not notification.is_read:
            notification.is_read = True
            notification.save(update_fields=("is_read",))
        return Response(NotificationSerializer(notification).data, status=status.HTTP_200_OK)


class MarkAllNotificationsReadView(APIView):
    permission_classes = (IsAuthenticated,)

    def post(self, request):
        updated_count = Notification.objects.filter(
            recipient=request.user,
            is_read=False,
        ).update(is_read=True)
        return Response({"updated_count": updated_count}, status=status.HTTP_200_OK)