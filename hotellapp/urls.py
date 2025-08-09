from __future__ import annotations

from django.urls import path

from .views import (
    RoomListView, RoomCreateView, RoomUpdateView,
    ClientListView, ClientCreateView, ClientUpdateView,
    ReservationListView, ReservationCreateView, ReservationUpdateView,
    ReservationCheckInView, ReservationCheckOutView, RoomMarkCleanedView,
    InvoiceListView, InvoiceDetailView,
)

urlpatterns = [
    # Rooms
    path("rooms/", RoomListView.as_view(), name="room_list"),
    path("rooms/add/", RoomCreateView.as_view(), name="room_add"),
    path("rooms/<int:pk>/edit/", RoomUpdateView.as_view(), name="room_edit"),
    path("rooms/<int:pk>/cleaned/", RoomMarkCleanedView.as_view(), name="room_mark_cleaned"),

    # Clients
    path("clients/", ClientListView.as_view(), name="client_list"),
    path("clients/add/", ClientCreateView.as_view(), name="client_add"),
    path("clients/<int:pk>/edit/", ClientUpdateView.as_view(), name="client_edit"),

    # Reservations
    path("reservations/", ReservationListView.as_view(), name="reservation_list"),
    path("reservations/add/", ReservationCreateView.as_view(), name="reservation_add"),
    path("reservations/<int:pk>/edit/", ReservationUpdateView.as_view(), name="reservation_edit"),
    path("reservations/<int:pk>/check-in/", ReservationCheckInView.as_view(), name="reservation_check_in"),
    path("reservations/<int:pk>/check-out/", ReservationCheckOutView.as_view(), name="reservation_check_out"),

    # Invoices
    path("invoices/", InvoiceListView.as_view(), name="invoice_list"),
    path("invoices/<int:pk>/", InvoiceDetailView.as_view(), name="invoice_detail"),
]
