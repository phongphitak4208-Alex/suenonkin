from django.db import models
# 08/12/2568 from .models_saas import Tenant   # อ้างถึงรุ่น Tenant ที่เราออกแบบก่อนหน้านี้
# piakweb/models.py

from django.utils import timezone
from datetime import timedelta

class SaaSUser(models.Model):
    """เก็บข้อมูลผู้ใช้ระบบ (Login)"""
    PROVIDER_EMAIL = 'email'
    PROVIDER_GOOGLE = 'google'
    PROVIDER_FACEBOOK = 'facebook'

    PROVIDER_CHOICES = [
        (PROVIDER_EMAIL, 'Email'),
        (PROVIDER_GOOGLE, 'Google'),
        (PROVIDER_FACEBOOK, 'Facebook'),
    ]

    email = models.EmailField(unique=True)
    password = models.CharField(max_length=255, blank=True, null=True)  # ถ้า social login อาจไม่ใช้
    full_name = models.CharField(max_length=100, blank=True, null=True)
    provider = models.CharField(max_length=20, choices=PROVIDER_CHOICES, default=PROVIDER_EMAIL)
    provider_id = models.CharField(max_length=255, blank=True, null=True)  # ไว้ผูกกับ id ของ Google/Facebook
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    last_login = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return self.email or f'User {self.id}'
    
    class Meta:
        db_table = 'SAASUSER'


class Tenant(models.Model):
    tenant_id = models.BigAutoField(primary_key=True, db_column='TENANT_ID')

    owner = models.ForeignKey(SaaSUser, on_delete=models.CASCADE, related_name='tenants')
    shop_name = models.CharField(max_length=200, db_column='SHOP_NAME')
    is_active = models.BooleanField(default=True, db_column='IS_ACTIVE')
    created_at = models.DateTimeField(auto_now_add=True, db_column='CREATED_AT')

    def __str__(self):
        return self.shop_name

    class Meta:
        db_table = 'TENANT'   # แนะนำตัวใหญ่สำหรับ Oracle
        

class Subscription(models.Model):
    """สถานะการใช้งาน (trial / active / หมดอายุ) ของแต่ละ tenant"""

    STATUS_TRIAL = 'trial'
    STATUS_ACTIVE = 'active'
    STATUS_EXPIRED = 'expired'
    STATUS_SUSPENDED = 'suspended'

    STATUS_CHOICES = [
        (STATUS_TRIAL, 'Trial'),
        (STATUS_ACTIVE, 'Active'),
        (STATUS_EXPIRED, 'Expired'),
        (STATUS_SUSPENDED, 'Suspended'),
    ]

    tenant = models.OneToOneField('Tenant', on_delete=models.CASCADE, related_name='subscription')

    price_per_month = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    # ---- แนว B: ใส่ default ให้ insert ผ่านเสมอ ----
    start_date = models.DateField(default=timezone.localdate)  # วันที่สมัคร/เริ่ม trial
    trial_end_date = models.DateField(default=timezone.localdate)

    current_period_start = models.DateField(default=timezone.localdate)
    current_period_end = models.DateField(default=timezone.localdate)
    grace_period_end = models.DateField(default=timezone.localdate)

    # กำหนดรอบบิลแบบง่ายก่อน
    trial_days = models.PositiveSmallIntegerField(default=7)
    billing_cycle_days = models.PositiveSmallIntegerField(default=30)
    grace_days = models.PositiveSmallIntegerField(default=2)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_TRIAL)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # ---------- helper methods ----------
    @property
    def is_trial_active(self):
        today = timezone.localdate()
        return self.status == self.STATUS_TRIAL and today <= self.trial_end_date

    @property
    def is_active(self):
        today = timezone.localdate()
        return self.status == self.STATUS_ACTIVE and today <= self.grace_period_end

    @property
    def days_to_period_end(self):
        today = timezone.localdate()
        return (self.current_period_end - today).days

    def _apply_trial_defaults_if_needed(self):
        """ใช้ตอนสร้าง record ใหม่/หรือ record ยังไม่ถูก init ให้ครบ"""
        # ถ้าเป็น record ใหม่หรือ field ยังเท่ากับวันเดียวกันแบบ default (บ่งชี้ว่ายังไม่ init จริง)
        today = timezone.localdate()

        # ถ้า status เป็น trial และยังไม่ได้ตั้ง trial_end_date ตาม trial_days
        if self.status == self.STATUS_TRIAL:
            # ตั้ง start_date ถ้ายังไม่มีค่า (กรณี backfill/แก้ไข)
            if not self.start_date:
                self.start_date = today

            # trial_end_date = start_date + trial_days
            self.trial_end_date = self.start_date + timedelta(days=int(self.trial_days))

            # รอบปัจจุบันสำหรับ trial
            self.current_period_start = self.start_date
            self.current_period_end = self.trial_end_date
            self.grace_period_end = self.trial_end_date  # trial ไม่ต้อง grace เพิ่มก็ได้

    def save(self, *args, **kwargs):
        creating = self._state.adding

        # ถ้าสร้างใหม่ และยังเป็น trial ให้ init ค่าให้ครบ
        if creating and self.status == self.STATUS_TRIAL:
            self._apply_trial_defaults_if_needed()

        super().save(*args, **kwargs)

    def start_trial(self, price_during_trial=0):
        """เรียกตอนสมัครใหม่ (ถ้าต้องการ override ค่า default)"""
        self.price_per_month = price_during_trial
        self.status = self.STATUS_TRIAL
        self._apply_trial_defaults_if_needed()
        self.save()

    def start_new_billing_cycle(self, monthly_price):
        """เรียกตอนยืนยันการชำระเงินรอบใหม่"""
        today = timezone.localdate()
        self.price_per_month = monthly_price
        self.current_period_start = today
        self.current_period_end = today + timedelta(days=int(self.billing_cycle_days))
        self.grace_period_end = self.current_period_end + timedelta(days=int(self.grace_days))
        self.status = self.STATUS_ACTIVE
        self.save()    

    class Meta:
        db_table = 'SUBSCRIPTION'
        

class Payment(models.Model):
    subscription = models.ForeignKey(
        Subscription,
        on_delete=models.CASCADE,
        related_name='payments'
    )

    amount = models.DecimalField(max_digits=10, decimal_places=2)
    paid_at = models.DateTimeField(default=timezone.now)
    note = models.CharField(max_length=255, blank=True, null=True)
    slip_image = models.ImageField(upload_to='payment_slips/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.subscription.tenant.shop_name} paid {self.amount}'

    class Meta:
        db_table = 'PAYMENT'

class Product(models.Model):
    product_id = models.BigAutoField(primary_key=True, db_column='PRODUCT_ID')

    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        db_column='TENANT_ID',
        related_name='products',
    )

    product_code = models.CharField(max_length=50, db_column='PRODUCT_CODE')
    product_name = models.CharField(max_length=200, db_column='PRODUCT_NAME')

    SalePrice = models.DecimalField(  # แนะนำให้เป็น snake_case ใน Python
        max_digits=10,
        decimal_places=2,
        db_column='saleprice',
        default=0,
    )

    lastbyprice = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        db_column='lastbyprice',
        default=0,
    )

    saleprice1 = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        db_column='saleprice1',
        default=0,
    )

    stock = models.IntegerField(db_column='STOCK', default=0)
    is_active = models.BooleanField(db_column='IS_ACTIVE', default=True)

    created_at = models.DateTimeField(db_column='CREATED_AT', auto_now_add=True)
    updated_at = models.DateTimeField(db_column='UPDATED_AT', auto_now=True)

    class Meta:
        db_table = 'B_PRODUCT'
     
        constraints = [
            models.UniqueConstraint(
                fields=['tenant', 'product_code'],
                name='UQ_B_PRODUCT_TENANT_CODE',
            ),
        ]
        indexes = [
         #   models.Index(fields=['tenant'], name='IX_B_PRODUCT_TENANT'),
            models.Index(fields=['tenant', 'product_name'], name='IX_B_PRODUCT_TENANT_NAME'),
        ]

    def __str__(self):
        return f'[{self.tenant_id}] {self.product_code} - {self.product_name}'
    

class Customer(models.Model):    # ลูกค้า  
    """
    ลูกค้า (Accounts Receivable) แยกตาม Tenant
    """
    ar_id = models.BigAutoField(primary_key=True, db_column='AR_ID')

    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        db_column='TENANT_ID',
        related_name='customers',
    )

    # รหัสลูกค้า: unique ต่อ tenant (ร้าน A/B ซ้ำกันได้)
    ar_code = models.CharField(max_length=50, db_column='AR_CODE')

    # ชื่อลูกค้า/ชื่อร้าน
    ar_name = models.CharField(max_length=200, db_column='AR_NAME')

    # ข้อมูลติดต่อ
    contact_name = models.CharField(max_length=200, blank=True, null=True, db_column='CONTACT_NAME')
    phone = models.CharField(max_length=50, blank=True, null=True, db_column='PHONE')
    email = models.EmailField(blank=True, null=True, db_column='EMAIL')
    line_id = models.CharField(max_length=100, blank=True, null=True, db_column='LINE_ID')

    # ที่อยู่
    address1 = models.CharField(max_length=255, blank=True, null=True, db_column='ADDRESS1')
    address2 = models.CharField(max_length=255, blank=True, null=True, db_column='ADDRESS2')
    subdistrict = models.CharField(max_length=100, blank=True, null=True, db_column='SUBDISTRICT')
    district = models.CharField(max_length=100, blank=True, null=True, db_column='DISTRICT')
    province = models.CharField(max_length=100, blank=True, null=True, db_column='PROVINCE')
    zipcode = models.CharField(max_length=20, blank=True, null=True, db_column='ZIPCODE')

    # ภาษี/ทะเบียน
    tax_id = models.CharField(max_length=30, blank=True, null=True, db_column='TAX_ID')  # เลขผู้เสียภาษี 13 หลัก (เผื่อรูปแบบอื่น)
    branch_no = models.CharField(max_length=10, blank=True, null=True, db_column='BRANCH_NO')  # สาขา (เช่น 00000)

    # เงื่อนไขเครดิต
    credit_days = models.IntegerField(default=0, db_column='CREDIT_DAYS')  # เครดิตกี่วัน
    credit_limit = models.DecimalField(max_digits=12, decimal_places=2, default=0, db_column='CREDIT_LIMIT')

    # หมายเหตุ/สถานะ
    remark = models.CharField(max_length=255, blank=True, null=True, db_column='REMARK')
    is_active = models.BooleanField(default=True, db_column='IS_ACTIVE')

    created_at = models.DateTimeField(auto_now_add=True, db_column='CREATED_AT')
    updated_at = models.DateTimeField(auto_now=True, db_column='UPDATED_AT')

    class Meta:
        db_table = 'B_AR'
        constraints = [
            models.UniqueConstraint(
                fields=['tenant', 'ar_code'],
                name='UQ_B_AR_TENANT_CODE',
            ),
        ]
        indexes = [
            models.Index(fields=['tenant', 'ar_name'], name='IX_B_AR_TENANT_NAME'),
            models.Index(fields=['tenant', 'phone'], name='IX_B_AR_TENANT_PHONE'),
        ]

    def __str__(self):
        return f'[{self.tenant_id}] {self.ar_code} - {self.ar_name}'
