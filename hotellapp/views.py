from __future__ import annotations

from django.contrib import messages
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView, DetailView, View

from .forms import RoomForm, ClientForm, ReservationForm
from .models import Room, Client, Reservation, Invoice
from .presenters import ReservationPresenter


# Rooms
class RoomListView(ListView):
    model = Room
    template_name = "hotellapp/room_list.html"
    context_object_name = "rooms"


class RoomCreateView(CreateView):
    model = Room
    form_class = RoomForm
    template_name = "hotellapp/room_form.html"
    success_url = reverse_lazy("room_list")


class RoomUpdateView(UpdateView):
    model = Room
    form_class = RoomForm
    template_name = "hotellapp/room_form.html"
    success_url = reverse_lazy("room_list")


# Clients
class ClientListView(ListView):
    model = Client
    template_name = "hotellapp/client_list.html"
    context_object_name = "clients"


class ClientCreateView(CreateView):
    model = Client
    form_class = ClientForm
    template_name = "hotellapp/client_form.html"
    success_url = reverse_lazy("client_list")


class ClientUpdateView(UpdateView):
    model = Client
    form_class = ClientForm
    template_name = "hotellapp/client_form.html"
    success_url = reverse_lazy("client_list")


# Reservations
class ReservationListView(ListView):
    model = Reservation
    template_name = "hotellapp/reservation_list.html"
    context_object_name = "reservations"


class ReservationCreateView(CreateView):
    model = Reservation
    form_class = ReservationForm
    template_name = "hotellapp/reservation_form.html"
    success_url = reverse_lazy("reservation_list")

    def form_valid(self, form):
        presenter = ReservationPresenter()
        presenter.create_reservation(self.request, form)
        return HttpResponseRedirect(self.get_success_url())


class ReservationUpdateView(UpdateView):
    model = Reservation
    form_class = ReservationForm
    template_name = "hotellapp/reservation_form.html"
    success_url = reverse_lazy("reservation_list")


# Workflow actions
class ReservationCheckInView(View):
    def post(self, request: HttpRequest, pk: int) -> HttpResponse:
        reservation = get_object_or_404(Reservation, pk=pk)
        ReservationPresenter().check_in(request, reservation)
        return redirect("reservation_list")


class ReservationCheckOutView(View):
    def post(self, request: HttpRequest, pk: int) -> HttpResponse:
        reservation = get_object_or_404(Reservation, pk=pk)
        ReservationPresenter().check_out(request, reservation)
        return redirect("reservation_list")


class RoomMarkCleanedView(View):
    def post(self, request: HttpRequest, pk: int) -> HttpResponse:
        room = get_object_or_404(Room, pk=pk)
        ReservationPresenter().mark_room_cleaned(request, room)
        return redirect("room_list")


# Invoices
class InvoiceListView(ListView):
    model = Invoice
    template_name = "hotellapp/invoice_list.html"
    context_object_name = "invoices"


class InvoiceDetailView(DetailView):
    model = Invoice
    template_name = "hotellapp/invoice_detail.html"
    context_object_name = "invoice"
