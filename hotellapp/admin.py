from django.contrib import admin

from .models import Room, Client, Reservation, Invoice, NightAudit


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


@admin.register(NightAudit)
class NightAuditAdmin(admin.ModelAdmin):
    list_display = ("date", "closed_at", "get_occupancy", "get_revenue")
    date_hierarchy = "date"
    ordering = ("-date",)

    def get_occupancy(self, obj):
        t = obj.totals or {}
        return f"{t.get('occupancy_percent', 0)}%"
    get_occupancy.short_description = "Occupancy"

    def get_revenue(self, obj):
        t = obj.totals or {}
        return t.get("revenue", "0.00")
    get_revenue.short_description = "Revenue"
