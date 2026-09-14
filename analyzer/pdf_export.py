"""Downloadable report PDFs using the existing Matplotlib dependency."""
from io import BytesIO
from textwrap import wrap
from django.http import HttpResponse
from django.utils import timezone
from matplotlib.figure import Figure
from matplotlib.backends.backend_pdf import PdfPages
from PIL import Image, ImageDraw


def export_pdf(title, lines, filename, images=()):
    output = BytesIO()
    with PdfPages(output) as pdf:
        wrapped = []
        for line in lines:
            wrapped.extend(wrap(str(line), 92) or [''])
        for start in range(0, max(len(wrapped), 1), 42):
            fig = Figure(figsize=(8.27, 11.69))
            fig.text(.08, .94, 'CalamanSense', size=23, weight='bold', color='#086839')
            fig.text(.08, .90, title, size=15, weight='bold')
            for index, line in enumerate(wrapped[start:start+42]):
                fig.text(.08, .855-index*.018, line, size=10)
            fig.text(.08, .035, 'CalamanSense | Saved analysis report', size=9, color='#657469')
            pdf.savefig(fig)
        for scan_image in images:
            if not scan_image.image:
                continue
            try:
                with scan_image.image.open('rb') as source:
                    picture = Image.open(source).convert('RGB')
                draw = ImageDraw.Draw(picture)
                colors = {'unripe':'#319843', 'ripe':'#e7ae00', 'overripe':'#eb4949'}
                for index, box in enumerate(scan_image.mock_annotations):
                    x, y = picture.width*box['x']/100, picture.height*box['y']/100
                    right, bottom = x+picture.width*box['width']/100, y+picture.height*box['height']/100
                    draw.rectangle((x,y,right,bottom), outline=colors.get(box.get('css_class'),'white'), width=max(2,picture.width//400))
                    draw.text((x+3,y+3),str(index+1),fill='white',stroke_width=1,stroke_fill='black')
                fig = Figure(figsize=(8.27,11.69))
                fig.text(.08,.94,'CalamanSense | Original detections',size=18,color='#086839')
                fig.text(.08,.90,f'Image {scan_image.id} - fruit numbers correspond to the inspector',size=10)
                ax=fig.add_axes([.06,.10,.88,.76]);ax.imshow(picture);ax.axis('off')
                pdf.savefig(fig)
            except (OSError, ValueError):
                fig=Figure(figsize=(8.27,11.69));fig.text(.08,.9,f'Image {scan_image.id} could not be loaded.',size=12);pdf.savefig(fig)
    response = HttpResponse(output.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    response['Cache-Control'] = 'private, no-store'
    return response


def scan_pdf(scan, ripeness, notes):
    images=list(scan.images.all())
    lines=[f'Scan #{scan.id} | {timezone.localtime(scan.created_at):%Y-%m-%d %H:%M}',
           f'Total fruits: {scan.fruit_count_total}', f'Original batch grade: {scan.quality_grade or "Not graded"}', '', 'ORIGINAL RIPENESS']
    lines += [f'{r["label"]}: {r["pct"]:.1f}%' for r in ripeness]
    lines += ['', 'NOTES']+notes
    for image in images:
        if image.label_corrections:
            counts={k:0 for k in ('unripe','ripe','overripe')}
            for i,box in enumerate(image.mock_annotations):
                key=image.label_corrections.get(str(i),box.get('css_class'))
                if key in counts: counts[key]+=1
            total=len(image.mock_annotations)
            lines+=['',f'REVIEWED IMAGE {image.id} - original result preserved']
            lines += [f'{key.capitalize()}: {count} ({count/total*100 if total else 0:.1f}%)' for key,count in counts.items()]
            lines += [f'Fruit {int(i)+1}: {label} (manual correction)' for i,label in image.label_corrections.items()]
    return export_pdf('Scan Result',lines,f'calamansense-scan-{scan.id}.pdf',images)


def scan_page_pdf(request, context, template_name="report_detail.html", filename=None):
    """Print the actual result template to a downloadable PDF using local Edge."""
    import os
    import re
    import subprocess
    import tempfile
    from pathlib import Path
    from django.conf import settings
    from django.template.loader import render_to_string
    from django.contrib.staticfiles import finders
    from html import escape

    candidates = [Path(os.environ.get('PROGRAMFILES(X86)', 'C:/Program Files (x86)')) / 'Microsoft/Edge/Application/msedge.exe',
                  Path(os.environ.get('PROGRAMFILES', 'C:/Program Files')) / 'Google/Chrome/Application/chrome.exe']
    browser = next((path for path in candidates if path.exists()), None)
    if browser is None:
        raise RuntimeError('PDF export requires Microsoft Edge or Google Chrome on the server.')
    html = render_to_string(template_name, context, request=request)
    # Only local application assets are needed; do not load remote fonts or run UI scripts.
    html = re.sub(r'<script\b[^>]*>[\s\S]*?</script>', '', html, flags=re.I)
    html = re.sub(r'<link\b[^>]*href="https?://[^>]*>', '', html, flags=re.I)
    def local_asset(match):
        attribute, url = match.group(1), match.group(2)
        path_only = url.split('?')[0]
        if path_only.startswith(settings.STATIC_URL):
            local = finders.find(path_only[len(settings.STATIC_URL):])
        elif path_only.startswith(settings.MEDIA_URL):
            local = str(Path(settings.MEDIA_ROOT) / path_only[len(settings.MEDIA_URL):])
        else:
            return match.group(0)
        return f'{attribute}="{Path(local).resolve().as_uri()}"' if local else match.group(0)
    html = re.sub(r'(src|href)="([^"]+)"', local_asset, html)
    reviews = []
    for image in (context['scan'].images.all() if 'scan' in context else []):
        if image.label_corrections:
            counts = dict.fromkeys(('unripe', 'ripe', 'overripe'), 0)
            for i, box in enumerate(image.mock_annotations):
                label = image.label_corrections.get(str(i), box.get('css_class'))
                if label in counts:
                    counts[label] += 1
            total = len(image.mock_annotations)
            detail = ' | '.join(f'{key.title()}: {value} ({value / total * 100 if total else 0:.1f}%)' for key, value in counts.items())
            reviews.append(f'<div class="pdf-review"><strong>Reviewed breakdown - Image {image.id}</strong><p>{escape(detail)}</p><small>Original results and grade are preserved.</small></div>')
    html = html.replace('</main>', ''.join(reviews) + '</main>')
    styles = '''<style>
    @page { size: A4 landscape; margin: 12mm; }
    html { font-family: Arial, sans-serif; } body { font-family: Arial, sans-serif !important; }
    * { print-color-adjust: exact !important; -webkit-print-color-adjust: exact !important; }
    @media print {
      .result-page { padding:0 !important; background:#f7faf8 !important; }
      .result-page .container { max-width:none; margin:0; padding:0; }
      .result-heading { display:block; margin-bottom:18px; }
      .result-heading h1 { font-size:27px; }
      .result-layout { display:grid !important; grid-template-columns:minmax(0,1.3fr) minmax(0,1fr) !important; gap:20px; }
      .result-summary { display:grid !important; grid-template-columns:1fr 1fr; gap:12px; align-content:start; }
      .result-page .image-viewer { max-width:none; border:5px solid white; }
      .result-figure { break-inside:avoid; }
      .result-page .bounding-box { pointer-events:none; }
      .result-actions,.result-back,.fruit-tools,#fruit-filters,#fruit-filter-status,#fruit-inspector,.mobile-result-actions,.mobile-report-pdf,.mobile-result-heading,.mobile-bottom-nav { display:none !important; }
      .material-symbols-outlined { display:none !important; }
      .result-visual-toolbar { display:block; }
      .result-score-help { font-size:10px; }
      .result-notes { margin-top:16px; }
      .pdf-review { margin-top:14px; padding:16px; border-radius:9px; background:#e8f6ee; break-inside:avoid; }
      .pdf-review p { font-size:12px; margin:8px 0; }
    }</style>'''
    html = html.replace('</head>', styles + '</head>')
    # Always export the standard light theme rather than inheriting browser preferences.
    html = html.replace('data-theme="dark"', '')
    with tempfile.TemporaryDirectory(prefix='calamansense-pdf-') as directory:
        folder = Path(directory)
        source, target = folder / 'result.html', folder / 'result.pdf'
        source.write_text(html, encoding='utf-8')
        subprocess.run([str(browser), '--headless', '--disable-gpu', '--no-first-run',
                        '--no-pdf-header-footer', '--allow-file-access-from-files',
                        '--user-data-dir=' + str(folder / 'browser'),
                        '--print-to-pdf=' + str(target), source.as_uri()],
                       check=True, timeout=60, capture_output=True,
                       creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        content = target.read_bytes()
    response = HttpResponse(content, content_type='application/pdf')
    filename = filename or f'calamansense-scan-{context["scan"].id}.pdf'
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    response['Cache-Control'] = 'private, no-store'
    return response

