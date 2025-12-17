import traceback

from django.conf import settings
from django.db import models  # ✅ FIX: for models.Q / Case / When if used anywhere
from django.db.models import Count, F, Avg  # ✅ NEW: Avg (safe if rating field exists)

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
        for key in ("secure_url", "url", "path", "src", "image", "file"):
            v = value.get(key)
            if isinstance(v, str):
                return v

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

    qs = OrderItem.objects.filter(review_product_id=pid_str).order_by("-id")
    if qs.exists():
        return qs.first()

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


def build_creator_meta_maps(request, video_list):
    """
    Builds two fast maps for the serializer to use:
      - followers_count_map: { creator_id: followers_count }
      - following_set: set(creator_ids current user follows)

    ✅ IMPORTANT FIX:
    - The annotate query only returns rows for users that have >=1 followers.
    - So creators with 0 followers were "missing" -> frontend showed "—" / 0 incorrectly.
    - We prefill all creator_ids with 0, then overwrite real counts.
    """
    creator_ids = list({v.user_id for v in video_list if getattr(v, "user_id", None)})
    if not creator_ids:
        return {}, set()

    # ✅ Prefill zeros for EVERY creator in the feed
    followers_count_map = {cid: 0 for cid in creator_ids}

    # Overwrite with real counts where they exist
    for row in (
        UserFollow.objects.filter(following_id__in=creator_ids)
        .values("following_id")
        .annotate(c=Count("id"))
    ):
        followers_count_map[row["following_id"]] = int(row["c"] or 0)

    following_set = set()
    if request.user and request.user.is_authenticated:
        following_set = set(
            UserFollow.objects.filter(
                follower=request.user,
                following_id__in=creator_ids,
            ).values_list("following_id", flat=True)
        )

    return followers_count_map, following_set


# ============================================================
# ✅ NEW: PRODUCT FEED (Tap product → watch reviews for this product)
# ============================================================
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def feed_product(request):
    """
    GET /api/reviews/feed/product/?product_id=<id>
    Returns only reviews tied to this product identifier (review_product_id).
    """
    pid = str(request.query_params.get("product_id") or "").strip()
    if not pid:
        return Response({"detail": "product_id is required."}, status=status.HTTP_400_BAD_REQUEST)

    videos = VideoReview.objects.filter(
        is_public=True,
        is_deleted=False,
        is_approved=True,
        review_product_id=pid,
    ).select_related("user").order_by("-created_at")

    paginator = StandardResultsSetPagination()
    page = paginator.paginate_queryset(videos, request)

    followers_map, following_set = build_creator_meta_maps(request, page)

    serializer = VideoReviewSerializer(
        page,
        many=True,
        context={
            "request": request,
            "followers_count_map": followers_map,
            "following_set": following_set,
        },
    )
    return paginator.get_paginated_response(serializer.data)


# ============================================================
# ✅ NEW: BULK REVIEW STATS (Store cards social proof)
# ============================================================
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def review_stats_by_product(request):
    """
    GET /api/reviews/stats/by-product/?ids=12,15,19
    Returns:
      {
        "12": {"reviews_count": 5, "creator_count": 3, "avg_rating": 0},
        "15": {"reviews_count": 0, "creator_count": 0, "avg_rating": 0}
      }

    Note: avg_rating is included ONLY if your VideoReview model has a numeric field
    like `rating` or `stars`. Otherwise it will safely stay 0.
    """
    ids_raw = (request.query_params.get("ids") or "").strip()
    if not ids_raw:
        return Response({}, status=status.HTTP_200_OK)

    ids = [s.strip() for s in ids_raw.split(",") if s.strip()]
    if not ids:
        return Response({}, status=status.HTTP_200_OK)

    base = VideoReview.objects.filter(
        is_public=True,
        is_deleted=False,
        is_approved=True,
        review_product_id__in=ids,
    )

    # Always compute counts
    agg = (
        base.values("review_product_id")
        .annotate(
            reviews_count=Count("id"),
            creator_count=Count("user_id", distinct=True),
        )
    )

    # Optional avg rating (only if field exists)
    # We try common names without crashing.
    rating_field = None
    for candidate in ("rating", "stars", "rating_value"):
        try:
            VideoReview._meta.get_field(candidate)
            rating_field = candidate
            break
        except Exception:
            continue

    if rating_field:
        agg = agg.annotate(avg_rating=Avg(rating_field))
    else:
        # keep shape consistent
        pass

    out = {pid: {"reviews_count": 0, "creator_count": 0, "avg_rating": 0} for pid in ids}

    for row in agg:
        pid = str(row.get("review_product_id") or "")
        out[pid] = {
            "reviews_count": int(row.get("reviews_count") or 0),
            "creator_count": int(row.get("creator_count") or 0),
            "avg_rating": float(row.get("avg_rating") or 0) if rating_field else 0,
        }

    return Response(out, status=status.HTTP_200_OK)


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

        raw_pid = data.get("product_id") or data.get("review_product_id")
        if not raw_pid:
            return Response(
                {
                    "error": "Missing product identifier. "
                    "Send 'product_id' or 'review_product_id' from the app."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

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

        product_name = getattr(item, "product_name_snapshot", None)
        product_image_raw = getattr(item, "product_image_snapshot", None)

        if not product_name:
            return Response(
                {"error": "Product name missing from OrderItem snapshot."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        product_image = normalize_media_value(product_image_raw)

        video_file = request.FILES.get("video")
        if not video_file:
            return Response(
                {"error": "Video file missing."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        thumbnail_image = request.FILES.get("thumbnail_image")
        thumbnail_time = data.get("thumbnail_time_ms")

        uploaded_video = cloudinary.uploader.upload_large(
            video_file,
            resource_type="video",
            folder="reviews/videos/",
        )

        video_url = uploaded_video["secure_url"]
        public_id = uploaded_video["public_id"]

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

        raw_duration = data.get("duration_seconds", 0)
        try:
            duration_seconds = int(raw_duration)
        except Exception:
            duration_seconds = 0

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
            review_product_id=str(item.review_product_id),
            product=None,
            product_name=product_name,
            product_image_url=product_image,
            thumbnail_time_ms=thumbnail_time,
            is_public=True,
        )

        return Response(
            {"message": "Review uploaded successfully!", "id": review.id},
            status=status.HTTP_201_CREATED,
        )

    except Exception as e:
        print("❌ UPLOAD REVIEW ERROR:", e)
        print(traceback.format_exc())
        return Response(
            {"error": "Server failed to upload review.", "details": str(e)},
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
    ).select_related("user").order_by("-created_at")

    paginator = StandardResultsSetPagination()
    page = paginator.paginate_queryset(videos, request)

    followers_map, following_set = build_creator_meta_maps(request, page)

    serializer = VideoReviewSerializer(
        page,
        many=True,
        context={
            "request": request,
            "followers_count_map": followers_map,
            "following_set": following_set,
        },
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
    ).select_related("user").order_by("-created_at")

    paginator = StandardResultsSetPagination()
    page = paginator.paginate_queryset(videos, request)

    followers_map, following_set = build_creator_meta_maps(request, page)

    serializer = VideoReviewSerializer(
        page,
        many=True,
        context={
            "request": request,
            "followers_count_map": followers_map,
            "following_set": following_set,
        },
    )
    return paginator.get_paginated_response(serializer.data)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def feed_trending(request):
    videos = (
        VideoReview.objects.filter(is_public=True, is_deleted=False)
        .select_related("user")
        .annotate(
            trending_score=(F("likes_count") * 2 + F("comments_count") * 3 + F("views_count"))
        )
        .order_by("-trending_score", "-created_at")
    )

    paginator = StandardResultsSetPagination()
    page = paginator.paginate_queryset(videos, request)

    followers_map, following_set = build_creator_meta_maps(request, page)

    serializer = VideoReviewSerializer(
        page,
        many=True,
        context={
            "request": request,
            "followers_count_map": followers_map,
            "following_set": following_set,
        },
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
        return Response({"detail": "Video not found."}, status=status.HTTP_404_NOT_FOUND)

    like, created = VideoLike.objects.get_or_create(user=user, video=video)

    if not created:
        like.delete()

    video.likes_count = VideoLike.objects.filter(video=video).count()
    video.save(update_fields=["likes_count"])

    return Response(
        {
            "liked": created,
            "likes_count": video.likes_count,
            "user_liked": created,
        }
    )


# ============================================================
# COMMENTS
# ============================================================
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def post_comment(request, video_id):
    user = request.user
    text = (request.data.get("text") or "").strip()

    if not text:
        return Response({"detail": "Comment cannot be empty."}, status=status.HTTP_400_BAD_REQUEST)

    try:
        video = VideoReview.objects.get(id=video_id, is_deleted=False)
    except VideoReview.DoesNotExist:
        return Response({"detail": "Video not found."}, status=status.HTTP_404_NOT_FOUND)

    comment = VideoComment.objects.create(video=video, user=user, text=text)

    video.comments_count = VideoComment.objects.filter(video=video, is_deleted=False).count()
    video.save(update_fields=["comments_count"])

    serializer = VideoCommentSerializer(comment, context={"request": request})
    return Response(serializer.data, status=status.HTTP_201_CREATED)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_comments(request, video_id):
    try:
        video = VideoReview.objects.get(id=video_id, is_deleted=False)
    except VideoReview.DoesNotExist:
        return Response({"detail": "Video not found."}, status=status.HTTP_404_NOT_FOUND)

    comments = VideoComment.objects.filter(video=video, is_deleted=False).select_related("user").order_by("-created_at")
    serializer = VideoCommentSerializer(comments, many=True, context={"request": request})
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
        return Response({"detail": "You can only delete your own comments."}, status=status.HTTP_403_FORBIDDEN)

    comment.is_deleted = True
    comment.save(update_fields=["is_deleted"])

    video = comment.video
    video.comments_count = VideoComment.objects.filter(video=video, is_deleted=False).count()
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

    return Response({"saved": created, "saves_count": video.saves_count, "user_saved": created})


# ============================================================
# VIEWS
# ============================================================
@api_view(["POST"])
@permission_classes([AllowAny])
def track_view(request, video_id):
    user = request.user if getattr(request, "user", None) and request.user.is_authenticated else None

    try:
        video = VideoReview.objects.get(id=video_id, is_deleted=False)
    except VideoReview.DoesNotExist:
        return Response({"detail": "Video not found."}, status=status.HTTP_404_NOT_FOUND)

    VideoView.objects.create(video=video, user=user)

    video.views_count = VideoView.objects.filter(video=video).count()
    video.save(update_fields=["views_count"])

    return Response({"views_count": video.views_count})


# ============================================================
# FOLLOW ✅ RETURNS BOTH SHAPES
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
        is_following = False
    else:
        is_following = True

    followers_count = UserFollow.objects.filter(following=target_user).count()

    return Response(
        {
            # ✅ ROOT (frontend patcher likes this)
            "following": is_following,
            "followers_count": followers_count,

            # ✅ NESTED (keep)
            "user": {
                "id": target_user.id,
                "username": getattr(target_user, "username", ""),
                "is_following": is_following,
                "followers_count": followers_count,
            },
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
        return Response({"detail": "User not found."}, status=status.HTTP_404_NOT_FOUND)

    videos = VideoReview.objects.filter(
        user=creator,
        is_public=True,
        is_deleted=False,
    ).select_related("user").order_by("-created_at")

    followers_count = UserFollow.objects.filter(following=creator).count()

    following_set = set()
    if request.user.is_authenticated:
        following_set = set(
            UserFollow.objects.filter(follower=request.user, following=creator).values_list("following_id", flat=True)
        )

    followers_map = {creator.id: followers_count}  # includes 0 OK

    serializer = VideoReviewSerializer(
        videos,
        many=True,
        context={
            "request": request,
            "followers_count_map": followers_map,
            "following_set": following_set,
        },
    )
    return Response(serializer.data)
