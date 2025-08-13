from __future__ import annotations

from django.db.models.signals import post_save, pre_save, post_delete
from django.dispatch import receiver

from .models import Reservation, Invoice, Room


@receiver(pre_save, sender=Reservation)
def _reservation_track_old_status(sender, instance: Reservation, **kwargs):
    """
    Store old status on the instance so we can compare in post_save.
    """
    if instance.pk:
        try:
            old = Reservation.objects.get(pk=instance.pk)
            instance._old_status = old.status  # type: ignore[attr-defined]
        except Reservation.DoesNotExist:
            instance._old_status = None  # type: ignore[attr-defined]
    else:
        instance._old_status = None  # type: ignore[attr-defined]


@receiver(post_save, sender=Reservation)
def _reservation_post_save(sender, instance: Reservation, created: bool, **kwargs):
    """
    - Auto-create Invoice when a Reservation is created (if not present).
    - Sync Room status when status changes.
    """
    # Ensure invoice exists
    if created:
        if not hasattr(instance, "invoice"):
            Invoice.objects.create(reservation=instance, client=instance.client)

    # Sync room status if status changed
    old_status = getattr(instance, "_old_status", None)
    if old_status != instance.status:
        room = instance.room
        if instance.status == Reservation.Status.CHECKED_IN:
            if room.status != Room.Status.OCCUPIED:
                room.status = Room.Status.OCCUPIED
                room.save(update_fields=["status"])
        elif instance.status == Reservation.Status.CHECKED_OUT:
            if room.status != Room.Status.CLEANING:
                room.status = Room.Status.CLEANING
                room.save(update_fields=["status"])
        elif instance.status == Reservation.Status.CANCELED:
            # Set available only if no other active checked-in for this room
            has_checked_in = Reservation.objects.filter(
                room=room, status=Reservation.Status.CHECKED_IN
            ).exists()
            if not has_checked_in and room.status != Room.Status.AVAILABLE:
                room.status = Room.Status.AVAILABLE
                room.save(update_fields=["status"])


@receiver(post_delete, sender=Reservation)
def _reservation_post_delete(sender, instance: Reservation, **kwargs):
    """
    If there are no checked-in reservations for the room, and room is not cleaning,
    mark it as available. This covers deletions performed outside the presenter.
    """
    room = instance.room
    has_checked_in = Reservation.objects.filter(room=room, status=Reservation.Status.CHECKED_IN).exists()
    if not has_checked_in and room.status not in (Room.Status.CLEANING, Room.Status.AVAILABLE):
        room.status = Room.Status.AVAILABLE
        room.save(update_fields=["status"])


# When a client is modified, refresh billing snapshot on all unlocked invoices for that client
from django.db.models.signals import post_save as _post_save  # avoid shadowing above imports
from .models import Client, Invoice  # re-import safe in Django apps


@receiver(_post_save, sender=Client)
def _client_sync_invoices(sender, instance: Client, **kwargs):
    invoices = Invoice.objects.filter(client=instance, locked=False)
    for inv in invoices:
        inv.fill_billing_from_client(instance)
        inv.save(update_fields=["billing_name", "billing_tax_id", "billing_address"])
