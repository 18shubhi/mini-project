"""Create in-app notifications from existing item and recovery workflows."""

from django.conf import settings

from items.models import Item
from matching.services import item_document, rank_matches

from .models import Notification


def _create_notification(
    *, recipient, notification_type, event_key, message, related_item=None,
    related_claim=None, similarity_score=None,
):
    return Notification.objects.get_or_create(
        recipient=recipient,
        event_key=event_key,
        defaults={
            "notification_type": notification_type,
            "message": message,
            "related_item": related_item,
            "related_claim": related_claim,
            "similarity_score": similarity_score,
        },
    )


def notify_potential_matches(source_item):
    if source_item.status != Item.Status.OPEN:
        return 0
    if source_item.type not in (Item.Type.LOST, Item.Type.FOUND):
        return 0

    opposite_type = Item.Type.FOUND if source_item.type == Item.Type.LOST else Item.Type.LOST
    candidates = list(
        Item.objects.select_related("reporter")
        .filter(type=opposite_type, status=Item.Status.OPEN)
        .exclude(pk=source_item.pk)
    )
    if not candidates:
        return 0

    minimum_score = float(getattr(settings, "NOTIFICATION_MATCH_MIN_SCORE", 35.0))
    ranked = rank_matches(
        item_document(source_item),
        [item_document(candidate) for candidate in candidates],
    )
    created_count = 0
    for match in ranked:
        score = match["similarity_score"]
        if score < minimum_score:
            continue
        candidate = next(
            candidate for candidate in candidates
            if candidate.pk == match["candidate"]["id"]
        )
        if source_item.reporter_id == candidate.reporter_id:
            continue

        pair_key = f"match:{min(source_item.pk, candidate.pk)}:{max(source_item.pk, candidate.pk)}"
        for recipient, matched_item in (
            (source_item.reporter, candidate),
            (candidate.reporter, source_item),
        ):
            if recipient.pk == matched_item.reporter_id:
                continue
            _, created = _create_notification(
                recipient=recipient,
                notification_type=Notification.Type.MATCH_SUGGESTION,
                event_key=pair_key,
                message=(
                    f"Possible match for your report: {matched_item.title} "
                    f"(item #{matched_item.pk}, similarity {score:.2f}/100). "
                    "This is a similarity suggestion, not a certainty."
                ),
                related_item=matched_item,
                similarity_score=score,
            )
            created_count += int(created)
    return created_count


def notify_claim_submitted(claim):
    return _create_notification(
        recipient=claim.item.reporter,
        notification_type=Notification.Type.CLAIM_SUBMITTED,
        event_key=f"claim:{claim.pk}:submitted",
        message=f"A user submitted a claim for your found item: {claim.item.title} (item #{claim.item_id}).",
        related_item=claim.item,
        related_claim=claim,
    )


def notify_claim_approved(claim):
    return _create_notification(
        recipient=claim.claimant,
        notification_type=Notification.Type.CLAIM_APPROVED,
        event_key=f"claim:{claim.pk}:approved",
        message=f"Your claim for {claim.item.title} (item #{claim.item_id}) was approved.",
        related_item=claim.item,
        related_claim=claim,
    )


def notify_claim_rejected(claim):
    note = f" Note: {claim.rejection_note}" if claim.rejection_note else ""
    return _create_notification(
        recipient=claim.claimant,
        notification_type=Notification.Type.CLAIM_REJECTED,
        event_key=f"claim:{claim.pk}:rejected",
        message=f"Your claim for {claim.item.title} (item #{claim.item_id}) was rejected.{note}",
        related_item=claim.item,
        related_claim=claim,
    )


def notify_claim_cancelled(claim):
    return _create_notification(
        recipient=claim.item.reporter,
        notification_type=Notification.Type.CLAIM_CANCELLED,
        event_key=f"claim:{claim.pk}:cancelled",
        message=f"A claim for your item {claim.item.title} (item #{claim.item_id}) was cancelled.",
        related_item=claim.item,
        related_claim=claim,
    )


def notify_recovery_completed(claim):
    recipients = {claim.claimant_id: claim.claimant, claim.item.reporter_id: claim.item.reporter}
    for recipient in recipients.values():
        _create_notification(
            recipient=recipient,
            notification_type=Notification.Type.RECOVERY_COMPLETED,
            event_key=f"claim:{claim.pk}:recovered",
            message=f"Recovery of {claim.item.title} (item #{claim.item_id}) was confirmed by both parties.",
            related_item=claim.item,
            related_claim=claim,
        )