import uuid
import os
from datetime import datetime, timedelta
from django.db import models
from django.conf import settings
from django.urls import reverse
from django.utils import timezone


class Folder(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    parent = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.CASCADE, related_name="children"
    )
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("owner", "name", "parent")
        ordering = ["name"]

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("folder_detail", args=[str(self.id)])

    def get_breadcrumbs(self):
        """Return list of parent folders for breadcrumb navigation."""
        breadcrumbs = []
        current = self
        while current:
            breadcrumbs.insert(0, current)
            current = current.parent
        return breadcrumbs

    def get_full_path(self):
        """Return the full path of the folder."""
        path = [self.name]
        current = self.parent
        while current:
            path.insert(0, current.name)
            current = current.parent
        return os.path.join(*path) if path else "/"

    def create_share_link(self):
        """Create a new share token for this folder."""
        return FolderShareToken.objects.create(
            folder=self, expiry=timezone.now() + timedelta(hours=12)
        )

    def delete(self, *args, **kwargs):
        """Override delete method to delete all files from storage before cascade deletion."""
        # First, recursively process all subfolders to ensure proper file deletion
        for subfolder in self.children.all():
            subfolder.delete()

        # Delete all files in this folder from storage
        for file in self.files.all():
            # Explicitly call file.delete() to ensure the overridden method is used
            file.delete()

        # Now proceed with normal deletion (this will remove the folder from db)
        super().delete(*args, **kwargs)


class File(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    folder = models.ForeignKey(
        Folder, null=True, blank=True, on_delete=models.CASCADE, related_name="files"
    )
    name = models.CharField(max_length=255)
    file = models.FileField(upload_to="files/")
    size = models.BigIntegerField()
    uploaded = models.DateTimeField(auto_now_add=True)
    thumb = models.ImageField(upload_to="thumbs/", null=True, blank=True)
    mime_type = models.CharField(max_length=100, blank=True, null=True)
    processed = models.BooleanField(default=False)

    class Meta:
        ordering = ["-uploaded"]
        unique_together = ("folder", "name", "owner")

    def __str__(self):
        return f"{self.name} ({self.owner.username})"

    def get_absolute_url(self):
        return reverse("file_detail", args=[str(self.id)])

    def create_share_link(self):
        """Create a new share token for this file."""
        return ShareToken.objects.create(
            file=self, expiry=timezone.now() + timedelta(hours=12)
        )

    def delete(self, *args, **kwargs):
        """Override delete method to also delete physical files."""
        # Delete the actual files from storage
        if self.file:
            storage = self.file.storage
            if storage.exists(self.file.name):
                storage.delete(self.file.name)

        if self.thumb:
            storage = self.thumb.storage
            if storage.exists(self.thumb.name):
                storage.delete(self.thumb.name)

        # Call the parent delete method
        super().delete(*args, **kwargs)


class Embedding(models.Model):
    file = models.OneToOneField(File, on_delete=models.CASCADE)
    vector = models.JSONField()  # list[float] length 1536
    extracted_text = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"Embedding for {self.file.name}"


class ShareToken(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4, unique=True)
    file = models.ForeignKey(File, on_delete=models.CASCADE)
    expiry = models.DateTimeField()

    def __str__(self):
        return f"Share link for {self.file.name} (expires: {self.expiry})"

    def is_valid(self):
        """Check if token is still valid."""
        return timezone.now() < self.expiry

    def get_absolute_url(self):
        return reverse("serve_share", args=[str(self.uuid)])


class FolderShareToken(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4, unique=True)
    folder = models.ForeignKey(Folder, on_delete=models.CASCADE)
    expiry = models.DateTimeField()

    def __str__(self):
        return f"Share link for folder {self.folder.name} (expires: {self.expiry})"

    def is_valid(self):
        """Check if token is still valid."""
        return timezone.now() < self.expiry

    def get_absolute_url(self):
        return reverse("serve_folder_share", args=[str(self.uuid)])
