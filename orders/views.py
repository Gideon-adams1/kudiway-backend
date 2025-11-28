from decimal import Decimal, InvalidOperation
from datetime import timedelta
import traceback
import uuid

from django.conf import settings
from django.contrib.auth.models import User
from django.http import HttpResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import (
    AllowAny,
    IsAdminUser,
    IsAuthenticated,
)
from rest_framework.response import Response

from kudiwallet.models import Wallet, Transaction
from users.models import KudiPoints
from .models import Order, OrderItem, Product, PartnerListing
from .serializers import ProductSerializer, PartnerListingSerializer


# ============================================================
# 💵 TRANSACTION LOGGER
# ============================================================
def log_transaction(user, transaction_type, amount, description=""):
    """Safely create a transaction record."""
    try:
        Transaction.objects.create(
            user=user,
            transaction_type=transaction_type,
            amount=Decimal(amount),
            description=description,
        )
        print(f"✅ Transaction logged: {transaction_type} ₵{amount} ({user.username})")
    except Exception as e:
        print("⚠️ Transaction log failed:", e)


# ============================================================
# 🏬 STORE PRODUCTS
# ============================================================
@api_view(["GET"])
@permission_classes([AllowAny])
def list_products(request):
    """List store products."""
    try:
        products = Product.objects.all().order_by("-created_at")
        serializer = ProductSerializer(products, many=True, context={"request": request})
        print(f"✅ Loaded {len(products)} products.")
        return Response(serializer.data, status=200)
    except Exception as e:
        print("❌ ERROR listing products:", e)
        print(traceback.format_exc())
        return Response({"error": "Failed to load store products."}, status=500)


# ============================================================
# 📦 SINGLE PRODUCT
# ============================================================
@api_view(["GET"])
@permission_classes([AllowAny])
def get_product(request, pk):
    """Retrieve a single product or partner listing."""
    try:
        product = Product.objects.get(pk=pk)
        serializer = ProductSerializer(product, context={"request": request})
        return Response(serializer.data, status=200)
    except Product.DoesNotExist:
        try:
            listing = PartnerListing.objects.get(pk=pk)
            serializer = PartnerListingSerializer(listing, context={"request": request})
            return Response(serializer.data, status=200)
        except PartnerListing.DoesNotExist:
            return Response({"error": "Product not found."}, status=404)
    except Exception as e:
        print("❌ ERROR get_product:", e)
        print(traceback.format_exc())
        return Response({"error": "Failed to fetch product."}, status=500)


# ============================================================
# 🧾 CREATE ORDER (Wallet + BNPL)
# ============================================================
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def create_order(request):
    user = request.user
    print(f"🧾 Creating order for {user.username}")

    wallet, _ = Wallet.objects.get_or_create(user=user)
    points_wallet, _ = KudiPoints.objects.get_or_create(user=user)

    data = request.data
    items = data.get("items", [])
    payment_method = data.get("payment_method", "wallet")

    if not items:
        return Response({"error": "No items provided."}, status=400)

    try:
        total_amount = sum(
            Decimal(str(i.get("price", 0))) * int(i.get("qty", 1))
            for i in items
        )
    except Exception:
        return Response({"error": "Invalid item price or quantity."}, status=400)

    usable_points_cedis = min(points_wallet.balance / Decimal("10"), total_amount)
    points_to_deduct = usable_points_cedis * Decimal("10")

    # WALLET PAYMENT
    if payment_method == "wallet":
        total_after_points = total_amount - usable_points_cedis

        if wallet.balance < total_after_points:
            return Response({"error": "Insufficient wallet balance."}, status=400)

        # Deduct points
        if points_to_deduct > 0:
            try:
                points_wallet.redeem_points(points_to_deduct)
            except Exception:
                pass

        wallet.balance -= total_after_points
        wallet.save()

        log_transaction(user, "wallet_purchase", total_after_points, "Purchase via wallet")
        if usable_points_cedis > 0:
            log_transaction(user, "points_used", usable_points_cedis, f"Used {points_to_deduct} pts")

        order = Order.objects.create(
            user=user,
            subtotal_amount=total_amount,
            total_amount=total_amount,
            payment_method="wallet",
            status="paid",
            note=f"₵{usable_points_cedis:.2f} from points, ₵{total_after_points:.2f} from wallet.",
        )

    # CREDIT (BNPL)
    elif payment_method == "credit":
        down_payment = total_amount * Decimal("0.30")
        remaining = total_amount - down_payment
        interest = remaining * Decimal("0.05")
        total_credit = remaining + interest

        if wallet.balance < down_payment:
            return Response({"error": "Insufficient wallet balance for downpayment."}, status=400)

        if wallet.credit_balance + total_credit > wallet.credit_limit:
            return Response({"error": "Credit limit exceeded."}, status=400)

        wallet.balance -= down_payment
        wallet.credit_balance += total_credit
        wallet.save()

        log_transaction(user, "credit_downpayment", down_payment, "BNPL downpayment")
        log_transaction(user, "credit_purchase", total_credit, "BNPL total")

        order = Order.objects.create(
            user=user,
            subtotal_amount=total_amount,
            total_amount=total_amount,
            payment_method="credit",
            status="pending",
            note=f"30% down ₵{down_payment:.2f}, 5% interest applied.",
        )

    else:
        return Response({"error": "Invalid payment method."}, status=400)

    # CREATE ORDER ITEMS
    for item in items:
        name = item.get("name", "Unnamed Product")
        price = Decimal(str(item.get("price", 0)))
        qty = int(item.get("qty", 1))
        image = item.get("image", "") or ""
        partner_id = item.get("partner_id")

        raw_product_id = (
            item.get("product_id")
            or item.get("productId")
            or item.get("product")
        )

        product_obj = None
        if raw_product_id:
            try:
                product_obj = Product.objects.get(id=raw_product_id)
            except Product.DoesNotExist:
                product_obj = None

        order_item = OrderItem.objects.create(
            order=order,
            product=product_obj,
            price=price,
            quantity=qty,
            product_name_snapshot=name,
            product_image_snapshot=image,
        )

        if partner_id:
            try:
                partner_user = User.objects.get(id=partner_id)
                order_item.partner = partner_user
                order_item.save(update_fields=["partner"])
            except Exception:
                pass

    return Response({"message": "Order created"}, status=201)


# ============================================================
# 📜 USER ORDERS — SAFE VERSION
# ============================================================
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def list_orders(request):
    user = request.user

    try:
        orders = (
            Order.objects.filter(user=user)
            .prefetch_related("items", "items__product")
            .order_by("-created_at")
        )

        result = []

        for order in orders:
            items_list = []

            for item in order.items.all():

                pid = (
                    item.review_product_id
                    or (item.product.id if item.product else None)
                )

                safe_name = (
                    item.product_name_snapshot
                    or (item.product.name if item.product else "Unknown Product")
                )

                raw_img = item.product_image_snapshot
                if not raw_img and item.product and hasattr(item.product.image, "url"):
                    try:
                        raw_img = item.product.image.url
                    except:
                        raw_img = None

                safe_image = raw_img or "https://via.placeholder.com/200x200.png"

                items_list.append(
                    {
                        "id": item.id,
                        "product_id": pid,
                        "review_product_id": pid,
                        "product_name": safe_name,
                        "image": safe_image,
                        "quantity": item.quantity,
                        "price": str(item.price),
                    }
                )

            result.append(
                {
                    "id": order.id,
                    "status": order.status,
                    "payment_method": order.payment_method,
                    "total_amount": str(order.total_amount),
                    "created_at": order.created_at,
                    "items": items_list,
                }
            )

        return Response(result, status=200)

    except Exception as e:
        print("❌ list_orders error:", e)
        print(traceback.format_exc())
        return Response(
            {"error": "Failed to load your orders."},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


# ============================================================
# ⭐ MISSING FUNCTION — ADDED BACK
# 🤝 CREATE PARTNER LISTING
# ============================================================
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def create_partner_listing(request):
    """
    Allow verified partners to create or update a resale listing.
    """
    try:
        user = request.user
        profile = getattr(user, "profile", None)
        if not profile or not getattr(profile, "is_verified_partner", False):
            return Response(
                {"error": "Only verified partners can create listings."},
                status=403,
            )

        product_id = request.data.get("product_id")
        markup_raw = request.data.get("markup", "0.00")

        if not product_id:
            return Response({"error": "product_id is required."}, status=400)

        try:
            markup = Decimal(str(markup_raw))
            if markup < 0:
                return Response({"error": "Markup cannot be negative."}, status=400)
        except (InvalidOperation, TypeError):
            return Response({"error": "Invalid markup value."}, status=400)

        try:
            product = Product.objects.get(id=product_id)
        except Product.DoesNotExist:
            return Response({"error": "Product not found."}, status=404)

        listing, created = PartnerListing.objects.get_or_create(
            partner=user,
            product=product,
            defaults={
                "markup": markup,
                "final_price": product.price + markup,
            },
        )

        if not created:
            listing.markup = markup
            listing.final_price = product.price + markup

        if not listing.referral_code:
            listing.referral_code = uuid.uuid4().hex[:8]

        listing.referral_url = f"https://kudiway.com/r/{listing.referral_code}"
        listing.save()

        serializer = PartnerListingSerializer(listing, context={"request": request})
        return Response(
            {
                "message": "Listing created successfully!",
                "listing": serializer.data,
            },
            status=201,
        )

    except Exception as e:
        print("❌ create_partner_listing error:", e)
        print(traceback.format_exc())
        return Response({"error": "Failed to create partner listing."}, status=500)


# ============================================================
# 🎥 PURCHASED ITEMS → for UploadReviewScreen
# ============================================================
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def purchased_items(request):
    user = request.user

    items = (
        OrderItem.objects.filter(order__user=user)
        .select_related("product", "order")
        .order_by("-id")
    )

    results = []

    for item in items:

        pid = item.review_product_id or (
            item.product.id if item.product else None
        )

        safe_name = item.product_name_snapshot or (
            item.product.name if item.product else "Unknown Product"
        )

        # ⭐ BEST IMAGE LOGIC
        image_url = None

        if item.product_image_snapshot:
            image_url = item.product_image_snapshot

        elif item.product and hasattr(item.product.image, "url"):
            try:
                image_url = item.product.image.url
            except:
                image_url = None

        if not image_url:
            image_url = "https://via.placeholder.com/200x200.png?text=No+Image"

        results.append(
            {
                "id": item.id,
                "order_id": item.order_id,
                "product_id": item.product.id if item.product else None,
                "review_product_id": pid,
                "product_name": safe_name,
                "image": image_url,
                "quantity": item.quantity,
                "price": str(item.price),
            }
        )

    return Response(results, status=200)
