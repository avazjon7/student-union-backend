# from rest_framework.views import APIView
# from rest_framework.response import Response
# from rest_framework import status
#
# from apps.events.models import Registration
# from .models import Payment, PaymentProvider
# from .serializers import PaymentSerializer
# from .services import mark_payment_paid
#
#
# class CreatePaymentView(APIView):
#     """
#     POST /api/payments/create/
#
#     Body:
#     {
#       "registration_id": 12,
#       "provider": "click" | "payme" | "uzum" | "manual"
#     }
#
#     Пока просто создаёт запись Payment и возвращает её.
#     Позже сюда добавим генерацию ссылки на оплату.
#     """
#
#     def post(self, request):
#         reg_id = request.data.get("registration_id")
#         provider = request.data.get("provider", PaymentProvider.MANUAL)
#
#         if not reg_id:
#             return Response({"detail": "registration_id is required"}, status=400)
#
#         try:
#             reg = Registration.objects.get(id=reg_id)
#         except Registration.DoesNotExist:
#             return Response({"detail": "Registration not found"}, status=404)
#
#         amount = reg.final_price or reg.event.base_price or 0
#
#         payment = Payment.objects.create(
#             registration=reg,
#             provider=provider,
#             amount=amount,
#         )
#
#         return Response(PaymentSerializer(payment).data, status=201)
#
#
# class MockPaymentCallbackView(APIView):
#     """
#     POST /api/payments/mock-success/
#
#     Dev-заглушка: помечаем платёж как оплаченный вручную.
#
#     Body:
#     {
#       "payment_id": 5
#     }
#     """
#
#     def post(self, request):
#         payment_id = request.data.get("payment_id")
#         if not payment_id:
#             return Response({"detail": "payment_id is required"}, status=400)
#
#         try:
#             payment = Payment.objects.select_related("registration").get(id=payment_id)
#         except Payment.DoesNotExist:
#             return Response({"detail": "Payment not found"}, status=404)
#
#         mark_payment_paid(payment)
#
#         return Response(PaymentSerializer(payment).data, status=200)
