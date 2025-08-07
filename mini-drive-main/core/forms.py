from django import forms
from django.core.exceptions import ValidationError
from django.conf import settings
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from .models import File


class FileUploadForm(forms.ModelForm):
    class Meta:
        model = File
        fields = ["file"]

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)
        self.fields["file"].widget.attrs.update({"class": "form-control"})

    def clean_file(self):
        file = self.cleaned_data.get("file")
        if file:
            # Check file size against user quota
            max_size_mb = settings.MAX_STORAGE_MB
            max_size_bytes = max_size_mb * 1024 * 1024

            # Get user's total storage used
            if self.user:
                user_storage = File.objects.filter(owner=self.user).values_list(
                    "size", flat=True
                )
                total_used = sum(user_storage)

                # Check if this file would exceed quota
                if total_used + file.size > max_size_bytes:
                    raise ValidationError(
                        f"This file would exceed your storage quota of {max_size_mb} MB."
                    )

            # Set instance attributes
            self.instance.name = file.name
            self.instance.size = file.size

            if self.user:
                self.instance.owner = self.user

        return file


class SearchForm(forms.Form):
    query = forms.CharField(
        max_length=200,
        required=True,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Search your files...",
            }
        ),
    )


class UserRegistrationForm(UserCreationForm):
    email = forms.EmailField(
        max_length=254,
        required=True,
        widget=forms.EmailInput(attrs={'class': 'form-control form-control-lg', 'placeholder': 'Enter your email'})
    )
    
    class Meta:
        model = User
        fields = ('username', 'email', 'password1', 'password2')
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].widget.attrs.update({
            'class': 'form-control form-control-lg',
            'placeholder': 'Choose a username'
        })
        self.fields['password1'].widget.attrs.update({
            'class': 'form-control form-control-lg',
            'placeholder': 'Create a password'
        })
        self.fields['password2'].widget.attrs.update({
            'class': 'form-control form-control-lg',
            'placeholder': 'Confirm your password'
        })
    
    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise ValidationError("A user with that email already exists.")
        return email
