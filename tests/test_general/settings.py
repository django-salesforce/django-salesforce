from django.utils.crypto import get_random_string

SECRET_KEY = get_random_string(length=32)
SF_CAN_RUN_WITHOUT_DJANGO = True
