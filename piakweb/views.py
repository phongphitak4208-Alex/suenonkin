# piakweb/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.hashers import make_password, check_password
from django.db.models import Q
from django.utils import timezone
from django.db import transaction, IntegrityError

from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.urls import reverse

from .tokens import saas_reset_token
from .utils import subscription_required
from .forms import ProductForm, CustomerForm
from .models import (
    SaaSUser, Product, Tenant, Subscription, Payment, Customer
)
from django.core.mail import EmailMultiAlternatives
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_protect

RESET_TOKEN_TTL_HOURS = 2  # ใช้เพื่อแสดงในอีเมล (อายุจริงควบคุมด้วย PASSWORD_RESET_TIMEOUT ใน settings.py)


# =========================
# Helpers (Session/Tenant)
# =========================
def get_current_user(request):
    """คืนค่า SaaSUser จาก session หรือ None"""
    user_id = request.session.get('saas_user_id')
    if not user_id:
        return None
    return SaaSUser.objects.filter(id=user_id).first()


def get_current_tenant(request):
    """คืนค่า Tenant ของ user จาก session หรือ None"""
    user = get_current_user(request)
    if not user:
        return None
    return Tenant.objects.filter(owner=user).first()


def saas_login_required(view_func):
    """Decorator ง่ายๆ สำหรับระบบ session ของเราเอง"""
    def _wrapped(request, *args, **kwargs):
        if not request.session.get('saas_user_id'):
            return redirect('landing')
        return view_func(request, *args, **kwargs)
    return _wrapped


# =========================
# Public pages
# =========================
def home(request):
    """
    (ถ้าไม่ได้ใช้ route มาที่ home แล้ว สามารถลบได้)
    ตอนนี้ให้ทำหน้าที่เหมือน landing เพื่อไม่สับสน
    """
    if request.session.get('saas_user_id'):
        return redirect('dashboard')
    return render(request, 'landing.html')


def landing(request):
    """
    หน้าแรก public (Landing)
    ถ้า login แล้วให้เด้งไป dashboard
    """
    if request.session.get('saas_user_id'):
        return redirect('dashboard')
    return render(request, 'landing.html')


def dashboard(request):
    if not request.session.get('saas_user_id'):
        return redirect('landing')
    return render(request, 'dashboard.html')


# =========================
# Auth (SaaSUser session)
# =========================
def register(request):
    if request.method == 'POST':
        email = (request.POST.get('email') or '').strip().lower()
        password = request.POST.get('password') or ''
        full_name = (request.POST.get('full_name') or '').strip()
        shop_name = (request.POST.get('shop_name') or '').strip()

        # validations
        if not full_name:
            messages.error(request, 'กรุณากรอกชื่อ-สกุล')
            return redirect('register')
        if not shop_name:
            messages.error(request, 'กรุณากรอกชื่อร้าน')
            return redirect('register')
        if not email:
            messages.error(request, 'กรุณากรอกอีเมล')
            return redirect('register')
        if not password:
            messages.error(request, 'กรุณากรอกรหัสผ่าน')
            return redirect('register')

        if SaaSUser.objects.filter(email=email).exists():
            messages.error(request, 'อีเมลนี้ถูกใช้แล้ว')
            return redirect('register')

        try:
            with transaction.atomic():
                user = SaaSUser.objects.create(
                    email=email,
                    password=make_password(password),
                    full_name=full_name,
                    provider=SaaSUser.PROVIDER_EMAIL
                )

                tenant = Tenant.objects.create(
                    owner=user,
                    shop_name=shop_name
                )

                today = timezone.localdate()
                sub, created = Subscription.objects.get_or_create(
                    tenant=tenant,
                    defaults={
                        "start_date": today,
                        "trial_end_date": today,          # start_trial จะ set ใหม่
                        "current_period_start": today,
                        "current_period_end": today,
                        "grace_period_end": today,
                    }
                )

                # เริ่ม trial (ให้ method นี้เป็นคน set วันที่ให้ถูก)
                sub.start_trial(price_during_trial=0)

            messages.success(request, 'สมัครสำเร็จ! เริ่มทดลองใช้งานฟรี 7 วัน')
            return redirect('login')

        except IntegrityError as e:
            messages.error(request, f'สมัครไม่สำเร็จ (ข้อมูลซ้ำ/ข้อจำกัดฐานข้อมูล): {e}')
            return redirect('register')
        except Exception as e:
            messages.error(request, f'สมัครไม่สำเร็จ: {e}')
            return redirect('register')

    return render(request, 'register.html')


def login_view(request):
    if request.session.get('saas_user_id'):
        return redirect('dashboard')

    if request.method == 'POST':
        email = (request.POST.get('email') or '').strip().lower()
        password = request.POST.get('password') or ''

        user = SaaSUser.objects.filter(email=email).first()
        if not user or not user.password or not check_password(password, user.password):
            messages.error(request, 'อีเมลหรือรหัสผ่านไม่ถูกต้อง')
            return render(request, 'login.html', {'email': email})

        request.session['saas_user_id'] = user.id
        messages.success(request, 'เข้าสู่ระบบสำเร็จ')
        return redirect('dashboard')

    return render(request, 'login.html')


def logout_view(request):
    request.session.flush()
    return redirect('landing')


# =========================
# Forgot / Reset Password
# =========================
@csrf_protect
@require_http_methods(["GET", "POST"])
def forgot_password(request):
    if request.method == "POST":
        email = (request.POST.get("email") or "").strip().lower()

           # ป้องกัน enumerate: ตอบเหมือนกันเสมอ
        user = SaaSUser.objects.filter(email=email).first()

        if user:
            uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
            token = saas_reset_token.make_token(user)
            reset_url = reverse("reset_password_confirm", kwargs={"uidb64": uidb64, "token": token})
            reset_link = request.build_absolute_uri(reset_url)
          
            subject = "ตั้งรหัสผ่านใหม่ - IPS AUTOPARTS SaaS"
            text_body = render_to_string("emails/reset_password.txt", {
                "full_name": user.full_name,
                "reset_link": reset_link,
                "ttl_hours": getattr(settings, "RESET_TOKEN_TTL_HOURS", 2),
            })
            html_body = render_to_string("emails/reset_password.html", {
                "full_name": user.full_name,
                "reset_link": reset_link,
                "ttl_hours": getattr(settings, "RESET_TOKEN_TTL_HOURS", 2),
            })

            msg = EmailMultiAlternatives(
                subject=subject,
                body=text_body,
                from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
                to=[user.email],
            )
            msg.attach_alternative(html_body, "text/html")
            msg.send(fail_silently=False)

        messages.success(request, "ถ้าอีเมลนี้มีอยู่ในระบบ เราได้ส่งลิงก์ตั้งรหัสใหม่ให้แล้ว")
        return redirect("login")

    return render(request, "forgot_password.html")


@csrf_protect
@require_http_methods(["GET", "POST"])
@csrf_protect
@require_http_methods(["GET", "POST"])
def reset_password_confirm(request, uidb64, token):
    # 1) decode uid
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = SaaSUser.objects.get(pk=uid)
    except Exception:
        user = None

    # 2) validate token
    if not user or not saas_reset_token.check_token(user, token):
        messages.error(request, "ลิงก์ไม่ถูกต้องหรือหมดอายุ กรุณาขอใหม่อีกครั้ง")
        return redirect("forgot_password")

    if request.method == "POST":
        password1 = request.POST.get("password1") or ""
        password2 = request.POST.get("password2") or ""

        if len(password1) < 8:
            messages.error(request, "รหัสผ่านต้องยาวอย่างน้อย 8 ตัวอักษร")
            return render(request, "reset_password_confirm.html", {"email": user.email})

        if password1 != password2:
            messages.error(request, "รหัสผ่านไม่ตรงกัน")
            return render(request, "reset_password_confirm.html", {"email": user.email})

        user.password = make_password(password1)
        user.save(update_fields=["password"])

        messages.success(request, "ตั้งรหัสผ่านใหม่สำเร็จ! กรุณาเข้าสู่ระบบ")
        return redirect("login")

    return render(request, "reset_password_confirm.html", {"email": user.email})


# =========================
# Backoffice pages
# =========================
def tenant_setup(request):
    if not request.session.get('saas_user_id'):
        return redirect('login')
    return render(request, 'tenant_setup.html')


@saas_login_required
def payment_required(request):
    return render(request, 'payment_required.html')


@saas_login_required
def upload_payment(request):
    """
    อัปโหลดสลิป + ต่ออายุรอบบิล
    """
    user = get_current_user(request)
    tenant = get_current_tenant(request)
    if not user or not tenant:
        return redirect('landing')

    # กันพังกรณียังไม่มี subscription
    subscription = Subscription.objects.filter(tenant=tenant).first()
    if not subscription:
        return redirect('no_subscription')

    if request.method == 'POST':
        amount = request.POST.get('amount')
        slip = request.FILES.get('slip_image')

        Payment.objects.create(
            subscription=subscription,
            amount=amount,
            slip_image=slip,
            note=f'โอนโดย {user.email}'
        )

        subscription.start_new_billing_cycle(monthly_price=amount)

        messages.success(request, 'บันทึกการชำระเงินเรียบร้อย ระบบต่ออายุให้แล้ว 30 วัน')
        return redirect('product_list')

    return render(request, 'upload_payment.html', {'subscription': subscription})


@saas_login_required
def no_subscription(request):
    return render(request, 'no_subscription.html')


# =========================
# Products (Multi-tenant)
# =========================
@subscription_required
def product_list(request):
    tenant = get_current_tenant(request)
    if not tenant:
        return redirect('tenant_setup')

    q = (request.GET.get('q') or '').strip()
    products = Product.objects.filter(tenant=tenant).order_by('product_code')

    if q:
        products = products.filter(
            Q(product_code__icontains=q) |
            Q(product_name__icontains=q)
        )

    return render(request, 'product_list.html', {'products': products, 'q': q})


@subscription_required
def add_product(request):
    tenant = get_current_tenant(request)
    if not tenant:
        return redirect('landing')

    if request.method == 'POST':
        form = ProductForm(request.POST)
        if form.is_valid():
            product = form.save(commit=False)
            product.tenant = tenant
            product.save()
            return redirect('product_list')
    else:
        form = ProductForm()

    return render(request, 'add_product.html', {'form': form})


@subscription_required
def edit_product(request, product_code):
    tenant = get_current_tenant(request)
    if not tenant:
        return redirect('landing')

    product = get_object_or_404(
        Product,
        tenant=tenant,
        product_code=product_code
    )

    if request.method == 'POST':
        product.product_name = request.POST.get('product_name')
        product.SalePrice = request.POST.get('SalePrice')
        product.stock = request.POST.get('stock')
        product.lastbyprice = request.POST.get('lastbyprice')
        product.saleprice1 = request.POST.get('saleprice1')
        product.save()
        return redirect('product_list')

    return render(request, 'edit_product.html', {'product': product})


@subscription_required
def delete_product(request, product_code):
    tenant = get_current_tenant(request)
    if not tenant:
        return redirect('landing')

    product = get_object_or_404(
        Product,
        tenant=tenant,
        product_code=product_code
    )

    if request.method == 'POST':
        product.delete()
        return redirect('product_list')

    return render(request, 'confirm_delete.html', {'product': product})


# =========================
# AR / Customers (Multi-tenant)
# =========================
@subscription_required
def ar_list(request):
    tenant = get_current_tenant(request)
    q = request.GET.get('q')

    customers = Customer.objects.filter(tenant=tenant)

    if q:
        customers = customers.filter(
            Q(ar_code__icontains=q) |
            Q(ar_name__icontains=q) |
            Q(phone__icontains=q)
        )

    customers = customers.order_by('ar_code')

    context = {
        'customers': customers,
        'q': q,
    }
    return render(request, 'ar_list.html', context)


@subscription_required
def add_ar(request):
    tenant = get_current_tenant(request)

    if request.method == 'POST':
        form = CustomerForm(request.POST)
        if form.is_valid():
            ar = form.save(commit=False)
            ar.tenant = tenant
            ar.save()

            messages.success(request, 'เพิ่มลูกค้าเรียบร้อยแล้ว')
            return redirect('ar_list')
    else:
        form = CustomerForm()

    return render(request, 'ar_form.html', {
        'form': form,
        'title': 'เพิ่มลูกค้าใหม่'
    })


@subscription_required
def edit_ar(request, ar_code):
    tenant = get_current_tenant(request)

    ar = get_object_or_404(
        Customer,
        tenant=tenant,
        ar_code=ar_code
    )

    if request.method == 'POST':
        form = CustomerForm(request.POST, instance=ar)
        if form.is_valid():
            form.save()
            messages.success(request, 'แก้ไขข้อมูลลูกค้าเรียบร้อยแล้ว')
            return redirect('ar_list')
    else:
        form = CustomerForm(instance=ar)

    return render(request, 'ar_form.html', {
        'form': form,
        'title': 'แก้ไขข้อมูลลูกค้า'
    })


@subscription_required
def delete_ar(request, ar_code):
    tenant = get_current_tenant(request)

    ar = get_object_or_404(
        Customer,
        tenant=tenant,
        ar_code=ar_code
    )

    ar.delete()
    messages.success(request, 'ลบลูกค้าเรียบร้อยแล้ว')
    return redirect('ar_list')
