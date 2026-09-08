from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _
import re

class UppercaseValidator:
    def validate(self, password, user=None):
        if not re.search('[A-Z]', password):
            raise ValidationError(
                _("The password must contain at least 1 capital letter, A-Z."),
                code='password_no_upper',
            )

    def get_help_text(self):
        return _("Your password must contain at least 1 capital letter, A-Z.")
