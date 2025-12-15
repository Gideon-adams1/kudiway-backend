import traceback

from django.conf import settings
from django.db.models import F
from django.contrib.auth import get_user_model

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework import status
from rest_framework.pagination import PageNumberPagination

import cloudinary.uploader

from .models import (
    VideoReview,
    Hashtag,
    UserFollow,
    VideoLike,
    VideoSave,
    VideoView,
    VideoComment,
)
from .serializers import VideoReviewSerializer, VideoCommentSerializer

from orders.models import OrderItem  # we link reviews to OrderItem snapshots

User = get_user_model()


# ============================================================
# Pagination
# ============================================================
class StandardResultsSetPagination(PageNumberPagination):
    page_size = 10
    max_page_size = 50


# ============================================================
# Helpers
# ============================================================
def normalize_media_value(value):
    """
    Turn any 'image' / 'file' / 'Cloudinary' style object into a plain string URL.
    Prevents 'Value is an object, expected a String' on the frontend.
    """
    if not value:
        return ""

    if isinstance(value, str):
        return value

    if isinstance(value, dict):
        # common keys from Cloudinary / DRF serializers
        for key in ("secure_url", "url", "path", "src", "image", "file"):
            v = value.get(key)
            if isinstance(v, str):
                return v

    # Fallback: string representation
    return str(value)


def resolve_order_item_for_review(raw_pid):
    """
    Resolve the correct OrderItem for this review.

    raw_pid comes from frontend: product_id or review_product_id (string like "13").

    We avoid MultipleObjectsReturned by:
      1) First trying review_product_id filter and taking the latest (highest id)
      2) If none, trying primary key lookup (id=<int>)
    """
    pid_str = str(raw_pid)

    # First: use review_product_id matches, pick the latest
    qs = OrderItem.objects.filter(review_product_id=pid_str).order_by("-id")
    if qs.exists():
        return qs.first()

    # Second: maybe the frontend sent the actual OrderItem pk (numeric)
    try:
        pid_int = int(pid_str)
    except (ValueError, TypeError):
        pid_int = None

    if pid_int is not None:
        try:
            return OrderItem.objects.get(id=pid_int)
        except OrderItem.DoesNotExist:
            return None

    return None


# ============================================================
# 🎥 UPLOAD REVIEW (FINAL + ROBUST)
# ============================================================
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def upload_review(request):
    try:
        user = request.user
        data = request.data

        print("📥 Incoming review upload:", data)

        # -----------------------------------------------------
        # 1) Support both product_id and review_product_id from app
        # -----------------------------------------------------
        raw_pid = data.get("product_id") or data.get("review_product_id")

        if not raw_pid:
            return Response(
                {
                    "error": "Missing product identifier. "
                    "Send 'product_id' or 'review_product_id' from the app."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # -----------------------------------------------------
        # 2) Resolve OrderItem snapshot safely (no MultipleObjectsReturned)
        # -----------------------------------------------------
        item = resolve_order_item_for_review(raw_pid)

        if not item:
            return Response(
                {
                    "error": (
                        "Invalid product identifier — no matching OrderItem found. "
                        "Make sure review_product_id on OrderItem matches what the app sends."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # These field names must match your OrderItem model
        product_name = getattr(item, "product_name_snapshot", None)
        product_image_raw = getattr(item, "product_image_snapshot", None)

        if not product_name:
            return Response(
                {"error": "Product name missing from OrderItem snapshot."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        product_image = normalize_media_value(product_image_raw)

        print("🧾 Matched OrderItem:", item.id, product_name, product_image)

        # -----------------------------------------------------
        # 3) Validate video file
        # -----------------------------------------------------
        video_file = request.FILES.get("video")
        if not video_file:
            return Response(
                {"error": "Video file missing."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        thumbnail_image = request.FILES.get("thumbnail_image")
        thumbnail_time = data.get("thumbnail_time_ms")

        # -----------------------------------------------------
        # 4) Upload video → Cloudinary
        # -----------------------------------------------------
        uploaded_video = cloudinary.uploader.upload_large(
            video_file,
            resource_type="video",
            folder="reviews/videos/",
        )

        video_url = uploaded_video["secure_url"]
        public_id = uploaded_video["public_id"]

        print("✅ Video uploaded:", video_url)

        # -----------------------------------------------------
        # 5) Thumbnail: either uploaded image or auto-generated frame
        # -----------------------------------------------------
        if thumbnail_image:
            thumb = cloudinary.uploader.upload(
                thumbnail_image,
                folder="reviews/thumbnails/",
                resource_type="image",
            )
            thumbnail_url = thumb["secure_url"]
        else:
            if thumbnail_time:
                thumbnail_url = (
                    f"https://res.cloudinary.com/{settings.CLOUDINARY_CLOUD_NAME}"
                    f"/video/upload/so_{thumbnail_time}/{public_id}.jpg"
                )
            else:
                thumbnail_url = ""

        # -----------------------------------------------------
        # 6) Duration
        # -----------------------------------------------------
        raw_duration = data.get("duration_seconds", 0)
        try:
            duration_seconds = int(raw_duration)
        except Exception:
            duration_seconds = 0

        # -----------------------------------------------------
        # 7) Create VideoReview object
        # -----------------------------------------------------
        caption = data.get("caption", "")
        location = data.get("location", "")

        review = VideoReview.objects.create(
            user=user,
            video_url=video_url,
            thumbnail_url=thumbnail_url,
            cloudinary_public_id=public_id,
            caption=caption,
            location=location,
            duration_seconds=duration_seconds,
            # Product metadata from order snapshot
            review_product_id=str(item.review_product_id),
            product=None,  # not linking to Product model here
            product_name=product_name,
            product_image_url=product_image,
            thumbnail_time_ms=thumbnail_time,
            is_public=True,
        )

        print("🎉 REVIEW SAVED:", review.id)

        return Response(
            {"message": "Review uploaded successfully!", "id": review.id},
            status=status.HTTP_201_CREATED,
        )

    except Exception as e:
        print("❌ UPLOAD REVIEW ERROR:", e)
        print(traceback.format_exc())
        return Response(
            {
                "error": "Server failed to upload review.",
                "details": str(e),
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


# ============================================================
# FEEDS
# ============================================================
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def feed_for_you(request):
    videos = VideoReview.objects.filter(
        is_public=True,
        is_deleted=False,
        is_approved=True,
    ).order_by("-created_at")

    paginator = StandardResultsSetPagination()
    page = paginator.paginate_queryset(videos, request)
    serializer = VideoReviewSerializer(
        page, many=True, context={"request": request}
    )
    return paginator.get_paginated_response(serializer.data)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def feed_following(request):
    user = request.user

    following_ids = UserFollow.objects.filter(
        follower=user
    ).values_list("following_id", flat=True)

    videos = VideoReview.objects.filter(
        user_id__in=following_ids,
        is_public=True,
        is_deleted=False,
    ).order_by("-created_at")

    paginator = StandardResultsSetPagination()
    page = paginator.paginate_queryset(videos, request)
    serializer = VideoReviewSerializer(
        page, many=True, context={"request": request}
    )
    return paginator.get_paginated_response(serializer.data)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def feed_trending(request):
    videos = VideoReview.objects.filter(
        is_public=True,
        is_deleted=False,
    ).order_by(
        -(F("likes_count") * 2 + F("comments_count") * 3 + F("views_count"))
    )

    paginator = StandardResultsSetPagination()
    page = paginator.paginate_queryset(videos, request)
    serializer = VideoReviewSerializer(
        page, many=True, context={"request": request}
    )
    return paginator.get_paginated_response(serializer.data)


# ============================================================
# LIKES
# ============================================================
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def toggle_like(request, video_id):
    user = request.user

    try:
        video = VideoReview.objects.get(id=video_id, is_deleted=False)
    except VideoReview.DoesNotExist:
        return Response(
            {"detail": "Video not found."},
            status=status.HTTP_404_NOT_FOUND,
        )

    like, created = VideoLike.objects.get_or_create(user=user, video=video)

    if not created:
        like.delete()
        video.likes_count = VideoLike.objects.filter(video=video).count()
        video.save(update_fields=["likes_count"])
        return Response({"liked": False, "likes_count": video.likes_count})

    video.likes_count = VideoLike.objects.filter(video=video).count()
    video.save(update_fields=["likes_count"])
    return Response({"liked": True, "likes_count": video.likes_count})


# ============================================================
# COMMENTS
# ============================================================
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def post_comment(request, video_id):
    user = request.user

    raw_text = request.data.get("text", "")
    text = raw_text.strip() if isinstance(raw_text, str) else str(raw_text).strip()

    if not text:
        return Response(
            {"detail": "Comment cannot be empty."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        video = VideoReview.objects.get(id=video_id, is_deleted=False)
    except VideoReview.DoesNotExist:
        return Response(
            {"detail": "Video not found."},
            status=status.HTTP_404_NOT_FOUND,
        )

    comment = VideoComment.objects.create(video=video, user=user, text=text)

    video.comments_count = VideoComment.objects.filter(
        video=video, is_deleted=False
    ).count()
    video.save(update_fields=["comments_count"])

    serializer = VideoCommentSerializer(comment)
    return Response(serializer.data, status=status.HTTP_201_CREATED)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_comments(request, video_id):
    try:
        video = VideoReview.objects.get(id=video_id, is_deleted=False)
    except VideoReview.DoesNotExist:
        return Response(
            {"detail": "Video not found."},
            status=status.HTTP_404_NOT_FOUND,
        )

    comments = VideoComment.objects.filter(
        video=video, is_deleted=False
    ).order_by("-created_at")
    serializer = VideoCommentSerializer(comments, many=True)
    return Response(serializer.data)


@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def delete_comment(request, comment_id):
    user = request.user

    try:
        comment = VideoComment.objects.get(id=comment_id, is_deleted=False)
    except VideoComment.DoesNotExist:
        return Response(
            {"detail": "Comment not found."},
            status=status.HTTP_404_NOT_FOUND,
        )

    if comment.user != user:
        return Response(
            {"detail": "You can only delete your own comments."},
            status=status.HTTP_403_FORBIDDEN,
        )

    comment.is_deleted = True
    comment.save(update_fields=["is_deleted"])

    video = comment.video
    video.comments_count = VideoComment.objects.filter(
        video=video, is_deleted=False
    ).count()
    video.save(update_fields=["comments_count"])

    return Response({"detail": "Comment deleted."}, status=status.HTTP_200_OK)


# ============================================================
# SAVES
# ============================================================
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def toggle_save(request, video_id):
    user = request.user

    try:
        video = VideoReview.objects.get(id=video_id, is_deleted=False)
    except VideoReview.DoesNotExist:
        return Response(
            {"detail": "Video not found."},
            status=status.HTTP_404_NOT_FOUND,
        )

    save_obj, created = VideoSave.objects.get_or_create(user=user, video=video)

    if not created:
        save_obj.delete()
        video.saves_count = VideoSave.objects.filter(video=video).count()
        video.save(update_fields=["saves_count"])
        return Response({"saved": False, "saves_count": video.saves_count})

    video.saves_count = VideoSave.objects.filter(video=video).count()
    video.save(update_fields=["saves_count"])
    return Response({"saved": True, "saves_count": video.saves_count})


# ============================================================
# VIEWS
# ============================================================
@api_view(["POST"])
@permission_classes([AllowAny])
def track_view(request, video_id):
    user = request.user if request.user.is_authenticated else None

    try:
        video = VideoReview.objects.get(id=video_id, is_deleted=False)
    except VideoReview.DoesNotExist:
        return Response(
            {"detail": "Video not found."},
            status=status.HTTP_404_NOT_FOUND,
        )

    VideoView.objects.create(video=video, user=user)

    video.views_count = VideoView.objects.filter(video=video).count()
    video.save(update_fields=["views_count"])

    return Response({"views_count": video.views_count})


# ============================================================
# FOLLOW ✅ FIXED: RETURN FOLLOWERS_COUNT + SHAPE FRONTEND EXPECTS
# ============================================================
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def toggle_follow(request, user_id):
    follower = request.user

    if follower.id == user_id:
        return Response(
            {"detail": "You cannot follow yourself."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        target_user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return Response(
            {"detail": "User not found."},
            status=status.HTTP_404_NOT_FOUND,
        )

    follow, created = UserFollow.objects.get_or_create(
        follower=follower,
        following=target_user,
    )

    if not created:
        follow.delete()
        followers_count = UserFollow.objects.filter(following=target_user).count()
        return Response(
            {
                "user": {
                    "id": target_user.id,
                    "is_following": False,
                    "followers_count": followers_count,
                },
                "following": False,          # kept for backward compatibility
                "followers_count": followers_count,  # kept for backward compatibility
            },
            status=status.HTTP_200_OK,
        )

    followers_count = UserFollow.objects.filter(following=target_user).count()
    return Response(
        {
            "user": {
                "id": target_user.id,
                "is_following": True,
                "followers_count": followers_count,
            },
            "following": True,            # kept for backward compatibility
            "followers_count": followers_count,  # kept for backward compatibility
        },
        status=status.HTTP_200_OK,
    )


# ============================================================
# CREATOR VIDEOS
# ============================================================
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def creator_videos(request, user_id):
    try:
        creator = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return Response(
            {"detail": "User not found."},
            status=status.HTTP_404_NOT_FOUND,
        )

    videos = VideoReview.objects.filter(
        user=creator,
        is_public=True,
        is_deleted=False,
    ).order_by("-created_at")

    serializer = VideoReviewSerializer(
        videos, many=True, context={"request": request}
    )
    return Response(serializer.data)
