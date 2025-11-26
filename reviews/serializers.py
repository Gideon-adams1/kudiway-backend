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

User = get_user_model()


# ------------------------------
# USER SERIALIZER
# ------------------------------
class UserMiniSerializer(serializers.ModelSerializer):
    avatar = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "username", "avatar"]

    def get_avatar(self, obj):
        # Add real avatar later when your user model has it
        return "https://ui-avatars.com/api/?name={}".format(obj.username)


# ------------------------------
# HASHTAG SERIALIZER
# ------------------------------
class HashtagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Hashtag
        fields = ["id", "name", "slug"]


# ------------------------------
# COMMENT SERIALIZER
# ------------------------------
class VideoCommentSerializer(serializers.ModelSerializer):
    user = UserMiniSerializer(read_only=True)

    class Meta:
        model = VideoComment
        fields = [
            "id",
            "user",
            "text",
            "created_at",
            "parent",
            "is_deleted",
        ]


# ------------------------------
# VIDEO REVIEW SERIALIZER
# ------------------------------
class VideoReviewSerializer(serializers.ModelSerializer):
    user = UserMiniSerializer(read_only=True)

    # nested hashtags
    hashtags = HashtagSerializer(many=True, read_only=True)

    # For upload
    hashtag_ids = serializers.ListField(
        child=serializers.IntegerField(), write_only=True, required=False
    )

    # FIXED FIELDS
    product_id = serializers.SerializerMethodField()
    product_name = serializers.SerializerMethodField()
    product_image_url = serializers.SerializerMethodField()

    class Meta:
        model = VideoReview
        fields = [
            "id",
            "user",
            "video_url",
            "thumbnail_url",
            "caption",
            "location",
            "duration_seconds",

            # PRODUCT INFO (auto-filled)
            "product_id",
            "product_name",
            "product_image_url",

            # social counters
            "likes_count",
            "comments_count",
            "views_count",
            "saves_count",
            "shares_count",

            "is_public",
            "is_featured",
            "created_at",

            "hashtags",
            "hashtag_ids",
        ]
        read_only_fields = [
            "user",
            "likes_count",
            "comments_count",
            "views_count",
            "saves_count",
            "shares_count",
            "created_at",
        ]

    # --------------------------
    # ATTACH HASHTAGS ON CREATE
    # --------------------------
    def create(self, validated_data):
        hashtag_ids = validated_data.pop("hashtag_ids", [])
        review = VideoReview.objects.create(**validated_data)

        if hashtag_ids:
            review.hashtags.set(hashtag_ids)

        return review

    # --------------------------
    # AUTO PRODUCT FIELDS
    # --------------------------
    def get_product_id(self, obj):
        return obj.product_id

    def get_product_name(self, obj):
        if obj.product_name:
            return obj.product_name
        if obj.product:
            return obj.product.name
        return None

    def get_product_image_url(self, obj):
        """
        Priority:
        1. Explicit snapshot saved during upload
        2. Product.image from Product model
        3. None
        """
        # If already stored snapshot
        if obj.product_image_url:
            return obj.product_image_url

        # If product still exists, pull image
        if obj.product and getattr(obj.product, "image", None):
            try:
                return obj.product.image.url
            except:
                return None

        return None
