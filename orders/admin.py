# orders/admin.py
import json
import uuid
from decimal import Decimal

from django import forms
from django.contrib import admin
from django.core.exceptions import ValidationError
from django.utils.text import slugify

from .models import Product, PartnerListing, Order, OrderItem


# ============================================================
# 🧩 CATEGORY → SPECS SCHEMA (same idea as serializer)
# ============================================================
CATEGORY_SPEC_SCHEMA = {
    "Phones": {
        "required": {
            "brand": "str",
            "model": "str",
            "storage_gb": "num",
            "ram_gb": "num",
        },
        "optional": {
            "battery_mah": "num",
            "screen_in": "num",
            "camera": "str",
            "os": "str",
            "network": "str",
            "condition": "str",
            "warranty_months": "num",
        },
    },
    "Accessories": {
        "required": {"type": "str"},
        "optional": {
            "brand": "str",
            "compatibility": "str",
            "power_w": "num",
            "material": "str",
            "condition": "str",
        },
    },
    "Electronics": {
        "required": {"brand": "str"},
        "optional": {
            "model": "str",
            "power_w": "num",
            "voltage": "str",
            "capacity": "str",
            "condition": "str",
            "warranty_months": "num",
        },
    },
    "Gadgets": {
        "required": {"brand": "str"},
        "optional": {
            "model": "str",
            "battery_mah": "num",
            "connectivity": "str",
            "condition": "str",
            "warranty_months": "num",
        },
    },
    "Fashion": {
        "required": {"size": "str"},
        "optional": {
            "brand": "str",
            "color": "str",
            "material": "str",
            "gender": "str",
            "condition": "str",
        },
    },
    "Other": {"required": {}, "optional": {}},
}


def _coerce(expected_type: str, value):
    if value is None:
        return None
    if expected_type == "str":
        v = str(value).strip()
        return v if v else None
    if expected_type == "num":
        try:
            if value == "":
                return None
            return float(value)
        except Exception:
            return None
    return value


def _get_category_from_request(request, obj=None):
    """
    Decide category in priority order:
    1) POSTed category (when submitting form)
    2) ?category= in URL (when page reloads after dropdown change)
    3) existing object category (edit)
    4) default Other
    """
    if request and request.method == "POST":
        c = request.POST.get("category")
        if c:
            return c

    if request:
        c = request.GET.get("category")
        if c:
            return c

    if obj and getattr(obj, "category", None):
        return obj.category

    return "Other"


# ============================================================
# ✅ Dynamic Product Admin Form
# ============================================================
class ProductAdminForm(forms.ModelForm):
    """
    Dynamic admin form:
    - Builds extra spec fields based on category.
    - Saves them into Product.specs as JSON.
    """

    class Meta:
        model = Product
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        # ProductAdmin injects request here
        self.request = kwargs.pop("request", None)
        super().__init__(*args, **kwargs)

        category = _get_category_from_request(self.request, obj=self.instance)
        schema = CATEGORY_SPEC_SCHEMA.get(category) or CATEGORY_SPEC_SCHEMA["Other"]

        # Specs textarea: optional + helpful note
        if "specs" in self.fields:
            self.fields["specs"].required = False
            self.fields["specs"].help_text = (
                "Auto-generated from the fields below. You can still paste JSON here if you want."
            )

        existing_specs = getattr(self.instance, "specs", None) or {}

        # Create dynamic fields (prefixed so no naming collision)
        def add_spec_field(key, t, required: bool):
            field_name = f"spec__{key}"
            if t == "num":
                self.fields[field_name] = forms.FloatField(required=required)
            else:
                self.fields[field_name] = forms.CharField(required=required)

            # Prefill existing specs when editing
            if key in existing_specs:
                self.initial[field_name] = existing_specs.get(key)

            # Better label
            self.fields[field_name].label = f"{key.replace('_', ' ').title()}"

        for k, t in schema.get("required", {}).items():
            add_spec_field(k, t, required=True)

        for k, t in schema.get("optional", {}).items():
            add_spec_field(k, t, required=False)

    def clean_specs(self):
        """
        Accept either:
        - JSON pasted in specs textarea, OR
        - Our dynamic spec__* fields (preferred)
        """
        specs_raw = self.cleaned_data.get("specs")

        # If admin textarea is a string, parse it safely
        if isinstance(specs_raw, str) and specs_raw.strip():
            try:
                parsed = json.loads(specs_raw)
                if not isinstance(parsed, dict):
                    raise ValueError()
                return parsed
            except Exception:
                raise ValidationError(
                    "Specs must be valid JSON object like: {\"brand\":\"Samsung\"}"
                )

        # If it's already dict (JSONField in some admin versions)
        if isinstance(specs_raw, dict):
            return specs_raw

        return {}

    def clean(self):
        cleaned = super().clean()
        category = cleaned.get("category") or _get_category_from_request(self.request, obj=self.instance)
        category = category or "Other"
        schema = CATEGORY_SPEC_SCHEMA.get(category) or CATEGORY_SPEC_SCHEMA["Other"]

        required = schema.get("required", {})
        optional = schema.get("optional", {})

        # Dynamic fields exist?
        has_dynamic = any(k.startswith("spec__") for k in self.fields.keys())

        if has_dynamic:
            specs = {}

            # required fields
            for key, t in required.items():
                v = _coerce(t, cleaned.get(f"spec__{key}"))
                if v is None:
                    raise ValidationError({f"spec__{key}": f"'{key}' is required for {category}."})
                specs[key] = v

            # optional fields
            for key, t in optional.items():
                v = _coerce(t, cleaned.get(f"spec__{key}"))
                if v is not None:
                    specs[key] = v

            cleaned["specs"] = specs
        else:
            incoming = cleaned.get("specs") or {}
            if not isinstance(incoming, dict):
                raise ValidationError({"specs": "Specs must be a JSON object."})
            cleaned["specs"] = incoming

        return cleaned


# ============================================================
# ✅ Product Admin (Jiji-style category reload + dynamic fieldsets)
# ============================================================
@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    form = ProductAdminForm
    list_display = ("id", "name", "category", "price", "stock", "vendor", "created_at")
    list_filter = ("category", "created_at")
    search_fields = ("name", "description", "vendor__username")
    readonly_fields = ("created_at",)

    # Base fieldsets (dynamic spec fields are injected automatically)
    base_fieldsets = (
        ("Basic", {"fields": ("name", "description", "category", "specs")}),
        ("Pricing", {"fields": ("price", "old_price", "rating", "stock")}),
        ("Images", {"fields": ("image", "image2", "image3", "image4", "image5")}),
        ("Ownership", {"fields": ("vendor", "created_at")}),
    )

    def get_form(self, request, obj=None, **kwargs):
        """
        Inject request into the form so it can read ?category=Phones
        and build correct dynamic fields on page reload.
        """
        form = super().get_form(request, obj, **kwargs)

        class RequestInjectedForm(form):
            def __init__(self2, *args, **kw):
                kw["request"] = request
                super().__init__(*args, **kw)

        return RequestInjectedForm

    def get_fieldsets(self, request, obj=None):
        """
        Make sure dynamic fields show up in the admin UI.
        Inject spec__* fields under the 'Basic' section after 'specs'.
        """
        category = _get_category_from_request(request, obj=obj)
        schema = CATEGORY_SPEC_SCHEMA.get(category) or CATEGORY_SPEC_SCHEMA["Other"]

        spec_fields = []
        for k in schema.get("required", {}).keys():
            spec_fields.append(f"spec__{k}")
        for k in schema.get("optional", {}).keys():
            spec_fields.append(f"spec__{k}")

        fieldsets = []
        for title, opts in self.base_fieldsets:
            fields = list(opts.get("fields", ()))

            if title == "Basic":
                # Put dynamic spec fields right after 'specs'
                if "specs" in fields:
                    idx = fields.index("specs") + 1
                else:
                    idx = len(fields)

                for f in spec_fields:
                    if f not in fields:
                        fields.insert(idx, f)
                        idx += 1

                opts = {**opts, "fields": tuple(fields)}

            fieldsets.append((title, opts))

        return tuple(fieldsets)

    class Media:
        # ✅ This makes category change reload the page (Jiji behavior)
        js = ("orders/admin_product_specs.js",)


# ============================================================
# PartnerListing Admin
# ============================================================
@admin.register(PartnerListing)
class PartnerListingAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "partner",
        "product",
        "markup",
        "final_price",
        "sales_count",
        "total_profit",
        "created_at",
    )
    search_fields = ("partner__username", "product__name", "referral_code")
    list_filter = ("created_at",)


# ============================================================
# Order Admin
# ============================================================
@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "status", "payment_method", "total_amount", "created_at")
    list_filter = ("status", "payment_method", "created_at")
    search_fields = ("user__username", "id")


# ============================================================
# OrderItem Admin
# ============================================================
@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "order",
        "product",
        "product_name_snapshot",
        "price",
        "quantity",
        "partner",
        "created_at",
    )
    search_fields = ("product_name_snapshot", "order__id")
    list_filter = ("created_at",)
