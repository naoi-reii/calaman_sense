import re
from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import VerifiedPhone


class PhoneForm(forms.Form):
    phone = forms.CharField(label='Mobile number', max_length=20,
                            widget=forms.TextInput(attrs={'autocomplete': 'tel', 'placeholder': '09XXXXXXXXX', 'type': 'tel'}))

    def clean_phone(self):
        number = re.sub(r'[\s()-]', '', self.cleaned_data['phone'])
        if re.fullmatch(r'09\d{9}', number):
            number = '+63' + number[1:]
        if not re.fullmatch(r'\+639\d{9}', number):
            raise forms.ValidationError('Enter a Philippine mobile number: 09XXXXXXXXX or +639XXXXXXXXX.')
        return number


class RegistrationForm(UserCreationForm, PhoneForm):
    def clean_phone(self):
        number = super().clean_phone()
        if VerifiedPhone.objects.filter(number=number).exists():
            raise forms.ValidationError('This mobile number is already registered. Sign in or reset your password.')
        return number


class CodeForm(forms.Form):
    code = forms.RegexField(r'^[0-9]{6}$', label='Verification code',
                           widget=forms.TextInput(attrs={'inputmode': 'numeric', 'autocomplete': 'one-time-code', 'maxlength': '6'}))
