from datetime import date

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import AccessToken

from items.models import Item

from .models import RecoveryClaim


User = get_user_model()


class RecoveryClaimApiTests(APITestCase):
    def setUp(self):
        self.reporter = User.objects.create_user(
            email="reporter@example.edu",
            password="CampusFind-Test-2026!",
            name="Item Reporter",
            role=User.Role.STUDENT,
        )
        self.claimant = User.objects.create_user(
            email="claimant@example.edu",
            password="CampusFind-Test-2026!",
            name="Item Claimant",
            role=User.Role.FACULTY,
        )
        self.other_user = User.objects.create_user(
            email="other@example.edu",
            password="CampusFind-Test-2026!",
            name="Other User",
            role=User.Role.STUDENT,
        )
        self.staff = User.objects.create_user(
            email="staff@example.edu",
            password="CampusFind-Test-2026!",
            name="Campus Staff",
            role=User.Role.SUPPORTING_STAFF,
            is_staff=True,
        )
        self.found_item = self.create_item(Item.Type.FOUND, self.reporter)
        self.lost_item = self.create_item(Item.Type.LOST, self.reporter)
        self.list_url = reverse("recovery:claim-list")
        self.client.force_authenticate(self.claimant)

    def create_item(self, item_type, reporter):
        return Item.objects.create(
            title=f"{item_type.title()} item",
            description="Item for recovery API tests.",
            category=Item.Category.OTHER,
            type=item_type,
            date=date.today(),
            location="Campus Library",
            reporter=reporter,
        )

    def submit_claim(self, item=None, reason="It has my name and unique markings."):
        return self.client.post(
            self.list_url,
            {"item_id": (item or self.found_item).id, "reason": reason},
            format="json",
        )

    def create_claim(self, item=None, claimant=None, **fields):
        return RecoveryClaim.objects.create(
            item=item or self.found_item,
            claimant=claimant or self.claimant,
            reason=fields.pop("reason", "It has my name and unique markings."),
            **fields,
        )

    def action_url(self, claim, action):
        return reverse(f"recovery:claim-{action}", args=[claim.id])

    def test_authenticated_user_can_submit_claim_for_found_item(self):
        response = self.submit_claim()

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["item"]["id"], self.found_item.id)
        self.assertEqual(response.data["claimant"]["id"], self.claimant.id)
        self.assertEqual(response.data["status"], RecoveryClaim.Status.PENDING)
        self.assertEqual(response.data["reason"], "It has my name and unique markings.")

    def test_claim_creation_requires_authentication_and_accepts_jwt(self):
        self.client.force_authenticate(user=None)
        response = self.submit_claim()
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

        token = AccessToken.for_user(self.claimant)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        response = self.submit_claim()
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_user_cannot_claim_own_item_or_a_lost_item(self):
        self.client.force_authenticate(self.reporter)
        own_item_response = self.submit_claim()
        self.assertEqual(own_item_response.status_code, status.HTTP_400_BAD_REQUEST)

        self.client.force_authenticate(self.claimant)
        lost_item_response = self.submit_claim(item=self.lost_item)
        self.assertEqual(lost_item_response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_duplicate_active_claim_is_rejected_but_cancelled_claim_can_be_resubmitted(self):
        first_response = self.submit_claim()
        duplicate_response = self.submit_claim()
        claim_id = first_response.data["id"]
        cancel_response = self.client.post(
            reverse("recovery:claim-cancel", args=[claim_id]), {}, format="json"
        )
        resubmitted_response = self.submit_claim()

        self.assertEqual(first_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(duplicate_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(cancel_response.status_code, status.HTTP_200_OK)
        self.assertEqual(cancel_response.data["status"], RecoveryClaim.Status.CANCELLED)
        self.assertEqual(resubmitted_response.status_code, status.HTTP_201_CREATED)

    def test_claim_lists_and_details_are_visible_only_to_related_users_or_staff(self):
        claim = self.create_claim()
        detail_url = reverse("recovery:claim-detail", args=[claim.id])

        claimant_list = self.client.get(self.list_url)
        self.client.force_authenticate(self.reporter)
        reporter_list = self.client.get(self.list_url)
        self.client.force_authenticate(self.other_user)
        unrelated_list = self.client.get(self.list_url)
        unrelated_detail = self.client.get(detail_url)
        self.client.force_authenticate(self.staff)
        staff_list = self.client.get(self.list_url)

        self.assertEqual(len(claimant_list.data), 1)
        self.assertEqual(len(reporter_list.data), 1)
        self.assertEqual(unrelated_list.data, [])
        self.assertEqual(unrelated_detail.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(len(staff_list.data), 1)

    def test_only_reporter_or_staff_can_approve_claim(self):
        claim = self.create_claim()
        self.client.force_authenticate(self.claimant)
        claimant_response = self.client.post(self.action_url(claim, "approve"), {}, format="json")
        self.assertEqual(claimant_response.status_code, status.HTTP_403_FORBIDDEN)

        self.client.force_authenticate(self.reporter)
        reporter_response = self.client.post(self.action_url(claim, "approve"), {}, format="json")
        self.assertEqual(reporter_response.status_code, status.HTTP_200_OK)
        self.assertEqual(reporter_response.data["status"], RecoveryClaim.Status.APPROVED)

    def test_authorized_staff_can_approve_claim(self):
        claim = self.create_claim()
        self.client.force_authenticate(self.staff)

        response = self.client.post(self.action_url(claim, "approve"), {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], RecoveryClaim.Status.APPROVED)

    def test_approval_rejects_other_pending_claims_for_the_item(self):
        first_claim = self.create_claim()
        other_claim = self.create_claim(claimant=self.other_user)
        self.client.force_authenticate(self.reporter)

        response = self.client.post(self.action_url(first_claim, "approve"), {}, format="json")

        other_claim.refresh_from_db()
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(other_claim.status, RecoveryClaim.Status.REJECTED)

    def test_reporter_can_reject_pending_claim_with_a_note(self):
        claim = self.create_claim()
        self.client.force_authenticate(self.reporter)

        response = self.client.post(
            self.action_url(claim, "reject"),
            {"note": "The identifying details do not match."},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], RecoveryClaim.Status.REJECTED)
        self.assertEqual(response.data["rejection_note"], "The identifying details do not match.")

    def test_claimant_can_cancel_pending_claim_but_reporter_cannot(self):
        claim = self.create_claim()
        self.client.force_authenticate(self.reporter)
        reporter_response = self.client.post(self.action_url(claim, "cancel"), {}, format="json")
        self.assertEqual(reporter_response.status_code, status.HTTP_403_FORBIDDEN)

        self.client.force_authenticate(self.claimant)
        claimant_response = self.client.post(self.action_url(claim, "cancel"), {}, format="json")
        self.assertEqual(claimant_response.status_code, status.HTTP_200_OK)
        self.assertEqual(claimant_response.data["status"], RecoveryClaim.Status.CANCELLED)

    def test_only_approved_claims_can_be_confirmed(self):
        claim = self.create_claim()

        response = self.client.post(
            self.action_url(claim, "confirm-recovery"), {}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_recovery_requires_claimant_and_reporter_confirmation(self):
        claim = self.create_claim()
        self.client.force_authenticate(self.reporter)
        approved = self.client.post(self.action_url(claim, "approve"), {}, format="json")
        self.assertEqual(approved.status_code, status.HTTP_200_OK)

        self.client.force_authenticate(self.claimant)
        claimant_confirmation = self.client.post(
            self.action_url(claim, "confirm-recovery"), {}, format="json"
        )
        self.found_item.refresh_from_db()
        self.assertEqual(claimant_confirmation.data["status"], RecoveryClaim.Status.APPROVED)
        self.assertEqual(self.found_item.status, Item.Status.OPEN)

        self.client.force_authenticate(self.reporter)
        reporter_confirmation = self.client.post(
            self.action_url(claim, "confirm-recovery"), {}, format="json"
        )
        self.found_item.refresh_from_db()
        self.assertEqual(reporter_confirmation.status_code, status.HTTP_200_OK)
        self.assertEqual(reporter_confirmation.data["status"], RecoveryClaim.Status.RECOVERED)
        self.assertIsNotNone(reporter_confirmation.data["completed_at"])
        self.assertEqual(self.found_item.status, Item.Status.RESOLVED)

    def test_unrelated_user_cannot_confirm_handover(self):
        claim = self.create_claim(status=RecoveryClaim.Status.APPROVED)
        self.client.force_authenticate(self.other_user)

        response = self.client.post(
            self.action_url(claim, "confirm-recovery"), {}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_invalid_claim_requests_are_rejected(self):
        blank_reason = self.submit_claim(reason="   ")
        missing_item = self.client.post(
            self.list_url,
            {"item_id": 999999, "reason": "It has my name."},
            format="json",
        )

        self.assertEqual(blank_reason.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(missing_item.status_code, status.HTTP_400_BAD_REQUEST)