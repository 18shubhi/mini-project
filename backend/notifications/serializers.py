from rest_framework import serializers

from .models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    related_item = serializers.SerializerMethodField()
    related_claim_id = serializers.IntegerField(read_only=True)

    class Meta:
        model = Notification
        fields = (
            "id",
            "notification_type",
            "message",
            "related_item",
            "related_claim_id",
            "similarity_score",
            "is_read",
            "created_at",
        )
        read_only_fields = fields

    def get_related_item(self, notification):
        item = notification.related_item
        if item is None:
            return None
        return {"id": item.pk, "title": item.title, "type": item.type}