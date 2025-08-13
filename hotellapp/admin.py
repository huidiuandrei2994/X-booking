from django.contrib import admin

from .models import Room, Client, Reservation, Invoice, InvoiceLine, NightAudit, RateSeason


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
    list_display = ("id", "client", "room", "check_in", "check_out", "status", "breakfast_included", "breakfast_price", "created_at")
    list_filter = ("status", "room__type", "breakfast_included")
    list_editable = ("breakfast_included", "breakfast_price")
    search_fields = ("client__first_name", "client__last_name", "room__number")
    actions = ("add_breakfast", "remove_breakfast")

    def add_breakfast(self, request, queryset):
        queryset.update(breakfast_included=True)
    add_breakfast.short_description = "Mark breakfast included"

    def remove_breakfast(self, request, queryset):
        queryset.update(breakfast_included=False, breakfast_price=0)
    remove_breakfast.short_description = "Remove breakfast"


class InvoiceLineInline(admin.TabularInline):
    model = InvoiceLine
    extra = 0
    fields = ("description", "quantity", "unit_price", "vat_rate", "total_excl_vat", "vat_amount", "total")
    readonly_fields = ("total_excl_vat", "vat_amount", "total")


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ("get_number", "client", "reservation", "issue_date", "due_date", "payment_method", "total", "currency", "locked")
    list_filter = ("currency", "issue_date", "payment_method", "locked")
    search_fields = ("client__first_name", "client__last_name", "series", "number", "billing_name", "billing_tax_id")
    inlines = [InvoiceLineInline]
    readonly_fields = ()

    def get_number(self, obj):
        return f"{obj.series}-{obj.number or '—'}"
    get_number.short_description = "Invoice No."


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


@admin.register(InvoiceLine)
class InvoiceLineAdmin(admin.ModelAdmin):
    list_display = ("invoice", "description", "quantity", "unit_price", "vat_rate", "total")
    list_filter = ("vat_rate",)
    search_fields = ("description", "invoice__series", "invoice__number")


@admin.register(RateSeason)
class RateSeasonAdmin(admin.ModelAdmin):
    list_display = ("name", "room", "room_type", "start_date", "end_date", "price", "active")
    list_filter = ("active", "room_type", "start_date", "end_date")
    search_fields = ("name",)
    autocomplete_fields = ("room",)
