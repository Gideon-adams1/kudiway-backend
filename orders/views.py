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

from django.apps import apps
from django.db.models import Count

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
    try:
        Transaction.objects.create(
            user=user,
            transaction_type=transaction_type,
            amount=Decimal(amount),
            description=description,
        )
    except Exception as e:
        print("⚠️ Transaction log failed:", e)


# ============================================================
# ✅ GLOBAL VIDEO REVIEW STATS (NO USER DEPENDENCY)
# Builds: {"12": {"count": 5}, ...} keyed by Product.id as string
# ============================================================
def build_review_stats_for_products(products_qs):
    """
    Uses reviews.VideoReview:
      - product FK if present
      - OR review_product_id (string) fallback

    Only counts: public + approved + not deleted
    """
    try:
        VideoReview = apps.get_model("reviews", "VideoReview")
    except Exception:
        return {}

    product_ids = list(products_qs.values_list("id", flat=True))
    if not product_ids:
        return {}

    # 1) FK-linked reviews
    fk_rows = (
        VideoReview.objects.filter(
            product_id__in=product_ids,
            is_public=True,
            is_approved=True,
            is_deleted=False,
        )
        .values("product_id")
        .annotate(count=Count("id"))
    )

    stats = {}
    for r in fk_rows:
        pid = str(r["product_id"])
        stats[pid] = {"count": int(r["count"] or 0)}

    # 2) review_product_id fallback (string) – only when product FK might be null
    str_ids = [str(x) for x in product_ids]
    rid_rows = (
        VideoReview.objects.filter(
            product__isnull=True,
            review_product_id__in=str_ids,
            is_public=True,
            is_approved=True,
            is_deleted=False,
        )
        .values("review_product_id")
        .annotate(count=Count("id"))
    )

    for r in rid_rows:
        pid = str(r["review_product_id"])
        prev = stats.get(pid, {"count": 0})
        prev["count"] = int(prev.get("count", 0)) + int(r["count"] or 0)
        stats[pid] = prev

    return stats


# ============================================================
# 🏬 STORE PRODUCTS
# ============================================================
@api_view(["GET"])
@permission_classes([AllowAny])
def list_products(request):
    try:
        products = Product.objects.all().order_by("-created_at")

        # ✅ build global review counts once
        review_stats = build_review_stats_for_products(products)

        serializer = ProductSerializer(
            products,
            many=True,
            context={"request": request, "review_stats": review_stats},
        )
        return Response(serializer.data, status=200)
    except Exception as e:
        print("❌ list_products:", e)
        return Response({"error": "Failed to load store products"}, status=500)


# ============================================================
# 📦 SINGLE PRODUCT
# ============================================================
@api_view(["GET"])
@permission_classes([AllowAny])
def get_product(request, pk):
    try:
        product = Product.objects.get(pk=pk)

        review_stats = build_review_stats_for_products(Product.objects.filter(id=product.id))

        serializer = ProductSerializer(
            product,
            context={"request": request, "review_stats": review_stats},
        )
        return Response(serializer.data)
    except Product.DoesNotExist:
        pass

    try:
        listing = PartnerListing.objects.get(pk=pk)

        # include review stats for underlying product (if exists)
        qs = Product.objects.filter(id=listing.product_id) if listing.product_id else Product.objects.none()
        review_stats = build_review_stats_for_products(qs)

        serializer = PartnerListingSerializer(
            listing,
            context={"request": request, "review_stats": review_stats},
        )
        return Response(serializer.data)
    except PartnerListing.DoesNotExist:
        return Response({"error": "Product not found"}, status=404)
    except Exception as e:
        print("❌ get_product:", e)
        return Response({"error": "Failed to fetch product"}, status=500)


# ============================================================
# 🧾 CREATE ORDER
# ============================================================
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def create_order(request):
    user = request.user
    wallet, _ = Wallet.objects.get_or_create(user=user)
    points_wallet, _ = KudiPoints.objects.get_or_create(user=user)

    data = request.data
    items = data.get("items", [])
    payment_method = data.get("payment_method", "wallet")

    if not items:
        return Response({"error": "No items provided"}, status=400)

    try:
        total_amount = sum(
            Decimal(str(i.get("price", 0))) * int(i.get("qty", 1))
            for i in items
        )
    except Exception:
        return Response({"error": "Invalid price or quantity"}, status=400)

    usable_points = min(points_wallet.balance / Decimal("10"), total_amount)
    points_to_deduct = usable_points * Decimal("10")

    if payment_method == "wallet":
        total_after_points = total_amount - usable_points

        if wallet.balance < total_after_points:
            return Response({"error": "Insufficient wallet balance"}, status=400)

        if points_to_deduct > 0:
            try:
                points_wallet.redeem_points(points_to_deduct)
            except:
                pass

        wallet.balance -= total_after_points
        wallet.save()

        order = Order.objects.create(
            user=user,
            subtotal_amount=total_amount,
            total_amount=total_amount,
            payment_method="wallet",
            status="paid",
        )

    elif payment_method == "credit":
        down_payment = total_amount * Decimal("0.30")
        remaining = total_amount - down_payment
        interest = remaining * Decimal("0.05")
        total_credit = remaining + interest

        if wallet.balance < down_payment:
            return Response({"error": "Insufficient wallet balance for downpayment"}, status=400)

        if wallet.credit_balance + total_credit > wallet.credit_limit:
            return Response({"error": "Credit limit exceeded"}, status=400)

        wallet.balance -= down_payment
        wallet.credit_balance += total_credit
        wallet.save()

        order = Order.objects.create(
            user=user,
            subtotal_amount=total_amount,
            total_amount=total_amount,
            payment_method="credit",
            status="pending",
        )

    else:
        return Response({"error": "Invalid payment method"}, status=400)

    for item in items:
        name = item.get("name", "Unnamed Product")
        price = Decimal(str(item.get("price", 0)))
        qty = int(item.get("qty", 1))
        image = item.get("image", "")
        partner_id = item.get("partner_id")

        raw_pid = item.get("product_id") or item.get("productId") or item.get("product")

        product_obj = None
        if raw_pid:
            try:
                product_obj = Product.objects.get(id=raw_pid)
            except Product.DoesNotExist:
                pass

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
            except:
                pass

    return Response({"message": "Order created"}, status=201)


# ============================================================
# 📜 USER ORDERS
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

        output = []

        for order in orders:
            items_list = []
            for item in order.items.all():

                pid = item.review_product_id or (item.product.id if item.product else None)

                name = (
                    item.product_name_snapshot
                    or item.product.name
                    if item.product else "Unknown Product"
                )

                img = (
                    item.product_image_snapshot
                    or (item.product.image.url if item.product and hasattr(item.product.image, "url") else None)
                    or "https://via.placeholder.com/200x200.png"
                )

                items_list.append(
                    {
                        "id": item.id,
                        "product_id": pid,
                        "product_name": name,
                        "image": img,
                        "quantity": item.quantity,
                        "price": str(item.price),
                    }
                )

            output.append(
                {
                    "id": order.id,
                    "status": order.status,
                    "payment_method": order.payment_method,
                    "total_amount": str(order.total_amount),
                    "created_at": order.created_at,
                    "items": items_list,
                }
            )

        return Response(output, status=200)

    except Exception as e:
        print("❌ list_orders:", e)
        return Response({"error": "Failed to load orders"}, status=500)


# ============================================================
# ⭐ GET PARTNER LISTINGS
# ============================================================
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_partner_listings(request):
    try:
        user = request.user
        listings = PartnerListing.objects.filter(partner=user).order_by("-created_at")

        # include review stats for products inside these listings
        prod_ids = list(listings.values_list("product_id", flat=True))
        qs = Product.objects.filter(id__in=[p for p in prod_ids if p]) if prod_ids else Product.objects.none()
        review_stats = build_review_stats_for_products(qs)

        serializer = PartnerListingSerializer(
            listings,
            many=True,
            context={"request": request, "review_stats": review_stats},
        )
        return Response(serializer.data, status=200)

    except Exception as e:
        print("❌ get_partner_listings:", e)
        return Response({"error": "Failed to load listings"}, status=500)


# ============================================================
# ⭐ CREATE PARTNER LISTING
# ============================================================
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def create_partner_listing(request):
    try:
        user = request.user
        profile = getattr(user, "profile", None)

        if not profile or not getattr(profile, "is_verified_partner", False):
            return Response({"error": "Only verified partners can create listings"}, status=403)

        product_id = request.data.get("product_id")
        markup_raw = request.data.get("markup", "0.00")

        if not product_id:
            return Response({"error": "product_id is required"}, status=400)

        try:
            product = Product.objects.get(id=product_id)
        except Product.DoesNotExist:
            return Response({"error": "Product not found"}, status=404)

        try:
            markup = Decimal(str(markup_raw))
        except InvalidOperation:
            return Response({"error": "Invalid markup value"}, status=400)

        listing, created = PartnerListing.objects.get_or_create(
            partner=user,
            product=product,
        )

        listing.markup = markup
        listing.final_price = product.price + markup

        if not listing.referral_code:
            listing.referral_code = uuid.uuid4().hex[:8]

        listing.referral_url = f"https://kudiway.com/r/{listing.referral_code}"
        listing.save()

        # include review stats for this one product
        review_stats = build_review_stats_for_products(Product.objects.filter(id=product.id))

        serializer = PartnerListingSerializer(
            listing,
            context={"request": request, "review_stats": review_stats},
        )

        return Response({"message": "Listing created", "listing": serializer.data}, status=201)

    except Exception as e:
        print("❌ create_partner_listing:", e)
        return Response({"error": "Failed to create listing"}, status=500)


# ============================================================
# 🎥 PURCHASED ITEMS
# ============================================================
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def purchased_items(request):
    user = request.user

    items = (
        OrderItem.objects.filter(order__user=user)
        .select_related("product")
        .order_by("-id")
    )

    output = []

    for item in items:
        pid = item.review_product_id or (item.product.id if item.product else None)

        name = item.product_name_snapshot or (
            item.product.name if item.product else "Unknown Product"
        )

        img = (
            item.product_image_snapshot
            or (item.product.image.url if item.product and hasattr(item.product.image, "url") else None)
            or "https://via.placeholder.com/200x200.png?text=No+Image"
        )

        output.append(
            {
                "id": item.id,
                "order_id": item.order_id,
                "product_id": item.product.id if item.product else None,
                "review_product_id": pid,
                "product_name": name,
                "image": img,
                "quantity": item.quantity,
                "price": str(item.price),
            }
        )

    return Response(output, status=200)


# ============================================================
# 🔗 REFERRAL PRODUCT LOOKUP
# ============================================================
@api_view(["GET"])
@permission_classes([AllowAny])
def get_referral_product(request, ref_code):
    try:
        listing = PartnerListing.objects.select_related("product", "partner").get(
            referral_code=ref_code
        )

        listing.clicks += 1
        listing.save(update_fields=["clicks"])

        qs = Product.objects.filter(id=listing.product_id) if listing.product_id else Product.objects.none()
        review_stats = build_review_stats_for_products(qs)

        serializer = PartnerListingSerializer(
            listing,
            context={"request": request, "review_stats": review_stats},
        )
        return Response(serializer.data)

    except PartnerListing.DoesNotExist:
        return Response({"error": "Invalid referral code"}, status=404)
    except Exception as e:
        print("❌ get_referral_product:", e)
        return Response({"error": "Failed to load referral product"}, status=500)


# ============================================================
# 🌐 REFERRAL CHECKOUT LANDING PAGE
# ============================================================
@csrf_exempt
def referral_checkout(request, ref_code):
    try:
        listing = PartnerListing.objects.select_related("product").get(
            referral_code=ref_code
        )
    except PartnerListing.DoesNotExist:
        return HttpResponse("<h2>Invalid referral link</h2>", status=404)

    product = listing.product

    img = ""
    try:
        img = product.image.url
    except:
        pass

    html = f"""
    <html>
        <head>
            <title>Kudiway Checkout</title>
            <meta name="viewport" content="width=device-width, initial-scale=1.0" />
        </head>
        <body style="font-family: Arial; text-align:center; padding:20px;">
            <h2>Buy: {product.name}</h2>
            <img src="{img}" style="width:200px;height:200px;object-fit:cover;border-radius:12px;" />

            <p style="font-size:20px;margin-top:20px;">
                Price: <b>₵{listing.final_price}</b>
            </p>

            <p>Sold by partner: <b>{listing.partner.username}</b></p>

            <a href="kudiway://checkout/{ref_code}"
                style="padding:14px 20px;background:#4CAF50;color:white;
                text-decoration:none;border-radius:8px;font-size:18px;">
                Open in Kudiway App
            </a>
        </body>
    </html>
    """
    return HttpResponse(html)


# ============================================================
# 🛒 ADMIN: LIST ALL ORDERS
# ============================================================
@api_view(["GET"])
@permission_classes([IsAdminUser])
def list_all_orders(request):
    try:
        orders = (
            Order.objects.all()
            .prefetch_related("items", "items__product", "user")
            .order_by("-created_at")
        )

        output = []

        for order in orders:
            items_list = []

            for item in order.items.all():
                pid = item.review_product_id or (item.product.id if item.product else None)

                name = (
                    item.product_name_snapshot
                    or (item.product.name if item.product else "Unknown Product")
                )

                img = (
                    item.product_image_snapshot
                    or (item.product.image.url if item.product and hasattr(item.product.image, "url") else None)
                    or "https://via.placeholder.com/200x200.png"
                )

                items_list.append(
                    {
                        "id": item.id,
                        "product_id": pid,
                        "product_name": name,
                        "image": img,
                        "quantity": item.quantity,
                        "price": str(item.price),
                    }
                )

            output.append(
                {
                    "order_id": order.id,
                    "user": order.user.username,
                    "status": order.status,
                    "payment_method": order.payment_method,
                    "subtotal_amount": str(order.subtotal_amount),
                    "total_amount": str(order.total_amount),
                    "created_at": order.created_at,
                    "items": items_list,
                }
            )

        return Response(output, status=200)

    except Exception as e:
        print("❌ list_all_orders:", e)
        return Response({"error": "Failed to fetch all orders"}, status=500)
