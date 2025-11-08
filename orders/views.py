from decimal import Decimal
from datetime import timedelta
from django.utils import timezone
from django.contrib.auth.models import User
from django.conf import settings
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework import status
import uuid

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
# 🏬 STORE — LIST PRODUCTS + PARTNER LISTINGS
# ============================================================
@api_view(["GET"])
@permission_classes([AllowAny])
def list_products(request):
    """Return all Kudiway products + partner resell listings."""
    try:
        products = Product.objects.all().order_by("-created_at")
        listings = PartnerListing.objects.select_related("product", "partner").order_by("-created_at")

        product_data = ProductSerializer(products, many=True, context={"request": request}).data
        listing_data = PartnerListingSerializer(listings, many=True, context={"request": request}).data

        print(f"✅ {len(products)} products + {len(listings)} partner listings loaded.")
        return Response(product_data + listing_data, status=200)
    except Exception as e:
        print("❌ ERROR listing products:", e)
        return Response({"error": str(e)}, status=500)


# ============================================================
# 📦 SINGLE PRODUCT OR LISTING
# ============================================================
@api_view(["GET"])
@permission_classes([AllowAny])
def get_product(request, pk):
    """Retrieve a product or resale listing by ID."""
    try:
        product = Product.objects.get(pk=pk)
        serializer = ProductSerializer(product, context={"request": request})
        return Response(serializer.data)
    except Product.DoesNotExist:
        try:
            listing = PartnerListing.objects.get(pk=pk)
            serializer = PartnerListingSerializer(listing, context={"request": request})
            return Response(serializer.data)
        except PartnerListing.DoesNotExist:
            return Response({"error": "Product not found."}, status=404)
    except Exception as e:
        print("❌ ERROR get_product:", e)
        return Response({"error": str(e)}, status=500)


# ============================================================
# 🧾 CREATE ORDER (Wallet or Credit)
# ============================================================
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def create_order(request):
    """Handles order creation and partner rewards."""
    user = request.user
    print(f"🧾 Creating order for {user.username}")

    wallet, _ = Wallet.objects.get_or_create(user=user)
    points_wallet, _ = KudiPoints.objects.get_or_create(user=user)

    data = request.data
    items = data.get("items", [])
    payment_method = data.get("payment_method", "wallet")

    if not items:
        return Response({"error": "No items provided."}, status=400)

    total_amount = sum(Decimal(str(i.get("price", 0))) * int(i.get("qty", 1)) for i in items)
    usable_points_cedis = min(points_wallet.balance / Decimal("10"), total_amount)
    points_to_deduct = usable_points_cedis * Decimal("10")

    # ========================================================
    # 💳 WALLET PAYMENT
    # ========================================================
    if payment_method == "wallet":
        total_after_points = total_amount - usable_points_cedis
        if wallet.balance < total_after_points:
            return Response({"error": "Insufficient wallet balance."}, status=400)

        try:
            points_wallet.redeem_points(points_to_deduct)
        except Exception as e:
            print("⚠️ Failed to redeem points:", e)

        wallet.balance -= total_after_points
        wallet.save()

        log_transaction(user, "wallet_purchase", total_after_points, "Purchase via wallet")
        log_transaction(user, "points_used", usable_points_cedis, f"Used {points_to_deduct} pts")

        order = Order.objects.create(
            user=user,
            subtotal_amount=total_amount,
            total_amount=total_amount,
            payment_method="wallet",
            status="paid",
            note=f"₵{usable_points_cedis:.2f} from points, ₵{total_after_points:.2f} from wallet.",
        )
        print(f"✅ Wallet order #{order.id} created.")

    # ========================================================
    # 💳 CREDIT (BNPL)
    # ========================================================
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
            note=f"30% down ₵{down_payment:.2f}, 5% interest.",
            created_at=timezone.now(),
            updated_at=timezone.now(),
        )
        print(f"✅ Credit order #{order.id} created.")

    else:
        return Response({"error": "Invalid payment method."}, status=400)

    # ========================================================
    # 🛒 CREATE ORDER ITEMS + REWARD PARTNERS
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

        if partner_id:
            try:
                partner_user = User.objects.get(id=partner_id)
                listing = PartnerListing.objects.filter(partner=partner_user, product__name=name).first()
                if listing:
                    profit = listing.markup * qty
                    points = profit * Decimal("10")
                    partner_points, _ = KudiPoints.objects.get_or_create(user=partner_user)
                    partner_points.add_points(points)
                    log_transaction(partner_user, "partner_points", profit, f"Resale of {name}")
                    listing.sales_count += 1
                    listing.save(update_fields=["sales_count"])
                    print(f"💎 Partner reward: +{points} pts ({partner_user.username})")
            except Exception as e:
                print("⚠️ Partner reward failed:", e)

    serializer = OrderSerializer(order, context={"request": request})
    return Response(serializer.data, status=201)


# ============================================================
# 📜 USER ORDERS
# ============================================================
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def list_orders(request):
    """List authenticated user's previous orders."""
    orders = Order.objects.filter(user=request.user).order_by("-created_at")
    serializer = OrderSerializer(orders, many=True, context={"request": request})
    return Response(serializer.data, status=200)


# ============================================================
# 🤝 CREATE PARTNER LISTING (AFFILIATE)
# ============================================================
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def create_partner_listing(request):
    """Allow verified partners to generate affiliate links for resale."""
    user = request.user
    if not hasattr(user, "profile") or not user.profile.is_verified_partner:
        return Response({"error": "Only verified partners can create listings."}, status=403)

    product_id = request.data.get("product_id")
    markup_raw = request.data.get("markup", "0.00")

    try:
        markup = Decimal(markup_raw)
    except Exception:
        return Response({"error": "Invalid markup value."}, status=400)

    try:
        product = Product.objects.get(id=product_id)
    except Product.DoesNotExist:
        return Response({"error": "Product not found."}, status=404)

    # Create or update listing
    listing, created = PartnerListing.objects.get_or_create(
        partner=user,
        product=product,
        defaults={"markup": markup, "final_price": product.price + markup},
    )

    if not created:
        listing.markup = markup
        listing.final_price = product.price + markup

    # Auto-generate referral code + link if missing
    if not listing.referral_code:
        listing.referral_code = uuid.uuid4().hex[:8]
    listing.referral_url = f"https://kudiwayapp.com/r/{listing.referral_code}"

    listing.save()

    return Response(
        {
            "message": "Listing created successfully!",
            "product": product.name,
            "markup": str(listing.markup),
            "final_price": str(listing.final_price),
            "referral_code": listing.referral_code,
            "referral_url": listing.referral_url,
        },
        status=201,
    )


# ============================================================
# 📋 MY PARTNER LISTINGS
# ============================================================
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_partner_listings(request):
    """Return all resale listings for the logged-in verified partner."""
    user = request.user
    if not hasattr(user, "profile") or not user.profile.is_verified_partner:
        return Response({"error": "Only verified partners can view listings."}, status=403)

    listings = PartnerListing.objects.filter(partner=user).select_related("product").order_by("-created_at")
    serializer = PartnerListingSerializer(listings, many=True, context={"request": request})
    return Response(serializer.data)


# ============================================================
# 🔗 AFFILIATE / REFERRAL PRODUCT (NEW)
# ============================================================
@api_view(["GET"])
@permission_classes([AllowAny])
def get_referral_product(request, ref_code):
    """
    When someone opens a referral link (e.g. /orders/referral/abc123/):
    - Look up the PartnerListing via referral_code
    - Count the click for analytics
    - Return the full product + partner + final price
    """
    try:
        listing = PartnerListing.objects.select_related("product", "partner").get(referral_code=ref_code)
        listing.clicks += 1
        listing.save(update_fields=["clicks"])
        serializer = PartnerListingSerializer(listing, context={"request": request})
        return Response(serializer.data, status=200)
    except PartnerListing.DoesNotExist:
        return Response({"error": "Invalid or expired referral code."}, status=404)
    except Exception as e:
        print("❌ Referral product error:", e)
        return Response({"error": str(e)}, status=500)
