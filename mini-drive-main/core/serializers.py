from rest_framework import serializers
from .models import File, ShareToken


class FileSerializer(serializers.ModelSerializer):
    thumb_url = serializers.SerializerMethodField()
    download_url = serializers.SerializerMethodField()
    owner_username = serializers.SerializerMethodField()

    class Meta:
        model = File
        fields = [
            "id",
            "name",
            "size",
            "uploaded",
            "thumb_url",
            "download_url",
            "owner_username",
            "processed",
        ]

    def get_thumb_url(self, obj):
        if obj.thumb:
            return obj.thumb.url
        return None

    def get_download_url(self, obj):
        request = self.context.get("request")
        if request:
            return request.build_absolute_uri(f"/download/{obj.id}/")
        return f"/download/{obj.id}/"

    def get_owner_username(self, obj):
        return obj.owner.username


class ShareTokenSerializer(serializers.ModelSerializer):
    file_name = serializers.SerializerMethodField()
    share_url = serializers.SerializerMethodField()

    class Meta:
        model = ShareToken
        fields = ["uuid", "file_name", "expiry", "share_url"]

    def get_file_name(self, obj):
        return obj.file.name

    def get_share_url(self, obj):
        request = self.context.get("request")
        if request:
            return request.build_absolute_uri(f"/s/{obj.uuid}/")
        return f"/s/{obj.uuid}/"


class FileUploadSerializer(serializers.ModelSerializer):
    class Meta:
        model = File
        fields = ["file"]

    def create(self, validated_data):
        request = self.context.get("request")
        file = validated_data.get("file")

        instance = File(owner=request.user, name=file.name, file=file, size=file.size)
        instance.save()

        return instance
