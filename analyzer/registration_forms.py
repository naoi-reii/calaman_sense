from django import forms
from django.contrib.auth.forms import UserCreationForm


class RegistrationForm(UserCreationForm):
    first_name = forms.CharField(max_length=150)
    last_name = forms.CharField(max_length=150)

    def clean_password1(self):
        password = self.cleaned_data['password1']
        if not 8 <= len(password) <= 16:
            raise forms.ValidationError('Password must be 8–16 characters.')
        return password

    class Meta(UserCreationForm.Meta):
        fields = ('first_name', 'last_name', 'username')
