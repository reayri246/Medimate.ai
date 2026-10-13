from django import forms

from accounts.models import User


class AdminNotificationForm(forms.Form):
    AUDIENCE_ALL = 'all'
    AUDIENCE_SELECTED = 'selected'
    AUDIENCE_CHOICES = (
        (AUDIENCE_ALL, 'All active users'),
        (AUDIENCE_SELECTED, 'Selected users'),
    )

    audience = forms.ChoiceField(
        choices=AUDIENCE_CHOICES,
        widget=forms.RadioSelect,
        initial=AUDIENCE_ALL,
    )
    recipients = forms.ModelMultipleChoiceField(
        queryset=User.objects.filter(is_active=True).order_by('username'),
        required=False,
        widget=forms.SelectMultiple(attrs={'size': 8}),
        label='Users',
    )
    title = forms.CharField(max_length=200)
    body = forms.CharField(widget=forms.Textarea(attrs={'rows': 4}))
    url = forms.CharField(
        max_length=500,
        required=False,
        label='Optional in-app link',
        help_text='Use a site-relative path such as /appointments/.',
    )

    def clean_url(self):
        value = self.cleaned_data['url'].strip()
        if value and (
            not value.startswith('/')
            or value.startswith('//')
            or '\\' in value
            or any(ord(character) < 32 for character in value)
        ):
            raise forms.ValidationError('Enter a local path beginning with a single slash.')
        return value

    def clean(self):
        cleaned_data = super().clean()
        if (
            cleaned_data.get('audience') == self.AUDIENCE_SELECTED
            and not cleaned_data.get('recipients')
        ):
            self.add_error('recipients', 'Choose at least one user to receive this notification.')
        return cleaned_data
