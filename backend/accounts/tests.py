"""Focused API tests for registration and JWT authentication."""
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken


User = get_user_model()
VALID_PASSWORD = "CampusFind-Auth-Test-2026!"


class RegistrationAndLoginTests(APITestCase):
    def test_registration_hashes_password_and_omits_it_from_response(self):
        response = self.client.post(
            reverse("accounts:register"),
            {
                "name": "Test Student",
                "email": "STUDENT@example.edu",
                "password": VALID_PASSWORD,
                "role": User.Role.STUDENT,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertNotIn("password", response.data)
        user = User.objects.get(email="student@example.edu")
        self.assertTrue(user.check_password(VALID_PASSWORD))
        self.assertNotEqual(user.password, VALID_PASSWORD)

    def test_registration_rejects_duplicate_email_and_invalid_role(self):
        User.objects.create_user(
            email="student@example.edu",
            password=VALID_PASSWORD,
            name="Existing Student",
            role=User.Role.STUDENT,
        )

        duplicate_response = self.client.post(
            reverse("accounts:register"),
            {
                "name": "Duplicate Student",
                "email": "STUDENT@example.edu",
                "password": VALID_PASSWORD,
                "role": User.Role.STUDENT,
            },
            format="json",
        )
        invalid_role_response = self.client.post(
            reverse("accounts:register"),
            {
                "name": "Invalid Role",
                "email": "new@example.edu",
                "password": VALID_PASSWORD,
                "role": "VISITOR",
            },
            format="json",
        )

        self.assertEqual(duplicate_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(invalid_role_response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_login_returns_jwt_tokens_and_safe_user_details(self):
        User.objects.create_user(
            email="student@example.edu",
            password=VALID_PASSWORD,
            name="Test Student",
            role=User.Role.STUDENT,
        )

        response = self.client.post(
            reverse("accounts:login"),
            {"email": "STUDENT@example.edu", "password": VALID_PASSWORD},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)
        self.assertEqual(response.data["user"]["email"], "student@example.edu")
        self.assertNotIn("password", response.data["user"])

    def test_login_rejects_invalid_password(self):
        User.objects.create_user(
            email="student@example.edu",
            password=VALID_PASSWORD,
            name="Test Student",
            role=User.Role.STUDENT,
        )

        response = self.client.post(
            reverse("accounts:login"),
            {"email": "student@example.edu", "password": "incorrect-password"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_current_user_requires_jwt_and_returns_safe_details(self):
        user = User.objects.create_user(
            email="student@example.edu",
            password=VALID_PASSWORD,
            name="Test Student",
            role=User.Role.STUDENT,
        )
        login_response = self.client.post(
            reverse("accounts:login"),
            {"email": "student@example.edu", "password": VALID_PASSWORD},
            format="json",
        )
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {login_response.data['access']}"
        )

        response = self.client.get(reverse("accounts:current-user"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], user.id)
        self.assertFalse(response.data["is_staff"])
        self.assertNotIn("password", response.data)

    def test_refresh_rejects_token_for_deleted_user(self):
        user = User.objects.create_user(
            email="deleted-user@example.edu",
            password=VALID_PASSWORD,
            name="Deleted User",
            role=User.Role.STUDENT,
        )
        refresh_token = str(RefreshToken.for_user(user))
        user.delete()

        response = self.client.post(
            reverse("accounts:token-refresh"),
            {"refresh": refresh_token},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
