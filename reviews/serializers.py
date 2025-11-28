from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import (
    VideoReview,
    VideoLike,
    VideoComment,
    VideoSave,
    VideoView,
    UserFollow,
    Hashtag,
)

from orders.models import Product  # for FK fallback

User = get_user_model()


# ============================================================
# USER MINI SERIALIZER
# ============================================================
class UserMiniSerializer(serializers.ModelSerializer):
    avatar = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "username", "avatar"]

    def get_avatar(self, obj):
        return f"https://ui-avatars.com/api/?name={obj.username}"
    

# ============================================================
# HASHTAG SERIALIZER
# ============================================================
class HashtagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Hashtag
        fields = ["id", "name", "slug"]


# ============================================================
# COMMENT SERIALIZER
# ============================================================
class VideoCommentSerializer(serializers.ModelSerializer):
    user = UserMiniSerializer(read_only=True)

    class Meta:
        model = VideoComment
        fields = [
            "id",
            "user",
            "text",
            "created_at",
            "is_deleted",
            "parent",
        ]


# ============================================================
# MAIN VIDEO REVIEW SERIALIZER
# ============================================================
class VideoReviewSerializer(serializers.ModelSerializer):
    user = UserMiniSerializer(read_only=True)
    hashtags = HashtagSerializer(read_only=True, many=True)

    # For POST
    hashtag_ids = serializers.ListField(
        child=serializers.IntegerField(),
        write_only=True,
        required=False
    )

    # Computed fields
    product_id = serializers.SerializerMethodField()
    product_name = serializers.SerializerMethodField()
    product_image_url = serializers.SerializerMethodField()
    review_product_id = serializers.SerializerMethodField()

    # UX helpers
    is_liked = serializers.SerializerMethodField()
    is_saved = serializers.SerializerMethodField()

    class Meta:
        model = VideoReview
        fields = [
            "id",
            "user",
            "video_url",
            "thumbnail_url",
            "thumbnail_time_ms",
            "caption",
            "location",
            "duration_seconds",

            # ⭐ Product reference fields
            "review_product_id",
            "product_id",
            "product_name",
            "product_image_url",

            # Stats
            "likes_count",
            "comments_count",
            "views_count",
            "saves_count",
            "shares_count",

            # UX
            "is_liked",
            "is_saved",

            "is_public",
            "is_featured",
            "created_at",

            "hashtags",
            "hashtag_ids",
        ]

        read_only_fields = [
            "id",
            "user",
            "likes_count",
            "comments_count",
            "views_count",
            "saves_count",
            "shares_count",
            "created_at",
        ]


    # ============================================================
    # CREATE — PACKAGES HASHTAGS
    # ============================================================
    def create(self, validated_data):
        hashtag_ids = validated_data.pop("hashtag_ids", [])
        review = VideoReview.objects.create(**validated_data)

        if hashtag_ids:
            review.hashtags.set(hashtag_ids)

        return review


    # ============================================================
    # PRODUCT INFO METHODS
    # ============================================================
    def get_review_product_id(self, obj):
        return obj.review_product_id


    def get_product_id(self, obj):
        """
        Priority:
        1. Explicit product_id saved on review
        2. Linked Product FK
        """
        if obj.product_id:
            return obj.product_id

        if obj.product:
            return obj.product.id

        return None


    def get_product_name(self, obj):
        """
        Priority:
        1. Snapshot saved during upload
        2. product FK
        """
        if obj.product_name:
            return obj.product_name

        if obj.product:
            return obj.product.name

        return None


    def get_product_image_url(self, obj):
        """
        Priority:
        1. Snapshot saved at upload time (stable)
        2. Product.image current
        """
        if obj.product_image_url:
            return obj.product_image_url

        if obj.product and getattr(obj.product, "image", None):
            try:
                return obj.product.image.url
            except:
                return None

        return None


    # ============================================================
    # UX — Like / Save status
    # ============================================================
    def get_is_liked(self, obj):
        user = self.context["request"].user
        if not user.is_authenticated:
            return False
        return VideoLike.objects.filter(user=user, video=obj).exists()


    def get_is_saved(self, obj):
        user = self.context["request"].user
        if not user.is_authenticated:
            return False
        return VideoSave.objects.filter(user=user, video=obj).exists()
