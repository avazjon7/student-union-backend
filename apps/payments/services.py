# from django.db import transaction
#
# from apps.events.models import PaymentStatus, RegistrationStatus, Ticket, SeatStatus
# from .models import Payment
#
#
# @transaction.atomic
# def mark_payment_paid(payment: Payment):
#     """
#     Универсальная функция: что происходит, когда деньги реально дошли.
#     Вызывается из webhook'а или dev-заглушки.
#     """
#     if payment.status == PaymentStatus.PAID:
#         return payment  # уже обработан
#
#     payment.status = PaymentStatus.PAID
#     payment.save(update_fields=["status"])
#
#     reg = payment.registration
#
#     # обновляем регистрацию
#     reg.payment_status = PaymentStatus.PAID
#     reg.status = RegistrationStatus.CONFIRMED
#     reg.save(update_fields=["payment_status", "status"])
#
#     # если есть уже забронированное место — делаем SOLD
#     seat = getattr(reg.ticket, "seat", None) if hasattr(reg, "ticket") else None
#     if seat and seat.status != SeatStatus.SOLD:
#         seat.status = SeatStatus.SOLD
#         seat.save(update_fields=["status"])
#
#     # если билета ещё нет — создаём
#     if not hasattr(reg, "ticket"):
#         Ticket.objects.create(registration=reg)
#
#     return payment
