from django.shortcuts import render, redirect, get_object_or_404
from django.db.models import Avg, Count
from django.utils import timezone
from datetime import timedelta
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
        
    scans = Scan.objects.prefetch_related('images').order_by('-created_at')
    
    # Simple filtering
    grade = request.GET.get('grade')
    if grade:
        scans = scans.filter(quality_grade=grade)
        
    period = request.GET.get('period', 'all')
    if period in ('7', '30', '90'):
        scans = scans.filter(created_at__gte=timezone.now() - timedelta(days=int(period)))
    else:
        period = 'all'
    context = {'scans': scans, 'selected_grade': grade or '', 'selected_period': period,
               'grade_choices': Scan.QUALITY_CHOICES}
    return render(request, 'reports.html', context)

@login_required
def report_detail_view(request, id):
    scan = get_object_or_404(Scan.objects.prefetch_related('images'), id=id)
    ripeness = [
        {'label': 'Unripe', 'key': 'unripe', 'pct': scan.ripeness_unripe_pct},
        {'label': 'Ripe', 'key': 'ripe', 'pct': scan.ripeness_ripe_pct},
        {'label': 'Overripe', 'key': 'overripe', 'pct': scan.ripeness_overripe_pct},
    ]
    # Stored scan totals describe the last uploaded image, so count its boxes.
    scan_images = list(scan.images.all())
    summary_image = max(scan_images, key=lambda image: image.id) if scan_images else None
    annotations = summary_image.mock_annotations if summary_image else []
    counts_available = bool(annotations) or scan.fruit_count_total == 0
    for row in ripeness:
        row['count'] = sum(box.get('css_class') == row['key'] for box in annotations)
    notes = []
    if not scan.fruit_count_total:
        notes.append('No fruits were detected. Try another scan with good lighting and the whole fruit visible.')
    else:
        highest = max(row['pct'] for row in ripeness)
        dominant = [row['label'].lower() for row in ripeness if row['pct'] == highest]
        if highest > 0:
            if len(dominant) == 1:
                notes.append(f"The largest ripeness group is {dominant[0]} ({highest:g}% of detected fruits).")
            else:
                notes.append(f"The leading ripeness groups are {' and '.join(dominant)}, each at {highest:g}%.")
        else:
            notes.append('Ripeness information is not available for this scan.')
        if scan.ripeness_overripe_pct > 0:
            notes.append('Overripe fruits were detected. Separate them for closer inspection during sorting.')
        if scan.fruit_count_defective > 0:
            notes.append(f'{scan.fruit_count_defective} fruit(s) were flagged as defective. Review them before packing.')
        if scan.quality_grade == 'Rejected':
            notes.append('This result is graded Rejected. Inspect the fruits and review the scan before proceeding.')
    if scan.images.count() > 1:
        notes.append('The saved totals, ripeness, and grade apply to the last uploaded image. All batch images are shown here.')
    if scan.model_version.startswith('mock'):
        notes.append('This scan uses demo analysis; the results are simulated.')
    return render(request, 'report_detail.html', {
        'scan': scan, 'ripeness': ripeness, 'result_notes': notes,
        'counts_available': counts_available,
    })

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

@login_required
def reports_overview(request):
    from datetime import date
    from .reporting import summarize, RIPENESS
    scans = Scan.objects.prefetch_related('images').order_by('created_at')
    errors = []
    dates = {}
    for key in ('start', 'end'):
        raw = request.GET.get(key, '')
        try:
            dates[key] = date.fromisoformat(raw) if raw else None
        except ValueError:
            dates[key] = None
            errors.append('Please enter a valid date range.')
    if dates['start'] and dates['end'] and dates['start'] > dates['end']:
        errors.append('The start date must be on or before the end date.')
    if errors:
        scans = scans.none()
    else:
        if dates['start']:
            scans = scans.filter(created_at__date__gte=dates['start'])
        if dates['end']:
            scans = scans.filter(created_at__date__lte=dates['end'])
    quality = request.GET.get('quality', '')
    if quality in dict(Scan.QUALITY_CHOICES):
        scans = scans.filter(quality_grade=quality)
    else:
        quality = ''
    ripeness = request.GET.get('ripeness', '')
    scans = list(scans)
    if ripeness in RIPENESS:
        scans = [s for s in scans if getattr(s, f'ripeness_{ripeness}_pct') > 0 and getattr(s, f'ripeness_{ripeness}_pct') == max(getattr(s, f'ripeness_{key}_pct') for key in RIPENESS)]
    else:
        ripeness = ''
    context = summarize(scans)
    context.update({'errors': errors, 'start': dates['start'].isoformat() if dates['start'] else '', 'end': dates['end'].isoformat() if dates['end'] else '', 'quality': quality, 'selected_ripeness': ripeness, 'grade_choices': Scan.QUALITY_CHOICES, 'ripeness_choices': RIPENESS})
    return render(request, 'reports_overview.html', context)

@login_required
def knowledge_hub(request):
    from .knowledge import CATEGORIES, INTRODUCTION_URL, INTRODUCTION_SOURCE, find_articles
    query = request.GET.get('q', '').strip()[:150]
    category = request.GET.get('category', 'all')
    if category not in dict(CATEGORIES):
        category = 'all'
    return render(request, 'knowledge_hub.html', {
        'query': query, 'selected_category': category, 'categories': CATEGORIES,
        'articles': find_articles(query, category), 'introduction_url': INTRODUCTION_URL,
        'introduction_source': INTRODUCTION_SOURCE,
    })

@login_required
def profile_view(request):
    # Placeholder only: this page never updates account information.
    return render(request, 'profile.html')
