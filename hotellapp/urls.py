from __future__ import annotations

from django.urls import path

from .views import (
    CalendarView,
    RoomListView, RoomCreateView, RoomUpdateView, RoomDeleteView,
    ClientListView, ClientCreateView, ClientUpdateView, ClientDeleteView,
    ReservationListView, ReservationCreateView, ReservationUpdateView, ReservationDeleteView,
    ReservationCheckInView, ReservationCheckOutView, ReservationCancelView, RoomMarkCleanedView,
    InvoiceListView, InvoiceDetailView, InvoicePrintView, InvoicesCsvExportView,
        NightAuditPreviewView, NightAuditCloseView, NightAuditListView, NightAuditDetailView, NightAuditCsvExportView,
    ReportsDashboardView, ReportOccupancyView, ReportRevenueView, ReportHousekeepingView,
    AvailabilityAPI, ClientQuickCreateAPI,
)

urlpatterns = [
    # Home / Calendar
    path("", CalendarView.as_view(), name="calendar"),
    path("calendar/", CalendarView.as_view(), name="calendar"),

    # Rooms
    path("rooms/", RoomListView.as_view(), name="room_list"),
    path("rooms/add/", RoomCreateView.as_view(), name="room_add"),
    path("rooms/<int:pk>/edit/", RoomUpdateView.as_view(), name="room_edit"),
    path("rooms/<int:pk>/delete/", RoomDeleteView.as_view(), name="room_delete"),
    path("rooms/<int:pk>/cleaned/", RoomMarkCleanedView.as_view(), name="room_mark_cleaned"),

    # Clients
    path("clients/", ClientListView.as_view(), name="client_list"),
    path("clients/add/", ClientCreateView.as_view(), name="client_add"),
    path("clients/<int:pk>/edit/", ClientUpdateView.as_view(), name="client_edit"),
    path("clients/<int:pk>/delete/", ClientDeleteView.as_view(), name="client_delete"),

    # Reservations
    path("reservations/", ReservationListView.as_view(), name="reservation_list"),
    path("reservations/add/", ReservationCreateView.as_view(), name="reservation_add"),
    path("reservations/<int:pk>/edit/", ReservationUpdateView.as_view(), name="reservation_edit"),
    path("reservations/<int:pk>/delete/", ReservationDeleteView.as_view(), name="reservation_delete"),
    path("reservations/<int:pk>/check-in/", ReservationCheckInView.as_view(), name="reservation_check_in"),
    path("reservations/<int:pk>/check-out/", ReservationCheckOutView.as_view(), name="reservation_check_out"),
    path("reservations/<int:pk>/cancel/", ReservationCancelView.as_view(), name="reservation_cancel"),

    # Invoices
    path("invoices/", InvoiceListView.as_view(), name="invoice_list"),
    path("invoices/<int:pk>/", InvoiceDetailView.as_view(), name="invoice_detail"),
    path("invoices/<int:pk>/print/", InvoicePrintView.as_view(), name="invoice_print"),
    path("invoices/export/csv/", InvoicesCsvExportView.as_view(), name="invoices_export_csv"),

        # Night Audit
        path("audit/", NightAuditPreviewView.as_view(), name="night_audit"),
        path("audit/close/", NightAuditCloseView.as_view(), name="night_audit_close"),
        path("audit/history/", NightAuditListView.as_view(), name="night_audit_list"),
        path("audit/<int:pk>/", NightAuditDetailView.as_view(), name="night_audit_detail"),
        path("audit/export/csv/", NightAuditCsvExportView.as_view(), name="night_audit_export_csv"),

    # Reports
    path("reports/", ReportsDashboardView.as_view(), name="reports_dashboard"),
    path("reports/occupancy/", ReportOccupancyView.as_view(), name="report_occupancy"),
    path("reports/revenue/", ReportRevenueView.as_view(), name="report_revenue"),
    path("reports/housekeeping/", ReportHousekeepingView.as_view(), name="report_housekeeping"),

    # API
    path("api/clients/quick-add/", ClientQuickCreateAPI.as_view(), name="api_client_quick_add"),
    path("api/availability/", AvailabilityAPI.as_view(), name="api_availability"),
]
