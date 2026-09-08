from django.contrib import admin
from .models import Scan, ScanImage, TrainingSample, Setting

admin.site.register(Scan)
admin.site.register(ScanImage)
admin.site.register(TrainingSample)
admin.site.register(Setting)
