from django.shortcuts import render
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
import os
import google.generativeai as genai



import numpy as np
from datetime import datetime
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404, JsonResponse
from django.contrib import messages
from django.views.decorators.http import require_POST
from django.db.models import Sum
from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser
from rest_framework.views import APIView
from rest_framework import status
from openai import OpenAI
from django.contrib.auth import login

from .models import File, Embedding, ShareToken, Folder, FolderShareToken
from .forms import FileUploadForm, SearchForm, UserRegistrationForm
from .serializers import FileSerializer, ShareTokenSerializer, FileUploadSerializer
from .tasks import postprocess_file



# Configure Gemini with API key
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

# Helper function to ask Gemini
def ask_gemini(prompt):
    model = genai.GenerativeModel("gemini-pro")
    response = model.generate_content(prompt)
    return response.text

# HTML Views


@login_required
def chat_with_gemini(request):
    user_prompt = request.GET.get("prompt", "Hello Gemini!")
    gemini_response = ask_gemini(user_prompt)
    return JsonResponse({"response": gemini_response})

@login_required
def dashboard(request):
    """Main dashboard showing root folders and files."""
    # Get root folders (no parent)
    root_folders = Folder.objects.filter(owner=request.user, parent=None).order_by(
        "name"
    )
    # Get root files (no folder)
    root_files = File.objects.filter(owner=request.user, folder=None).order_by(
        "-uploaded"
    )

    # Calculate storage usage
    storage_used = (
        File.objects.filter(owner=request.user).aggregate(total=Sum("size"))["total"]
        or 0
    )
    storage_used_mb = storage_used / (1024 * 1024)
    storage_limit_mb = settings.MAX_STORAGE_MB
    storage_percent = (
        (storage_used_mb / storage_limit_mb) * 100 if storage_limit_mb > 0 else 0
    )

    return render(
        request,
        "dashboard.html",
        {
            "folders": root_folders,
            "files": root_files,
            "current_folder": None,
            "breadcrumbs": [],
            "storage_used_mb": round(storage_used_mb, 2),
            "storage_limit_mb": storage_limit_mb,
            "storage_percent": min(100, round(storage_percent, 1)),
        },
    )


@login_required
def folder_detail(request, folder_id):
    """Show contents of a folder."""
    folder = get_object_or_404(Folder, id=folder_id)

    # Check permissions
    if folder.owner != request.user:
        raise PermissionDenied("You don't have permission to access this folder.")

    # Get subfolders and files
    subfolders = folder.children.all().order_by("name")
    files = folder.files.all().order_by("-uploaded")

    # Calculate storage usage (same as dashboard)
    storage_used = (
        File.objects.filter(owner=request.user).aggregate(total=Sum("size"))["total"]
        or 0
    )
    storage_used_mb = storage_used / (1024 * 1024)
    storage_limit_mb = settings.MAX_STORAGE_MB
    storage_percent = (
        (storage_used_mb / storage_limit_mb) * 100 if storage_limit_mb > 0 else 0
    )

    return render(
        request,
        "folder_detail.html",
        {
            "folders": subfolders,
            "files": files,
            "current_folder": folder,
            "breadcrumbs": folder.get_breadcrumbs(),
            "storage_used_mb": round(storage_used_mb, 2),
            "storage_limit_mb": storage_limit_mb,
            "storage_percent": min(100, round(storage_percent, 1)),
        },
    )


@login_required
@require_POST
def create_folder(request):
    """Create a new folder."""
    folder_name = request.POST.get("folder_name", "").strip()
    parent_id = request.POST.get("parent_id")

    if not folder_name:
        messages.error(request, "Folder name cannot be empty.")
        return redirect(request.META.get("HTTP_REFERER", "dashboard"))

    # Set parent folder if provided
    parent = None
    if parent_id:
        parent = get_object_or_404(Folder, id=parent_id)
        if parent.owner != request.user:
            raise PermissionDenied("You don't have permission to add to this folder.")

    # Check if folder already exists at this level
    if Folder.objects.filter(
        owner=request.user, name=folder_name, parent=parent
    ).exists():
        messages.error(request, f"A folder named '{folder_name}' already exists here.")
        return redirect(request.META.get("HTTP_REFERER", "dashboard"))

    # Create the folder
    new_folder = Folder.objects.create(
        owner=request.user, name=folder_name, parent=parent
    )

    messages.success(request, f"Folder '{folder_name}' created successfully.")

    # Redirect to appropriate place
    if parent:
        return redirect("folder_detail", folder_id=parent.id)
    else:
        return redirect("dashboard")


@login_required
@require_POST
def delete_folder(request, folder_id):
    """Delete a folder and all its contents."""
    folder = get_object_or_404(Folder, id=folder_id)

    # Check permissions
    if folder.owner != request.user:
        raise PermissionDenied("You don't have permission to delete this folder.")

    folder_name = folder.name
    parent_id = folder.parent.id if folder.parent else None

    # Delete folder (will cascade to all contents)
    folder.delete()

    messages.success(
        request, f"Folder '{folder_name}' and all its contents have been deleted."
    )

    # Support HTMX
    if request.headers.get("HX-Request"):
        return render(request, "partials/folder_deleted.html")

    # Redirect to parent or dashboard
    if parent_id:
        return redirect("folder_detail", folder_id=parent_id)
    else:
        return redirect("dashboard")


@login_required
def upload_file(request):
    """File upload page and form handler."""
    # Get the target folder if specified
    folder_id = request.GET.get("folder") or request.POST.get("folder")
    folder = None

    if folder_id:
        folder = get_object_or_404(Folder, id=folder_id)
        if folder.owner != request.user:
            raise PermissionDenied(
                "You don't have permission to upload to this folder."
            )

    if request.method == "POST":
        form = FileUploadForm(request.POST, request.FILES, user=request.user)
        if form.is_valid():
            file_obj = form.save(commit=False)
            file_obj.owner = request.user
            file_obj.folder = folder

            # Check if a file with the same name exists in this location
            if File.objects.filter(
                owner=request.user, name=file_obj.name, folder=folder
            ).exists():
                messages.error(
                    request,
                    f"A file named '{file_obj.name}' already exists in this location.",
                )
                return redirect(request.META.get("HTTP_REFERER", "upload_file"))

            file_obj.save()

            # Process file in background (but eagerly in this setup)
            postprocess_file.delay(file_obj.id)

            messages.success(
                request,
                f"File '{file_obj.name}' uploaded successfully and is being processed.",
            )

            # Redirect to appropriate location
            if folder:
                return redirect("folder_detail", folder_id=folder.id)
            else:
                return redirect("dashboard")
    else:
        form = FileUploadForm(user=request.user)

    return render(
        request,
        "upload.html",
        {
            "form": form,
            "folder": folder,
            "breadcrumbs": folder.get_breadcrumbs() if folder else [],
        },
    )


@login_required
@require_POST
def create_folder_share(request, folder_id):
    """Create a share link for a folder."""
    folder = get_object_or_404(Folder, id=folder_id)

    # Check permissions
    if folder.owner != request.user:
        raise PermissionDenied("You don't have permission to share this folder.")

    # Create share token
    token = folder.create_share_link()

    if request.headers.get("HX-Request"):
        # Return partial HTML for HTMX
        return render(request, "partials/folder_row.html", {"folder": folder})

    messages.success(
        request,
        f"Share link for folder '{folder.name}' created! It will expire in 12 hours.",
    )

    if folder.parent:
        return redirect("folder_detail", folder_id=folder.parent.id)
    else:
        return redirect("dashboard")


def serve_folder_share(request, uuid):
    """Serve a shared folder and its contents."""
    token = get_object_or_404(FolderShareToken, uuid=uuid)

    # Check if token is expired
    if timezone.now() > token.expiry:
        raise Http404("This share link has expired.")

    # Get subfolder if specified
    subfolder_id = request.GET.get("subfolder")
    current_folder = token.folder

    if subfolder_id:
        try:
            # Make sure this subfolder is actually a child of the shared folder
            subfolder = Folder.objects.get(id=subfolder_id)

            # Verify this is actually a subfolder of the shared folder (security check)
            is_subfolder = False
            parent = subfolder.parent
            while parent:
                if parent.id == token.folder.id:
                    is_subfolder = True
                    break
                parent = parent.parent

            if is_subfolder:
                current_folder = subfolder
            else:
                raise Http404("Access denied to this folder.")
        except Folder.DoesNotExist:
            raise Http404("Folder not found.")

    # Get contents
    subfolders = current_folder.children.all().order_by("name")
    files = current_folder.files.all().order_by("-uploaded")

    # Build breadcrumbs
    breadcrumbs = []
    if current_folder.id != token.folder.id:
        # Start with the root shared folder
        breadcrumbs.append(
            {
                "id": token.folder.id,
                "name": token.folder.name,
                "url": f"/sf/{token.uuid}/",
            }
        )

        # Add subfolder parents
        temp_folder = current_folder.parent
        collected_folders = []

        while temp_folder and temp_folder.id != token.folder.id:
            collected_folders.insert(
                0,
                {
                    "id": temp_folder.id,
                    "name": temp_folder.name,
                    "url": f"/sf/{token.uuid}/?subfolder={temp_folder.id}",
                },
            )
            temp_folder = temp_folder.parent

        breadcrumbs.extend(collected_folders)

        # Add current folder
        breadcrumbs.append(
            {
                "id": current_folder.id,
                "name": current_folder.name,
                "url": f"/sf/{token.uuid}/?subfolder={current_folder.id}",
            }
        )

    return render(
        request,
        "shared_folder.html",
        {
            "folders": subfolders,
            "files": files,
            "folder": current_folder,
            "token": token,
            "is_shared": True,
            "breadcrumbs": breadcrumbs,
            "root_folder": token.folder,
        },
    )


@login_required
def download_file(request, file_id):
    """Download a file owned by the user."""
    file_obj = get_object_or_404(File, id=file_id)

    # Check permissions
    if file_obj.owner != request.user:
        raise PermissionDenied("You don't have permission to access this file.")

    return FileResponse(file_obj.file, as_attachment=True, filename=file_obj.name)


@login_required
def search_files(request):
    """Search files by content using embeddings."""
    search_results = []
    form = SearchForm(request.GET)

    if form.is_valid() and "query" in request.GET:
        query = form.cleaned_data["query"]

        try:
            # Generate embedding for search query
            client = OpenAI(api_key=settings.OPENAI_API_KEY)
            response = client.embeddings.create(input=query, model=settings.EMBED_MODEL)
            query_vector = response.data[0].embedding

            # Get all user's file embeddings
            user_files = File.objects.filter(owner=request.user)
            file_embeddings = Embedding.objects.filter(file__in=user_files)

            # Calculate similarity scores
            results = []
            for embedding in file_embeddings:
                file_vector = np.array(embedding.vector)
                query_vector_np = np.array(query_vector)

                # Calculate cosine similarity
                similarity = np.dot(file_vector, query_vector_np) / (
                    np.linalg.norm(file_vector) * np.linalg.norm(query_vector_np)
                )

                results.append({"file": embedding.file, "similarity": similarity})

            # Sort by similarity (descending)
            results.sort(key=lambda x: x["similarity"], reverse=True)
            search_results = [r["file"] for r in results[:20]]

        except Exception as e:
            messages.error(request, f"Search error: {str(e)}")

    return render(
        request,
        "search.html",
        {
            "form": form,
            "results": search_results,
            "query": request.GET.get("query", ""),
        },
    )


@login_required
@require_POST
def create_share(request, file_id):
    """Create a share link for a file."""
    file_obj = get_object_or_404(File, id=file_id)

    # Check permissions
    if file_obj.owner != request.user:
        raise PermissionDenied("You don't have permission to share this file.")

    # Create share token
    token = file_obj.create_share_link()

    if request.headers.get("HX-Request"):
        # Return partial HTML for HTMX
        return render(request, "partials/file_row.html", {"file": file_obj})

    messages.success(request, f"Share link created! It will expire in 12 hours.")
    return redirect("dashboard")


def serve_share(request, uuid):
    """Serve a file through a share link."""
    token = get_object_or_404(ShareToken, uuid=uuid)

    # Check if token is expired
    if timezone.now() > token.expiry:
        raise Http404("This share link has expired.")

    # Stream the file
    return FileResponse(token.file.file, filename=token.file.name)


def serve_shared_file(request, uuid, file_id):
    """Serve a file inside a shared folder."""
    token = get_object_or_404(FolderShareToken, uuid=uuid)

    # Check if token is expired
    if timezone.now() > token.expiry:
        raise Http404("This share link has expired.")

    # Get the file
    file = get_object_or_404(File, id=file_id)

    # Security check: make sure this file belongs to the shared folder or a subfolder
    folder = file.folder
    can_access = False

    if folder:
        # Check if it's in the shared folder directly
        if folder.id == token.folder.id:
            can_access = True
        else:
            # Check if it's in a subfolder
            parent = folder
            while parent:
                if parent.id == token.folder.id:
                    can_access = True
                    break
                parent = parent.parent

    if not can_access:
        raise Http404("Access denied to this file.")

    # Stream the file
    return FileResponse(file.file, filename=file.name)


@login_required
@require_POST
def delete_file(request, file_id):
    """Delete a file and associated data."""
    file_obj = get_object_or_404(File, id=file_id)

    # Check permissions
    if file_obj.owner != request.user:
        raise PermissionDenied("You don't have permission to delete this file.")

    file_name = file_obj.name

    # Delete the file and all associated data (ShareTokens and Embedding)
    # The actual media files will be deleted due to on_delete=CASCADE
    file_obj.delete()

    messages.success(request, f"File '{file_name}' has been deleted.")

    # Support HTMX partial updates
    if request.headers.get("HX-Request"):
        return render(request, "partials/file_deleted.html")

    return redirect("dashboard")


# API Views


class FileListAPI(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """List all files for the authenticated user."""
        files = File.objects.filter(owner=request.user).order_by("-uploaded")
        serializer = FileSerializer(files, many=True, context={"request": request})
        return Response(serializer.data)


class FileUploadAPI(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser]

    def post(self, request):
        """Upload a file via API."""
        serializer = FileUploadSerializer(
            data=request.data, context={"request": request}
        )

        if serializer.is_valid():
            file_obj = serializer.save()

            # Process file in background
            postprocess_file.delay(file_obj.id)

            # Return serialized file data
            return Response(
                FileSerializer(file_obj, context={"request": request}).data,
                status=status.HTTP_201_CREATED,
            )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def search_api(request):
    """Search files by content using embeddings via API."""
    query = request.GET.get("q", "")

    if not query:
        return Response(
            {"error": "Query parameter 'q' is required"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        # Generate embedding for search query
        client = OpenAI(api_key=settings.OPENAI_API_KEY)
        response = client.embeddings.create(input=query, model=settings.EMBED_MODEL)
        query_vector = response.data[0].embedding

        # Get all user's file embeddings
        user_files = File.objects.filter(owner=request.user)
        file_embeddings = Embedding.objects.filter(file__in=user_files)

        # Calculate similarity scores
        results = []
        for embedding in file_embeddings:
            file_vector = np.array(embedding.vector)
            query_vector_np = np.array(query_vector)

            # Calculate cosine similarity
            similarity = np.dot(file_vector, query_vector_np) / (
                np.linalg.norm(file_vector) * np.linalg.norm(query_vector_np)
            )

            results.append(
                {
                    "file": embedding.file,
                    "similarity": float(similarity),  # Convert to float for JSON
                }
            )

        # Sort by similarity (descending) and take top 20
        results.sort(key=lambda x: x["similarity"], reverse=True)
        top_results = results[:20]

        # Serialize and return
        serialized_files = FileSerializer(
            [r["file"] for r in top_results], many=True, context={"request": request}
        ).data

        # Add similarity scores to serialized data
        for i, file_data in enumerate(serialized_files):
            file_data["similarity"] = top_results[i]["similarity"]

        return Response(serialized_files)

    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def register(request):
    """Registration view for new users."""
    if request.user.is_authenticated:
        return redirect('dashboard')
        
    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, f"Account created successfully! Welcome to MiniDrive, {user.username}.")
            return redirect('dashboard')
    else:
        form = UserRegistrationForm()
        
    return render(request, 'register.html', {'form': form})
