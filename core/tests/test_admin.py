from django.contrib import admin
from django.contrib.auth.models import AnonymousUser
from django.contrib.auth.models import Permission
from django.contrib.auth.models import User
from django.http import HttpRequest
from django.test import RequestFactory
from django.test import TestCase

from core.admin import DetectorAdmin
from core.models import Detector


class DetectorAdminPermissionTest(TestCase):
    def setUp(self) -> None:
        self.factory = RequestFactory()
        self.admin = DetectorAdmin(Detector, admin.site)

        self.owner = User.objects.create_user(username="owner", password="Pass1234!")
        self.other_staff = User.objects.create_user(username="staff", password="Pass1234!", is_staff=True)
        self.superuser = User.objects.create_superuser(
            username="root",
            password="Pass1234!",
            email="root@example.com",
        )

        permissions = Permission.objects.filter(
            codename__in=["view_detector", "add_detector", "change_detector", "delete_detector"]
        )
        self.other_staff.user_permissions.set(permissions)

        self.owned_detector = Detector.objects.create(
            mac_address="AA:BB:CC:DD:EE:FF",
            name="Owned",
            owner=self.other_staff,
            description="",
        )
        self.foreign_detector = Detector.objects.create(
            mac_address="11:22:33:44:55:66",
            name="Foreign",
            owner=self.owner,
            description="",
        )

    def _request(self, user: User) -> HttpRequest:
        request = self.factory.get("/admin/core/detector/")
        request.user = user
        return request

    def _anonymous_request(self) -> HttpRequest:
        request = self.factory.get("/admin/core/detector/")
        request.user = AnonymousUser()
        return request

    def test_staff_queryset_only_contains_owned_detectors(self) -> None:
        request = self._request(self.other_staff)

        queryset = self.admin.get_queryset(request)

        self.assertQuerySetEqual(queryset.order_by("id"), [self.owned_detector], transform=lambda obj: obj)

    def test_superuser_queryset_contains_all_detectors(self) -> None:
        request = self._request(self.superuser)

        queryset = self.admin.get_queryset(request)

        self.assertQuerySetEqual(
            queryset.order_by("id"),
            [self.owned_detector, self.foreign_detector],
            transform=lambda obj: obj,
        )

    def test_anonymous_queryset_is_empty(self) -> None:
        request = self._anonymous_request()

        queryset = self.admin.get_queryset(request)

        self.assertFalse(queryset.exists())

    def test_staff_cannot_view_change_or_delete_foreign_detector(self) -> None:
        request = self._request(self.other_staff)

        self.assertFalse(self.admin.has_view_permission(request, self.foreign_detector))
        self.assertFalse(self.admin.has_change_permission(request, self.foreign_detector))
        self.assertFalse(self.admin.has_delete_permission(request, self.foreign_detector))

    def test_staff_can_manage_owned_detector(self) -> None:
        request = self._request(self.other_staff)

        self.assertTrue(self.admin.has_view_permission(request, self.owned_detector))
        self.assertTrue(self.admin.has_change_permission(request, self.owned_detector))
        self.assertTrue(self.admin.has_delete_permission(request, self.owned_detector))

    def test_staff_cannot_choose_owner_field_and_save_forces_current_user(self) -> None:
        request = self._request(self.other_staff)
        detector = Detector(
            mac_address="22:33:44:55:66:77",
            name="CreatedByStaff",
            owner=self.owner,
            description="",
        )

        exclude = self.admin.get_exclude(request)
        self.admin.save_model(request, detector, form=None, change=False)

        self.assertEqual(exclude, ("owner",))
        self.assertEqual(detector.owner, self.other_staff)

    def test_superuser_keeps_owner_field_visible(self) -> None:
        request = self._request(self.superuser)

        exclude = self.admin.get_exclude(request)

        self.assertIsNone(exclude)

    def test_staff_has_list_view_permission_without_object(self) -> None:
        request = self._request(self.other_staff)

        self.assertTrue(self.admin.has_view_permission(request, None))
        self.assertTrue(self.admin.has_change_permission(request, None))
        self.assertTrue(self.admin.has_delete_permission(request, None))

    def test_anonymous_user_has_no_object_permissions(self) -> None:
        request = self._anonymous_request()

        self.assertFalse(self.admin.has_view_permission(request, self.owned_detector))
        self.assertFalse(self.admin.has_change_permission(request, self.owned_detector))
        self.assertFalse(self.admin.has_delete_permission(request, self.owned_detector))
