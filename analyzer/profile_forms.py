from django import forms
from .models import UserProfile

class ProfileForm(forms.ModelForm):
    first_name = forms.CharField(max_length=150, required=False)
    last_name = forms.CharField(max_length=150, required=False)
    email = forms.EmailField(max_length=254, required=False)
    remove_photo = forms.BooleanField(required=False)
    class Meta:
        model = UserProfile
        fields = ['first_name', 'last_name', 'email', 'photo', 'contact_number', 'farm_name', 'location']
        widgets = {'photo': forms.FileInput(attrs={'accept': 'image/jpeg,image/png,image/webp'})}

    def clean_photo(self):
        photo = self.cleaned_data.get('photo')
        if photo and hasattr(photo, 'content_type'):
            if photo.size > 5 * 1024 * 1024:
                raise forms.ValidationError('Please choose a photo smaller than 5MB.')
            if photo.image.format not in ('JPEG', 'PNG', 'WEBP'):
                raise forms.ValidationError('Please choose a JPG, PNG, or WebP image.')
        return photo

    def clean(self):
        data = super().clean()
        if data.get('remove_photo') and 'photo' in self.files:
            self.add_error('photo', 'Choose either a new photo or Remove photo, not both.')
        return data
