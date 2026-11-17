import hashlib
from urllib.parse import urlsplit, urlunsplit
from django import forms
from django.contrib.auth.forms import SetPasswordForm
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from .models import Site, Invitation, AuditEvent, ReferenceSite, Page, KnowledgeSource

class SiteForm(forms.ModelForm):
    url = forms.URLField(max_length=2048, assume_scheme='https')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        help_texts = {
            'name': 'Your internal website label, for example Denim Yard.',
            'url': 'The managed website URL. Add competitors under Reference websites instead.',
            'environment': 'Production means the real public site; Staging means a separate test copy. This does not enable publishing.',
            'timezone': 'Display/schedule timezone, for example Asia/Colombo.',
            'industry': 'Business category, for example E-commerce / apparel if accurate.',
            'services': 'List actual products/categories or services. Do not add items you do not sell.',
            'audience': 'Describe your actual customers and their needs; avoid unverified demographic claims.',
            'countries': 'Countries you really serve or ship to; confirm your shipping policy.',
            'languages': 'Languages actually used on the site or planned with human review.',
            'brand_voice': 'Preferred writing style, such as clear, friendly and concise.',
            'verified_facts': 'Only confirmed business facts. Do not invent delivery times, materials, guarantees or certifications.',
            'prohibited_claims': 'Claims content must avoid, such as unsupported best-price or quality guarantees.',
            'conversion_goals': 'Desired actions: completed purchases, enquiries or add-to-cart. These are goals; analytics tracking is not connected yet.',
        }
        for name, text in help_texts.items():
            self.fields[name].help_text = text
        self.fields['services'].label = 'Products, categories and services'
    class Meta:
        model = Site
        fields = ['name', 'url', 'environment', 'timezone', 'industry', 'services', 'audience',
                  'countries', 'languages', 'brand_voice', 'verified_facts', 'prohibited_claims', 'conversion_goals']
        widgets = {name: forms.Textarea(attrs={'rows': 3}) for name in
                   ['services', 'audience', 'brand_voice', 'verified_facts', 'prohibited_claims', 'conversion_goals']}

    def clean_url(self):
        value = self.cleaned_data['url']
        parts = urlsplit(value)
        if parts.scheme not in ('http', 'https') or parts.username or parts.password or parts.query or parts.fragment:
            raise ValidationError('Use an HTTP(S) site URL without credentials, query or fragment.')
        host = parts.hostname.encode('idna').decode('ascii').lower()
        if ':' in host:
            host = f'[{host}]'
        try:
            port = parts.port
        except ValueError:
            raise ValidationError('Invalid port.')
        netloc = host if not port or (parts.scheme, port) in [('http', 80), ('https', 443)] else f'{host}:{port}'
        return urlunsplit((parts.scheme.lower(), netloc, parts.path.rstrip('/'), '', ''))

def invitation_for(token, lock=False):
    query = Invitation.objects.select_related('membership__user')
    if lock:
        query = query.select_for_update(of=('self',))
    return query.filter(token_digest=hashlib.sha256(token.encode()).hexdigest(),
                        expires_at__gt=timezone.now(), accepted_at__isnull=True,
                        membership__active=True).first()

class AcceptInvitationForm(SetPasswordForm):
    @transaction.atomic
    def accept(self, token):
        invitation = invitation_for(token, lock=True)
        if not invitation or invitation.membership.user_id != self.user.pk:
            raise ValidationError('This invitation has expired or has already been used.')
        user = self.save(commit=False)
        user.is_active = True
        user.save()
        invitation.accepted_at = timezone.now()
        invitation.save(update_fields=['accepted_at'])
        AuditEvent.objects.create(organization=invitation.membership.organization, actor=user, action='invitation.accepted')
        return user

class ReferenceForm(forms.ModelForm):
    url = forms.URLField(max_length=2048, assume_scheme='https')
    class Meta:
        model = ReferenceSite
        fields = ['url', 'relationship']

    def clean_url(self):
        return SiteForm.clean_url(self)

class ReferenceImportForm(forms.Form):
    csv_file = forms.FileField(label='CSV file', help_text='UTF-8 CSV with url,relationship columns; at most 100 rows and 100 KB.')

    def clean_csv_file(self):
        import csv
        import io
        uploaded = self.cleaned_data['csv_file']
        data = uploaded.read(100_001)
        if len(data) > 100_000:
            raise ValidationError('CSV must be no larger than 100 KB.')
        try:
            reader = csv.DictReader(io.StringIO(data.decode('utf-8-sig')), strict=True)
            if set(reader.fieldnames or []) != {'url', 'relationship'}:
                raise ValidationError('CSV columns must be exactly url,relationship.')
            rows = []
            for line, row in enumerate(reader, start=2):
                if len(rows) >= 100:
                    raise ValidationError('CSV must contain no more than 100 rows.')
                form = ReferenceForm({'url': row.get('url', ''), 'relationship': row.get('relationship') or 'research'})
                if None in row or not form.is_valid():
                    raise ValidationError(f'Invalid URL or relationship on CSV row {line}.')
                rows.append(form.cleaned_data)
            if not rows:
                raise ValidationError('CSV contains no reference URLs.')
            return rows
        except (UnicodeDecodeError, csv.Error):
            raise ValidationError('Upload a valid UTF-8 CSV.')

class ConnectionForm(forms.Form):
    username = forms.CharField(max_length=150, label='Dedicated WordPress username',
        help_text='Use a user with Company SEO Reader role. Do not use your normal administrator password.')
    application_password = forms.CharField(max_length=200, widget=forms.PasswordInput(render_value=False),
        help_text='WordPress Users → dedicated user → Application Passwords. Stored encrypted; never shown again.')

    def clean_username(self):
        value = self.cleaned_data['username'].strip()
        if ':' in value or any(ord(c) < 32 for c in value):
            raise ValidationError('Invalid username.')
        return value

class AuditScheduleForm(forms.Form):
    enabled = forms.BooleanField(required=False, label='Enable scheduled read-only public audits')
    interval_minutes = forms.IntegerField(min_value=60, max_value=10080, initial=1440,
        help_text='60–10080 minutes; 1440 is daily. n8n checks due work every minute. This does not enable publishing.')

class MetadataDraftForm(forms.Form):
    page=forms.ModelChoiceField(queryset=Page.objects.none(),help_text='Only public inventory records with a WordPress ID can be selected.')
    change_title=forms.BooleanField(required=False,label='Propose an SEO title change')
    proposed_title=forms.CharField(max_length=200,required=False)
    change_description=forms.BooleanField(required=False,initial=True,label='Propose a meta description change')
    proposed_description=forms.CharField(max_length=500,required=False,widget=forms.Textarea(attrs={'rows':4}))
    sources=forms.ModelMultipleChoiceField(queryset=KnowledgeSource.objects.none(),required=False,
        help_text='Select this site’s evidence. Public marketing claims still require factual review.')
    reason=forms.CharField(max_length=2000,required=False,widget=forms.Textarea(attrs={'rows':3}))

    def __init__(self,*args,site,**kwargs):
        super().__init__(*args,**kwargs)
        self.fields['page'].queryset=Page.objects.filter(site=site,wordpress_id__isnull=False).order_by('url')
        self.fields['sources'].queryset=KnowledgeSource.objects.filter(site=site)

    def clean(self):
        data=super().clean()
        if not data.get('change_title') and not data.get('change_description'): raise ValidationError('Select at least one metadata field.')
        for flag,field in [('change_title','proposed_title'),('change_description','proposed_description')]:
            if data.get(flag) and not data.get(field): self.add_error(field,'Enter a nonempty proposal for this field.')
        return data
