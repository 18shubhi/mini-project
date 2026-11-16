from rest_framework import serializers

from items.models import Item

from .models import RecoveryClaim


class RecoveryClaimSerializer(serializers.ModelSerializer):
    item_id = serializers.PrimaryKeyRelatedField(
        source="item",
        queryset=Item.objects.all(),
        write_only=True,
    )
    item = serializers.SerializerMethodField(read_only=True)
    claimant = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = RecoveryClaim
        fields = (
            "id",
            "item_id",
            "item",
            "claimant",
            "reason",
            "status",
            "rejection_note",
            "claimant_confirmed_at",
            "reporter_confirmed_at",
            "completed_at",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "item",
            "claimant",
            "status",
            "rejection_note",
            "claimant_confirmed_at",
            "reporter_confirmed_at",
            "completed_at",
            "created_at",
            "updated_at",
        )

    def get_item(self, claim):
        return {
            "id": claim.item_id,
            "title": claim.item.title,
            "type": claim.item.type,
            "status": claim.item.status,
            "reporter_id": claim.item.reporter_id,
        }

    def get_claimant(self, claim):
        return {
            "id": claim.claimant_id,
            "name": claim.claimant.name,
            "role": claim.claimant.role,
        }

    def validate_reason(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Explain why this item belongs to you.")
        return value


class ClaimRejectionSerializer(serializers.Serializer):
    note = serializers.CharField(required=False, allow_blank=True, max_length=1000)