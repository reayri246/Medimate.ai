from django import forms


class SafetyCheckForm(forms.Form):
    age = forms.IntegerField(
        label='Age in years',
        min_value=0,
        max_value=120,
        help_text='Enter 0 for a child under 1 year.',
    )
    duration = forms.CharField(
        label='When did this start?',
        max_length=200,
        widget=forms.TextInput(attrs={'placeholder': 'For example: yesterday'}),
    )
    trend = forms.ChoiceField(
        label='Are the symptoms improving, staying the same, or getting worse?',
        choices=[
            ('improving', 'Improving'),
            ('same', 'Staying the same'),
            ('worsening', 'Getting worse'),
        ],
    )
    severity = forms.ChoiceField(
        label='How severe does it feel?',
        choices=[
            ('mild', 'Mild'),
            ('moderate', 'Moderate'),
            ('severe', 'Severe'),
        ],
    )
    symptoms = forms.CharField(
        label='What symptoms are you experiencing?',
        max_length=2000,
        widget=forms.Textarea(attrs={
            'rows': 4,
            'placeholder': 'Describe what you feel, when it happens, and any other symptoms.',
        }),
    )
