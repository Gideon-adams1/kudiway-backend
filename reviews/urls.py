from django.urls import path
from . import views

urlpatterns = [
    # Feeds
    path("feed/for-you/", views.feed_for_you, name="feed_for_you"),
    path("feed/following/", views.feed_following, name="feed_following"),
    path("feed/trending/", views.feed_trending, name="feed_trending"),

    # Upload
    path("upload/", views.upload_video_review, name="upload_video_review"),

    # Creator videos
    path("creator/<int:user_id>/videos/", views.creator_videos, name="creator_videos"),

    # Likes / Saves / Follows
    path("<uuid:video_id>/like/", views.toggle_like, name="toggle_like"),
    path("<uuid:video_id>/save/", views.toggle_save, name="toggle_save"),
    path("follow/<int:user_id>/", views.toggle_follow, name="toggle_follow"),

    # Comments
    path("<uuid:video_id>/comment/", views.post_comment, name="post_comment"),
    path("comments/<uuid:video_id>/", views.get_comments, name="get_comments"),
    path("comment/delete/<uuid:comment_id>/", views.delete_comment, name="delete_comment"),

    # Views
    path("<uuid:video_id>/view/", views.track_view, name="track_view"),
]
