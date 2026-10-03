from django.urls import path

from accounts import views

app_name = "accounts"

urlpatterns = [
    path("login/", views.SMSLoginView.as_view(), name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("register/", views.RegisterView.as_view(), name="register"),
    # Profile
    path("profile/", views.ProfileView.as_view(), name="profile"),
    path("profile/edit/", views.ProfileUpdateView.as_view(), name="profile_edit"),
    path("profile/password/", views.PasswordChangeView.as_view(), name="password_change"),
    path(
        "profile/password/done/",
        views.password_change_done,
        name="password_change_done",
    ),
    path("profile/activity/", views.my_activity, name="my_activity"),
    # User administration
    path("users/", views.UserListView.as_view(), name="user_list"),
    path("users/add/", views.UserCreateView.as_view(), name="user_add"),
    path("users/export/", views.UserListView.as_view(), name="user_export"),
    path("users/<int:pk>/", views.UserDetailView.as_view(), name="user_detail"),
    path("users/<int:pk>/edit/", views.UserUpdateView.as_view(), name="user_edit"),
    path("users/<int:pk>/delete/", views.UserDeleteView.as_view(), name="user_delete"),
    path("users/<int:pk>/toggle/", views.UserToggleActiveView.as_view(), name="user_toggle"),
]
