from django import forms

from ..models import Message


class MessageForm(forms.ModelForm):
    body = forms.CharField(max_length=2000, widget=forms.Textarea(attrs={"rows": 4}))

    class Meta:
        model = Message
        fields = ["body"]


class StatusForm(forms.Form):
    status = forms.ChoiceField(choices=Message.Status.choices)
