from django.db import transaction
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from apps.accounts.models import UserProfile
from .models import Event, Registration, RegistrationStatus, PaymentStatus, Seat, SeatStatus, SeatGroup
from .serializers import RegistrationSerializer, TicketSerializer, SeatSerializer
from .models import Ticket


class EventRegisterView(APIView):
    """
    POST /api/events/<slug>/register/

    Body:
    {
      "telegram_id": 123,
      "telegram_username": "user",
      "full_name": "Имя Фамилия",
      "phone": "+998...",
      "promo_code": "ABC",
      "seat_id": 101   # опционально: конкретное место
    }
    """

    @transaction.atomic
    def post(self, request, slug: str):
        try:
            event = Event.objects.get(slug=slug, is_active=True)
        except Event.DoesNotExist:
            return Response({"detail": "Event not found"}, status=404)

        data = request.data
        telegram_id = data.get("telegram_id")
        full_name = data.get("full_name")

        if not telegram_id or not full_name:
            return Response({"detail": "telegram_id and full_name are required"}, status=400)

        user, _ = UserProfile.objects.get_or_create(
            telegram_id=telegram_id,
            defaults={
                "telegram_username": data.get("telegram_username", ""),
                "full_name": full_name,
                "phone": data.get("phone", ""),
            },
        )

        registration, created = Registration.objects.get_or_create(
            event=event,
            user=user,
            defaults={
                "promo_code": data.get("promo_code", ""),
                "final_price": event.base_price or 0,
                "payment_status": PaymentStatus.NONE if not event.is_paid else PaymentStatus.PENDING,
                "status": RegistrationStatus.PENDING if event.is_paid else RegistrationStatus.CONFIRMED,
            },
        )

        seat_id = data.get("seat_id")
        ticket = None

        # если передано конкретное место — резервируем его и создаём билет (пока без реальной оплаты)
        if seat_id:
            try:
                seat = Seat.objects.select_for_update().get(id=seat_id, event=event)
            except Seat.DoesNotExist:
                return Response({"detail": "Seat not found"}, status=404)

            if seat.status != SeatStatus.FREE:
                return Response({"detail": "Seat is not available"}, status=400)

            seat.status = SeatStatus.SOLD if not event.is_paid else SeatStatus.RESERVED
            seat.reserved_by = user
            seat.save(update_fields=["status", "reserved_by"])

            # создаём/обновляем билет
            ticket, _ = Ticket.objects.get_or_create(
                registration=registration,
                defaults={"seat": seat},
            )
            if ticket.seat_id != seat.id:
                ticket.seat = seat
                ticket.save(update_fields=["seat"])

        # для бесплатных без мест всё равно нужен билет
        if not event.is_paid and seat_id is None and created:
            ticket = Ticket.objects.create(registration=registration)

        payload = RegistrationSerializer(registration).data
        if ticket:
            payload["ticket"] = TicketSerializer(ticket).data

        return Response(payload, status=201 if created else 200)


class SeatListByGroupView(APIView):
    """
    GET /api/seat-groups/<group_id>/seats/
    """

    def get(self, request, group_id: int):
        seats = Seat.objects.filter(group_id=group_id).order_by("seat_number")
        return Response(SeatSerializer(seats, many=True).data)


class MyRegistrationsView(APIView):
    """
    GET /api/my/registrations/?telegram_id=...
    """

    def get(self, request):
        telegram_id = request.query_params.get("telegram_id")
        if not telegram_id:
            return Response({"detail": "telegram_id is required"}, status=400)

        regs = Registration.objects.filter(user__telegram_id=telegram_id).select_related("event")
        return Response(RegistrationSerializer(regs, many=True).data)


class MyTicketsView(APIView):
    """
    GET /api/my/tickets/?telegram_id=...
    """

    def get(self, request):
        telegram_id = request.query_params.get("telegram_id")
        if not telegram_id:
            return Response({"detail": "telegram_id is required"}, status=400)

        tickets = Ticket.objects.filter(registration__user__telegram_id=telegram_id)\
            .select_related("registration__event", "seat", "seat__group")
        return Response(TicketSerializer(tickets, many=True).data)
