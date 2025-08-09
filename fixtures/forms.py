from django import forms
# This line was wrong before. We need to import the MODEL, not the form itself.
from .models import Fixture

class ScorerForm(forms.ModelForm):
    class Meta:
        # Tell the form which model it is linked to.
        model = Fixture
        # This is the only field the user is allowed to edit through this form.
        fields = ['scorers_text']
        # This provides a more user-friendly label for the text box.
        labels = {
            'scorers_text': 'Goal Scorers (comma-separated, e.g., "John Smith (2), Jane Doe")'
        }
        # This defines the HTML input type and adds some styling attributes.
        widgets = {
            'scorers_text': forms.Textarea(attrs={'rows': 4, 'class': 'form-control'}),
        }