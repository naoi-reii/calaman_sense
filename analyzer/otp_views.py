import secrets
from datetime import timedelta
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password, check_password
from django.contrib.auth.forms import SetPasswordForm
from django.db import transaction, IntegrityError
from django.shortcuts import render, redirect
from django.utils import timezone
from .models import PhoneOTP, VerifiedPhone, UserProfile
from .otp_forms import RegistrationForm, PhoneForm, CodeForm
from .sms import send_code, SMSUnavailable


def start(request, purpose):
    if request.user.is_authenticated:
        return redirect('dashboard')
    form = (RegistrationForm if purpose == 'register' else PhoneForm)(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        number = form.cleaned_data['phone']
        now = timezone.now()
        recent = PhoneOTP.objects.filter(number=number)
        # Shared across sessions and purposes so restarting the form cannot bypass limits.
        if recent.filter(created_at__gt=now - timedelta(seconds=60)).exists():
            form.add_error(None, 'Please wait 60 seconds before requesting another code.')
        elif recent.filter(created_at__gt=now - timedelta(hours=1)).count() >= 5:
            form.add_error(None, 'Too many requests for this number. Please try again in an hour.')
        else:
            payload = {}
            if purpose == 'register':
                payload = {'username': form.cleaned_data['username'],
                           'password': make_password(form.cleaned_data['password1'])}
            else:
                phone = VerifiedPhone.objects.filter(number=number, user__is_active=True).first()
                payload = {'user_id': phone.user_id if phone else None}
            code = f'{secrets.randbelow(1000000):06d}'
            challenge = PhoneOTP.objects.create(number=number, purpose=purpose, payload=payload,
                code_hash=make_password(code), expires_at=now + timedelta(minutes=5))
            try:
                if purpose == 'register' or payload.get('user_id'):
                    send_code(number, code)
            except SMSUnavailable as exc:
                challenge.consumed = True
                challenge.payload = {}
                challenge.save(update_fields=['consumed', 'payload'])
                form.add_error(None, str(exc))
            else:
                recent.exclude(pk=challenge.pk).update(consumed=True, payload={})
                request.session.cycle_key()
                request.session['phone_otp'] = str(challenge.token)
                return redirect('verify_otp')
    return render(request, 'register.html' if purpose == 'register' else 'otp_form.html',
                  {'form': form, 'title': 'Forgot password', 'description': 'Enter the mobile number you verified during registration.',
                   'button': 'Send verification code'})


def register(request):
    return start(request, 'register')


def forgot_password(request):
    return start(request, 'reset')


def verify(request):
    token = request.session.get('phone_otp')
    if not token:
        return redirect('login')
    form = CodeForm(request.POST or None)
    challenge = PhoneOTP.objects.filter(token=token).first()
    if not challenge:
        return redirect('login')
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            challenge = PhoneOTP.objects.select_for_update().get(pk=challenge.pk)
            # Atomic claim prevents concurrent requests consuming the same challenge.
            claimed = PhoneOTP.objects.filter(pk=challenge.pk, consumed=False,
                expires_at__gt=timezone.now(), attempts__lt=5).update(attempts=challenge.attempts + 1)
            if not claimed:
                form.add_error(None, 'This code has expired or reached its attempt limit. Request a new code.')
            elif not check_password(form.cleaned_data['code'], challenge.code_hash):
                form.add_error('code', 'Invalid verification code.')
            else:
                challenge.consumed = True
                payload = challenge.payload
                challenge.payload = {}
                challenge.save(update_fields=['consumed', 'payload'])
                if challenge.purpose == 'register':
                    try:
                        with transaction.atomic():
                            user = get_user_model().objects.create(username=payload['username'], password=payload['password'])
                            VerifiedPhone.objects.create(user=user, number=challenge.number)
                            UserProfile.objects.get_or_create(user=user, defaults={'contact_number': challenge.number})
                    except IntegrityError:
                        form.add_error(None, 'Username or mobile number is already registered. Please start again.')
                    else:
                        request.session.pop('phone_otp', None)
                        return redirect('/login/?registered=1')
                elif payload.get('user_id'):
                    request.session.pop('phone_otp', None)
                    request.session.cycle_key()
                    request.session['phone_reset'] = {'user_id': payload['user_id'],
                        'expires': (timezone.now() + timedelta(minutes=5)).timestamp()}
                    return redirect('reset_password')
                else:
                    form.add_error(None, 'Invalid verification code.')
    return render(request, 'otp_form.html', {'form': form, 'title': 'Verify mobile number',
        'description': 'If eligible, a 6-digit code was sent to your mobile number. It expires in 5 minutes.',
        'button': 'Verify code', 'restart': 'register' if challenge.purpose == 'register' else 'forgot_password'})


def reset_password(request):
    grant = request.session.get('phone_reset', {})
    if grant.get('expires', 0) <= timezone.now().timestamp():
        request.session.pop('phone_reset', None)
        return redirect('forgot_password')
    user = get_user_model().objects.filter(pk=grant.get('user_id'), is_active=True).first()
    if not user:
        return redirect('forgot_password')
    form = SetPasswordForm(user, request.POST or None)
    if request.method == 'POST' and form.is_valid():
        form.save()
        request.session.flush()
        return redirect('/login/?password_reset=1')
    return render(request, 'otp_form.html', {'form': form, 'title': 'Set a new password', 'button': 'Save password'})
