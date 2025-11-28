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

from orders.models import OrderItem  # 🔧 only import what we know exists

User = get_user_model()


# ============================================================
# Pagination
# ============================================================
class StandardResultsSetPagination(PageNumberPagination):
    page_size = 10
    max_page_size = 50


# ============================================================
# 🎥 UPLOAD REVIEW (FINAL VERSION – FIXED)
# ============================================================
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def upload_review(request):
    try:
        user = request.user
        data = request.data

        print("📥 Incoming review upload:", data)

        # --------------------------------------------------
        # 1) Get product identifier from request
        #    Support both "product_id" and "review_product_id"
        # --------------------------------------------------
        raw_pid = data.get("product_id") or data.get("review_product_id")

        if not raw_pid:
            return Response(
                {"error": "Missing product identifier (product_id or review_product_id)."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        product_obj = None   # placeholder if you later support real Product FK
        product_name = None
        product_image = None

        # --------------------------------------------------
        # 2) If it's an "OI-xx" style id → use OrderItem
        #    (this matches your purchased-items API)
        # --------------------------------------------------
        try:
            item = OrderItem.objects.get(review_product_id=str(raw_pid))
            # Use the actual fields from your JSON response:
            # {
            #   "product_name": "...",
            #   "image": "..."
            # }
            product_name = getattr(item, "product_name", None)
            product_image = getattr(item, "image", None)
            print("🧾 Matched OrderItem for review:", item.id, product_name, product_image)
        except OrderItem.DoesNotExist:
            # If you later support real product IDs, you can add logic here.
            # For now, fail clearly if no matching OrderItem.
            return Response(
                {"error": "Invalid product identifier for review."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not product_name:
            return Response(
                {"error": "Product name missing from order item."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not product_image:
            product_image = ""

        # --------------------------------------------------
        # 3) Validate video file
        # --------------------------------------------------
        video_file = request.FILES.get("video")
        if not video_file:
            return Response(
                {"error": "Video file missing."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        thumbnail_image = request.FILES.get("thumbnail_image")
        thumbnail_time = data.get("thumbnail_time_ms")

        # --------------------------------------------------
        # 4) Upload video → Cloudinary
        # --------------------------------------------------
        uploaded_video = cloudinary.uploader.upload_large(
            video_file,
            resource_type="video",
            folder="reviews/videos/",
        )

        video_url = uploaded_video["secure_url"]
        public_id = uploaded_video["public_id"]
        print("✅ Video uploaded:", video_url, public_id)

        # --------------------------------------------------
        # 5) Thumbnail handling
        # --------------------------------------------------
        if thumbnail_image:
            thumb = cloudinary.uploader.upload(
                thumbnail_image,
                folder="reviews/thumbnails/",
                resource_type="image",
            )
            thumbnail_url = thumb["secure_url"]
            print("✅ Custom thumbnail uploaded:", thumbnail_url)
        else:
            # Cloudinary auto thumbnail from time (if provided)
            if thumbnail_time:
                thumbnail_url = (
                    f"https://res.cloudinary.com/{settings.CLOUDINARY_CLOUD_NAME}"
                    f"/video/upload/so_{thumbnail_time}/{public_id}.jpg"
                )
            else:
                thumbnail_url = ""
            print("🖼 Auto thumbnail url:", thumbnail_url)

        # --------------------------------------------------
        # 6) Duration: be defensive in case of ""
        # --------------------------------------------------
        raw_duration = data.get("duration_seconds", 0)
        try:
            duration_seconds = int(raw_duration) if raw_duration not in [None, ""] else 0
        except ValueError:
            duration_seconds = 0

        # --------------------------------------------------
        # 7) Save Review
        #    ⚠️ Removed product_id kwarg – avoid unexpected field error
        # --------------------------------------------------
        review = VideoReview.objects.create(
            user=user,
            video_url=video_url,
            thumbnail_url=thumbnail_url,
            cloudinary_public_id=public_id,
            caption=data.get("caption", ""),
            location=data.get("location", ""),
            duration_seconds=duration_seconds,

            # product metadata
            review_product_id=str(raw_pid),
            product=product_obj,  # keep None for now, or set later if you add real Product FK
            product_name=product_name,
            product_image_url=product_image,

            # thumbnail
            thumbnail_time_ms=thumbnail_time,
            is_public=True,
        )

        print("✅ Review saved with ID:", review.id)

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
        is_public=True, is_deleted=False, is_approved=True
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
        user_id__in=following_ids, is_public=True, is_deleted=False
    ).order_by("-created_at")

    paginator = StandardResultsSetPagination()
    page = paginator.paginate_queryset(videos, request)
    serializer = VideoReviewSerializer(page, many=True, context={"request": request})
    return paginator.get_paginated_response(serializer.data)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def feed_trending(request):
    videos = VideoReview.objects.filter(
        is_public=True, is_deleted=False
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
        return Response({"detail": "Video not found."}, status=status.HTTP_404_NOT_FOUND)

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
        return Response({"detail": "Comment cannot be empty."}, status=status.HTTP_400_BAD_REQUEST)

    try:
        video = VideoReview.objects.get(id=video_id, is_deleted=False)
    except VideoReview.DoesNotExist:
        return Response({"detail": "Video not found."}, status=status.HTTP_404_NOT_FOUND)

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
        return Response({"detail": "Video not found."}, status=status.HTTP_404_NOT_FOUND)

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
        return Response({"detail": "Comment not found."}, status=status.HTTP_404_NOT_FOUND)

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
        return Response({"detail": "Video not found."}, status=status.HTTP_404_NOT_FOUND)

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
        return Response({"detail": "Video not found."}, status=status.HTTP_404_NOT_FOUND)

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
        return Response({"detail": "You cannot follow yourself."}, status=status.HTTP_400_BAD_REQUEST)

    try:
        target_user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return Response({"detail": "User not found."}, status=status.HTTP_404_NOT_FOUND)

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
        return Response({"detail": "User not found."}, status=status.HTTP_404_NOT_FOUND)

    videos = VideoReview.objects.filter(
        user=creator,
        is_public=True,
        is_deleted=False,
    ).order_by("-created_at")

    serializer = VideoReviewSerializer(videos, many=True, context={"request": request})
    return Response(serializer.data)
