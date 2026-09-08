from django.shortcuts import render, redirect, get_object_or_404
from django.db.models import Avg, Count
from django.contrib.auth.decorators import login_required
from .models import Scan, ScanImage, TrainingSample, Setting
import os
import sys

# Ensure services is in path so we can import it
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.forms import SetPasswordForm
from services.analysis import get_analysis_provider

@login_required
def dashboard(request):
    scans = Scan.objects.all()
    total_scans = scans.count()
    
    # Calculate Average Grade
    grade_map = {'Best Quality': 4, 'Good Quality': 3, 'Average': 2, 'Rejected': 1}
    reverse_map = {4: 'Best Quality', 3: 'Good Quality', 2: 'Average', 1: 'Rejected'}
    
    total_score = 0
    valid_scans = 0
    for scan in scans:
        if scan.quality_grade in grade_map:
            total_score += grade_map[scan.quality_grade]
            valid_scans += 1
            
    average_grade = "N/A"
    if valid_scans > 0:
        avg_score = round(total_score / valid_scans)
        average_grade = reverse_map.get(avg_score, "N/A")
    
    recent_scans = scans.order_by('-created_at')[:5]
    
    total_fruits = sum(scan.fruit_count_total for scan in scans)
    total_good = sum(scan.fruit_count_good for scan in scans)
    total_defective = sum(scan.fruit_count_defective for scan in scans)
    
    unripe_count = sum(int(scan.fruit_count_total * scan.ripeness_unripe_pct / 100) for scan in scans)
    ripe_count = sum(int(scan.fruit_count_total * scan.ripeness_ripe_pct / 100) for scan in scans)
    overripe_count = sum(int(scan.fruit_count_total * scan.ripeness_overripe_pct / 100) for scan in scans)
    
    unripe_pct = int((unripe_count / total_fruits * 100)) if total_fruits > 0 else 0
    ripe_pct = int((ripe_count / total_fruits * 100)) if total_fruits > 0 else 0
    overripe_pct = int((overripe_count / total_fruits * 100)) if total_fruits > 0 else 0
    
    defect_rate = int((total_defective / total_fruits * 100)) if total_fruits > 0 else 0
    
    context = {
        'total_scans': total_scans,
        'average_grade': average_grade,
        'recent_scans': recent_scans,
        'total_fruits': total_fruits,
        'total_good': total_good,
        'unripe_count': unripe_count,
        'ripe_count': ripe_count,
        'unripe_pct': unripe_pct,
        'ripe_pct': ripe_pct,
        'overripe_pct': overripe_pct,
        'defect_rate': defect_rate,
    }
    return render(request, 'dashboard.html', context)

@login_required
def upload_view(request):
    if request.method == 'POST':
        images = request.FILES.getlist('images')
        batch_name = request.POST.get('batch_name', '')
        supplier_name = request.POST.get('supplier_name', '')
        
        if images:
            # Create Scan
            scan = Scan.objects.create(
                batch_name=batch_name,
                supplier_name=supplier_name,
                created_by=request.user if request.user.is_authenticated else None
            )
            
            provider = get_analysis_provider()
            
            for img in images:
                scan_img = ScanImage.objects.create(scan=scan, image=img)
                # Analyze
                result = provider.analyze(scan_img.image.path)
                
                # Update Scan fields with result
                scan.quality_grade = result.quality_grade
                scan.fruit_count_total = result.fruit_count_total
                scan.fruit_count_good = result.fruit_count_good
                scan.fruit_count_defective = result.fruit_count_defective
                scan.size_small_pct = result.size_small_pct
                scan.size_medium_pct = result.size_medium_pct
                scan.size_large_pct = result.size_large_pct
                scan.size_xl_pct = result.size_xl_pct
                scan.ripeness_unripe_pct = result.ripeness_unripe_pct
                scan.ripeness_ripe_pct = result.ripeness_ripe_pct
                scan.ripeness_overripe_pct = result.ripeness_overripe_pct
                scan.defect_blemished_pct = result.defect_blemished_pct
                scan.defect_mold_pct = result.defect_mold_pct
                scan.defect_cracked_pct = result.defect_cracked_pct
                scan.defect_insect_pct = result.defect_insect_pct
                scan.defect_bruised_pct = result.defect_bruised_pct
                scan.defect_foreign_matter_pct = result.defect_foreign_matter_pct
                scan.model_version = result.model_version
                scan.save()
                
                scan_img.mock_annotations = result.mock_annotations
                scan_img.save()
            
            return redirect('report_detail', id=scan.id)
            
    return render(request, 'upload.html')

@login_required
def reports_view(request):
    if request.method == 'POST' and request.POST.get('action') == 'delete':
        scan_ids = request.POST.getlist('scan_ids')
        if scan_ids:
            Scan.objects.filter(id__in=scan_ids).delete()
            if not Scan.objects.exists():
                from django.db import connection
                with connection.cursor() as cursor:
                    try:
                        cursor.execute("DELETE FROM sqlite_sequence WHERE name='analyzer_scan';")
                        cursor.execute("DELETE FROM sqlite_sequence WHERE name='analyzer_scanimage';")
                    except Exception:
                        pass
        return redirect('reports')
        
    scans = Scan.objects.all().order_by('-created_at')
    
    # Simple filtering
    grade = request.GET.get('grade')
    if grade:
        scans = scans.filter(quality_grade=grade)
        
    context = {'scans': scans}
    return render(request, 'reports.html', context)

@login_required
def report_detail_view(request, id):
    scan = get_object_or_404(Scan, id=id)
    return render(request, 'report_detail.html', {'scan': scan})

@login_required
def training_view(request):
    samples = TrainingSample.objects.all().order_by('-uploaded_at')
    if request.method == 'POST':
        image = request.FILES.get('image')
        label = request.POST.get('label')
        if image and label:
            TrainingSample.objects.create(
                image=image,
                label=label,
                uploaded_by=request.user if request.user.is_authenticated else None
            )
            return redirect('training')
    return render(request, 'training.html', {'samples': samples})

@login_required
def settings_view(request):
    settings = Setting.objects.all()
    
    if request.method == 'POST':
        if 'key' in request.POST and 'value' in request.POST:
            key = request.POST.get('key')
            value = request.POST.get('value')
            if key and value:
                Setting.objects.update_or_create(key=key, defaults={'value': value})
                return redirect('settings')
        elif 'new_password1' in request.POST:
            password_form = SetPasswordForm(request.user, request.POST)
            if password_form.is_valid():
                user = password_form.save()
                update_session_auth_hash(request, user)
                return redirect('settings')
        elif 'update_profile' in request.POST:
            request.user.first_name = request.POST.get('first_name', '')
            request.user.last_name = request.POST.get('last_name', '')
            username = request.POST.get('username')
            if username:
                request.user.username = username
            request.user.save()
            return redirect('settings')
        else:
            password_form = SetPasswordForm(request.user)
    else:
        password_form = SetPasswordForm(request.user)
        
    return render(request, 'settings.html', {'settings': settings, 'password_form': password_form})
