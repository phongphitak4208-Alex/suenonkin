from django.contrib import admin
from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
from . import views

urlpatterns = [
    path('admin/', admin.site.urls),

    # public
    path('', views.landing, name='landing'),

    # auth
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('register/', views.register, name='register'),

    # after login
    path('dashboard/', views.dashboard, name='dashboard'),

    # reset password
    path('forgot-password/', views.forgot_password, name='forgot_password'),
    path('reset-password/<uidb64>/<token>/', views.reset_password_confirm, name='reset_password_confirm'),

    # products
    path('product_list/', views.product_list, name='product_list'),
    path('product/add/', views.add_product, name='add_product'),
    path('product/<str:product_code>/edit/', views.edit_product, name='edit_product'),
    path('product/<str:product_code>/delete/', views.delete_product, name='delete_product'),
    path('tenant/setup/', views.tenant_setup, name='tenant_setup'),

    # AR
    path('customers/', views.ar_list, name='ar_list'),
    path('customers/add/', views.add_ar, name='add_ar'),
    path('customers/edit/<str:ar_code>/', views.edit_ar, name='edit_ar'),
    path('customers/delete/<str:ar_code>/', views.delete_ar, name='delete_ar'),
]

# Serve MEDIA in development only
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
