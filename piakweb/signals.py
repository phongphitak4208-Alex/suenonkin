from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Tenant, Subscription

@receiver(post_save, sender=Tenant)
def create_subscription_for_tenant(sender, instance, created, **kwargs):
    if created:
        Subscription.objects.create(tenant=instance)
