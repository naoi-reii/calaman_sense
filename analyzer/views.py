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
from django.core import signing
from django.http import Http404
from uuid import uuid4
from django.contrib.auth.views import LogoutView


def _is_mobile_request(request):
    agent = request.META.get('HTTP_USER_AGENT', '').lower()
    return any(device in agent for device in ('android', 'iphone', 'ipad', 'ipod', 'mobile'))


class DeviceLogoutView(LogoutView):
    def get_default_redirect_url(self):
        if _is_mobile_request(self.request):
            return '/login/?logged_out=1'
        return super().get_default_redirect_url()


def _saved_group_tokens(scans, user):
    group_ids = {scan.upload_group_id for scan in scans if scan.upload_group_id}
    if not group_ids:
        return {}
    siblings = Scan.objects.filter(upload_group_id__in=group_ids).order_by('id')
    if not user.is_superuser:
        siblings = siblings.filter(created_by=user)
    groups = {}
    for group_id, scan_id in siblings.values_list('upload_group_id', 'id'):
        groups.setdefault(group_id, []).append(scan_id)
    return {group_id: signing.dumps(ids, salt='upload-results')
            for group_id, ids in groups.items() if 2 <= len(ids) <= 5}


def _upload_results(token, user):
    try:
        ids = signing.loads(token, salt='upload-results')
    except signing.BadSignature:
        raise Http404('Upload results not found.')
    if not isinstance(ids, list) or not 2 <= len(ids) <= 5 or any(type(i) is not int for i in ids) or len(set(ids)) != len(ids):
        raise Http404('Invalid upload results.')
    scans = Scan.objects.filter(id__in=ids).prefetch_related('images')
    if not user.is_superuser:
        scans = scans.filter(created_by=user)
    by_id = {scan.id: scan for scan in scans}
    if len(by_id) != len(ids):
        raise Http404('Upload results not found.')
    return [by_id[i] for i in ids]


@login_required
def upload_results_view(request, token):
    scans = _upload_results(token, request.user)
    if request.method == 'POST':
        image_id = request.POST.get('image_id', '')
        image = next((photo for scan in scans for photo in scan.images.all() if str(photo.id) == image_id), None)
        if image is None:
            raise Http404('Image is not part of this upload.')
        return report_detail_view(request, image.scan_id)
    cards = []
    for scan in scans:
        images = list(scan.images.all())
        photo = max(images, key=lambda image: image.id) if images else None
        boxes = photo.mock_annotations if photo else []
        rows = [
            {'key': 'unripe', 'label': 'Unripe', 'pct': scan.ripeness_unripe_pct},
            {'key': 'ripe', 'label': 'Ripe', 'pct': scan.ripeness_ripe_pct},
            {'key': 'overripe', 'label': 'Overripe', 'pct': scan.ripeness_overripe_pct},
        ]
        for row in rows:
            row['count'] = sum(box.get('css_class') == row['key'] for box in boxes)
        cards.append({'scan': scan, 'photo': photo, 'rows': rows,
                      'counts_available': bool(boxes) or scan.fruit_count_total == 0})
    total = sum(scan.fruit_count_total for scan in scans)
    counts_available = all(
        card['counts_available'] and sum(row['count'] for row in card['rows']) == card['scan'].fruit_count_total
        for card in cards
    )
    overall_rows = []
    for index, key in enumerate(('unripe', 'ripe', 'overripe')):
        count = sum(card['rows'][index]['count'] for card in cards)
        # Older records may lack fruit boxes; weight their saved percentages by
        # fruit count rather than giving small and large photos equal weight.
        pct = (count * 100 / total if counts_available else
               sum(card['rows'][index]['pct'] * card['scan'].fruit_count_total for card in cards) / total) if total else 0
        overall_rows.append({'key': key, 'count': count if counts_available else None, 'pct': pct})
    highest = max(row['pct'] for row in overall_rows)
    leaders = [row['key'] for row in overall_rows if row['pct'] == highest]
    dominant = leaders[0] if total and len(leaders) == 1 else 'mixed' if total else 'none'
    from types import SimpleNamespace
    photos = [card['photo'] for card in cards if card['photo']]
    grades = list(dict.fromkeys(scan.quality_grade for scan in scans if scan.quality_grade))
    # Match the real analysis provider's grading thresholds, applied to the
    # combined fruit distribution rather than averaging image grade labels.
    unripe_pct = overall_rows[0]['pct']
    combined_grade = ('Best Quality' if unripe_pct >= 75 else
                      'Good Quality' if unripe_pct >= 50 else 'Average') if total else None
    for row in overall_rows:
        row['label'] = row['key'].title()
    summary_scan = SimpleNamespace(
        id=scans[0].id, batch_name=scans[0].batch_name or f'{len(scans)} uploaded images',
        created_at=scans[0].created_at, fruit_count_total=total,
        quality_grade=combined_grade,
        images=SimpleNamespace(all=lambda: photos, count=lambda: len(photos)),
    )
    notes = [f'Combined results from all {len(scans)} uploaded images. Each image keeps its own individual result.']
    if total:
        notes.append(f'Overall batch grade: {combined_grade}, based on {unripe_pct:.1f}% unripe fruits across all images '
                     '(Best Quality: at least 75%; Good Quality: at least 50%; Average: below 50%).')
    else:
        notes.append('No fruits were detected across the uploaded images, so an overall batch grade is not available.')
    if len(grades) > 1:
        notes.append('Image grades differ: ' + ', '.join(grades) + '. Open an individual result to review its grade.')
    if not counts_available:
        notes.append('Some saved images have no complete fruit boxes. Ripeness percentages are weighted by the fruit count in each image.')
    if any(scan.model_version.startswith('mock') for scan in scans):
        notes.append('Some images use demo analysis; those results are simulated.')
    context = {
        'upload_scans': scans, 'upload_group': token, 'result_cards': cards,
        'overall': {'total': total, 'rows': overall_rows, 'counts_available': counts_available,
                    'dominant': dominant, 'quality_grade': combined_grade},
        'scan': summary_scan, 'ripeness': overall_rows, 'counts_available': counts_available,
        'result_notes': notes, 'combined_result': True,
    }
    if request.GET.get('download') == 'pdf':
        from .pdf_export import scan_page_pdf
        return scan_page_pdf(request, context, template_name='upload_results.html', filename='calamansense-combined-results.pdf')
    return render(request, 'upload_results.html', context)

def home(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    if _is_mobile_request(request):
        return redirect('/login/?opening=1')
    return render(request, 'home.html')


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
        if len(images) > 5:
            return render(request, 'upload.html', {'upload_errors': ['You can upload 1–5 images at a time. Please select no more than 5 images.']})
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
            upload_group_id = uuid4() if len(images) > 1 else None
            for img in images:
                scan_img = ScanImage(scan=None, image=img)
                try:
                    with transaction.atomic():
                        # Each photo represents an independent observation, not a combined batch.
                        scan = Scan.objects.create(
                            batch_name=batch_name,
                            created_by=request.user,
                            upload_group_id=upload_group_id,
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
                token = signing.dumps([scan.id for scan in created_scans], salt='upload-results')
                return redirect('upload_results', token=token)
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
    if period == 'today':
        scans = scans.filter(created_at__date=timezone.localdate())
    elif period in ('7', '30', '90'):
        scans = scans.filter(created_at__gte=timezone.now() - timedelta(days=int(period)))
    else:
        period = 'all'
    context = {'scans': scans, 'selected_grade': grade or '', 'selected_period': period,
               'grade_choices': Scan.QUALITY_CHOICES}
    history_data = []
    for scan in scans:
        images = list(scan.images.all())
        photo = max(images, key=lambda image: image.id) if images else None
        boxes = photo.mock_annotations if photo else []
        rows = [{'key': key, 'label': label,
                 'pct': getattr(scan, 'ripeness_' + key + '_pct'),
                 'count': sum(box.get('css_class') == key for box in boxes) if boxes or scan.fruit_count_total == 0 else None}
                for key, label in [('unripe', 'Unripe'), ('ripe', 'Ripe'), ('overripe', 'Overripe')]]
        leading = max(rows, key=lambda row: row['pct'])
        summary = ('Mostly ' + leading['label']) if leading['pct'] > 50 else 'Mixed Ripeness'
        if not scan.fruit_count_total:
            summary = 'No fruits detected'
        history_data.append({'id': scan.id, 'batch': scan.batch_name or 'Unnamed sample',
                             'date': timezone.localtime(scan.created_at).strftime('%b %d, %Y'),
                             'time': timezone.localtime(scan.created_at).strftime('%I:%M %p'),
                             'image': photo.image.url if photo else '', 'total': scan.fruit_count_total,
                             'grade': scan.quality_grade or 'Pending', 'rows': rows,
                             'summary': summary, 'key': leading['key'], 'annotations': boxes})
    context['history_data'] = history_data
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
    upload_group = request.GET.get('group', '')
    if not upload_group and scan.upload_group_id:
        upload_group = _saved_group_tokens([scan], request.user).get(scan.upload_group_id, '')
    upload_scans = _upload_results(upload_group, request.user) if upload_group else []
    if upload_scans and scan.id not in [item.id for item in upload_scans]:
        raise Http404('This scan is not part of this upload.')
    return render(request, 'report_detail.html', {
        'scan': scan, 'ripeness': ripeness, 'result_notes': notes,
        'counts_available': counts_available,
        'upload_scans': upload_scans, 'upload_group': upload_group,
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
def settings_guide(request, page):
    from django.http import Http404
    pages = {
        'about': ('About CalamanSense', 'Tungkol sa CalamanSense', 'eco'),
        'scanning': ('How Scanning Works', 'Paano Mag-scan', 'center_focus_weak'),
        'help': ('Help', 'Tulong', 'help_outline'),
        'user-guide': ('User Guide', 'Gabay sa Paggamit', 'menu_book'),
    }
    if page not in pages:
        raise Http404
    title, title_fil, icon = pages[page]
    return render(request, 'settings_guide.html', {
        'guide_title': title, 'guide_title_fil': title_fil, 'guide_icon': icon,
        'guide_content': 'guides/' + page + '.html',
    })


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
    from collections import Counter
    leading = max(context['distribution'], key=lambda row: row['pct'])
    context['dominant_ripeness'] = leading
    grades = Counter(scan.quality_grade for scan in scans if scan.quality_grade)
    context['most_common_grade'] = grades.most_common(1)[0][0] if grades else 'N/A'
    fruit_days = Counter()
    for scan in scans:
        date_label = timezone.localtime(scan.created_at).strftime('%b %Y' if len(context['trend']) and len(context['trend'][0]['date']) == 8 else '%b %d, %Y')
        fruit_days[date_label] += scan.fruit_count_total
    fruit_max = max(fruit_days.values(), default=1) or 1
    for point in context['trend']:
        point['fruits'] = fruit_days[point['date']]
        point['fruit_y'] = round(175 - point['fruits'] / fruit_max * 140, 2)
    context['trend_fruit_max'] = fruit_max
    context['trend_fruit_points'] = ' '.join(f"{p['x']},{p['fruit_y']}" for p in context['trend'])
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
    context['recent_activity'] = sorted(scans, key=lambda scan: (scan.created_at, scan.pk), reverse=True)[:3]
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
    from .profile_forms import ProfileForm, ProfilePhotoForm
    from django.db import transaction
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    old_photo = profile.photo.name
    photo_action = request.method == 'POST' and request.POST.get('action') == 'photo'
    form = ProfileForm(request.POST if request.method == 'POST' and not photo_action else None, instance=profile,
                       initial={key: getattr(request.user, key) for key in ('first_name', 'last_name', 'email')})
    photo_form = ProfilePhotoForm(request.POST if photo_action else None,
                                 request.FILES if photo_action else None, instance=profile)
    active_form = photo_form if photo_action else form
    if request.method == 'POST' and active_form.is_valid():
        with transaction.atomic():
            if not photo_action:
                for key in ('first_name', 'last_name', 'email'):
                    setattr(request.user, key, form.cleaned_data[key])
                request.user.save(update_fields=['first_name', 'last_name', 'email'])
            updated = active_form.save(commit=False)
            if photo_action and photo_form.cleaned_data['remove_photo']:
                updated.photo = ''
            updated.save()
            if old_photo and old_photo != updated.photo.name:
                storage = profile._meta.get_field('photo').storage
                transaction.on_commit(lambda: storage.delete(old_photo))
        return redirect('/profile/?saved=' + ('photo' if photo_action else '1'))
    return render(request, 'profile.html', {'profile_form': form, 'photo_form': photo_form,
                  'saved': request.GET.get('saved') == '1', 'photo_saved': request.GET.get('saved') == 'photo'})

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

@login_required
def settings_appearance(request):
    return render(request, 'settings_appearance.html')
