from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from items.models import Item
from recovery.models import RecoveryClaim

from .models import Notification
from .services import notify_potential_matches


User = get_user_model()


class NotificationApiTests(APITestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            email="notice-owner@example.edu",
            password="CampusFind-Test-2026!",
            name="Report Owner",
            role=User.Role.STUDENT,
        )
        self.other = User.objects.create_user(
            email="notice-other@example.edu",
            password="CampusFind-Test-2026!",
            name="Other Reporter",
            role=User.Role.FACULTY,
        )
        self.unrelated = User.objects.create_user(
            email="notice-unrelated@example.edu",
            password="CampusFind-Test-2026!",
            name="Unrelated User",
            role=User.Role.STUDENT,
        )
        self.client.force_authenticate(self.owner)
        self.items_url = reverse("items:item-list")
        self.notifications_url = reverse("notifications:notification-list")

    def create_item(self, reporter, item_type, **overrides):
        values = {
            "title": "Blue water bottle",
            "description": "Steel bottle with a mountain sticker.",
            "category": Item.Category.WATER_BOTTLES,
            "type": item_type,
            "date": date.today() - timedelta(days=1),
            "location": "Main Library",
            "status": Item.Status.OPEN,
            "reporter": reporter,
        }
        values.update(overrides)
        return Item.objects.create(**values)

    def create_notification(self, recipient, key, **overrides):
        values = {
            "recipient": recipient,
            "event_key": key,
            "notification_type": Notification.Type.CLAIM_SUBMITTED,
            "message": "Test notification.",
        }
        values.update(overrides)
        return Notification.objects.create(**values)

    def create_claim(self, item, claimant=None, **overrides):
        return RecoveryClaim.objects.create(
            item=item,
            claimant=claimant or self.owner,
            reason="The item has my initials and a unique scratch.",
            **overrides,
        )

    def submit_claim(self, item):
        return self.client.post(
            reverse("recovery:claim-list"),
            {"item_id": item.pk, "reason": "The item has my initials and a unique scratch."},
            format="json",
        )

    def test_new_report_creates_ranked_match_notifications_for_both_owners(self):
        found = self.create_item(self.other, Item.Type.FOUND)
        payload = {
            "title": "Blue bottle lost",
            "description": "Steel water bottle with mountain sticker.",
            "category": Item.Category.WATER_BOTTLES,
            "type": Item.Type.LOST,
            "date": date.today().isoformat(),
            "location": "Main Library entrance",
        }

        with override_settings(NOTIFICATION_MATCH_MIN_SCORE=0):
            response = self.client.post(self.items_url, payload, format="json")

        source = Item.objects.get(pk=response.data["id"])
        notifications = Notification.objects.filter(
            notification_type=Notification.Type.MATCH_SUGGESTION
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(notifications.count(), 2)
        owner_notice = notifications.get(recipient=self.owner)
        other_notice = notifications.get(recipient=self.other)
        self.assertEqual(owner_notice.related_item_id, found.pk)
        self.assertEqual(other_notice.related_item_id, source.pk)
        self.assertIsNotNone(owner_notice.similarity_score)
        self.assertIn(str(found.pk), owner_notice.message)
        self.assertIn("similarity", owner_notice.message)

    def test_same_type_resolved_candidates_and_below_threshold_do_not_notify(self):
        self.create_item(self.other, Item.Type.LOST)
        self.create_item(self.other, Item.Type.FOUND, status=Item.Status.RESOLVED)
        self.create_item(
            self.other,
            Item.Type.FOUND,
            title="A red umbrella",
            description="An umbrella at the sports field.",
            category=Item.Category.ACCESSORIES,
            location="Sports field",
        )
        payload = {
            "title": "Blue wallet lost",
            "description": "A leather wallet with a student card.",
            "category": Item.Category.BAGS_WALLETS,
            "type": Item.Type.LOST,
            "date": date.today().isoformat(),
            "location": "Library",
        }

        with override_settings(NOTIFICATION_MATCH_MIN_SCORE=101):
            self.client.post(self.items_url, payload, format="json")

        self.assertFalse(
            Notification.objects.filter(
                notification_type=Notification.Type.MATCH_SUGGESTION
            ).exists()
        )

    def test_users_are_not_notified_about_their_own_report_as_a_match(self):
        self.create_item(self.owner, Item.Type.FOUND)
        payload = {
            "title": "Blue bottle lost",
            "description": "Steel bottle with mountain sticker.",
            "category": Item.Category.WATER_BOTTLES,
            "type": Item.Type.LOST,
            "date": date.today().isoformat(),
            "location": "Main Library",
        }

        with override_settings(NOTIFICATION_MATCH_MIN_SCORE=0):
            response = self.client.post(self.items_url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertFalse(
            Notification.objects.filter(
                notification_type=Notification.Type.MATCH_SUGGESTION
            ).exists()
        )

    def test_repeated_match_processing_does_not_duplicate_pair_notifications(self):
        found = self.create_item(self.other, Item.Type.FOUND)
        with override_settings(NOTIFICATION_MATCH_MIN_SCORE=0):
            response = self.client.post(
                self.items_url,
                {
                    "title": "Blue bottle lost",
                    "description": "Steel bottle with mountain sticker.",
                    "category": Item.Category.WATER_BOTTLES,
                    "type": Item.Type.LOST,
                    "date": date.today().isoformat(),
                    "location": "Main Library",
                },
                format="json",
            )
            source = Item.objects.get(pk=response.data["id"])
            notify_potential_matches(source)
            notify_potential_matches(source)

        self.assertEqual(
            Notification.objects.filter(
                notification_type=Notification.Type.MATCH_SUGGESTION
            ).count(),
            2,
        )
        self.assertNotEqual(source.reporter_id, found.reporter_id)

    def test_claim_submission_approval_rejection_and_cancellation_notify_relevant_users(self):
        approved_item = self.create_item(self.other, Item.Type.FOUND)
        claim_response = self.submit_claim(approved_item)
        claim = RecoveryClaim.objects.get(pk=claim_response.data["id"])
        self.assertTrue(
            Notification.objects.filter(
                recipient=self.other,
                related_claim=claim,
                notification_type=Notification.Type.CLAIM_SUBMITTED,
            ).exists()
        )

        self.client.force_authenticate(self.other)
        approve_response = self.client.post(
            reverse("recovery:claim-approve", args=[claim.pk]), {}, format="json"
        )
        self.assertEqual(approve_response.status_code, status.HTTP_200_OK)
        self.assertTrue(
            Notification.objects.filter(
                recipient=self.owner,
                related_claim=claim,
                notification_type=Notification.Type.CLAIM_APPROVED,
            ).exists()
        )

        rejected_item = self.create_item(self.other, Item.Type.FOUND, title="Found keys")
        self.client.force_authenticate(self.owner)
        rejected_response = self.submit_claim(rejected_item)
        rejected_claim = RecoveryClaim.objects.get(pk=rejected_response.data["id"])
        self.client.force_authenticate(self.other)
        self.client.post(
            reverse("recovery:claim-reject", args=[rejected_claim.pk]),
            {"note": "The details do not match."},
            format="json",
        )
        self.assertTrue(
            Notification.objects.filter(
                recipient=self.owner,
                related_claim=rejected_claim,
                notification_type=Notification.Type.CLAIM_REJECTED,
            ).exists()
        )

        cancelled_item = self.create_item(self.other, Item.Type.FOUND, title="Found keys 2")
        self.client.force_authenticate(self.owner)
        cancelled_response = self.submit_claim(cancelled_item)
        cancelled_claim = RecoveryClaim.objects.get(pk=cancelled_response.data["id"])
        self.client.post(
            reverse("recovery:claim-cancel", args=[cancelled_claim.pk]), {}, format="json"
        )
        self.assertTrue(
            Notification.objects.filter(
                recipient=self.other,
                related_claim=cancelled_claim,
                notification_type=Notification.Type.CLAIM_CANCELLED,
            ).exists()
        )

    def test_recovery_completion_notifies_both_parties_after_both_confirm(self):
        item = self.create_item(self.other, Item.Type.FOUND)
        claim = self.create_claim(item)
        claim.status = RecoveryClaim.Status.APPROVED
        claim.save(update_fields=("status",))

        first_confirmation = self.client.post(
            reverse("recovery:claim-confirm-recovery", args=[claim.pk]), {}, format="json"
        )
        self.assertEqual(first_confirmation.status_code, status.HTTP_200_OK)
        self.assertFalse(
            Notification.objects.filter(
                notification_type=Notification.Type.RECOVERY_COMPLETED
            ).exists()
        )

        self.client.force_authenticate(self.other)
        second_confirmation = self.client.post(
            reverse("recovery:claim-confirm-recovery", args=[claim.pk]), {}, format="json"
        )
        self.assertEqual(second_confirmation.status_code, status.HTTP_200_OK)
        self.assertEqual(
            Notification.objects.filter(
                notification_type=Notification.Type.RECOVERY_COMPLETED,
                related_claim=claim,
            ).count(),
            2,
        )

    def test_notification_list_count_and_read_actions_are_recipient_scoped(self):
        first = self.create_notification(self.owner, "api:first")
        self.create_notification(self.owner, "api:second")
        someone_elses = self.create_notification(self.other, "api:other")

        list_response = self.client.get(self.notifications_url, {"page_size": 1})
        count_response = self.client.get(reverse("notifications:unread-count"))
        mark_response = self.client.patch(
            reverse("notifications:mark-read", args=[first.pk]), {}, format="json"
        )
        denied_response = self.client.patch(
            reverse("notifications:mark-read", args=[someone_elses.pk]), {}, format="json"
        )
        missing_response = self.client.patch(
            reverse("notifications:mark-read", args=[999999]), {}, format="json"
        )

        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertEqual(list_response.data["count"], 2)
        self.assertEqual(len(list_response.data["results"]), 1)
        self.assertEqual(count_response.data["unread_count"], 2)
        self.assertEqual(mark_response.status_code, status.HTTP_200_OK)
        self.assertTrue(mark_response.data["is_read"])
        self.assertEqual(denied_response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(missing_response.status_code, status.HTTP_404_NOT_FOUND)

        mark_all_response = self.client.post(reverse("notifications:read-all"), {}, format="json")
        self.assertEqual(mark_all_response.data["updated_count"], 1)
        self.assertEqual(
            Notification.objects.filter(recipient=self.owner, is_read=False).count(),
            0,
        )

    def test_notification_endpoints_require_authentication(self):
        self.client.force_authenticate(user=None)

        list_response = self.client.get(self.notifications_url)
        count_response = self.client.get(reverse("notifications:unread-count"))
        mark_all_response = self.client.post(reverse("notifications:read-all"), {}, format="json")

        self.assertEqual(list_response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(count_response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(mark_all_response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_notification_model_rejects_similarity_scores_outside_range(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.create_notification(
                self.owner,
                "api:invalid-score",
                notification_type=Notification.Type.MATCH_SUGGESTION,
                similarity_score=101,
            )