from django import forms
from .models import SkilledWorker


class WorkerPayForm(forms.ModelForm):
    class Meta:
        model = SkilledWorker
        fields = ['name']
        fields = ['daily_rate', 'pay_frequency', 'pay_rate']
        widgets = {
            'daily_rate': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'e.g. 5000'}),
        }
