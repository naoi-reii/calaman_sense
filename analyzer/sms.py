import requests
from django.conf import settings


class SMSUnavailable(Exception):
    pass


def send_code(number, code):
    """No console or fixed-code fallback: missing configuration fails closed."""
    if not settings.SMS_API_KEY:
        raise SMSUnavailable('SMS delivery is not configured yet. Please contact the administrator.')
    try:
        response = requests.post(
            'https://api.semaphore.co/api/v4/messages',
            data={'apikey': settings.SMS_API_KEY, 'number': number.lstrip('+'),
                  'message': f'Your CalamanSense verification code is {code}. Expires in 5 minutes. Do not share this code.',
                  'sendername': settings.SMS_SENDER_NAME}, timeout=15,
        )
        response.raise_for_status()
        result = response.json()
        if not isinstance(result, list) or not result or not result[0].get('message_id'):
            raise SMSUnavailable('SMS could not be sent. Please try again later.')
    except (requests.RequestException, ValueError) as exc:
        raise SMSUnavailable('SMS could not be sent. Please try again later.') from exc
