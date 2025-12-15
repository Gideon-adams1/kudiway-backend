from rest_framework import serializers
from django.contrib.auth import get_user_model

from .models import (
    VideoReview,
    VideoLike,
    VideoComment,
    VideoSave,
    UserFollow,
    Hashtag,
)

User = get_user_model()


# ============================================================
# USER MINI SERIALIZER
# ============================================================
class UserMiniSerializer(serializers.ModelSerializer):
    avatar = serializers.SerializerMethodField()
    followers_count = serializers.SerializerMethodField()
    is_following = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "username", "avatar", "followers_count", "is_following"]

    def _req(self):
        return self.context.get("request") if isinstance(self.context, dict) else None

    def _abs_if_needed(self, url):
        req = self._req()
        if req and isinstance(url, str) and url.startswith("/"):
            try:
                return req.build_absolute_uri(url)
            except Exception:
                return url
        return url

    def get_avatar(self, obj):
        req = self._req()
        try:
            profile = getattr(obj, "profile", None)
            pic = getattr(profile, "profile_picture", None)
            if pic:
                try:
                    url = pic.url
                except Exception:
                    url = str(pic)

                url = self._abs_if_needed(url)
                return url if isinstance(url, str) else str(url)
        except Exception:
            pass

        username = getattr(obj, "username", "") or "User"
        return f"https://ui-avatars.com/api/?name={username}"

    def get_followers_count(self, obj):
        """
        ✅ IMPORTANT RULE:
        - If followers_count_map has a value for this user -> return it (even 0).
        - If followers_count_map DOES NOT contain this user -> return None (unknown),
          so the frontend never flashes fake 0.
        - Only fallback to DB count when map is not provided at all.
        """
        followers_map = self.context.get("followers_count_map") if isinstance(self.context, dict) else None

        # If the view provided the map, use it as source of truth:
        # - present in map => return int(value) (allow 0)
        # - missing from map => return None (unknown)
        if isinstance(followers_map, dict):
            if obj.id in followers_map:
                v = followers_map.get(obj.id)
                try:
                    return int(v) if v is not None else 0
                except Exception:
                    return 0
            return None  # ✅ do NOT default to 0

        # If no map at all, fallback to DB
        try:
            return UserFollow.objects.filter(following=obj).count()
        except Exception:
            return 0

    def get_is_following(self, obj):
        """
        Prefer: following_set from view context.
        Fallback: DB exists.
        """
        req = self._req()
        if not req or not getattr(req, "user", None) or not req.user.is_authenticated:
            return False

        following_set = self.context.get("following_set") if isinstance(self.context, dict) else None
        if isinstance(following_set, (set, list, tuple)):
            try:
                return obj.id in set(following_set)
            except Exception:
                return False

        try:
            return UserFollow.objects.filter(follower=req.user, following=obj).exists()
        except Exception:
            return False


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
        fields = ["id", "user", "text", "created_at", "is_deleted", "parent"]


# ============================================================
# MAIN VIDEO REVIEW SERIALIZER
# ============================================================
class VideoReviewSerializer(serializers.ModelSerializer):
    user = UserMiniSerializer(read_only=True)
    hashtags = HashtagSerializer(read_only=True, many=True)

    hashtag_ids = serializers.ListField(
        child=serializers.IntegerField(),
        write_only=True,
        required=False,
    )

    product_id = serializers.SerializerMethodField()
    product_name = serializers.SerializerMethodField()
    product_image_url = serializers.SerializerMethodField()
    review_product_id = serializers.SerializerMethodField()

    is_liked = serializers.SerializerMethodField()
    is_saved = serializers.SerializerMethodField()

    # aliases expected by your player
    user_liked = serializers.SerializerMethodField()
    user_saved = serializers.SerializerMethodField()

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
            "review_product_id",
            "product_id",
            "product_name",
            "product_image_url",
            "likes_count",
            "comments_count",
            "views_count",
            "saves_count",
            "shares_count",
            "is_liked",
            "is_saved",
            "user_liked",
            "user_saved",
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

    def create(self, validated_data):
        hashtag_ids = validated_data.pop("hashtag_ids", [])
        review = VideoReview.objects.create(**validated_data)
        if hashtag_ids:
            review.hashtags.set(hashtag_ids)
        return review

    def get_review_product_id(self, obj):
        return obj.review_product_id

    def get_product_id(self, obj):
        if getattr(obj, "product_id", None):
            return obj.product_id
        if getattr(obj, "product", None):
            return obj.product.id
        return None

    def get_product_name(self, obj):
        if getattr(obj, "product_name", None):
            return obj.product_name
        if getattr(obj, "product", None):
            return obj.product.name
        return None

    def get_product_image_url(self, obj):
        if getattr(obj, "product_image_url", None):
            return obj.product_image_url
        if getattr(obj, "product", None) and getattr(obj.product, "image", None):
            try:
                return obj.product.image.url
            except Exception:
                return None
        return None

    def _user(self):
        req = self.context.get("request") if isinstance(self.context, dict) else None
        return getattr(req, "user", None)

    def get_is_liked(self, obj):
        user = self._user()
        if not user or not user.is_authenticated:
            return False
        return VideoLike.objects.filter(user=user, video=obj).exists()

    def get_is_saved(self, obj):
        user = self._user()
        if not user or not user.is_authenticated:
            return False
        return VideoSave.objects.filter(user=user, video=obj).exists()

    def get_user_liked(self, obj):
        return self.get_is_liked(obj)

    def get_user_saved(self, obj):
        return self.get_is_saved(obj)
