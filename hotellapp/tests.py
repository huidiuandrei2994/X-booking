from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase

from .models import Room, Client, Reservation, Invoice
from .presenters import ReservationPresenter


class ReservationValidationTests(TestCase):
    def setUp(self):
        self.room = Room.objects.create(number="101", type=Room.Type.DOUBLE, price_per_night=Decimal("100.00"))
        self.client = Client.objects.create(first_name="Ana", last_name="Pop")

    def test_overlap_validation(self):
        start = date.today() + timedelta(days=1)
        end = start + timedelta(days=3)
        Reservation.objects.create(client=self.client, room=self.room, check_in=start, check_out=end)
        # Overlaps
        r2 = Reservation(client=self.client, room=self.room, check_in=start + timedelta(days=1), check_out=end + timedelta(days=1))
        with self.assertRaises(ValidationError):
            r2.full_clean()

    def test_nights_and_invoice_total_auto_created(self):
        start = date.today() + timedelta(days=1)
        end = start + timedelta(days=4)  # 3 nights
        res = Reservation.objects.create(client=self.client, room=self.room, check_in=start, check_out=end)
        self.assertEqual(res.nights, 3)
        # Invoice should be auto-created by signal
        inv = res.invoice
        self.assertIsNotNone(inv)
        self.assertEqual(inv.total, Decimal("300.00"))


class PresenterWorkflowTests(TestCase):
    def setUp(self):
        self.room = Room.objects.create(number="102", type=Room.Type.SINGLE, price_per_night=Decimal("50.00"))
        self.client = Client.objects.create(first_name="Ion", last_name="Ionescu")
        start = date.today() + timedelta(days=1)
        end = start + timedelta(days=2)
        self.res = Reservation.objects.create(client=self.client, room=self.room, check_in=start, check_out=end)

    def test_check_in_out_updates_room_status(self):
        presenter = ReservationPresenter()
        class DummyReq: pass
        req = DummyReq()
        setattr(req, "_messages", None)

        presenter.check_in(req, self.res)
        self.res.refresh_from_db()
        self.room.refresh_from_db()
        self.assertEqual(self.res.status, Reservation.Status.CHECKED_IN)
        self.assertEqual(self.room.status, Room.Status.OCCUPIED)

        presenter.check_out(req, self.res)
        self.res.refresh_from_db()
        self.room.refresh_from_db()
        self.assertEqual(self.res.status, Reservation.Status.CHECKED_OUT)
        self.assertEqual(self.room.status, Room.Status.CLEANING)

    def test_direct_status_change_syncs_room_via_signals(self):
        # Change status directly (simulating admin edit)
        self.res.status = Reservation.Status.CHECKED_IN
        self.res.save(update_fields=["status"])
        self.room.refresh_from_db()
        self.assertEqual(self.room.status, Room.Status.OCCUPIED)

        self.res.status = Reservation.Status.CANCELED
        self.res.save(update_fields=["status"])
        self.room.refresh_from_db()
        # No checked-in reservations remain, room becomes available
        self.assertEqual(self.room.status, Room.Status.AVAILABLE)
