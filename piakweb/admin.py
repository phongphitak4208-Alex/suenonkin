from django.contrib import admin
from .models import Product

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('product_code', 'product_name', 'SalePrice')
    search_fields = ('product_code', 'product_name')

   

Debug = True
