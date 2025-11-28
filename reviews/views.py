from django.db import transaction
from django.db.models import F
from django.contrib.auth import get_user_model

from rest_framework.decorators import api_view, permission_classes, parser_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response
from rest_framework import status
from rest_framework.pagination import PageNumberPagination

import cloudinary
import cloudinary.uploader
from cloudinary.utils import cloudinary_url

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

from orders.models import Product  # ⭐ needed for linking purchased product

User = get_user_model()


# ============================================================
# Pagination
# ============================================================
class StandardResultsSetPagination(PageNumberPagination):
    page_size = 10
    max_page_size = 50


# ============================================================
# UPLOAD REVIEW (UPDATED)
# ============================================================
@api_view(["POST"])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser, FormParser])
@transaction.atomic
def upload_video_review(request):
    """
    Upload video + thumbnail + product information.
    Handles review_product_id for linking to actual purchased item.
    """

    user = request.user

    # -----------------------------
    # Validate video
    # -----------------------------
    file_obj = request.FILES.get("video")
    if not file_obj:
        return Response(
            {"detail": "No video file provided (form-data field: video)."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    caption = request.data.get("caption", "").strip()
    location = request.data.get("location", "").strip()
    country_code = request.data.get("country_code", "").strip()

    # Product metadata
    review_product_id = request.data.get("review_product_id")  # NEW
    product_id_raw = request.data.get("product_id")
    product_name = request.data.get("product_name", "").strip()
    product_image_url = request.data.get("product_image_url", "").strip()

    # Thumbnail options
    thumbnail_time_ms = request.data.get("thumbnail_time_ms")
    custom_thumbnail = request.FILES.get("thumbnail_image")

    # -----------------------------
    # Hashtags
    # -----------------------------
    hashtags_raw = request.data.get("hashtags", "")
    hashtag_objs = []
    if hashtags_raw:
        parts = [h.strip().lstrip("#") for h in hashtags_raw.split(",")]
        for name in parts:
            if name:
                tag, _ = Hashtag.objects.get_or_create(name=name)
                hashtag_objs.append(tag)

    # -----------------------------
    # Upload to Cloudinary
    # -----------------------------
    try:
        upload_result = cloudinary.uploader.upload_large(
            file_obj,
            resource_type="video",
            folder="kudiway/reviews",
            eager=[{"format": "mp4"}],
        )
    except Exception as e:
        return Response(
            {"detail": f"Cloudinary upload failed: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    public_id = upload_result.get("public_id")
    video_url = upload_result.get("secure_url")
    duration = int(upload_result.get("duration", 0))

    # -----------------------------
    # Generate default thumbnail
    # -----------------------------
    thumbnail_url, _ = cloudinary_url(
        public_id,
        resource_type="video",
        format="jpg",
        transformation={
            "width": 720,
            "height": 1280,
            "crop": "fill",
            "gravity": "auto",
        },
        secure=True,
    )

    # -----------------------------
    # Override with custom thumbnail
    # -----------------------------
    if custom_thumbnail:
        try:
            thumb_up = cloudinary.uploader.upload(
                custom_thumbnail,
                folder="kudiway/reviews/thumbnails",
                resource_type="image",
            )
            thumbnail_url = thumb_up.get("secure_url")
        except Exception as e:
            return Response(
                {"detail": f"Thumbnail upload failed: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    # -----------------------------
    # Try linking to Product model
    # -----------------------------
    product_obj = None

    if review_product_id:
        try:
            product_obj = Product.objects.get(id=review_product_id)
        except Product.DoesNotExist:
            product_obj = None

    # fallback: try product_id_raw
    elif product_id_raw:
        try:
            product_obj = Product.objects.get(id=product_id_raw)
        except Product.DoesNotExist:
            product_obj = None

    # -----------------------------
    # Create review record
    # -----------------------------
    video = VideoReview.objects.create(
        user=user,
        video_url=video_url,
        thumbnail_url=thumbnail_url,
        cloudinary_public_id=public_id,
        caption=caption,
        location=location,
        duration_seconds=duration,
        country_code=country_code,

        # Product linking
        review_product_id=review_product_id,
        product=product_obj,
        product_id=int(product_id_raw) if str(product_id_raw).isdigit() else None,
        product_name=product_name,
        product_image_url=product_image_url,

        # Thumbnail metadata
        thumbnail_time_ms=thumbnail_time_ms,
    )

    if hashtag_objs:
        video.hashtags.set([h.id for h in hashtag_objs])

    serializer = VideoReviewSerializer(video, context={"request": request})
    return Response(serializer.data, status=201)


# ============================================================
# FEEDS (unchanged)
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
    serializer = VideoReviewSerializer(page, many=True, context={"request": request})
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
    serializer = VideoReviewSerializer(page, many=True, context={"request": request})
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
    serializer = VideoReviewSerializer(page, many=True, context={"request": request})
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
        return Response({"detail": "Video not found."}, status=404)

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
    text = request.data.get("text", "").strip()

    if not text:
        return Response({"detail": "Comment cannot be empty."}, status=400)

    try:
        video = VideoReview.objects.get(id=video_id, is_deleted=False)
    except VideoReview.DoesNotExist:
        return Response({"detail": "Video not found."}, status=404)

    comment = VideoComment.objects.create(video=video, user=user, text=text)

    video.comments_count = VideoComment.objects.filter(
        video=video, is_deleted=False
    ).count()
    video.save(update_fields=["comments_count"])

    serializer = VideoCommentSerializer(comment)
    return Response(serializer.data, status=201)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_comments(request, video_id):
    try:
        video = VideoReview.objects.get(id=video_id, is_deleted=False)
    except VideoReview.DoesNotExist:
        return Response({"detail": "Video not found."}, status=404)

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
        return Response({"detail": "Comment not found."}, status=404)

    if comment.user != user:
        return Response(
            {"detail": "You can only delete your own comments."},
            status=403,
        )

    comment.is_deleted = True
    comment.save(update_fields=["is_deleted"])

    video = comment.video
    video.comments_count = VideoComment.objects.filter(
        video=video, is_deleted=False
    ).count()
    video.save(update_fields=["comments_count"])

    return Response({"detail": "Comment deleted."}, status=200)


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
        return Response({"detail": "Video not found."}, status=404)

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
        return Response({"detail": "Video not found."}, status=404)

    VideoView.objects.create(video=video, user=user)

    video.views_count = VideoView.objects.filter(video=video).count()
    video.save(update_fields=["views_count"])

    return Response({"views_count": video.views_count})


# ============================================================
# FOLLOW
# ============================================================
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def toggle_follow(request, user_id):
    follower = request.user

    if follower.id == user_id:
        return Response({"detail": "You cannot follow yourself."}, status=400)

    try:
        target_user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return Response({"detail": "User not found."}, status=404)

    follow, created = UserFollow.objects.get_or_create(
        follower=follower,
        following=target_user,
    )

    if not created:
        follow.delete()
        return Response({"following": False})

    return Response({"following": True})


# ============================================================
# CREATOR VIDEOS
# ============================================================
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def creator_videos(request, user_id):
    try:
        creator = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return Response({"detail": "User not found."}, status=404)

    videos = VideoReview.objects.filter(
        user=creator,
        is_public=True,
        is_deleted=False,
    ).order_by("-created_at")

    serializer = VideoReviewSerializer(videos, many=True, context={"request": request})
    return Response(serializer.data)
