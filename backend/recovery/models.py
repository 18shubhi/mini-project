from django.conf import settings
from django.db import models
from django.db.models import Q

from items.models import Item


class RecoveryClaim(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        APPROVED = "APPROVED", "Approved"
        REJECTED = "REJECTED", "Rejected"
        CANCELLED = "CANCELLED", "Cancelled"
        RECOVERED = "RECOVERED", "Recovered"

    item = models.ForeignKey(
        Item,
        on_delete=models.CASCADE,
        related_name="recovery_claims",
    )
    claimant = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="recovery_claims",
    )
    reason = models.TextField(max_length=2000)
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.PENDING,
    )
    rejection_note = models.CharField(max_length=1000, blank=True)
    claimant_confirmed_at = models.DateTimeField(blank=True, null=True)
    reporter_confirmed_at = models.DateTimeField(blank=True, null=True)
    completed_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)
        constraints = [
            models.UniqueConstraint(
                fields=("item", "claimant"),
                condition=Q(status__in=("PENDING", "APPROVED")),
                name="uniq_active_claimant_per_item",
            ),
            models.UniqueConstraint(
                fields=("item",),
                condition=Q(status="APPROVED"),
                name="uniq_approved_claim_per_item",
            ),
        ]
        indexes = [models.Index(fields=("item", "status"))]

    def __str__(self):
        return f"Claim {self.pk} for {self.item} ({self.get_status_display()})"