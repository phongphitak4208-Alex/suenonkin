from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.utils.crypto import constant_time_compare
from django.utils.http import int_to_base36
from django.utils import timezone


class SaaSResetTokenGenerator(PasswordResetTokenGenerator):
    """
    Token จะ invalid ทันทีเมื่อ password เปลี่ยน (เพราะเอา hash มารวมในการคำนวณ)
    และมีอายุตาม settings.PASSWORD_RESET_TIMEOUT
    """
    def _make_hash_value(self, user, timestamp):
        return f"{user.pk}{user.password}{timestamp}"

saas_reset_token = SaaSResetTokenGenerator()
