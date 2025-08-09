from django.contrib import admin

from .models import Room, Client, Reservation, Invoice


@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = ("number", "type", "price_per_night", "status")
    list_filter = ("type", "status")
    search_fields = ("number",)
    actions = ["mark_as_available"]

    def mark_as_available(self, request, queryset):
        queryset.update(status=Room.Status.AVAILABLE)
    mark_as_available.short_description = "Mark selected rooms as available"


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ("first_name", "last_name", "email", "phone")
    search_fields = ("first_name", "last_name", "email")


@admin.register(Reservation)
class ReservationAdmin(admin.ModelAdmin):
    list_display = ("id", "client", "room", "check_in", "check_out", "status", "created_at")
    list_filter = ("status", "room__type")
    search_fields = ("client__first_name", "client__last_name", "room__number")


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ("id", "client", "reservation", "issue_date", "total", "currency")
    list_filter = ("currency", "issue_date")
    search_fields = ("client__first_name", "client__last_name")
