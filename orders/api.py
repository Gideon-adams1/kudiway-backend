# orders/api.py
from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db import transaction
from decimal import Decimal

from .models import Order, OrderItem, Product
from .serializers import OrderSerializer
from kudiwallet.models import Wallet


class OrderViewSet(viewsets.ModelViewSet):
    queryset = Order.objects.all().order_by("-created_at")
    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Restrict users to their own orders."""
        return Order.objects.filter(user=self.request.user).order_by("-created_at")

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        """
        Create a new order based on cart items from the app.
        Deduct from wallet or add to credit depending on payment method.
        """
        user = request.user
        data = request.data
        items = data.get("items", [])
        payment_method = data.get("payment_method", "wallet")

        if not items:
            return Response({"error": "Cart is empty"}, status=status.HTTP_400_BAD_REQUEST)

        # Compute total
        total = Decimal("0.00")
        for item in items:
            total += Decimal(str(item.get("price", 0))) * int(item.get("qty", 1))

        # Get or create wallet
        try:
            wallet = Wallet.objects.get(user=user)
        except Wallet.DoesNotExist:
            return Response({"error": "Wallet not found"}, status=status.HTTP_404_NOT_FOUND)

        # Handle payment method
        if payment_method == "wallet":
            if wallet.balance < total:
                return Response(
                    {"error": "Insufficient balance in wallet"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            wallet.balance -= total
            wallet.save()
            status_value = Order.Status.PAID

        elif payment_method == "credit":
            wallet.credit_balance += total
            wallet.save()
            status_value = Order.Status.PENDING  # Credit orders are pending until repaid
        else:
            return Response({"error": "Invalid payment method"}, status=status.HTTP_400_BAD_REQUEST)

        # Create Order
        order = Order.objects.create(
            user=user,
            subtotal_amount=total,
            total_amount=total,
            payment_method=payment_method,
            status=status_value,
        )

        # Add Order Items
        for item in items:
            product_name = item.get("name")
            price = Decimal(str(item.get("price", 0)))
            qty = int(item.get("qty", 1))
            image = item.get("image", "")

            OrderItem.objects.create(
                order=order,
                price=price,
                quantity=qty,
                product_name_snapshot=product_name,
                product_image_snapshot=image,
            )

        serializer = OrderSerializer(order)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
