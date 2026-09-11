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
from django.contrib.auth import update_session_auth_hash, login
from django.contrib.auth.forms import SetPasswordForm, UserCreationForm
from services.analysis import get_analysis_provider

@login_required
def dashboard(request):
    if request.user.is_superuser:
        scans = Scan.objects.all()
    else:
        scans = Scan.objects.filter(created_by=request.user)
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
        batch_name = request.POST.get('batch_name', '').strip()[:255]
        
        if not images:
            return render(request, 'upload.html', {'upload_errors': ['Please choose at least one image before uploading.']})
        if images:
            from django.db import transaction
            import logging
            logger = logging.getLogger(__name__)
            try:
                provider = get_analysis_provider()
            except Exception:
                logger.exception('Could not initialize scan analysis')
                return render(request, 'upload.html', {'upload_errors': ['Analysis is temporarily unavailable. Please try again.']})
            failed_images = []
            created_scans = []
            for img in images:
                scan_img = ScanImage(scan=None, image=img)
                try:
                    with transaction.atomic():
                        # Each photo represents an independent observation, not a combined batch.
                        scan = Scan.objects.create(
                            batch_name=batch_name,
                            created_by=request.user,
                        )
                        if not batch_name:
                            scan.batch_name = f'Scan #{scan.id}'
                        scan_img.scan = scan
                        scan_img.save()
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
                    created_scans.append(scan)
                except Exception:
                    logger.exception('Image analysis failed')
                    # Database rollback does not remove an uploaded storage file.
                    if scan_img.image and getattr(scan_img.image, '_committed', False):
                        try:
                            scan_img.image.delete(save=False)
                        except Exception:
                            logger.exception('Could not remove failed upload file')
                    failed_images.append(img.name)
            if failed_images:
                return render(request, 'upload.html', {
                    'upload_errors': [f'Could not analyze {name}. Please select this photo again or try a clearer JPG/PNG image.' for name in failed_images],
                    'successful_scans': created_scans,
                })
            if len(created_scans) > 1:
                return redirect('reports')
            return redirect('report_detail', id=created_scans[0].id)
            
    return render(request, 'upload.html')

@login_required
def reports_view(request):
    if request.method == 'POST' and request.POST.get('action') == 'delete':
        scan_ids = request.POST.getlist('scan_ids')
        if scan_ids:
            if request.user.is_superuser:
                Scan.objects.filter(id__in=scan_ids).delete()
            else:
                Scan.objects.filter(id__in=scan_ids, created_by=request.user).delete()
            if not Scan.objects.exists():
                from django.db import connection
                with connection.cursor() as cursor:
                    try:
                        cursor.execute("DELETE FROM sqlite_sequence WHERE name='analyzer_scan';")
                        cursor.execute("DELETE FROM sqlite_sequence WHERE name='analyzer_scanimage';")
                    except Exception:
                        pass
        return redirect('reports')
        
    if request.user.is_superuser:
        scans = Scan.objects.prefetch_related('images').order_by('-created_at')
    else:
        scans = Scan.objects.filter(created_by=request.user).prefetch_related('images').order_by('-created_at')
    
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
    if request.user.is_superuser:
        scan = get_object_or_404(Scan.objects.prefetch_related('images'), id=id)
    else:
        scan = get_object_or_404(Scan.objects.filter(created_by=request.user).prefetch_related('images'), id=id)
    if request.method == 'POST':
        from django.http import JsonResponse
        from django.db import transaction
        try:
            image_id = int(request.POST.get('image_id', ''))
            index = int(request.POST.get('index', ''))
        except ValueError:
            return JsonResponse({'error': 'Invalid fruit selection.'}, status=400)
        label = request.POST.get('label', '')
        if label not in ('unripe', 'ripe', 'overripe', 'original'):
            return JsonResponse({'error': 'Invalid ripeness label.'}, status=400)
        with transaction.atomic():
            selected = get_object_or_404(ScanImage.objects.select_for_update(), id=image_id, scan=scan)
            if index < 0 or index >= len(selected.mock_annotations):
                return JsonResponse({'error': 'Fruit no longer available.'}, status=400)
            corrections = dict(selected.label_corrections)
            if label == 'original':
                corrections.pop(str(index), None)
            else:
                corrections[str(index)] = label
            selected.label_corrections = corrections
            selected.save(update_fields=['label_corrections'])
        return JsonResponse({'corrections': corrections})
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
    if request.GET.get('download') == 'pdf':
        from .pdf_export import scan_page_pdf
        return scan_page_pdf(request, {'scan': scan, 'ripeness': ripeness, 'result_notes': notes, 'counts_available': counts_available})
    return render(request, 'report_detail.html', {
        'scan': scan, 'ripeness': ripeness, 'result_notes': notes,
        'counts_available': counts_available,
    })

@login_required
def training_view(request):
    if request.user.is_superuser:
        samples = TrainingSample.objects.all().order_by('-uploaded_at')
    else:
        samples = TrainingSample.objects.filter(uploaded_by=request.user).order_by('-uploaded_at')
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
    if request.method == 'POST' and 'language' in request.POST:
        language = request.POST.get('language')
        if language not in ('en', 'fil'):
            from django.http import HttpResponseBadRequest
            return HttpResponseBadRequest('Unsupported language')
        response = redirect('settings')
        response.set_cookie('calamansense_language', language, max_age=31536000,
                            samesite='Lax', secure=request.is_secure(), httponly=True)
        return response
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
        else:
            password_form = SetPasswordForm(request.user)
    else:
        password_form = SetPasswordForm(request.user)
        
    return render(request, 'settings.html', {'settings': settings, 'password_form': password_form})

@login_required
def reports_overview(request):
    from datetime import date
    from .reporting import summarize, RIPENESS
    if request.user.is_superuser:
        scans = Scan.objects.prefetch_related('images').order_by('created_at')
    else:
        scans = Scan.objects.filter(created_by=request.user).prefetch_related('images').order_by('created_at')
    selected_ids = request.GET.getlist('scan_ids')
    if selected_ids:
        from django.http import HttpResponseBadRequest
        if len(selected_ids) > 500 or any(not value.isdecimal() for value in selected_ids):
            return HttpResponseBadRequest('Select up to 500 valid scans.')
        scans = scans.filter(pk__in=selected_ids)
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
    period = request.GET.get('period', 'all')
    if period not in ('all', 'today', '7', '30'):
        period = 'all'
    if period != 'all':
        days = 1 if period == 'today' else int(period)
        dates['end'] = timezone.localdate()
        dates['start'] = dates['end'] - timedelta(days=days - 1)
        scans = scans.filter(created_at__date__gte=dates['start'], created_at__date__lte=dates['end'])
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
    context['selected_period'] = period
    context['period_choices'] = [('all', 'All'), ('today', 'Today'), ('7', 'Last 7 Days'), ('30', 'Last 30 Days')]
    context['grade_distribution'] = [
        {'label': label, 'count': sum(s.quality_grade == label for s in scans),
         'pct': round(sum(s.quality_grade == label for s in scans) / len(scans) * 100, 1) if scans else 0,
         'color': color}
        for label, color in zip(('Best Quality', 'Good Quality', 'Average', 'Rejected'), ('#158443', '#65ad50', '#efb829', '#e95b50'))
    ]
    for point in context['trend']:
        point['pct'] = round(point['count'] / len(scans) * 100, 1) if scans else 0
    context['recent_activity'] = sorted(scans, key=lambda scan: (scan.created_at, scan.pk), reverse=True)[:5]
    context.update({'errors': errors, 'start': dates['start'].isoformat() if dates['start'] else '', 'end': dates['end'].isoformat() if dates['end'] else '', 'quality': quality, 'selected_ripeness': ripeness, 'grade_choices': Scan.QUALITY_CHOICES, 'ripeness_choices': RIPENESS})
    if request.GET.get('download') == 'csv':
        import csv
        from django.http import HttpResponse
        response = HttpResponse(content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = 'attachment; filename="calamansense-scans.csv"'
        response['Cache-Control'] = 'private, no-store'
        response.write('\ufeff')
        writer = csv.writer(response)
        writer.writerow(['Scan ID', 'Date', 'Sample name', 'Total fruits', 'Original grade', 'Unripe %', 'Ripe %', 'Overripe %'])
        for scan in scans:
            name = scan.batch_name or ''
            if name.lstrip().startswith(('=', '+', '-', '@')):
                name = "'" + name
            writer.writerow([scan.pk, timezone.localtime(scan.created_at).isoformat(), name, scan.fruit_count_total, scan.quality_grade, scan.ripeness_unripe_pct, scan.ripeness_ripe_pct, scan.ripeness_overripe_pct])
        return response
    if request.GET.get('download') == 'pdf':
        from .pdf_export import scan_page_pdf
        context['recent_activity'] = sorted(scans, key=lambda scan: (scan.created_at, scan.pk), reverse=True)
        context['pdf_export'] = True
        return scan_page_pdf(request, context, template_name='reports_overview.html', filename='calamansense-reports.pdf')
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
    from .models import UserProfile
    from .profile_forms import ProfileForm
    from django.db import transaction
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    old_photo = profile.photo.name
    form = ProfileForm(request.POST or None, request.FILES or None, instance=profile,
                       initial={key: getattr(request.user, key) for key in ('first_name', 'last_name', 'email')})
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            for key in ('first_name', 'last_name', 'email'):
                setattr(request.user, key, form.cleaned_data[key])
            request.user.save(update_fields=['first_name', 'last_name', 'email'])
            updated = form.save(commit=False)
            if form.cleaned_data['remove_photo']:
                updated.photo = ''
            updated.save()
            if old_photo and old_photo != updated.photo.name:
                storage = profile._meta.get_field('photo').storage
                transaction.on_commit(lambda: storage.delete(old_photo))
        return redirect('/profile/?saved=1')
    return render(request, 'profile.html', {'profile_form': form, 'saved': request.GET.get('saved') == '1'})

def register_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('dashboard')
    else:
        form = UserCreationForm()
        
    return render(request, 'register.html', {'form': form})














@login_required
def compare_scans(request):
    ids = request.GET.getlist('scan_ids')
    if len(ids) != 2 or any(not value.isdecimal() for value in ids) or ids[0] == ids[1]:
        return render(request, 'compare_scans.html', {'selection_error': 'Select exactly two different scans in History to compare.'}, status=400)
    available = Scan.objects.prefetch_related('images')
    if not request.user.is_superuser:
        available = available.filter(created_by=request.user)
    scans = [get_object_or_404(available, pk=value) for value in ids]
    cards = []
    for scan in scans:
        cards.append({'scan': scan, 'rows': [
            {'label': label, 'key': key, 'pct': getattr(scan, 'ripeness_' + key + '_pct')}
            for key, label in [('unripe', 'Unripe'), ('ripe', 'Ripe'), ('overripe', 'Overripe')]
        ]})
    difference = scans[1].fruit_count_total - scans[0].fruit_count_total
    return render(request, 'compare_scans.html', {'cards': cards, 'difference': difference,
        'difference_abs': abs(difference), 'same_sample': bool(scans[0].batch_name and scans[0].batch_name == scans[1].batch_name)})
