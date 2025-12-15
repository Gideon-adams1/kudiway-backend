import uuid
from django.conf import settings
from django.db import models
from django.utils.text import slugify
from django.db.models import Q

User = settings.AUTH_USER_MODEL


# ============================================================
# 🏷️ HASHTAGS
# ============================================================
class Hashtag(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=120, unique=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        indexes = [
            models.Index(fields=["slug"]),
            models.Index(fields=["name"]),
        ]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


# ============================================================
# 👥 FOLLOW SYSTEM (OPTIMIZED + SCALE SAFE)
# ============================================================
class UserFollow(models.Model):
    follower = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="following_relations",
        db_index=True,
    )
    following = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="follower_relations",
        db_index=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            # Prevent duplicate follow rows
            models.UniqueConstraint(
                fields=["follower", "following"],
                name="uniq_follow_follower_following",
            ),
            # Prevent self-follow at DB level (in addition to view validation)
            models.CheckConstraint(
                check=~Q(follower=models.F("following")),
                name="no_self_follow",
            ),
        ]
        indexes = [
            models.Index(fields=["follower", "created_at"]),
            models.Index(fields=["following", "created_at"]),
        ]

    def __str__(self):
        return f"{self.follower} → {self.following}"


# ============================================================
# 🎥 VIDEO REVIEW
# ============================================================
class VideoReview(models.Model):
    """
    A user’s video review for a purchased product.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="video_reviews",
        db_index=True,
    )

    # ---------------------------------------------------------
    # 🔥 Product / OrderItem linking
    # ---------------------------------------------------------
    review_product_id = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        help_text="Matches OrderItem.review_product_id",
        db_index=True,
    )

    product = models.ForeignKey(
        "orders.Product",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="video_reviews",
        db_index=True,
    )

    product_name = models.CharField(max_length=255, blank=True)
    product_image_url = models.URLField(blank=True)

    # ---------------------------------------------------------
    # 🎥 Video & thumbnail (Cloudinary)
    # ---------------------------------------------------------
    video_url = models.URLField()
    thumbnail_url = models.URLField(blank=True)
    cloudinary_public_id = models.CharField(max_length=255, blank=True)

    thumbnail_time_ms = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Timestamp used when generating thumbnail",
    )

    # ---------------------------------------------------------
    # ✏️ Content
    # ---------------------------------------------------------
    caption = models.TextField(blank=True)
    location = models.CharField(max_length=255, blank=True)
    hashtags = models.ManyToManyField(Hashtag, blank=True, related_name="videos")
    duration_seconds = models.PositiveIntegerField(default=0)

    # ---------------------------------------------------------
    # 📊 Stats (denormalized counters)
    # ---------------------------------------------------------
    likes_count = models.PositiveIntegerField(default=0)
    comments_count = models.PositiveIntegerField(default=0)
    views_count = models.PositiveIntegerField(default=0)
    saves_count = models.PositiveIntegerField(default=0)
    shares_count = models.PositiveIntegerField(default=0)

    # ---------------------------------------------------------
    # ⚙️ Moderation flags
    # ---------------------------------------------------------
    is_public = models.BooleanField(default=True, db_index=True)
    is_approved = models.BooleanField(default=True, db_index=True)
    is_featured = models.BooleanField(default=False, db_index=True)
    is_deleted = models.BooleanField(default=False, db_index=True)

    country_code = models.CharField(max_length=5, blank=True, db_index=True)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["-created_at"]),
            models.Index(fields=["user", "-created_at"]),
            models.Index(fields=["is_public", "is_deleted", "is_approved", "-created_at"]),
        ]

    def __str__(self):
        return f"Review of {self.product_name or 'Unknown'} by {self.user}"


# ============================================================
# ❤️ LIKES
# ============================================================
class VideoLike(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="video_likes",
        db_index=True,
    )
    video = models.ForeignKey(
        VideoReview,
        on_delete=models.CASCADE,
        related_name="likes",
        db_index=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "video"], name="uniq_video_like_user_video"),
        ]
        indexes = [
            models.Index(fields=["video", "created_at"]),
            models.Index(fields=["user", "created_at"]),
        ]

    def __str__(self):
        return f"{self.user} ♥ {self.video_id}"


# ============================================================
# 💾 SAVED VIDEOS
# ============================================================
class VideoSave(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="saved_videos",
        db_index=True,
    )
    video = models.ForeignKey(
        VideoReview,
        on_delete=models.CASCADE,
        related_name="saves",
        db_index=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "video"], name="uniq_video_save_user_video"),
        ]
        indexes = [
            models.Index(fields=["video", "created_at"]),
            models.Index(fields=["user", "created_at"]),
        ]

    def __str__(self):
        return f"{self.user} saved {self.video_id}"


# ============================================================
# 👁️ VIEWS
# ============================================================
class VideoView(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="video_views",
        db_index=True,
    )
    video = models.ForeignKey(
        VideoReview,
        on_delete=models.CASCADE,
        related_name="views",
        db_index=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["video", "created_at"]),
        ]

    def __str__(self):
        return f"View: {self.video_id} by {self.user or 'anonymous'}"


# ============================================================
# 💬 COMMENTS
# ============================================================
class VideoComment(models.Model):
    video = models.ForeignKey(
        VideoReview,
        on_delete=models.CASCADE,
        related_name="comments",
        db_index=True,
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="video_comments",
        db_index=True,
    )
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    is_deleted = models.BooleanField(default=False, db_index=True)

    parent = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="replies",
    )

    class Meta:
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["video", "is_deleted", "created_at"]),
            models.Index(fields=["user", "created_at"]),
        ]

    def __str__(self):
        return f"Comment by {self.user} on {self.video_id}"


# ============================================================
# 🚨 REPORTS
# ============================================================
class VideoReport(models.Model):
    REASON_CHOICES = [
        ("spam", "Spam / Advertising"),
        ("nudity", "Nudity or sexual content"),
        ("violence", "Violence / Harmful content"),
        ("fraud", "Fraud / Scam"),
        ("hate", "Hate speech"),
        ("other", "Other"),
    ]

    video = models.ForeignKey(
        VideoReview,
        on_delete=models.CASCADE,
        related_name="reports",
        db_index=True,
    )
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="video_reports",
        db_index=True,
    )

    reason = models.CharField(max_length=20, choices=REASON_CHOICES, db_index=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    handled = models.BooleanField(default=False, db_index=True)
    handled_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["video", "created_at"]),
            models.Index(fields=["handled", "created_at"]),
        ]

    def __str__(self):
        return f"Report: {self.video_id} ({self.reason})"
