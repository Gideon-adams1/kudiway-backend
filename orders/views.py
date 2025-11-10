from decimal import Decimal, InvalidOperation
from datetime import timedelta
from django.utils import timezone
from django.contrib.auth.models import User
from django.conf import settings
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework import status
import uuid
import traceback

from kudiwallet.models import Wallet, Transaction
from users.models import KudiPoints
from .models import Order, OrderItem, Product, PartnerListing
from .serializers import OrderSerializer, ProductSerializer, PartnerListingSerializer


# ============================================================
# 💵 HELPER — TRANSACTION LOGGER
# ============================================================
def log_transaction(user, transaction_type, amount, description=""):
    """Create a transaction log safely."""
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
# 🏬 STORE — LIST PRODUCTS (Only Originals)
# ============================================================
@api_view(["GET"])
@permission_classes([AllowAny])
def list_products(request):
    """Return only Kudiway store products."""
    try:
        products = Product.objects.all().order_by("-created_at")
        data = ProductSerializer(products, many=True, context={"request": request}).data
        print(f"✅ {len(products)} original products loaded.")
        return Response(data, status=status.HTTP_200_OK)
    except Exception as e:
        print("❌ ERROR listing products:", e)
        print(traceback.format_exc())
        return Response({"error": "Failed to load store products."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ============================================================
# 📦 SINGLE PRODUCT OR PARTNER LISTING
# ============================================================
@api_view(["GET"])
@permission_classes([AllowAny])
def get_product(request, pk):
    """Retrieve a single product or partner listing."""
    try:
        product = Product.objects.get(pk=pk)
        serializer = ProductSerializer(product, context={"request": request})
        return Response(serializer.data, status=status.HTTP_200_OK)
    except Product.DoesNotExist:
        try:
            listing = PartnerListing.objects.get(pk=pk)
            serializer = PartnerListingSerializer(listing, context={"request": request})
            return Response(serializer.data, status=status.HTTP_200_OK)
        except PartnerListing.DoesNotExist:
            return Response({"error": "Product not found."}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        print("❌ ERROR get_product:", e)
        print(traceback.format_exc())
        return Response({"error": "Failed to fetch item."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ============================================================
# 🧾 CREATE ORDER (Wallet or Credit)
# ============================================================
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def create_order(request):
    """Handles order creation, partner tracking, and payment deductions."""
    user = request.user
    print(f"🧾 Creating order for {user.username}")

    wallet, _ = Wallet.objects.get_or_create(user=user)
    points_wallet, _ = KudiPoints.objects.get_or_create(user=user)

    data = request.data
    items = data.get("items", [])
    payment_method = data.get("payment_method", "wallet")

    if not items:
        return Response({"error": "No items provided."}, status=status.HTTP_400_BAD_REQUEST)

    try:
        total_amount = sum(Decimal(str(i.get("price", 0))) * int(i.get("qty", 1)) for i in items)
    except Exception:
        return Response({"error": "Invalid item price/qty."}, status=status.HTTP_400_BAD_REQUEST)

    usable_points_cedis = min(points_wallet.balance / Decimal("10"), total_amount)
    points_to_deduct = usable_points_cedis * Decimal("10")

    # ========================================================
    # 💳 WALLET PAYMENT
    # ========================================================
    if payment_method == "wallet":
        total_after_points = total_amount - usable_points_cedis
        if wallet.balance < total_after_points:
            return Response({"error": "Insufficient wallet balance."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            if points_to_deduct > 0:
                points_wallet.redeem_points(points_to_deduct)
        except Exception as e:
            print("⚠️ Failed to redeem points:", e)

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

    # ========================================================
    # 💳 CREDIT (BNPL)
    # ========================================================
    elif payment_method == "credit":
        down_payment = total_amount * Decimal("0.30")
        remaining = total_amount - down_payment
        interest = remaining * Decimal("0.05")
        total_credit = remaining + interest

        if wallet.balance < down_payment:
            return Response({"error": "Insufficient wallet balance for downpayment."}, status=status.HTTP_400_BAD_REQUEST)
        if wallet.credit_balance + total_credit > wallet.credit_limit:
            return Response({"error": "Credit limit exceeded."}, status=status.HTTP_400_BAD_REQUEST)

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
            note=f"30% down ₵{down_payment:.2f}, 5% interest.",
            created_at=timezone.now(),
            updated_at=timezone.now(),
        )

    else:
        return Response({"error": "Invalid payment method."}, status=status.HTTP_400_BAD_REQUEST)

    # ========================================================
    # 🛒 CREATE ORDER ITEMS + LINK PARTNER SALES
    # ========================================================
    for item in items:
        name = item.get("name", "Unnamed Product")
        price = Decimal(str(item.get("price", 0)))
        qty = int(item.get("qty", 1))
        image = item.get("image", "")
        partner_id = item.get("partner_id")

        order_item = OrderItem.objects.create(
            order=order,
            price=price,
            quantity=qty,
            product_name_snapshot=name,
            product_image_snapshot=image,
        )

        # 🔗 If sold through referral link → link partner
        if partner_id:
            try:
                partner_user = User.objects.get(id=partner_id)
                order_item.partner = partner_user
                order_item.save(update_fields=["partner"])
                print(f"🔗 Linked partner {partner_user.username} to {name}")
            except Exception as e:
                print("⚠️ Failed to link partner:", e)

    serializer = OrderSerializer(order, context={"request": request})
    return Response(serializer.data, status=status.HTTP_201_CREATED)


# ============================================================
# 📜 USER ORDERS
# ============================================================
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def list_orders(request):
    """List authenticated user's previous orders."""
    orders = Order.objects.filter(user=request.user).order_by("-created_at")
    serializer = OrderSerializer(orders, many=True, context={"request": request})
    return Response(serializer.data, status=status.HTTP_200_OK)


# ============================================================
# 🤝 CREATE PARTNER LISTING (AFFILIATE)
# ============================================================
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def create_partner_listing(request):
    """Allow verified partners to create or update affiliate listings safely."""
    try:
        user = request.user
        profile = getattr(user, "profile", None)
        if not profile or not getattr(profile, "is_verified_partner", False):
            return Response({"error": "Only verified partners can create listings."}, status=status.HTTP_403_FORBIDDEN)

        product_id = request.data.get("product_id")
        markup_raw = request.data.get("markup", "0.00")

        if not product_id:
            return Response({"error": "product_id is required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            markup = Decimal(str(markup_raw))
            if markup < 0:
                return Response({"error": "Markup cannot be negative."}, status=status.HTTP_400_BAD_REQUEST)
        except (InvalidOperation, TypeError):
            return Response({"error": "Invalid markup value."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            product = Product.objects.get(id=product_id)
        except Product.DoesNotExist:
            return Response({"error": "Product not found."}, status=status.HTTP_404_NOT_FOUND)

        listing, created = PartnerListing.objects.get_or_create(
            partner=user,
            product=product,
            defaults={"markup": markup, "final_price": product.price + markup},
        )

        if not created:
            listing.markup = markup
            listing.final_price = product.price + markup

        if not listing.referral_code:
            listing.referral_code = uuid.uuid4().hex[:8]

        listing.referral_url = f"https://kudiwayapp.com/r/{listing.referral_code}"
        listing.save()

        serializer = PartnerListingSerializer(listing, context={"request": request})
        return Response(
            {
                "message": "Listing created successfully!",
                "listing": serializer.data,
                "redirect_to": "KPartnerHubScreen",
            },
            status=status.HTTP_201_CREATED,
        )

    except Exception as e:
        print("❌ create_partner_listing error:", e)
        print(traceback.format_exc())
        return Response({"error": "Failed to create partner listing."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ============================================================
# 📋 MY PARTNER LISTINGS
# ============================================================
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_partner_listings(request):
    """Return all resale listings for the logged-in verified partner."""
    user = request.user
    profile = getattr(user, "profile", None)
    if not profile or not getattr(profile, "is_verified_partner", False):
        return Response({"error": "Only verified partners can view listings."}, status=status.HTTP_403_FORBIDDEN)

    listings = PartnerListing.objects.filter(partner=user).select_related("product").order_by("-created_at")
    serializer = PartnerListingSerializer(listings, many=True, context={"request": request})
    return Response(serializer.data, status=status.HTTP_200_OK)


# ============================================================
# 🔗 AFFILIATE / REFERRAL PRODUCT (BUYER VIEW)
# ============================================================
@api_view(["GET"])
@permission_classes([AllowAny])
def get_referral_product(request, ref_code):
    """
    When someone opens a referral link (e.g. /r/abc123):
    - Look up the PartnerListing via referral_code
    - Increment click count
    - Return full product + partner info for checkout screen
    """
    try:
        listing = PartnerListing.objects.select_related("product", "partner").get(referral_code=ref_code)
        listing.clicks += 1
        listing.save(update_fields=["clicks"])
        serializer = PartnerListingSerializer(listing, context={"request": request})
        return Response(serializer.data, status=status.HTTP_200_OK)
    except PartnerListing.DoesNotExist:
        return Response({"error": "Invalid or expired referral code."}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        print("❌ Referral product error:", e)
        print(traceback.format_exc())
        return Response({"error": "Failed to load referral product."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
from django.shortcuts import render, redirect
from django.http import HttpResponse
from django.template import loader

def referral_redirect(request, ref_code):
    """
    Handles browser visits to https://kudiway.com/r/<ref_code>
    - Shows a simple landing page with product info and 'Open in Kudiway App' button.
    - Automatically redirects to the mobile app deep link if opened on a phone.
    """
    try:
        listing = PartnerListing.objects.select_related("product", "partner").get(referral_code=ref_code)
        deep_link = f"kudiwayapp://r/{ref_code}"
        context = {
            "listing": listing,
            "deep_link": deep_link,
            "product": listing.product,
            "partner_name": listing.partner.username,
        }
        template = loader.get_template("referral_landing.html")
        return HttpResponse(template.render(context, request))
    except PartnerListing.DoesNotExist:
        return HttpResponse("<h2>Referral link not found or expired.</h2>", status=404)
