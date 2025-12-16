# orders/admin.py
import json
from django.contrib import admin
from django import forms
from django.core.exceptions import ValidationError

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
            # admin fields may send "" → treat as None
            if value == "":
                return None
            return float(value)
        except Exception:
            return None
    return value


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
        super().__init__(*args, **kwargs)

        # Category comes from:
        # 1) bound POST data (when submitting)
        # 2) instance (when editing)
        # 3) initial/query param fallback
        category = None
        if self.data.get("category"):
            category = self.data.get("category")
        elif getattr(self.instance, "category", None):
            category = self.instance.category
        else:
            category = self.initial.get("category") or "Other"

        category = category or "Other"
        schema = CATEGORY_SPEC_SCHEMA.get(category) or CATEGORY_SPEC_SCHEMA["Other"]

        # Make specs field optional + show nice help
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

            # prefill from existing specs if editing
            if key in existing_specs:
                self.initial[field_name] = existing_specs.get(key)

            # nicer label
            self.fields[field_name].label = f"Spec • {key}"

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
                raise ValidationError("Specs must be valid JSON object like: {\"brand\":\"Samsung\"}")

        # If it's already dict (JSONField in some admin versions)
        if isinstance(specs_raw, dict):
            return specs_raw

        return {}

    def clean(self):
        cleaned = super().clean()
        category = cleaned.get("category") or "Other"
        schema = CATEGORY_SPEC_SCHEMA.get(category) or CATEGORY_SPEC_SCHEMA["Other"]

        # Build specs from dynamic fields
        specs = {}
        required = schema.get("required", {})
        optional = schema.get("optional", {})

        # If dynamic fields exist, they win
        has_dynamic = any(k.startswith("spec__") for k in self.cleaned_data.keys())
        if has_dynamic:
            # required
            for key, t in required.items():
                v = _coerce(t, self.cleaned_data.get(f"spec__{key}"))
                if v is None:
                    raise ValidationError({f"spec__{key}": f"'{key}' is required for {category}."})
                specs[key] = v

            # optional
            for key, t in optional.items():
                v = _coerce(t, self.cleaned_data.get(f"spec__{key}"))
                if v is not None:
                    specs[key] = v

            cleaned["specs"] = specs
        else:
            # No dynamic fields (maybe category=Other) → keep textarea JSON
            incoming = cleaned.get("specs") or {}
            if not isinstance(incoming, dict):
                raise ValidationError({"specs": "Specs must be a JSON object."})
            cleaned["specs"] = incoming

        return cleaned


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    form = ProductAdminForm
    list_display = ("id", "name", "category", "price", "stock", "vendor", "created_at")
    list_filter = ("category", "created_at")
    search_fields = ("name", "description", "vendor__username")
    readonly_fields = ("created_at",)

    fieldsets = (
        ("Basic", {"fields": ("name", "description", "category", "specs")}),
        ("Pricing", {"fields": ("price", "old_price", "rating", "stock")}),
        ("Images", {"fields": ("image", "image2", "image3", "image4", "image5")}),
        ("Ownership", {"fields": ("vendor", "created_at")}),
    )


@admin.register(PartnerListing)
class PartnerListingAdmin(admin.ModelAdmin):
    list_display = ("id", "partner", "product", "markup", "final_price", "sales_count", "total_profit", "created_at")
    search_fields = ("partner__username", "product__name", "referral_code")
    list_filter = ("created_at",)


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "status", "payment_method", "total_amount", "created_at")
    list_filter = ("status", "payment_method", "created_at")
    search_fields = ("user__username", "id")


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ("id", "order", "product", "product_name_snapshot", "price", "quantity", "partner", "created_at")
    search_fields = ("product_name_snapshot", "order__id")
    list_filter = ("created_at",)
