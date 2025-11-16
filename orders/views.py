from decimal import Decimal, InvalidOperation
from datetime import timedelta
from django.utils import timezone
from django.contrib.auth.models import User
from django.conf import settings
from django.shortcuts import render
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
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
from rest_framework.permissions import IsAdminUser

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
    """List only Kudiway original products."""
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
# 🧾 CREATE ORDER (App checkout)
# ============================================================
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def create_order(request):
    """Handles wallet & credit orders and partner commission tracking."""
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
            Decimal(str(i.get("price", 0))) * int(i.get("qty", 1)) for i in items
        )
    except Exception:
        return Response({"error": "Invalid item price or quantity."}, status=400)

    usable_points_cedis = min(points_wallet.balance / Decimal("10"), total_amount)
    points_to_deduct = usable_points_cedis * Decimal("10")

    # 💳 WALLET PAYMENT
    if payment_method == "wallet":
        total_after_points = total_amount - usable_points_cedis
        if wallet.balance < total_after_points:
            return Response({"error": "Insufficient wallet balance."}, status=400)

        if points_to_deduct > 0:
            try:
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

    # 💳 CREDIT (BNPL)
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

    # 🛍 CREATE ORDER ITEMS
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

        # Link partner if from referral
        if partner_id:
            try:
                partner_user = User.objects.get(id=partner_id)
                order_item.partner = partner_user
                order_item.save(update_fields=["partner"])
                print(f"🔗 Linked partner {partner_user.username} to item {name}")
            except Exception as e:
                print("⚠️ Failed to link partner:", e)

    serializer = OrderSerializer(order, context={"request": request})
    return Response(serializer.data, status=201)


# ============================================================
# 📜 USER ORDERS
# ============================================================
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def list_orders(request):
    """List all orders of logged-in user."""
    orders = Order.objects.filter(user=request.user).order_by("-created_at")
    serializer = OrderSerializer(orders, many=True, context={"request": request})
    return Response(serializer.data, status=200)


# ============================================================
# 🤝 CREATE PARTNER LISTING
# ============================================================
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def create_partner_listing(request):
    """Allow verified partners to create or update a resale listing."""
    try:
        user = request.user
        profile = getattr(user, "profile", None)
        if not profile or not getattr(profile, "is_verified_partner", False):
            return Response({"error": "Only verified partners can create listings."}, status=403)

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
            defaults={"markup": markup, "final_price": product.price + markup},
        )

        if not created:
            listing.markup = markup
            listing.final_price = product.price + markup

        if not listing.referral_code:
            listing.referral_code = uuid.uuid4().hex[:8]

        # ✅ Use your real domain
        listing.referral_url = f"https://kudiway.com/r/{listing.referral_code}"
        listing.save()

        serializer = PartnerListingSerializer(listing, context={"request": request})
        return Response(
            {
                "message": "Listing created successfully!",
                "listing": serializer.data,
                "redirect_to": "KPartnerHubScreen",
            },
            status=201,
        )

    except Exception as e:
        print("❌ create_partner_listing error:", e)
        print(traceback.format_exc())
        return Response({"error": "Failed to create partner listing."}, status=500)


# ============================================================
# 📋 MY PARTNER LISTINGS
# ============================================================
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_partner_listings(request):
    """Get all listings for a verified partner."""
    user = request.user
    profile = getattr(user, "profile", None)
    if not profile or not getattr(profile, "is_verified_partner", False):
        return Response({"error": "Only verified partners can view listings."}, status=403)

    listings = PartnerListing.objects.filter(partner=user).select_related("product").order_by("-created_at")
    serializer = PartnerListingSerializer(listings, many=True, context={"request": request})
    return Response(serializer.data, status=200)


# ============================================================
# 🔗 REFERRAL PRODUCT (API JSON for the app)
# ============================================================
@api_view(["GET"])
@permission_classes([AllowAny])
def get_referral_product(request, ref_code):
    """API endpoint for in-app use."""
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
        print(traceback.format_exc())
        return Response({"error": "Failed to load referral product."}, status=500)


# ============================================================
# 🌐 REFERRAL LANDING PAGE (WEB)
# ============================================================
def referral_redirect(request, ref_code):
    """
    Handles browser visits to https://kudiway.com/r/<ref_code>
    Renders referral_landing.html for web users.
    """
    try:
        listing = PartnerListing.objects.select_related("product", "partner").get(referral_code=ref_code)
        product = listing.product
        context = {
            "listing": listing,
            "product": product,
            "partner_name": listing.partner.username,
            # must match your app Linking config: kudiwayapp://r/<code>
            "deep_link": f"kudiwayapp://r/{ref_code}",
        }
        return render(request, "referral_landing.html", context)
    except PartnerListing.DoesNotExist:
        return HttpResponse("<h2>Referral link not found or expired.</h2>", status=404)
    except Exception as e:
        print("❌ Referral redirect error:", e)
        print(traceback.format_exc())
        return HttpResponse("<h2>Server error.</h2>", status=500)


# ============================================================
# 🧾 REFERRAL CHECKOUT (WEB) — saves Order + OrderItem
# ============================================================
def _get_or_create_guest_user() -> User:
    """
    Ensure we always have a user to attach Orders to.
    Order.user is not nullable, so we use a shared 'guest_web' user.
    """
    guest, created = User.objects.get_or_create(
        username="guest_web",
        defaults={"first_name": "Guest", "last_name": "Checkout"},
    )
    return guest

@csrf_exempt  # form posts from the public page (no CSRF token)
def referral_checkout(request, ref_code):
    """
    Web checkout for buyers who visit referral link.
    Shows form (GET) and creates a pending Order (POST).
    """
    try:
        listing = PartnerListing.objects.select_related("product", "partner").get(referral_code=ref_code)
        product = listing.product

        if request.method == "POST":
            name = (request.POST.get("name") or "").strip()
            phone = (request.POST.get("phone") or "").strip()
            address = (request.POST.get("address") or "").strip()

            if not name or not phone or not address:
                # Re-render with error message
                return render(
                    request,
                    "referral_checkout.html",
                    {
                        "product": product,
                        "listing": listing,
                        "partner_name": listing.partner.username,
                        "error": "Please fill all fields to continue.",
                    },
                )

            # 🧑‍🤝‍🧑 Attach to a 'guest' user so Order.user is not null
            guest_user = _get_or_create_guest_user()

            # Create a pending order (COD / manual follow-up)
            order = Order.objects.create(
                user=guest_user,
                partner=listing.partner,  # if your Order model has this field
                subtotal_amount=listing.final_price,
                total_amount=listing.final_price,
                payment_method="wallet",  # semantic placeholder
                status="pending",
                note=f"Web guest order — Name: {name}, Phone: {phone}, Address: {address}",
            )

            OrderItem.objects.create(
                order=order,
                product=product,
                price=listing.final_price,
                quantity=1,
                product_name_snapshot=product.name,
                product_image_snapshot=getattr(product.image, "url", ""),
                partner=listing.partner,
            )

            # ⚠️ Do NOT increment total_profit yet; wait until you mark order paid/delivered.

            # 🎉 Show confirmation page
            return render(
                request,
                "order_confirmed.html",
                {"product": product, "customer_name": name},
            )

        # GET → initial form
        return render(
            request,
            "referral_checkout.html",
            {
                "product": product,
                "listing": listing,
                "partner_name": listing.partner.username,
            },
        )
    except PartnerListing.DoesNotExist:
        return HttpResponse("<h2>Referral not found or expired.</h2>", status=404)
    except Exception as e:
        print("❌ referral_checkout error:", e)
        print(traceback.format_exc())
        return HttpResponse("<h2>Server error.</h2>", status=500)
# ------------------------------------------
# 📦 GET MY PARTNER LISTINGS
# ------------------------------------------
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from .models import PartnerListing

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def my_listings(request):
    user = request.user

    listings = PartnerListing.objects.filter(partner=user)

    data = []
    for l in listings:
        data.append({
            "id": l.id,
            "name": l.product.name,
            "product": {
                "name": l.product.name,
                "price": float(l.product.price),
                "image": str(getattr(l.product.image, "url", "")),
            },
            "markup": float(l.markup),
            "total_profit": float(l.total_profit or 0),
            "slug": l.slug,
            "referral_url": l.referral_url,
        })

    return Response(data)
@api_view(["GET"])
@permission_classes([IsAdminUser])
def list_all_orders(request):
    """
    Admin-only: list all orders (used for dashboard stats).
    """
    orders = Order.objects.all().order_by("-created_at")

    data = []
    for o in orders:
        data.append(
            {
                "id": o.id,
                "user": o.user.username,
                "total_amount": float(o.total_amount),
                "status": o.status,
                "payment_method": o.payment_method,
                "created_at": o.created_at,
            }
        )

    return Response(data, status=status.HTTP_200_OK)