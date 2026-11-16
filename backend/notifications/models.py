from django.conf import settings
from django.db import models
from django.db.models import Q

from items.models import Item


class Notification(models.Model):
    class Type(models.TextChoices):
        MATCH_SUGGESTION = "MATCH_SUGGESTION", "Potential item match"
        CLAIM_SUBMITTED = "CLAIM_SUBMITTED", "Claim submitted"
        CLAIM_APPROVED = "CLAIM_APPROVED", "Claim approved"
        CLAIM_REJECTED = "CLAIM_REJECTED", "Claim rejected"
        CLAIM_CANCELLED = "CLAIM_CANCELLED", "Claim cancelled"
        RECOVERY_COMPLETED = "RECOVERY_COMPLETED", "Recovery completed"

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    notification_type = models.CharField(max_length=32, choices=Type.choices)
    message = models.TextField()
    related_item = models.ForeignKey(
        Item,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="notifications",
    )
    related_claim = models.ForeignKey(
        "recovery.RecoveryClaim",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="notifications",
    )
    similarity_score = models.FloatField(null=True, blank=True)
    event_key = models.CharField(max_length=180)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)
        constraints = [
            models.UniqueConstraint(
                fields=("recipient", "event_key"),
                name="uniq_notif_recipient_event",
            ),
            models.CheckConstraint(
                condition=(
                    Q(similarity_score__isnull=True)
                    | Q(similarity_score__gte=0, similarity_score__lte=100)
                ),
                name="notif_score_0_100",
            ),
        ]
        indexes = [models.Index(fields=("recipient", "is_read", "created_at"))]

    def __str__(self):
        return f"{self.get_notification_type_display()} for {self.recipient_id}"