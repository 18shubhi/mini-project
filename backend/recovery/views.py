from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from items.models import Item
from notifications.services import (
    notify_claim_approved,
    notify_claim_cancelled,
    notify_claim_rejected,
    notify_claim_submitted,
    notify_recovery_completed,
)

from .models import RecoveryClaim
from .serializers import ClaimRejectionSerializer, RecoveryClaimSerializer


class RecoveryClaimViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = RecoveryClaimSerializer
    permission_classes = (IsAuthenticated,)

    def get_queryset(self):
        queryset = RecoveryClaim.objects.select_related(
            "item", "item__reporter", "claimant"
        )
        user = self.request.user
        if user.is_staff or user.is_superuser:
            return queryset.all()
        return queryset.filter(Q(claimant=user) | Q(item__reporter=user))

    def perform_create(self, serializer):
        item = serializer.validated_data["item"]
        with transaction.atomic():
            item = Item.objects.select_for_update().get(pk=item.pk)
            if item.type != Item.Type.FOUND:
                raise ValidationError({"item_id": "Claims can only be made for found items."})
            if item.reporter_id == self.request.user.id:
                raise ValidationError({"item_id": "You cannot claim your own reported item."})
            if item.status != Item.Status.OPEN:
                raise ValidationError({"item_id": "This item is no longer available to claim."})
            if RecoveryClaim.objects.filter(
                item=item,
                status=RecoveryClaim.Status.APPROVED,
            ).exists():
                raise ValidationError({"item_id": "A claim has already been approved for this item."})
            if RecoveryClaim.objects.filter(
                item=item,
                claimant=self.request.user,
                status__in=(RecoveryClaim.Status.PENDING, RecoveryClaim.Status.APPROVED),
            ).exists():
                raise ValidationError({"item_id": "You already have an active claim for this item."})
            try:
                with transaction.atomic():
                    claim = serializer.save(item=item, claimant=self.request.user)
            except IntegrityError as exc:
                raise ValidationError(
                    {"item_id": "An active claim already exists for this item."}
                ) from exc
            notify_claim_submitted(claim)

    def _require_decision_permission(self, request, claim):
        user = request.user
        if (
            claim.item.reporter_id != user.id
            and not user.is_staff
            and not user.is_superuser
        ):
            raise PermissionDenied("Only the item reporter or authorized staff can decide this claim.")

    @action(detail=True, methods=("post",))
    def approve(self, request, pk=None):
        claim = self.get_object()
        self._require_decision_permission(request, claim)

        with transaction.atomic():
            item = Item.objects.select_for_update().get(pk=claim.item_id)
            claim = RecoveryClaim.objects.select_for_update().get(pk=claim.pk)
            if claim.status != RecoveryClaim.Status.PENDING:
                raise ValidationError({"status": "Only pending claims can be approved."})
            if item.type != Item.Type.FOUND or item.status != Item.Status.OPEN:
                raise ValidationError({"item": "This item is no longer available for recovery."})
            if RecoveryClaim.objects.filter(
                item=item,
                status=RecoveryClaim.Status.APPROVED,
            ).exclude(pk=claim.pk).exists():
                raise ValidationError({"status": "Another claim has already been approved."})

            pending_claims = list(
                RecoveryClaim.objects.select_related("item", "claimant")
                .filter(item=item, status=RecoveryClaim.Status.PENDING)
                .exclude(pk=claim.pk)
            )
            claim.status = RecoveryClaim.Status.APPROVED
            claim.save(update_fields=("status", "updated_at"))
            for other_claim in pending_claims:
                other_claim.status = RecoveryClaim.Status.REJECTED
                other_claim.rejection_note = "Another claim for this item was approved."
                other_claim.save(update_fields=("status", "rejection_note", "updated_at"))
                notify_claim_rejected(other_claim)
            notify_claim_approved(claim)

        return Response(self.get_serializer(claim).data)

    @action(detail=True, methods=("post",))
    def reject(self, request, pk=None):
        claim = self.get_object()
        self._require_decision_permission(request, claim)
        note_serializer = ClaimRejectionSerializer(data=request.data)
        note_serializer.is_valid(raise_exception=True)

        with transaction.atomic():
            Item.objects.select_for_update().get(pk=claim.item_id)
            claim = RecoveryClaim.objects.select_for_update().get(pk=claim.pk)
            if claim.status != RecoveryClaim.Status.PENDING:
                raise ValidationError({"status": "Only pending claims can be rejected."})
            claim.status = RecoveryClaim.Status.REJECTED
            claim.rejection_note = note_serializer.validated_data.get("note", "").strip()
            claim.save(update_fields=("status", "rejection_note", "updated_at"))
            notify_claim_rejected(claim)

        return Response(self.get_serializer(claim).data)

    @action(detail=True, methods=("post",))
    def cancel(self, request, pk=None):
        claim = self.get_object()
        if claim.claimant_id != request.user.id:
            raise PermissionDenied("Only the claimant can cancel this claim.")

        with transaction.atomic():
            Item.objects.select_for_update().get(pk=claim.item_id)
            claim = RecoveryClaim.objects.select_for_update().get(pk=claim.pk)
            if claim.status != RecoveryClaim.Status.PENDING:
                raise ValidationError({"status": "Only pending claims can be cancelled."})
            claim.status = RecoveryClaim.Status.CANCELLED
            claim.save(update_fields=("status", "updated_at"))
            notify_claim_cancelled(claim)

        return Response(self.get_serializer(claim).data)

    @action(detail=True, methods=("post",), url_path="confirm-recovery")
    def confirm_recovery(self, request, pk=None):
        claim = self.get_object()
        user_id = request.user.id
        if user_id not in (claim.claimant_id, claim.item.reporter_id):
            raise PermissionDenied("Only the claimant and item reporter can confirm handover.")

        with transaction.atomic():
            item = Item.objects.select_for_update().get(pk=claim.item_id)
            claim = RecoveryClaim.objects.select_for_update().get(pk=claim.pk)
            if claim.status == RecoveryClaim.Status.RECOVERED:
                return Response(self.get_serializer(claim).data)
            if claim.status != RecoveryClaim.Status.APPROVED:
                raise ValidationError({"status": "Only an approved claim can be confirmed."})

            confirmed_at = timezone.now()
            if user_id == claim.claimant_id:
                claim.claimant_confirmed_at = claim.claimant_confirmed_at or confirmed_at
            else:
                claim.reporter_confirmed_at = claim.reporter_confirmed_at or confirmed_at

            update_fields = ["claimant_confirmed_at", "reporter_confirmed_at", "updated_at"]
            if claim.claimant_confirmed_at and claim.reporter_confirmed_at:
                claim.status = RecoveryClaim.Status.RECOVERED
                claim.completed_at = confirmed_at
                item.status = Item.Status.RESOLVED
                item.save(update_fields=("status", "updated_at"))
                update_fields.extend(("status", "completed_at"))
            claim.save(update_fields=tuple(update_fields))
            if claim.status == RecoveryClaim.Status.RECOVERED:
                notify_recovery_completed(claim)

        return Response(self.get_serializer(claim).data)