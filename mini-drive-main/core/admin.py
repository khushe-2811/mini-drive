from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from .models import File, Folder, Embedding, ShareToken, FolderShareToken


class EmbeddingInline(admin.StackedInline):
    model = Embedding
    readonly_fields = ("vector",)
    can_delete = False
    extra = 0


class ShareTokenInline(admin.TabularInline):
    model = ShareToken
    readonly_fields = ("uuid", "expiry")
    extra = 0


@admin.register(File)
class FileAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "owner_username",
        "folder_name",
        "size_formatted",
        "uploaded",
        "processed",
        "has_thumb",
        "view_link",
    )
    list_filter = ("processed", "uploaded", "mime_type")
    search_fields = ("name", "owner__username")
    readonly_fields = ("size", "uploaded", "processed", "preview_thumb")
    inlines = [EmbeddingInline, ShareTokenInline]

    def owner_username(self, obj):
        return obj.owner.username

    owner_username.short_description = "Owner"

    def folder_name(self, obj):
        if obj.folder:
            return obj.folder.name
        return "-"

    folder_name.short_description = "Folder"

    def size_formatted(self, obj):
        # Convert bytes to appropriate unit
        size = obj.size
        for unit in ["B", "KB", "MB", "GB"]:
            if size < 1024 or unit == "GB":
                return f"{size:.2f} {unit}"
            size /= 1024

    size_formatted.short_description = "Size"

    def has_thumb(self, obj):
        return bool(obj.thumb)

    has_thumb.boolean = True
    has_thumb.short_description = "Thumbnail"

    def preview_thumb(self, obj):
        if obj.thumb:
            return format_html(
                '<img src="{}" style="max-height: 200px; max-width: 200px;" />',
                obj.thumb.url,
            )
        return "-"

    preview_thumb.short_description = "Thumbnail Preview"

    def view_link(self, obj):
        # Create a download link
        url = reverse("download_file", args=[obj.id])
        return format_html('<a href="{}" target="_blank">Download</a>', url)

    view_link.short_description = "Actions"


class FolderShareTokenInline(admin.TabularInline):
    model = FolderShareToken
    readonly_fields = ("uuid", "expiry")
    extra = 0


class FileInline(admin.TabularInline):
    model = File
    fields = ("name", "size_formatted", "uploaded", "processed")
    readonly_fields = ("name", "size_formatted", "uploaded", "processed")
    extra = 0
    max_num = 0  # Don't allow adding files through this inline
    can_delete = False

    def size_formatted(self, obj):
        # Convert bytes to appropriate unit
        size = obj.size
        for unit in ["B", "KB", "MB", "GB"]:
            if size < 1024 or unit == "GB":
                return f"{size:.2f} {unit}"
            size /= 1024

    size_formatted.short_description = "Size"


@admin.register(Folder)
class FolderAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "owner_username",
        "parent_folder",
        "created",
        "file_count",
        "view_link",
    )
    list_filter = ("created",)
    search_fields = ("name", "owner__username")
    readonly_fields = ("created", "full_path")
    inlines = [FolderShareTokenInline, FileInline]

    def owner_username(self, obj):
        return obj.owner.username

    owner_username.short_description = "Owner"

    def parent_folder(self, obj):
        if obj.parent:
            return obj.parent.name
        return "-"

    parent_folder.short_description = "Parent Folder"

    def full_path(self, obj):
        path = []
        current = obj
        while current:
            path.insert(0, current.name)
            current = current.parent
        return "/" + "/".join(path)

    full_path.short_description = "Full Path"

    def file_count(self, obj):
        return obj.files.count()

    file_count.short_description = "Files"

    def view_link(self, obj):
        # Create a view link
        url = reverse("folder_detail", args=[obj.id])
        return format_html('<a href="{}" target="_blank">View</a>', url)

    view_link.short_description = "Actions"


@admin.register(Embedding)
class EmbeddingAdmin(admin.ModelAdmin):
    list_display = ("file_name", "owner_username", "vector_length", "has_text")
    search_fields = ("file__name", "file__owner__username")
    readonly_fields = ("vector", "extracted_text_preview")

    def file_name(self, obj):
        return obj.file.name

    file_name.short_description = "File"

    def owner_username(self, obj):
        return obj.file.owner.username

    owner_username.short_description = "Owner"

    def vector_length(self, obj):
        if isinstance(obj.vector, list):
            return len(obj.vector)
        return 0

    vector_length.short_description = "Vector Length"

    def has_text(self, obj):
        return bool(obj.extracted_text)

    has_text.boolean = True
    has_text.short_description = "Has Text"

    def extracted_text_preview(self, obj):
        if obj.extracted_text:
            # Return first 200 chars
            return obj.extracted_text[:200] + (
                "..." if len(obj.extracted_text) > 200 else ""
            )
        return "-"

    extracted_text_preview.short_description = "Text Preview"


@admin.register(ShareToken)
class ShareTokenAdmin(admin.ModelAdmin):
    list_display = (
        "uuid",
        "file_name",
        "owner_username",
        "expiry",
        "is_valid",
        "view_link",
    )
    list_filter = ("expiry",)
    search_fields = ("file__name", "file__owner__username")
    readonly_fields = ("uuid", "expiry")

    def file_name(self, obj):
        return obj.file.name

    file_name.short_description = "File"

    def owner_username(self, obj):
        return obj.file.owner.username

    owner_username.short_description = "Owner"

    def view_link(self, obj):
        # Create a view link
        url = reverse("serve_share", args=[obj.uuid])
        return format_html('<a href="{}" target="_blank">View</a>', url)

    view_link.short_description = "Actions"


@admin.register(FolderShareToken)
class FolderShareTokenAdmin(admin.ModelAdmin):
    list_display = (
        "uuid",
        "folder_name",
        "owner_username",
        "expiry",
        "is_valid",
        "view_link",
    )
    list_filter = ("expiry",)
    search_fields = ("folder__name", "folder__owner__username")
    readonly_fields = ("uuid", "expiry")

    def folder_name(self, obj):
        return obj.folder.name

    folder_name.short_description = "Folder"

    def owner_username(self, obj):
        return obj.folder.owner.username

    owner_username.short_description = "Owner"

    def is_valid(self, obj):
        return obj.is_valid()

    is_valid.boolean = True
    is_valid.short_description = "Valid"

    def view_link(self, obj):
        # Create a view link
        url = reverse("serve_folder_share", args=[obj.uuid])
        return format_html('<a href="{}" target="_blank">View</a>', url)

    view_link.short_description = "Actions"
