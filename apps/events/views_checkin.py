from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.db import transaction

from apps.accounts.models import UserProfile
from .models import Ticket, CheckInLog


class CheckInView(APIView):
    """
    POST /api/checkin/

    Body:
    {
      "token": "<qr_token>",
      "checker_telegram_id": 123  # кто сканирует (организатор/волонтёр)
    }
    """

    @transaction.atomic
    def post(self, request):
        token = request.data.get("token")
        if not token:
            return Response({"detail": "token is required"}, status=400)

        try:
            ticket = Ticket.objects.select_related(
                "registration__user", "registration__event", "seat", "seat__group"
            ).get(token=token)
        except Ticket.DoesNotExist:
            return Response({"detail": "Ticket not found"}, status=404)

        if ticket.is_used:
            return Response(
                {
                    "detail": "Ticket already used",
                    "used_at": ticket.used_at,
                },
                status=400,
            )

        checker = None
        checker_tid = request.data.get("checker_telegram_id")
        if checker_tid:
            checker = UserProfile.objects.filter(telegram_id=checker_tid).first()

        ticket.mark_used()
        CheckInLog.objects.create(ticket=ticket, checked_by=checker)

        reg = ticket.registration
        user = reg.user
        seat = ticket.seat

        return Response(
            {
                "status": "ok",
                "event": reg.event.title,
                "user": user.full_name,
                "university": user.university.name if user.university else None,
                "table": seat.group.name if seat and seat.group else None,
                "seat_number": seat.seat_number if seat else None,
                "used_at": ticket.used_at,
            }
        )
