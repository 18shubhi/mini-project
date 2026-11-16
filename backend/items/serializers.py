from django.conf import settings
from rest_framework import serializers

from .models import Item


class ItemSerializer(serializers.ModelSerializer):
    reporter = serializers.SerializerMethodField()

    class Meta:
        model = Item
        fields = (
            "id",
            "title",
            "description",
            "category",
            "type",
            "date",
            "location",
            "image",
            "reporter",
            "status",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "reporter", "status", "created_at", "updated_at")

    def get_reporter(self, obj):
        return {
            "id": obj.reporter_id,
            "name": obj.reporter.name,
            "role": obj.reporter.role,
        }

    def validate_image(self, image):
        max_size = getattr(settings, "ITEM_IMAGE_MAX_SIZE", 5 * 1024 * 1024)
        if image.size > max_size:
            raise serializers.ValidationError(
                f"Image size must not exceed {max_size // (1024 * 1024)} MB."
            )
        return image