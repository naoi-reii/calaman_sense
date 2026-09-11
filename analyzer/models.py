from django.db import models
from django.contrib.auth.models import User

class Scan(models.Model):
    QUALITY_CHOICES = [
        ('Best Quality', 'Best Quality'),
        ('Good Quality', 'Good Quality'),
        ('Average', 'Average'),
        ('Rejected', 'Rejected'),
    ]

    id = models.AutoField(primary_key=True)
    created_at = models.DateTimeField(auto_now_add=True)
    batch_name = models.CharField(max_length=255, blank=True, null=True)
    supplier_name = models.CharField(max_length=255, blank=True, null=True)
    quality_grade = models.CharField(max_length=50, choices=QUALITY_CHOICES, blank=True, null=True)
    
    # Counts
    fruit_count_total = models.IntegerField(default=0)
    fruit_count_good = models.IntegerField(default=0)
    fruit_count_defective = models.IntegerField(default=0)
    
    # Sizes
    size_small_pct = models.FloatField(default=0.0)
    size_medium_pct = models.FloatField(default=0.0)
    size_large_pct = models.FloatField(default=0.0)
    size_xl_pct = models.FloatField(default=0.0)
    
    # Ripeness
    ripeness_unripe_pct = models.FloatField(default=0.0)
    ripeness_ripe_pct = models.FloatField(default=0.0)
    ripeness_overripe_pct = models.FloatField(default=0.0)
    
    # Defects
    defect_blemished_pct = models.FloatField(default=0.0)
    defect_mold_pct = models.FloatField(default=0.0)
    defect_cracked_pct = models.FloatField(default=0.0)
    defect_insect_pct = models.FloatField(default=0.0)
    defect_bruised_pct = models.FloatField(default=0.0)
    defect_foreign_matter_pct = models.FloatField(default=0.0)
    
    model_version = models.CharField(max_length=50, default="mock-v0")
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return f"Scan {self.id} - {self.created_at.strftime('%Y-%m-%d %H:%M')}"

class ScanImage(models.Model):
    id = models.AutoField(primary_key=True)
    scan = models.ForeignKey(Scan, related_name='images', on_delete=models.CASCADE)
    image = models.ImageField(upload_to='scans/')
    mock_annotations = models.JSONField(default=list, blank=True)
    label_corrections = models.JSONField(default=dict, blank=True)

    def __str__(self):
        return f"Image for Scan {self.scan.id}"

class TrainingSample(models.Model):
    id = models.AutoField(primary_key=True)
    image = models.ImageField(upload_to='training/')
    label = models.CharField(max_length=255)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return f"Training Sample {self.id} ({self.label})"

class Setting(models.Model):
    key = models.CharField(max_length=255, unique=True)
    value = models.CharField(max_length=255)

    def __str__(self):
        return f"{self.key}: {self.value}"

from django.db.models.signals import post_delete
from django.dispatch import receiver
import os

@receiver(post_delete, sender=ScanImage)
def auto_delete_file_on_delete(sender, instance, **kwargs):
    """
    Deletes file from filesystem
    when corresponding `ScanImage` object is deleted.
    """
    if instance.image:
        if os.path.isfile(instance.image.path):
            os.remove(instance.image.path)


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    photo = models.ImageField(upload_to='profiles/', blank=True)
    contact_number = models.CharField(max_length=30, blank=True)
    farm_name = models.CharField(max_length=150, blank=True)
    location = models.CharField(max_length=255, blank=True)
