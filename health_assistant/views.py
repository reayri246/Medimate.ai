from django.shortcuts import render

from .forms import HealthQuestionForm
from .services.retrieval import answer_health_question


def assistant_home(request):
    answer = None
    if request.method == 'POST':
        form = HealthQuestionForm(request.POST)
        if form.is_valid():
            answer = answer_health_question(form.cleaned_data['question'])
        else:
            answer = None
    else:
        form = HealthQuestionForm()
    return render(
        request,
        'health_assistant/home.html',
        {
            'form': form,
            'answer': answer,
            'example_questions': [
                'What general steps can help with a fever?',
                'What should I know about cold-like symptoms?',
                'How can I find verified ingredient information for a medicine?',
                'What are general ways to support healthy sleep?',
            ],
        },
    )
