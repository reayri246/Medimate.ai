from django import forms


class HealthQuestionForm(forms.Form):
    question = forms.CharField(
        label='Ask a health question',
        max_length=2000,
        widget=forms.Textarea(attrs={
            'rows': 4,
            'placeholder': 'Ask about general fever information, cold-like symptoms, blood pressure, medicine safety, sleep, or prevention.',
        }),
    )
