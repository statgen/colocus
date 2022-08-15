from django.contrib.auth.models import AbstractUser
from django.db.models import CharField
from django.utils.translation import gettext_lazy as _


class User(AbstractUser):
    """
    Even though our app has no users in first iteration, it's easier to customize fields if a stub model is in place

    Default custom user model for colocus.
    If adding fields that need to be filled at user signup,
    check forms.SignupForm and forms.SocialSignupForms accordingly.
    """

    #: First and last name do not cover name patterns around the globe
    name = CharField(_("Name of User"), blank=True, max_length=255)
    first_name = None  # type: ignore
    last_name = None  # type: ignore
