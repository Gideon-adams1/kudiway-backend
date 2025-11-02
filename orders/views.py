from decimal import Decimal
from datetime import timedelta
from django.utils import timezone
from django.contrib.auth.models import User
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework import status

from kudiwallet.models import Wallet, Transaction
from users.models import KudiPoints
from .models import Order, OrderItem, Product, PartnerListing
from .serializers import OrderSerializer, ProductSerializer, PartnerListingSerializer


# ============================================================
# 💵 Helper: Log Transactions
# ============================================================
def log_transaction(user, transaction_type, amount, description=""):
    try:
        Transaction.objects.create(
            user=user,
            transaction_type=transaction_type,
            amount=Decimal(amount),
            description=description,
        )
        print(f"✅ Transaction logged: {transaction_type} ₵{amount} for {user.username}")
    except Exception as e:
        print("⚠️ Transaction log failed:", e)


# ============================================================
# 🏬 STORE: List all products & partner listings
# ============================================================
@api_view(["GET"])
@permission_classes([AllowAny])
def list_products(request):
    """List all vendor products and partner listings"""
    print("📦 DEBUG: Fetching all products + partner listings")
    try:
        products = Product.objects.all().order_by("-created_at")
        listings = PartnerListing.objects.select_related("product", "partner").order_by("-created_at")

        product_data = ProductSerializer(products, many=True, context={"request": request}).data
        listing_data = PartnerListingSerializer(listings, many=True, context={"request": request}).data

        print(f"✅ Products: {len(products)}, Partner Listings: {len(listings)}")
        return Response(product_data + listing_data, status=status.HTTP_200_OK)

    except Exception as e:
        print("❌ ERROR in list_products:", e)
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ============================================================
# 📦 GET SINGLE PRODUCT (by vendor or partner)
# ============================================================
@api_view(["GET"])
@permission_classes([AllowAny])
def get_product(request, pk):
    """Retrieve single product or partner listing by ID"""
    print(f"🔍 DEBUG: Fetching product by ID = {pk}")
    try:
        product = Product.objects.get(pk=pk)
        print(f"✅ Found product: {product.name}")
        serializer = ProductSerializer(product, context={"request": request})
        return Response(serializer.data, status=status.HTTP_200_OK)
    except Product.DoesNotExist:
        try:
            listing = PartnerListing.objects.get(pk=pk)
            print(f"✅ Found partner listing for product: {listing.product.name}")
            serializer = PartnerListingSerializer(listing, context={"request": request})
            return Response(serializer.data, status=status.HTTP_200_OK)
        except PartnerListing.DoesNotExist:
            print("❌ Product not found in both tables")
            return Response({"error": "Product not found."}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        print("❌ ERROR in get_product:", e)
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ============================================================
# 🧾 CREATE ORDER
# ============================================================
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def create_order(request):
    user = request.user
    print(f"🧾 DEBUG: create_order() called by {user.username}")
    print("📨 Incoming data:", request.data)

    wallet, _ = Wallet.objects.get_or_create(user=user)
    points_wallet, _ = KudiPoints.objects.get_or_create(user=user)
    data = request.data
    items = data.get("items", [])
    payment_method = data.get("payment_method", "wallet")

    if not items:
        print("⛔ No items in order")
        return Response({"error": "No items in order."}, status=status.HTTP_400_BAD_REQUEST)

    total_amount = sum(
        Decimal(str(item.get("price", 0))) * int(item.get("qty", 1)) for item in items
    )
    print(f"💰 Total amount: ₵{total_amount}")

    points_value = points_wallet.balance / Decimal("10")
    usable_points = min(points_value, total_amount)
    points_to_deduct = usable_points * Decimal("10")

    # ========================================================
    # 💰 WALLET PAYMENT
    # ========================================================
    if payment_method == "wallet":
        print("💳 Using WALLET payment method")
        total_after_points = total_amount - usable_points

        if wallet.balance < total_after_points:
            print("❌ Insufficient wallet balance")
            return Response({"error": "Insufficient wallet balance."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            points_wallet.redeem_points(points_to_deduct)
        except Exception as e:
            print("⚠️ Failed to redeem points:", e)

        wallet.balance -= total_after_points
        wallet.save()

        log_transaction(user, "withdraw", total_after_points, "Wallet purchase")
        log_transaction(user, "points_used", usable_points, f"Used {points_to_deduct} points")

        order = Order.objects.create(
            user=user,
            subtotal_amount=total_amount,
            total_amount=total_amount,
            payment_method="wallet",
            status="paid",
            note=f"₵{usable_points:.2f} from points, ₵{total_after_points:.2f} wallet.",
        )
        print(f"✅ Order created (wallet): ID={order.id}")

    # ========================================================
    # 💳 CREDIT (BNPL)
    # ========================================================
    elif payment_method == "credit":
        print("💳 Using CREDIT payment method")
        down_payment = total_amount * Decimal("0.30")
        remaining = total_amount - down_payment
        interest = remaining * Decimal("0.05")
        total_credit = remaining + interest

        print(f"📊 Down: ₵{down_payment}, Interest: ₵{interest}, Credit: ₵{total_credit}")

        if wallet.balance < down_payment:
            print("❌ Insufficient wallet balance for downpayment")
            return Response({"error": "Insufficient wallet balance for downpayment."}, status=status.HTTP_400_BAD_REQUEST)
        if wallet.credit_balance + total_credit > wallet.credit_limit:
            print("❌ Credit limit exceeded")
            return Response({"error": "Credit limit exceeded."}, status=status.HTTP_400_BAD_REQUEST)

        wallet.balance -= down_payment
        wallet.credit_balance += total_credit
        wallet.save()

        log_transaction(user, "withdraw", down_payment, "Credit downpayment")
        log_transaction(user, "credit_purchase", total_credit, "BNPL order")

        order = Order.objects.create(
            user=user,
            subtotal_amount=total_amount,
            total_amount=total_amount,
            payment_method="credit",
            status="pending",
            note=f"30% down ₵{down_payment:.2f}, 5% interest.",
            down_payment=down_payment,
            interest=interest,
            credit_amount=total_credit,
            due_date=timezone.now() + timedelta(days=14),
        )
        print(f"✅ Order created (credit): ID={order.id}")

    else:
        print("❌ Invalid payment method")
        return Response({"error": "Invalid payment method."}, status=status.HTTP_400_BAD_REQUEST)

    # ========================================================
    # 🛍 Save order items
    # ========================================================
    for item in items:
        product_name = item.get("name", "Unnamed")
        price = Decimal(str(item.get("price", 0)))
        qty = int(item.get("qty", 1))
        image = item.get("image", "")
        partner_id = item.get("partner_id")

        print(f"🧩 Adding item: {product_name}, ₵{price}, Qty {qty}, Partner {partner_id}")

        order_item = OrderItem.objects.create(
            order=order,
            price=price,
            quantity=qty,
            product_name_snapshot=product_name,
            product_image_snapshot=image,
        )

        # 🤝 Reward partner
        if partner_id:
            try:
                partner_user = User.objects.get(id=partner_id)
                listing = PartnerListing.objects.filter(
                    partner=partner_user, product__name=product_name
                ).first()
                if listing:
                    profit = listing.markup * qty
                    points_earned = profit * Decimal("10")
                    print(f"💎 Partner profit ₵{profit} → +{points_earned} pts")

                    partner_points, _ = KudiPoints.objects.get_or_create(user=partner_user)
                    partner_points.add_points(points_earned)
                    log_transaction(partner_user, "partner_points_earned", profit, f"Resale of {product_name}")
            except Exception as e:
                print("⚠️ Partner reward failed:", e)

    serializer = OrderSerializer(order, context={"request": request})
    print("✅ Order complete and serialized")
    return Response(serializer.data, status=status.HTTP_201_CREATED)


# ============================================================
# 📜 LIST USER ORDERS
# ============================================================
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def list_orders(request):
    print(f"📜 DEBUG: Fetching orders for {request.user.username}")
    orders = Order.objects.filter(user=request.user).order_by("-created_at")
    serializer = OrderSerializer(orders, many=True, context={"request": request})
    print(f"✅ Found {len(orders)} orders")
    return Response(serializer.data, status=status.HTTP_200_OK)


# ============================================================
# 🤝 CREATE PARTNER LISTING
# ============================================================
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def create_partner_listing(request):
    print("🚀 DEBUG: create_partner_listing called")
    print("🧾 Incoming data:", request.data)
    print("👤 User:", request.user)

    user = request.user
    if not hasattr(user, "profile") or not user.profile.is_verified_partner:
        print("⛔ User not verified partner")
        return Response({"error": "Only verified partners can create listings."}, status=403)

    product_id = request.data.get("product_id")
    markup_raw = request.data.get("markup", "0.00")
    print("🧩 Product ID:", product_id, "| Markup:", markup_raw)

    try:
        markup = Decimal(markup_raw)
    except Exception:
        print("❌ Invalid markup input")
        return Response({"error": "Invalid markup amount."}, status=400)

    try:
        product = Product.objects.get(id=product_id)
        print("✅ Product found:", product.name)
    except Product.DoesNotExist:
        print("❌ Product not found")
        return Response({"error": "Product not found."}, status=404)

    try:
        listing, created = PartnerListing.objects.get_or_create(
            partner=user,
            product=product,
            defaults={"markup": markup, "resale_price": product.price + markup},
        )

        if not created:
            listing.markup = markup
            listing.resale_price = product.price + markup
            listing.save()
            print("🔁 Updated existing listing")

        print("✅ Listing created successfully")
        return Response(
            {
                "message": "Listing created successfully!",
                "product": product.name,
                "markup": str(listing.markup),
                "resale_price": str(listing.resale_price),
            },
            status=201,
        )
    except Exception as e:
        print("❌ ERROR creating listing:", e)
        return Response({"error": str(e)}, status=500)


# ============================================================
# 🤝 LIST MY PARTNER LISTINGS
# ============================================================
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_partner_listings(request):
    user = request.user
    print(f"📋 DEBUG: get_partner_listings() called by {user.username}")

    if not hasattr(user, "profile") or not user.profile.is_verified_partner:
        print("⛔ User not verified partner")
        return Response({"error": "Only verified partners can view listings."}, status=403)

    listings = PartnerListing.objects.filter(partner=user).select_related("product").order_by("-created_at")
    print(f"✅ Found {listings.count()} listings for {user.username}")
    serializer = PartnerListingSerializer(listings, many=True, context={"request": request})
    return Response(serializer.data, status=200)
