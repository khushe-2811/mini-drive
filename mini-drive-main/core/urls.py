from django.urls import path
from django.contrib.auth.views import LoginView, LogoutView
from . import views

urlpatterns = [
    # Authentication
    path("login/", LoginView.as_view(template_name="login.html", redirect_authenticated_user=True), name="login"),
    path("logout/", LogoutView.as_view(next_page="login"), name="logout"),
    path("register/", views.register, name="register"),
    # Folder Management
    path("folder/<int:folder_id>/", views.folder_detail, name="folder_detail"),
    path("folder/create/", views.create_folder, name="create_folder"),
    path("folder/<int:folder_id>/delete/", views.delete_folder, name="delete_folder"),
    path(
        "folder/<int:folder_id>/share/",
        views.create_folder_share,
        name="create_folder_share",
    ),
    path("sf/<uuid:uuid>/", views.serve_folder_share, name="serve_folder_share"),
    path(
        "sf/<uuid:uuid>/file/<int:file_id>/",
        views.serve_shared_file,
        name="serve_shared_file",
    ),
    # HTML views
    path("", views.dashboard, name="dashboard"),
    path("upload/", views.upload_file, name="upload_file"),
    path("download/<int:file_id>/", views.download_file, name="download_file"),
    path("delete/<int:file_id>/", views.delete_file, name="delete_file"),
    path("search/", views.search_files, name="search_files"),
    path("share/<int:file_id>/", views.create_share, name="create_share"),
    path("s/<uuid:uuid>/", views.serve_share, name="serve_share"),
    # API endpoints
    path("api/files/", views.FileListAPI.as_view(), name="api_files"),
    path("api/upload/", views.FileUploadAPI.as_view(), name="api_upload"),
    path("api/search/", views.search_api, name="api_search"),
    
     path("chat_with_gemini/", views.chat_with_gemini, name="chat_with_gemini"),
]
