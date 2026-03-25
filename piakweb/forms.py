# piakweb/forms.py

from django import forms
from .models import Product
from .models import Customer

class ProductForm(forms.ModelForm):  #สินค้้า
    class Meta:
        model = Product
        fields = [
            'product_code',
            'product_name',
            'SalePrice',
            'stock',
            'lastbyprice',
            'saleprice1'
        ]

        labels = {
            'product_code' : 'รหัสสินค้า',
            'product_name' : 'ชื่อสินค้า',
            'SalePrice' : 'ราคาขาย',
            'stock' : 'สต็อคคงเหลือ',
            'lastbyprice' : 'ราคาทุน',
            'saleprice1' : 'ราคาพิเศษ'
        }

        widgets = {
            'product_code' : forms.TextInput(attrs={'class': 'form-control'}),
            'product_name' : forms.TextInput(attrs={'class': 'form-control'}),
            'SalePrice' : forms.NumberInput(attrs={'class': 'form-control'}),
            'stock' : forms.NumberInput(attrs={'class': 'form-control'}),
            'lastbyprice' : forms.NumberInput(attrs={'class': 'form-control'}),
            'saleprice1' : forms.NumberInput(attrs={'class': 'form-control'}),
        }


class CustomerForm(forms.ModelForm):  #ลูกค้า

    class Meta:
        model = Customer
        fields = [
            'ar_code',
            'ar_name',
            'contact_name',
            'phone',
            'email',
            'line_id',

            'address1',
            'address2',
            'subdistrict',
            'district',
            'province',
            'zipcode',

            'tax_id',
            'branch_no',

            'credit_days',
            'credit_limit',

            'remark',
            'is_active',
        ]

        widgets = {
            'ar_code': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'เช่น C0001'
            }),
            'ar_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'ชื่อลูกค้า / ชื่อร้าน'
            }),
            'contact_name': forms.TextInput(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'line_id': forms.TextInput(attrs={'class': 'form-control'}),

            'address1': forms.TextInput(attrs={'class': 'form-control'}),
            'address2': forms.TextInput(attrs={'class': 'form-control'}),
            'subdistrict': forms.TextInput(attrs={'class': 'form-control'}),
            'district': forms.TextInput(attrs={'class': 'form-control'}),
            'province': forms.TextInput(attrs={'class': 'form-control'}),
            'zipcode': forms.TextInput(attrs={'class': 'form-control'}),

            'tax_id': forms.TextInput(attrs={'class': 'form-control'}),
            'branch_no': forms.TextInput(attrs={'class': 'form-control'}),

            'credit_days': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 0
            }),
            'credit_limit': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01'
            }),

            'remark': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
        }

    def clean_ar_code(self):
        return self.cleaned_data['ar_code'].strip().upper()