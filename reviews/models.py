import uuid
from django.conf import settings
from django.db import models
from django.utils.text import slugify

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

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


# ============================================================
# 👥 FOLLOW SYSTEM
# ============================================================
class UserFollow(models.Model):
    follower = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="following_relations",
    )
    following = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="follower_relations",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("follower", "following")

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
    )

    # ---------------------------------------------------------
    # 🔥 Product / OrderItem linking
    # ---------------------------------------------------------
    review_product_id = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        help_text="Matches OrderItem.review_product_id"
    )

    product = models.ForeignKey(
        "orders.Product",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="video_reviews",
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
    # 📊 Stats
    # ---------------------------------------------------------
    likes_count = models.PositiveIntegerField(default=0)
    comments_count = models.PositiveIntegerField(default=0)
    views_count = models.PositiveIntegerField(default=0)
    saves_count = models.PositiveIntegerField(default=0)
    shares_count = models.PositiveIntegerField(default=0)

    # ---------------------------------------------------------
    # ⚙️ Moderation flags
    # ---------------------------------------------------------
    is_public = models.BooleanField(default=True)
    is_approved = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False)
    is_deleted = models.BooleanField(default=False)

    country_code = models.CharField(max_length=5, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

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
    )
    video = models.ForeignKey(
        VideoReview,
        on_delete=models.CASCADE,
        related_name="likes",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "video")

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
    )
    video = models.ForeignKey(
        VideoReview,
        on_delete=models.CASCADE,
        related_name="saves",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "video")

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
    )
    video = models.ForeignKey(
        VideoReview,
        on_delete=models.CASCADE,
        related_name="views",
    )
    created_at = models.DateTimeField(auto_now_add=True)

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
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="video_comments",
    )
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    is_deleted = models.BooleanField(default=False)

    parent = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="replies",
    )

    class Meta:
        ordering = ["created_at"]

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
    )
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="video_reports",
    )

    reason = models.CharField(max_length=20, choices=REASON_CHOICES)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    handled = models.BooleanField(default=False)
    handled_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Report: {self.video_id} ({self.reason})"
