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
# USER SERIALIZER (LIGHT VERSION)
# ------------------------------
class UserMiniSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "username"]  # Add avatar later if you want


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
# LIKE SERIALIZER
# ------------------------------
class VideoLikeSerializer(serializers.ModelSerializer):
    class Meta:
        model = VideoLike
        fields = ["id", "user", "video", "created_at"]


# ------------------------------
# SAVE SERIALIZER
# ------------------------------
class VideoSaveSerializer(serializers.ModelSerializer):
    class Meta:
        model = VideoSave
        fields = ["id", "user", "video", "created_at"]


# ------------------------------
# VIDEO REVIEW SERIALIZER (MAIN)
# ------------------------------
class VideoReviewSerializer(serializers.ModelSerializer):
    user = UserMiniSerializer(read_only=True)
    hashtags = HashtagSerializer(many=True, read_only=True)

    # For upload (only accept hashtag list, not full objects)
    hashtag_ids = serializers.ListField(
        child=serializers.IntegerField(),
        write_only=True,
        required=False,
    )

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
            "product_id",
            "product_name",
            "product_image_url",
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
            "likes_count",
            "comments_count",
            "views_count",
            "saves_count",
            "shares_count",
            "created_at",
            "user",
        ]

    # Attach hashtags on create
    def create(self, validated_data):
        hashtag_ids = validated_data.pop("hashtag_ids", [])
        video = VideoReview.objects.create(**validated_data)

        if hashtag_ids:
            video.hashtags.set(hashtag_ids)

        return video


# ------------------------------
# VIEW SERIALIZER
# ------------------------------
class VideoViewSerializer(serializers.ModelSerializer):
    class Meta:
        model = VideoView
        fields = ["id", "user", "video", "created_at"]


# ------------------------------
# FOLLOW SERIALIZER
# ------------------------------
class UserFollowSerializer(serializers.ModelSerializer):
    follower = UserMiniSerializer(read_only=True)
    following = UserMiniSerializer(read_only=True)

    class Meta:
        model = UserFollow
        fields = ["id", "follower", "following", "created_at"]
