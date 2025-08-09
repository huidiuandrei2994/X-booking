from __future__ import annotations

from django.contrib import messages
from django.db import transaction
from django.http import HttpRequest

from .models import Reservation, Room, Invoice


class ReservationPresenter:
    """
    Presenter that orchestrates reservation lifecycle:
    - create reservation (validates, saves, generates invoice)
    - check-in / check-out (updates reservation and room statuses)
    - mark room cleaned (sets available)
    """

    def create_reservation(self, request: HttpRequest, form) -> Reservation:
        if not form.is_valid():
            raise ValueError("Form must be valid before creating reservation.")
        with transaction.atomic():
            reservation: Reservation = form.save(commit=False)
            reservation.status = Reservation.Status.BOOKED
            reservation.save()
            # Create invoice snapshot for the booking immediately
            Invoice.objects.create(reservation=reservation, client=reservation.client)
        messages.success(request, "Reservation created and invoice generated.")
        return reservation

    def check_in(self, request: HttpRequest, reservation: Reservation) -> None:
        if reservation.status in [Reservation.Status.CANCELED, Reservation.Status.CHECKED_OUT]:
            messages.error(request, "Cannot check-in a canceled or checked-out reservation.")
            return
        with transaction.atomic():
            reservation.status = Reservation.Status.CHECKED_IN
            reservation.save(update_fields=["status", "updated_at"])
            room = reservation.room
            room.status = Room.Status.OCCUPIED
            room.save(update_fields=["status"])
        messages.success(request, f"Guest checked-in. Room {reservation.room.number} is now occupied.")

    def check_out(self, request: HttpRequest, reservation: Reservation) -> None:
        if reservation.status != Reservation.Status.CHECKED_IN:
            messages.error(request, "Only checked-in reservations can be checked-out.")
            return
        with transaction.atomic():
            reservation.status = Reservation.Status.CHECKED_OUT
            reservation.save(update_fields=["status", "updated_at"])
            room = reservation.room
            room.status = Room.Status.CLEANING
            room.save(update_fields=["status"])
        messages.success(request, f"Guest checked-out. Room {reservation.room.number} set to cleaning.")

    def mark_room_cleaned(self, request: HttpRequest, room: Room) -> None:
        with transaction.atomic():
            room.status = Room.Status.AVAILABLE
            room.save(update_fields=["status"])
        messages.success(request, f"Room {room.number} marked as available after cleaning.")

    def cancel(self, request: HttpRequest, reservation: Reservation) -> None:
        if reservation.status == Reservation.Status.CANCELED:
            messages.info(request, "Reservation already canceled.")
            return
        with transaction.atomic():
            reservation.status = Reservation.Status.CANCELED
            reservation.save(update_fields=["status", "updated_at"])
            # If not checked-in, ensure room stays available
            if reservation.room.status != Room.Status.OCCUPIED:
                reservation.room.status = Room.Status.AVAILABLE
                reservation.room.save(update_fields=["status"])
        messages.success(request, "Reservation canceled.")
