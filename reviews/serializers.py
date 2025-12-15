from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.db.models import Count

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


# ============================================================
# USER MINI SERIALIZER (FAST + followers_count + is_following)
# ============================================================
class UserMiniSerializer(serializers.ModelSerializer):
    avatar = serializers.SerializerMethodField()
    followers_count = serializers.SerializerMethodField()
    is_following = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "username", "avatar", "followers_count", "is_following"]

    def _get_request(self):
        return self.context.get("request") if isinstance(self.context, dict) else None

    def _get_request_user(self):
        req = self._get_request()
        if not req or not hasattr(req, "user") or not req.user:
            return None
        return req.user

    def get_avatar(self, obj):
        """
        Priority:
        1) Profile.profile_picture (absolute URL if possible)
        2) ui-avatars fallback
        """
        req = self._get_request()

        try:
            profile = getattr(obj, "profile", None)
            pic = getattr(profile, "profile_picture", None)
            if pic:
                try:
                    url = pic.url
                except Exception:
                    url = str(pic)

                if req and isinstance(url, str) and url.startswith("/"):
                    return req.build_absolute_uri(url)

                return url
        except Exception:
            pass

        return f"https://ui-avatars.com/api/?name={getattr(obj, 'username', 'User')}"

    def get_followers_count(self, obj):
        """
        Uses precomputed context map if provided to avoid N+1 queries.
        context["followers_count_map"] = { "<user_id>": <count>, ... }
        """
        try:
            m = self.context.get("followers_count_map") if isinstance(self.context, dict) else None
            if isinstance(m, dict):
                v = m.get(str(obj.id))
                if v is not None:
                    return int(v)
        except Exception:
            pass

        # Fallback (works but slower)
        try:
            return UserFollow.objects.filter(following=obj).count()
        except Exception:
            return 0

    def get_is_following(self, obj):
        """
        Uses precomputed following set if provided.
        context["following_id_set"] = set(["2","5",...]) meaning request.user follows these.
        """
        user = self._get_request_user()
        if not user or not user.is_authenticated:
            return False

        try:
            s = self.context.get("following_id_set") if isinstance(self.context, dict) else None
            if isinstance(s, (set, list, tuple)):
                return str(obj.id) in set(map(str, s))
        except Exception:
            pass

        # Fallback
        try:
            return UserFollow.objects.filter(follower=user, following=obj).exists()
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

    hashtag_ids = serializers.ListField(
        child=serializers.IntegerField(),
        write_only=True,
        required=False
    )

    product_id = serializers.SerializerMethodField()
    product_name = serializers.SerializerMethodField()
    product_image_url = serializers.SerializerMethodField()
    review_product_id = serializers.SerializerMethodField()

    # Keep old naming
    is_liked = serializers.SerializerMethodField()
    is_saved = serializers.SerializerMethodField()

    # Frontend expects these
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

    def _get_request_user(self):
        req = self.context.get("request") if isinstance(self.context, dict) else None
        if not req or not hasattr(req, "user") or not req.user:
            return None
        return req.user

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

    def get_is_liked(self, obj):
        user = self._get_request_user()
        if not user or not user.is_authenticated:
            return False

        # ✅ Use precomputed map if provided
        try:
            liked_map = self.context.get("liked_map") if isinstance(self.context, dict) else None
            if isinstance(liked_map, dict):
                v = liked_map.get(str(obj.id))
                if v is not None:
                    return bool(v)
        except Exception:
            pass

        return VideoLike.objects.filter(user=user, video=obj).exists()

    def get_is_saved(self, obj):
        user = self._get_request_user()
        if not user or not user.is_authenticated:
            return False

        # ✅ Use precomputed map if provided
        try:
            saved_map = self.context.get("saved_map") if isinstance(self.context, dict) else None
            if isinstance(saved_map, dict):
                v = saved_map.get(str(obj.id))
                if v is not None:
                    return bool(v)
        except Exception:
            pass

        return VideoSave.objects.filter(user=user, video=obj).exists()

    def get_user_liked(self, obj):
        return self.get_is_liked(obj)

    def get_user_saved(self, obj):
        return self.get_is_saved(obj)
