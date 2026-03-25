# piakweb/utils.py
from functools import wraps
from django.shortcuts import redirect
from django.utils import timezone

from .models import SaaSUser, Tenant, Subscription  # ปรับตามชื่อ model จริงของเปี๊ยก

def subscription_required(view_func):
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):

        # 1) ต้อง login ก่อน
        user_id = request.session.get('saas_user_id')
        if not user_id:
            return redirect('login')

        # 2) ต้องมี tenant
        user = SaaSUser.objects.filter(id=user_id).first()
        if not user:
            request.session.flush()
            return redirect('login')

        # ดึง tenant จาก DB ตรง ๆ (กันปัญหา related_name)
        tenant = Tenant.objects.filter(owner=user).first()
        if not tenant:
            return redirect('tenant_setup')  # หรือ landing/register แล้วแต่ flow

        # 3) ต้องมี subscription ที่ใช้งานได้ (ถ้ายังไม่ทำระบบนี้ ให้ “ข้าม” ได้ก่อน)
        sub = Subscription.objects.filter(tenant=tenant).order_by('-id').first()
        if not sub:
            return redirect('no_subscription')

        # ถ้ามี field วันหมดอายุ เช่น end_date ให้เช็คเพิ่ม
        # if sub.end_date and sub.end_date < timezone.now():
        #     return redirect('no_subscription')

        return view_func(request, *args, **kwargs)

    return _wrapped
